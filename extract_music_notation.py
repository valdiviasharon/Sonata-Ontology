from __future__ import annotations
import os
import sys
import json
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional, Tuple


# ====================================================
# Configuration
# ====================================================

MUSICXML_PATH = r"C:\PFC 3\Sonata Ontology\Beethoven_Piano_Sonata_Dataset_v2\RawData\score_musicxml\Beethoven_Op002No1-01.xml"

if len(sys.argv) > 1:
    MUSICXML_PATH = sys.argv[1]

JSONLD_DIR = "JSON_LD"

SO_IRI  = "https://github.com/valdiviasharon/Sonata-Ontology/sonata_ontology#"
MO_IRI  = "http://purl.org/ontology/mo/"
MTO_IRI = "http://purl.org/ontology/mto/"
MSO_IRI = "http://linkeddata.uni-muenster.de/ontology/musicscore#"
HO_IRI  = "https://github.com/andreamust/HaMSE_Ontology/schema#"
DCT_IRI = "http://purl.org/dc/terms/"
RDFS_IRI = "http://www.w3.org/2000/01/rdf-schema#"


# ====================================================
# Helpers
# ====================================================

def derive_work_ids(xml_path: str) -> Dict[str, str]:
    base_name = os.path.splitext(os.path.basename(xml_path))[0]
    work_local_id = base_name
    work_iri = f"so:{work_local_id}"
    return {"work_local_id": work_local_id, "work_iri": work_iri}


def detect_movements(measures: List[ET.Element]) -> List[Dict[str, int]]:
    start_indices: List[int] = []
    for i, meas in enumerate(measures):
        if meas.get("number") == "1":
            start_indices.append(i)

    if not start_indices:
        return [{"movement_index": 1, "start_idx": 0, "end_idx": len(measures)}]

    start_indices = sorted(start_indices)
    movements: List[Dict[str, int]] = []
    for idx, start in enumerate(start_indices):
        movement_index = idx + 1
        if idx + 1 < len(start_indices):
            end = start_indices[idx + 1]
        else:
            end = len(measures)
        movements.append(
            {"movement_index": movement_index, "start_idx": start, "end_idx": end}
        )
    return movements


def sanitize_measure_number(raw_number: Optional[str], fallback_index: int) -> str:
    if not raw_number:
        raw_number = str(fallback_index)
    return "".join(ch if ch.isalnum() else "_" for ch in raw_number)


def parse_int_or_keep_string(value: Optional[str]):
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return value


def append_unique_id_ref(list_value: Any, new_id: str) -> List[Dict[str, str]]:
    if list_value is None:
        current = []
    elif isinstance(list_value, dict):
        current = [list_value]
    elif isinstance(list_value, list):
        current = list_value
    else:
        current = []

    if not any(isinstance(item, dict) and item.get("@id") == new_id for item in current):
        current.append({"@id": new_id})

    return current


def map_accidental_class_and_shift(acc_text: str) -> Tuple[Optional[str], Optional[int]]:
    acc_text = acc_text.strip().lower()
    mapping: Dict[str, Tuple[Optional[str], Optional[int]]] = {
        "flat": ("so:Flat", -1),
        "natural": ("so:Natural", 0),
        "sharp": ("so:Sharp", 1),
        "double-flat": ("so:DoubleFlat", -2),
        "double-sharp": ("so:DoubleSharp", 2),
        "flat-flat": ("so:FlatFlat", -2),
        "sharp-sharp": ("so:SharpSharp", 2),
    }
    return mapping.get(acc_text, (None, None))


def map_duration_class(note_type: Optional[str], dots: int) -> Optional[str]:
    if note_type is None:
        return None

    note_type = note_type.strip().lower()

    base_mapping = {
        "whole": "so:WholeNote",
        "half": "so:HalfNote",
        "quarter": "so:QuarterNote",
        "eighth": "so:EighthNote",
        "16th": "so:SixteenthNote",
        "32nd": "so:ThirtySecondNote",
        "64th": "so:SixtyFourthNote",
    }

    if dots == 0:
        return base_mapping.get(note_type)

    if dots == 1:
        if note_type == "whole":
            return None
        dotted_mapping = {
            "half": "so:DottedHalf",
            "quarter": "so:DottedQuarter",
            "eighth": "so:DottedEighth",
        }
        return dotted_mapping.get(note_type)

    return None


def map_time_signature_class(numerator: int, denominator: int) -> Optional[str]:
    return f"so:TS_{numerator}_{denominator}"


# ====================================================
# Core
# ====================================================

def extend_with_music_notation(xml_path: str) -> Dict[str, Any]:
    ids = derive_work_ids(xml_path)
    work_local_id = ids["work_local_id"]

    tree = ET.parse(xml_path)
    root = tree.getroot()

    part_el = root.find("./part")
    if part_el is None:
        raise ValueError("No <part> element found in MusicXML file.")

    measures = part_el.findall("measure")
    if not measures:
        raise ValueError("No <measure> elements found in the first <part>.")

    movements_info = detect_movements(measures)

    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        base_dir = os.getcwd()

    jsonld_dir = os.path.join(base_dir, JSONLD_DIR)
    os.makedirs(jsonld_dir, exist_ok=True)

    base_name = os.path.splitext(os.path.basename(xml_path))[0]
    jsonld_path = os.path.join(jsonld_dir, base_name + ".jsonld")

    if not os.path.isfile(jsonld_path):
        raise FileNotFoundError(
            f"JSON-LD file not found: {jsonld_path}. "
            f"Please run extract_metadata.py and extract_structure.py first."
        )

    with open(jsonld_path, "r", encoding="utf-8") as f:
        jsonld_obj = json.load(f)

    context = jsonld_obj.get("@context", {})
    context.setdefault("so", SO_IRI)
    context.setdefault("mo", MO_IRI)
    context.setdefault("mto", MTO_IRI)
    context.setdefault("mso", MSO_IRI)
    context.setdefault("ho", HO_IRI)
    context.setdefault("dct", DCT_IRI)
    context.setdefault("rdfs", RDFS_IRI)
    jsonld_obj["@context"] = context

    graph: List[Dict[str, Any]] = jsonld_obj.get("@graph", [])

    node_by_id: Dict[str, Dict[str, Any]] = {}
    for node in graph:
        if isinstance(node, dict) and "@id" in node:
            node_by_id[node["@id"]] = node

    def get_or_create_node(node_id: str, base_types: List[str]) -> Dict[str, Any]:
        node = node_by_id.get(node_id)
        if node is None:
            node = {"@id": node_id, "@type": list(base_types)}
            graph.append(node)
            node_by_id[node_id] = node
        else:
            types = node.get("@type", [])
            if isinstance(types, str):
                types = [types]
            for t in base_types:
                if t not in types:
                    types.append(t)
            node["@type"] = types
        return node

    # active_clef_by_staff: current clef *instance* id per staff (per movement)
    active_clef_by_staff: Dict[Tuple[int, int], str] = {}

    global_event_counter = 1

    for m_info in movements_info:
        movement_index = m_info["movement_index"]
        start_idx = m_info["start_idx"]
        end_idx = m_info["end_idx"]

        for i in range(start_idx, end_idx):
            meas_el = measures[i]
            raw_number = meas_el.get("number")
            sanitized_number = sanitize_measure_number(raw_number, fallback_index=i + 1)

            measure_id = f"so:{work_local_id}_M{movement_index}_Measure_{sanitized_number}"
            measure_node = node_by_id.get(measure_id)
            if measure_node is None:
                value_for_number = parse_int_or_keep_string(raw_number) if raw_number else (i + 1)
                measure_node = {
                    "@id": measure_id,
                    "@type": ["mso:Measure"],
                    "so:number": value_for_number,
                }
                graph.append(measure_node)
                node_by_id[measure_id] = measure_node

            attrs = meas_el.find("attributes")

            # ---------------- Time signature ----------------
            time_el = attrs.find("time") if attrs is not None else None
            if time_el is not None:
                beats_el = time_el.find("beats")
                beat_type_el = time_el.find("beat-type")
                symbol_el = time_el.find("symbol")

                numerator = None
                denominator = None
                symbol = None

                if beats_el is not None and beats_el.text:
                    numerator = parse_int_or_keep_string(beats_el.text.strip())
                if beat_type_el is not None and beat_type_el.text:
                    denominator = parse_int_or_keep_string(beat_type_el.text.strip())
                if symbol_el is not None and symbol_el.text:
                    symbol = symbol_el.text.strip()

                if numerator is not None and denominator is not None:
                    ts_id = f"{measure_id}_TimeSig"
                    ts_node = get_or_create_node(
                        ts_id,
                        base_types=["mso:TimeSignature", "so:MusicNotationElement", "mto:Signature" ],
                    )
                    ts_node["so:numerator"] = numerator
                    ts_node["so:denominator"] = denominator
                    if symbol is not None:
                        ts_node["so:symbol"] = symbol

                    if isinstance(numerator, int) and isinstance(denominator, int):
                        ts_class = map_time_signature_class(numerator, denominator)
                        if ts_class is not None:
                            ts_types = ts_node.get("@type", [])
                            if isinstance(ts_types, str):
                                ts_types = [ts_types]
                            if ts_class not in ts_types:
                                ts_types.append(ts_class)
                            ts_node["@type"] = ts_types

                    measure_node["so:hasTimeSignature"] = {"@id": ts_id}
                    ts_node["so:timeSignatureOf"] = {"@id": measure_id}

            # ---------------- Clefs (staff-level) ----------------
            # Here we create **one clef instance per (movement, staff)**:
            #   so:Beethoven_Op002No1-01_M1_Staff_1_Clef
            # and reuse it across all measures. staffHasClef references only this.
            if attrs is not None:
                for clef_el in attrs.findall("clef"):
                    sign_el = clef_el.find("sign")
                    line_el = clef_el.find("line")
                    staff_el = clef_el.find("staff")

                    sign = sign_el.text.strip() if sign_el is not None and sign_el.text else None
                    line_val = None
                    if line_el is not None and line_el.text:
                        line_val = parse_int_or_keep_string(line_el.text.strip())

                    staff_index = 1
                    if staff_el is not None and staff_el.text:
                        try:
                            staff_index = int(staff_el.text.strip())
                        except ValueError:
                            pass

                    # Single clef per (movement, staff), independent of measure:
                    clef_id = f"so:{work_local_id}_M{movement_index}_Staff_{staff_index}_Clef"
                    clef_node = get_or_create_node(
                        clef_id,
                        base_types=["mso:Clef", "so:MusicNotationElement"],
                    )

                    if sign is not None:
                        clef_node["so:sign"] = sign
                    if line_val is not None:
                        clef_node["so:line"] = line_val

                    # Update active clef for this (movement, staff) pair
                    active_clef_by_staff[(movement_index, staff_index)] = clef_id

                    # Link staff -> clef (so:staffHasClef) ONLY to this staff-level clef
                    staff_id = f"so:{work_local_id}_M{movement_index}_Staff_{staff_index}"
                    staff_node = node_by_id.get(staff_id)
                    if staff_node is not None:
                        staff_node["so:staffHasClef"] = append_unique_id_ref(
                            staff_node.get("so:staffHasClef"), clef_id
                        )

                    # Optional: measure can also reference which clef is in effect
                    measure_node["so:hasClef"] = append_unique_id_ref(
                        measure_node.get("so:hasClef"), clef_id
                    )

            # ---------------- Tempo ----------------
            tempo_local_index = 1

            for sound_el in meas_el.findall("sound"):
                tempo_attr = sound_el.get("tempo")
                if tempo_attr:
                    try:
                        bpm_val = int(tempo_attr)
                    except ValueError:
                        bpm_val = tempo_attr.strip()

                    tempo_id = f"{measure_id}_Tempo_{tempo_local_index}"
                    tempo_local_index += 1

                    tempo_node = get_or_create_node(
                        tempo_id,
                        base_types=["so:Tempo", "so:MusicNotationElement"],
                    )
                    tempo_node["so:bpm"] = bpm_val

                    measure_node["so:hasTempo"] = append_unique_id_ref(
                        measure_node.get("so:hasTempo"), tempo_id
                    )
                    tempo_node["so:isTempoOf"] = {"@id": measure_id}

            for direction in meas_el.findall("direction"):
                tempo_text = None
                words_el = direction.find("./direction-type/words")
                if words_el is not None and words_el.text:
                    tempo_text = words_el.text.strip()

                sound_el = direction.find("sound")
                if sound_el is not None and sound_el.get("tempo"):
                    tempo_attr = sound_el.get("tempo")
                    try:
                        bpm_val = int(tempo_attr)
                    except ValueError:
                        bpm_val = tempo_attr.strip()

                    tempo_id = f"{measure_id}_Tempo_{tempo_local_index}"
                    tempo_local_index += 1

                    tempo_node = get_or_create_node(
                        tempo_id,
                        base_types=["so:Tempo", "so:MusicNotationElement"],
                    )
                    tempo_node["so:bpm"] = bpm_val
                    if tempo_text is not None:
                        tempo_node["so:tempoText"] = tempo_text

                    measure_node["so:hasTempo"] = append_unique_id_ref(
                        measure_node.get("so:hasTempo"), tempo_id
                    )
                    tempo_node["so:isTempoOf"] = {"@id": measure_id}
                    continue

                metro_el = direction.find("./direction-type/metronome")
                if metro_el is not None:
                    beat_unit_el = metro_el.find("beat-unit")
                    per_minute_el = metro_el.find("per-minute")

                    bpm_val = None
                    if per_minute_el is not None and per_minute_el.text:
                        try:
                            bpm_val = int(per_minute_el.text.strip())
                        except ValueError:
                            bpm_val = per_minute_el.text.strip()

                    if bpm_val is not None:
                        tempo_id = f"{measure_id}_Tempo_{tempo_local_index}"
                        tempo_local_index += 1

                        tempo_node = get_or_create_node(
                            tempo_id,
                            base_types=["so:Tempo", "so:MusicNotationElement"],
                        )
                        tempo_node["so:bpm"] = bpm_val
                        if tempo_text is not None:
                            tempo_node["so:tempoText"] = tempo_text
                        if beat_unit_el is not None and beat_unit_el.text:
                            tempo_node["so:beatUnit"] = beat_unit_el.text.strip()

                        measure_node["so:hasTempo"] = append_unique_id_ref(
                            measure_node.get("so:hasTempo"), tempo_id
                        )
                        tempo_node["so:isTempoOf"] = {"@id": measure_id}

            # ---------------- Symbolic events (Note/Rest) ----------------
            for note_el in meas_el.findall("note"):
                is_rest = note_el.find("rest") is not None

                staff_index = 1
                staff_el = note_el.find("staff")
                if staff_el is not None and staff_el.text:
                    try:
                        staff_index = int(staff_el.text.strip())
                    except ValueError:
                        pass

                event_index_str = f"{global_event_counter:06d}"
                global_event_counter += 1

                event_id = (
                    f"so:{work_local_id}_M{movement_index}_Measure_"
                    f"{sanitized_number}_Event_{event_index_str}"
                )

                base_types = ["ho:SymbolicEvent", "so:MusicNotationElement"]
                if is_rest:
                    base_types.append("mso:Rest")
                else:
                    base_types.append("mso:Note")

                event_node = get_or_create_node(event_id, base_types=base_types)

                event_node["so:isInMeasure"] = {"@id": measure_id}
                measure_node["so:hasSymbolicEvent"] = append_unique_id_ref(
                    measure_node.get("so:hasSymbolicEvent"), event_id
                )

                # Duration
                duration_el = note_el.find("duration")
                type_el = note_el.find("type")
                dots_count = len(note_el.findall("dot"))

                if duration_el is not None and duration_el.text:
                    duration_val = parse_int_or_keep_string(duration_el.text.strip())
                else:
                    duration_val = None

                note_type_text = type_el.text.strip() if type_el is not None and type_el.text else None
                duration_class = map_duration_class(note_type_text, dots_count)

                dur_id = f"{event_id}_Dur"
                dur_node = get_or_create_node(
                    dur_id,
                    base_types=["so:Duration", "so:MusicNotationElement"],
                )

                #if duration_val is not None:
                #    dur_node["so:musicXmlDuration"] = duration_val
                if note_type_text is not None:
                    dur_node["so:noteType"] = note_type_text
                dur_node["so:dots"] = dots_count

                if duration_class is not None:
                    dur_types = dur_node.get("@type", [])
                    if isinstance(dur_types, str):
                        dur_types = [dur_types]
                    if duration_class not in dur_types:
                        dur_types.append(duration_class)
                    dur_node["@type"] = dur_types

                event_node["so:hasDuration"] = {"@id": dur_id}

                # Clef for this event: use staff-level active clef
                clef_id = active_clef_by_staff.get((movement_index, staff_index))
                if clef_id is not None:
                    event_node["so:hasClef"] = {"@id": clef_id}

                # Pitch + accidentals
                if not is_rest:
                    pitch_el = note_el.find("pitch")
                    if pitch_el is not None:
                        step_el = pitch_el.find("step")
                        octave_el = pitch_el.find("octave")

                        step = step_el.text.strip().upper() if step_el is not None and step_el.text else None
                        octave_val = None
                        if octave_el is not None and octave_el.text:
                            octave_val = parse_int_or_keep_string(octave_el.text.strip())

                        if octave_val is not None:
                            event_node["so:octave"] = octave_val

                        if step in {"A", "B", "C", "D", "E", "F", "G"}:
                            pitch_id = f"{event_id}_Pitch"
                            pitch_node = get_or_create_node(
                                pitch_id,
                                base_types=["so:Pitch", "so:MelodicElement"],
                            )

                            specific_pitch_class = f"so:{step}"
                            pitch_types = pitch_node.get("@type", [])
                            if isinstance(pitch_types, str):
                                pitch_types = [pitch_types]
                            if specific_pitch_class not in pitch_types:
                                pitch_types.append(specific_pitch_class)
                            pitch_node["@type"] = pitch_types

                            event_node["so:hasPitch"] = {"@id": pitch_id}

                            accidental_el = note_el.find("accidental")
                            if accidental_el is not None and accidental_el.text:
                                acc_text = accidental_el.text.strip()
                                acc_class, semitone_shift = map_accidental_class_and_shift(acc_text)

                                acc_id = f"{event_id}_Accidental"
                                acc_node = get_or_create_node(
                                    acc_id,
                                    base_types=["mto:Accidental", "so:MelodicElement"],
                                )

                                if acc_class is not None:
                                    acc_types = acc_node.get("@type", [])
                                    if isinstance(acc_types, str):
                                        acc_types = [acc_types]
                                    if acc_class not in acc_types:
                                        acc_types.append(acc_class)
                                    acc_node["@type"] = acc_types

                                if semitone_shift is not None:
                                    acc_node["so:semitoneShift"] = semitone_shift

                                pitch_node["so:hasAccidental"] = {"@id": acc_id}

    jsonld_obj["@graph"] = graph
    return jsonld_obj


# ====================================================
# Main
# ====================================================

if __name__ == "__main__":
    xml_path = MUSICXML_PATH

    if not os.path.isfile(xml_path):
        raise FileNotFoundError(f"MusicXML file not found: {xml_path}")

    jsonld_obj = extend_with_music_notation(xml_path)

    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        base_dir = os.getcwd()

    output_dir = os.path.join(base_dir, JSONLD_DIR)
    os.makedirs(output_dir, exist_ok=True)

    base_name = os.path.splitext(os.path.basename(xml_path))[0]
    output_jsonld_path = os.path.join(output_dir, base_name + ".jsonld")

    with open(output_jsonld_path, "w", encoding="utf-8") as f:
        json.dump(jsonld_obj, f, indent=2, ensure_ascii=False)

    print(f"JSON-LD written to: {output_jsonld_path}")
