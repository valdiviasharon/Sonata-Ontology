import sys
import json
from music21 import converter, dynamics, chord, key, roman, clef, tempo, meter

def extract_elements(xml_file, metadata_file, output_file):
    # --- Load and update metadata ---
    with open(metadata_file, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    score = converter.parse(xml_file)
    measures_dict = {}
    all_notes = []
    all_rests = []
    all_chords = []
    all_dynamics = []
    all_clefs = []
    all_tempos = []
    all_keysigs = []
    all_timesigs = []
    all_keys = []
    all_romans = []

    clef_objs = {}
    tempo_objs = {}
    key_objs = {}
    time_objs = {}
    global_key_objs = {}
    global_roman_objs = {}
    note_to_chord = {}

    note_counter = 1
    rest_counter = 1
    chord_counter = 1
    dynamic_counter = 1
    clef_counter = [1]
    tempo_counter = [1]
    key_counter = [1]
    time_counter = [1]
    global_key_counter = [1]
    global_roman_counter = [1]

    skipped_elements = 0
    dynamic_lookup = {}

    last_tempo = None
    last_key = None
    last_time = None

    def clef_to_obj(clef_obj):
        if clef_obj is None:
            return None
        key_tuple = (clef_obj.sign, clef_obj.line, clef_obj.octaveChange)
        if key_tuple not in clef_objs:
            clef_id = f"clef_{clef_counter[0]:03d}"
            clef_dict = {
                "@type": "Clef",
                "id": clef_id,
                "sign": clef_obj.sign,
                "line": clef_obj.line
            }
            clef_objs[key_tuple] = clef_id
            all_clefs.append(clef_dict)
            clef_counter[0] += 1
        return clef_objs[key_tuple]

    def tempo_to_obj(tempo_obj, measure_num):
        if tempo_obj is None:
            return None
        key_tuple = (tempo_obj.number, tempo_obj.text, measure_num)
        if key_tuple not in tempo_objs:
            tempo_id = f"tempo_{tempo_counter[0]:03d}"
            tempo_dict = {
                "@type": "Tempo",
                "id": tempo_id,
                "bpm": tempo_obj.number if hasattr(tempo_obj, "number") else None,
                "text": tempo_obj.text if hasattr(tempo_obj, "text") else None,
                "measure_start": measure_num
            }
            tempo_objs[key_tuple] = tempo_id
            all_tempos.append(tempo_dict)
            tempo_counter[0] += 1
        return tempo_objs[key_tuple]

    def key_to_obj(key_obj, measure_num):
        if key_obj is None:
            return None
        tonality = None
        try:
            if hasattr(key_obj, "sharps") and hasattr(key_obj, "mode"):
                tonality = key.KeySignature(key_obj.sharps).asKey(mode=key_obj.mode).name
            elif hasattr(key_obj, "tonic") and hasattr(key_obj, "mode"):
                tonality = f"{key_obj.tonic.name} {key_obj.mode}"
        except Exception:
            tonality = None
        if hasattr(key_obj, "sharps"):
            key_tuple = (key_obj.sharps, getattr(key_obj, "mode", None), measure_num)
            if key_tuple not in key_objs:
                key_id = f"keySig_{key_counter[0]:03d}"
                key_dict = {
                    "@type": "KeySignature",
                    "id": key_id,
                    "fifths": key_obj.sharps,
                    "mode": getattr(key_obj, "mode", None),
                    "tonality": tonality,
                    "measure_start": measure_num
                }
                key_objs[key_tuple] = key_id
                all_keysigs.append(key_dict)
                key_counter[0] += 1
            return key_objs[key_tuple]
        elif hasattr(key_obj, "tonic") and hasattr(key_obj, "mode"):
            key_tuple = (key_obj.tonic.name, key_obj.mode, measure_num)
            if key_tuple not in key_objs:
                key_id = f"keySig_{key_counter[0]:03d}"
                key_dict = {
                    "@type": "KeySignature",
                    "id": key_id,
                    "tonic": key_obj.tonic.name,
                    "mode": key_obj.mode,
                    "tonality": tonality,
                    "measure_start": measure_num
                }
                key_objs[key_tuple] = key_id
                all_keysigs.append(key_dict)
                key_counter[0] += 1
            return key_objs[key_tuple]
        return None

    def time_to_obj(time_obj, measure_num):
        if time_obj is None:
            return None
        key_tuple = (time_obj.numerator, time_obj.denominator, getattr(time_obj, "symbol", "normal"), measure_num)
        if key_tuple not in time_objs:
            time_id = f"timesig_{time_counter[0]:03d}"
            time_dict = {
                "@type": "TimeSignature",
                "id": time_id,
                "numerator": time_obj.numerator,
                "denominator": time_obj.denominator,
                "symbol": getattr(time_obj, "symbol", "normal"),
                "measure_start": measure_num
            }
            time_objs[key_tuple] = time_id
            all_timesigs.append(time_dict)
            time_counter[0] += 1
        return time_objs[key_tuple]

    def register_global_key(tonic, mode):
        key_tuple = (tonic, mode)
        if key_tuple not in global_key_objs:
            key_id = f"key_{global_key_counter[0]:03d}"
            key_obj = {
                "@type": "Key",
                "id": key_id,
                "tonic": tonic,
                "mode": mode
            }
            global_key_objs[key_tuple] = key_id
            all_keys.append(key_obj)
            global_key_counter[0] += 1
        return global_key_objs[key_tuple]

    def register_global_roman(figure, key_id, mode, inversion, bass):
        roman_tuple = (figure, key_id, mode, inversion, bass)
        if roman_tuple not in global_roman_objs:
            roman_id = f"roman_{global_roman_counter[0]:04d}"
            roman_obj = {
                "@type": "RomanNumeral",
                "id": roman_id,
                "figure": figure,
                "key": key_id,
                "mode": mode,
                "inversion": inversion,
                "bass": bass
            }
            global_roman_objs[roman_tuple] = roman_id
            all_romans.append(roman_obj)
            global_roman_counter[0] += 1
        return global_roman_objs[roman_tuple]

    # --- DETECT GLOBAL KEY AND TONALITY ---
    global_key_id = None
    tonality = None
    try:
        score_key = score.analyze('key')
        tonic = score_key.tonic.name if hasattr(score_key, 'tonic') else None
        mode = score_key.mode if hasattr(score_key, 'mode') else None
        if tonic and mode:
            global_key_id = register_global_key(tonic, mode)
            tonality = f"{tonic} {mode}"
    except Exception:
        global_key_id = None
        tonality = None

    # --- UPDATE METADATA IN PLACE ---
    metadata["global_key"] = global_key_id
    metadata["tonality"] = tonality
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    # --- EXTRACT ELEMENTS ---
    measures_dict = {}
    measures_list = []
    for part in score.parts:
        part_name = part.partName if part.partName else "Piano"
        for m in part.getElementsByClass('Measure'):
            m_num = m.measureNumber if m.measureNumber else 0
            if m_num not in measures_dict:
                measure_id = f"measure_{m_num:03d}"
                measures_dict[m_num] = {
                    "@type": "Measure",
                    "id": measure_id,
                    "number": m_num,
                    "notes": [],
                    "rests": [],
                    "chords": [],
                    "dynamics": []
                }
                dynamic_lookup[m_num] = []
            if measures_dict[m_num] not in measures_list:
                measures_list.append(measures_dict[m_num])
            measure_obj = measures_dict[m_num]
            # Tempo/key/time ONLY when changed
            tempo_obj = m.getContextByClass(tempo.MetronomeMark)
            if tempo_obj and (last_tempo is None or tempo_obj.number != last_tempo.number or tempo_obj.text != last_tempo.text):
                tempo_to_obj(tempo_obj, m_num)
                last_tempo = tempo_obj
            key_obj = m.getContextByClass(key.KeySignature) or m.getContextByClass(key.Key)
            if key_obj and (last_key is None or getattr(key_obj, "sharps", None) != getattr(last_key, "sharps", None) or getattr(key_obj, "mode", None) != getattr(last_key, "mode", None)):
                key_to_obj(key_obj, m_num)
                last_key = key_obj
            time_obj = m.getContextByClass(meter.TimeSignature)
            if time_obj and (last_time is None or time_obj.numerator != last_time.numerator or time_obj.denominator != last_time.denominator or getattr(time_obj, "symbol", "normal") != getattr(last_time, "symbol", "normal")):
                time_to_obj(time_obj, m_num)
                last_time = time_obj
            # Dynamics in measure
            dynamics_in_measure = []
            for d in m.getElementsByClass(dynamics.Dynamic):
                dyn_obj = {
                    "@type": "Dynamic",
                    "id": f"dynamic_{dynamic_counter:04d}",
                    "value": d.value,
                    "offset": float(d.offset)
                }
                dynamics_in_measure.append(dyn_obj)
                all_dynamics.append(dyn_obj)
                dynamic_counter += 1
            dynamic_lookup[m_num].extend(dynamics_in_measure)
            for dyn in dynamics_in_measure:
                measure_obj["dynamics"].append(dyn["id"])
            for n in m.notesAndRests:
                note_offset = float(n.offset) if hasattr(n, "offset") else 0.0
                # Find last applicable dynamic (by offset)
                applicable_dynamic_id = None
                dynamics_sorted = sorted(dynamic_lookup[m_num], key=lambda x: x["offset"])
                for dyn in reversed(dynamics_sorted):
                    if dyn["offset"] <= note_offset:
                        applicable_dynamic_id = dyn["id"]
                        break
                note_clef = n.getContextByClass(clef.Clef)
                clef_id = clef_to_obj(note_clef)
                # Note
                if getattr(n, "isNote", False):
                    pitch = getattr(n, "pitch", None)
                    if pitch is None or pitch.name is None or pitch.octave is None:
                        skipped_elements += 1
                        continue
                    note_id = f"note_{note_counter:05d}"
                    note_obj = {
                        "@type": "Note",
                        "id": note_id,
                        "part": part_name,
                        "measure": measure_obj["id"],
                        "offset": note_offset,
                        "pitch": pitch.name,
                        "octave": pitch.octave,
                        "duration": n.duration.type if hasattr(n, "duration") else None,
                        "accidental": pitch.accidental.name if pitch.accidental else None,
                        "dynamic": applicable_dynamic_id,
                        "articulation": n.articulations[0].name if n.articulations else None,
                        "tie": n.tie.type if n.tie else None,
                        "inChord": None,
                        "clef": clef_id
                    }
                    measure_obj["notes"].append(note_id)
                    all_notes.append(note_obj)
                    note_counter += 1
                # Rest
                elif getattr(n, "isRest", False):
                    rest_id = f"rest_{rest_counter:05d}"
                    rest_obj = {
                        "@type": "Rest",
                        "id": rest_id,
                        "part": part_name,
                        "measure": measure_obj["id"],
                        "offset": note_offset,
                        "duration": n.duration.type if hasattr(n, "duration") else None,
                        "clef": clef_id
                    }
                    measure_obj["rests"].append(rest_id)
                    all_rests.append(rest_obj)
                    rest_counter += 1
                # Chord
                elif isinstance(n, chord.Chord):
                    chord_id = f"chord_{chord_counter:05d}"
                    chord_notes = []
                    note_ids = []
                    for p in n.pitches:
                        note_id = f"note_{note_counter:05d}"
                        note_ids.append(note_id)
                        chord_notes.append(p.nameWithOctave)
                        note_to_chord[note_id] = chord_id
                        note_obj = {
                            "@type": "Note",
                            "id": note_id,
                            "part": part_name,
                            "measure": measure_obj["id"],
                            "offset": note_offset,
                            "pitch": p.name,
                            "octave": p.octave,
                            "duration": n.duration.type if hasattr(n, "duration") else None,
                            "accidental": p.accidental.name if p.accidental else None,
                            "dynamic": applicable_dynamic_id,
                            "articulation": n.articulations[0].name if n.articulations else None,
                            "tie": n.tie.type if n.tie else None,
                            "inChord": chord_id,
                            "clef": clef_id
                        }
                        measure_obj["notes"].append(note_id)
                        all_notes.append(note_obj)
                        note_counter += 1
                    # Register Key and Roman globally (no key on Chord)
                    local_key = m.getContextByClass(key.Key) or m.getContextByClass(key.KeySignature)
                    tonic = local_key.tonic.name if (local_key and hasattr(local_key, "tonic")) else None
                    mode = local_key.mode if (local_key and hasattr(local_key, "mode")) else None
                    key_id = register_global_key(tonic, mode)
                    try:
                        roman_obj = roman.romanNumeralFromChord(n, local_key) if local_key else None
                    except Exception:
                        roman_obj = None
                    roman_id = None
                    roman_figure = None
                    if roman_obj is not None:
                        roman_id = register_global_roman(
                            roman_obj.figure,
                            key_id,
                            mode,
                            roman_obj.inversion(),
                            roman_obj.bass().nameWithOctave if hasattr(roman_obj, "bass") else None
                        )
                        roman_figure = roman_obj.figure
                    # Chord naming
                    symbol = None
                    pitchedCommonName = None
                    commonName = None
                    try:
                        symbol = n.symbol if hasattr(n, 'symbol') and n.symbol else None
                    except Exception:
                        symbol = None
                    try:
                        pitchedCommonName = n.pitchedCommonName if hasattr(n, 'pitchedCommonName') else None
                    except Exception:
                        pitchedCommonName = None
                    try:
                        commonName = n.commonName if hasattr(n, 'commonName') else None
                    except Exception:
                        commonName = None
                    if not symbol and len(chord_notes) > 0:
                        symbol = '-'.join(chord_notes)
                    chord_obj = {
                        "@type": "Chord",
                        "id": chord_id,
                        "measure": measure_obj["id"],
                        "offset": note_offset,
                        "pitches": chord_notes,
                        "hasNote": note_ids,
                        "hasRomanNumeral": roman_id,
                        "inversion": n.inversion() if hasattr(n, "inversion") else None,
                        "bass": n.bass().nameWithOctave if hasattr(n, "bass") else None,
                        "clef": clef_id,
                        "symbol": symbol,
                        "commonName": commonName,
                        "pitchedCommonName": pitchedCommonName,
                        "roman_figure": roman_figure
                    }
                    measure_obj["chords"].append(chord_id)
                    all_chords.append(chord_obj)
                    chord_counter += 1
                else:
                    skipped_elements += 1
                    print(f"Skipped element in measure {m_num}: {n}")
                    continue
    for note_obj in all_notes:
        if note_obj["id"] in note_to_chord:
            note_obj["inChord"] = note_to_chord[note_obj["id"]]
    measures = [measures_dict[m_num] for m_num in sorted(measures_dict)]

    output_data = {
        "measures": measures,
        "notes": all_notes,
        "rests": all_rests,
        "chords": all_chords,
        "dynamics": all_dynamics,
        "clefs": all_clefs,
        "tempos": all_tempos,
        "key_signatures": all_keysigs,
        "time_signatures": all_timesigs,
        "keys": all_keys,
        "romans": all_romans
    }
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    print(f"Elements exported to {output_file}")

    print(f"Measures: {len(measures)}, Notes: {len(all_notes)}, Rests: {len(all_rests)}, Chords: {len(all_chords)}, "
      f"Dynamics: {len(all_dynamics)}, Clefs: {len(all_clefs)}, Tempos: {len(all_tempos)}, "
      f"Key Signatures: {len(all_keysigs)}, Time Signatures: {len(all_timesigs)}, "
      f"Global Keys: {len(all_keys)}, Romans: {len(all_romans)}; Elements skipped: {skipped_elements}")
    
if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python xml_to_elements_json.py <input_xml_file> <metadata_json_file> <output_json_file>")
        sys.exit(1)
    xml_file = sys.argv[1]
    metadata_file = sys.argv[2]
    output_file = sys.argv[3]
    extract_elements(xml_file, metadata_file, output_file)
