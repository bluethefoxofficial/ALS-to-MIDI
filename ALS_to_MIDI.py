import sys
import os
import gzip
import binascii
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import ElementTree, fromstring
from zipfile import ZipFile, BadZipFile
from midiutil import MIDIFile


# ---------- helpers ----------
def fval(elem, name, default=0.0):
    try:
        return float(elem.find(name).attrib.get('Value'))
    except:
        return default


def ival(elem, name, default=0):
    try:
        return int(float(elem.attrib.get(name)))
    except:
        return default


def load_als(path):
    try:
        with ZipFile(path):
            with ZipFile(path, 'r') as z:
                for f in z.namelist():
                    if f.endswith(".als"):
                        return ET.parse(z.open(f))
    except BadZipFile:
        pass

    with open(path, "rb") as f:
        if binascii.hexlify(f.read(2)) == b'1f8b':
            with gzip.open(path, 'rb') as g:
                return ElementTree(fromstring(g.read().decode("utf-8")))
        else:
            return ET.parse(path)


# ---------- main ----------
def main():
    if len(sys.argv) < 2:
        print("Usage: python3 ALS_to_MIDI.py <file.als>")
        sys.exit(1)

    input_file = sys.argv[1]

    if not os.path.exists(input_file):
        print("Error: file not found")
        sys.exit(1)

    tree = load_als(input_file)
    root = tree.getroot()

    # tempo
    tempo = 120
    for t in root.iter('Tempo'):
        for f in t.iter('FloatEvent'):
            try:
                tempo = int(float(f.get('Value')))
            except:
                pass

    tracks = root.findall('.//MidiTrack')
    print(f"Tracks: {len(tracks)} | Tempo: {tempo}")

    midi = MIDIFile(len(tracks), adjust_origin=True)
    midi.addTempo(0, 0, tempo)

    track_index = 0

    for miditrack in tracks:
        # name
        name_elem = miditrack.find('./Name/EffectiveName')
        name = name_elem.attrib.get('Value') if name_elem is not None else f"Track {track_index}"
        print(f"\nTrack {track_index}: {name}")
        midi.addTrackName(track_index, 0, name)

        clips = miditrack.findall(
            './/DeviceChain/MainSequencer/ClipTimeable/ArrangerAutomation/Events/MidiClip'
        )

        for clip in clips:
            loop = clip.find('Loop')
            if loop is None:
                continue

            loop_on = loop.find('LoopOn').attrib.get('Value') == 'true'
            loop_start = fval(loop, 'LoopStart')
            loop_end = fval(loop, 'LoopEnd')

            clip_start = fval(clip, 'CurrentStart')
            clip_end = fval(clip, 'CurrentEnd')

            clip_len = loop_end - loop_start
            if clip_len <= 0:
                continue

            keytracks = clip.findall('.//Notes/KeyTracks/KeyTrack')

            for kt in keytracks:
                key_elem = kt.find('MidiKey')
                if key_elem is None:
                    continue

                key = int(key_elem.attrib.get('Value'))

                for note in kt.findall('.//MidiNoteEvent'):
                    try:
                        base_time = float(note.attrib.get('Time'))
                        duration = float(note.attrib.get('Duration'))

                        # 🔥 FIXED velocity handling
                        velocity = int(float(note.attrib.get('Velocity')))
                        velocity = max(0, min(127, velocity))
                    except:
                        continue

                    if loop_on:
                        t = clip_start
                        while t < clip_end:
                            note_time = t + (base_time - loop_start)

                            if clip_start <= note_time < clip_end:
                                midi.addNote(
                                    track_index,
                                    0,
                                    key,
                                    note_time,
                                    duration,
                                    velocity
                                )

                            t += clip_len
                    else:
                        note_time = clip_start + base_time
                        midi.addNote(
                            track_index,
                            0,
                            key,
                            note_time,
                            duration,
                            velocity
                        )

        track_index += 1

    out = os.path.splitext(os.path.basename(input_file))[0] + ".mid"

    with open(out, "wb") as f:
        midi.writeFile(f)

    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
