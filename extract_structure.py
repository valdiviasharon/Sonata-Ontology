from __future__ import annotations
import os
import sys
import json
import xml.etree.ElementTree as ET
from typing import Dict, Any, List


# ====================================================
# Configuration
# ====================================================

MUSICXML_PATH = r"C:\PFC 3\Sonata Ontology\Beethoven_Piano_Sonata_Dataset_v2\RawData\score_musicxml\Beethoven_Op002No1-01.xml"

JSONLD_DIR = "JSON_LD"
OUTPUT_JSONLD_DIR = JSONLD_DIR

SO_IRI  = "https://github.com/valdiviasharon/Sonata-Ontology/sonata_ontology#"
MO_IRI  = "http://purl.org/ontology/mo/"
MTO_IRI = "http://purl.org/ontology/mto/"
MSO_IRI = "http://linkeddata.uni-muenster.de/ontology/musicscore#"
DCT_IRI = "http://purl.org/dc/terms/"
RDFS_IRI = "http://www.w3.org/2000/01/rdf-schema#"


# ====================================================
# Helpers
# ====================================================

def derive_work_ids(xml_path: str) -> Dict[str, str]:
    base_name = os.path.splitext(os.path.basename(xml_path))[0]
    work_local_id = base_name              # e.g. "Beethoven_Op002No1-01"
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


def detect_number_of_staves(part_el: ET.Element) -> int:
    # 1) Explicit <attributes><staves>
    for meas in part_el.findall("measure"):
        attrs = meas.find("attributes")
        if attrs is not None:
            staves_el = attrs.find("staves")
            if staves_el is not None and staves_el.text:
                try:
                    val = int(staves_el.text.strip())
                    if val > 0:
                        return val
                except ValueError:
                    pass

    # 2) Infer from <note><staff>
    max_staff = 0
    for meas in part_el.findall("measure"):
        for note in meas.findall("note"):
            staff_el = note.find("staff")
            if staff_el is not None and staff_el.text:
                try:
                    val = int(staff_el.text.strip())
                    if val > max_staff:
                        max_staff = val
                except ValueError:
                    pass

    if max_staff > 0:
        return max_staff

    # 3) Default for piano
    return 2


def sanitize_measure_number(raw_number: str, fallback_index: int) -> str:
    if not raw_number:
        raw_number = str(fallback_index)
    return "".join(ch if ch.isalnum() else "_" for ch in raw_number)


def parse_int_or_keep_string(value: str):
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


# ====================================================
# Core
# ====================================================

def extend_metadata_with_structure(xml_path: str) -> Dict[str, Any]:
    ids = derive_work_ids(xml_path)
    work_local_id = ids["work_local_id"]
    work_iri = ids["work_iri"]

    # --- MusicXML ---
    tree = ET.parse(xml_path)
    root = tree.getroot()

    part_el = root.find("./part")
    if part_el is None:
        raise ValueError("No <part> element found in MusicXML file.")

    measures = part_el.findall("measure")
    if not measures:
        raise ValueError("No <measure> elements found in the first <part>.")

    movements_info = detect_movements(measures)
    num_staves = detect_number_of_staves(part_el)

    # --- Load existing JSON-LD (metadata) ---
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        base_dir = os.getcwd()

    jsonld_dir = os.path.join(base_dir, JSONLD_DIR)
    base_name = os.path.splitext(os.path.basename(xml_path))[0]
    jsonld_path = os.path.join(jsonld_dir, base_name + ".jsonld")

    if not os.path.isfile(jsonld_path):
        raise FileNotFoundError(
            f"Metadata JSON-LD not found: {jsonld_path}. "
            f"Run extract_metadata.py first."
        )

    with open(jsonld_path, "r", encoding="utf-8") as f:
        jsonld_obj = json.load(f)

    # Ensure context
    context = jsonld_obj.get("@context", {})
    context.setdefault("so", SO_IRI)
    context.setdefault("mo", MO_IRI)
    context.setdefault("mto", MTO_IRI)
    context.setdefault("mso", MSO_IRI)
    context.setdefault("dct", DCT_IRI)
    context.setdefault("rdfs", RDFS_IRI)
    jsonld_obj["@context"] = context

    graph: List[Dict[str, Any]] = jsonld_obj.get("@graph", [])

    # Index nodes by @id
    node_by_id: Dict[str, Dict[str, Any]] = {}
    for node in graph:
        if isinstance(node, dict):
            node_id = node.get("@id")
            if node_id:
                node_by_id[node_id] = node

    # Work node
    work_node = node_by_id.get(work_iri)
    if work_node is None:
        work_node = {
            "@id": work_iri,
            "@type": ["mo:MusicalWork", "so:Sonata"],
        }
        graph.append(work_node)
        node_by_id[work_iri] = work_node
    else:
        types = work_node.get("@type", [])
        if isinstance(types, str):
            types = [types]
        for t in ["mo:MusicalWork", "so:Sonata"]:
            if t not in types:
                types.append(t)
        work_node["@type"] = types

    has_movement_list: List[Dict[str, str]] = []

    # --- Movements, staffs, measures ---
    for m_info in movements_info:
        movement_index = m_info["movement_index"]
        start_idx = m_info["start_idx"]
        end_idx = m_info["end_idx"]

        movement_id = f"so:{work_local_id}_M{movement_index}"

        movement_node = node_by_id.get(movement_id)
        if movement_node is None:
            movement_types = ["mso:Movement", "so:SonataMovement", "so:StructuralElement"]
            movement_node = {"@id": movement_id, "@type": movement_types}
            graph.append(movement_node)
            node_by_id[movement_id] = movement_node
        else:
            types = movement_node.get("@type", [])
            if isinstance(types, str):
                types = [types]
            for t in ["mso:Movement", "so:SonataMovement", "so:StructuralElement"]:
                if t not in types:
                    types.append(t)
            movement_node["@type"] = types

        movement_node["so:movementIndex"] = movement_index

        # --- Staffs (PianoStaff, StructuralElement) ---
        staff_ids_for_movement: List[Dict[str, str]] = []
        staff_nodes_for_movement: List[Dict[str, Any]] = []

        for staff_idx in range(1, num_staves + 1):
            staff_id = f"so:{work_local_id}_M{movement_index}_Staff_{staff_idx}"

            staff_node = node_by_id.get(staff_id)
            if staff_node is None:
                staff_types = ["mso:Staff", "so:PianoStaff", "so:StructuralElement"]
                if staff_idx == 1:
                    staff_types.append("so:UpperPianoStaff")
                elif staff_idx == 2:
                    staff_types.append("so:LowerPianoStaff")

                staff_node = {
                    "@id": staff_id,
                    "@type": staff_types,
                    "so:staffIndex": staff_idx,
                }
                graph.append(staff_node)
                node_by_id[staff_id] = staff_node
            else:
                types = staff_node.get("@type", [])
                if isinstance(types, str):
                    types = [types]
                for t in ["mso:Staff", "so:PianoStaff", "so:StructuralElement"]:
                    if t not in types:
                        types.append(t)
                if staff_idx == 1 and "so:UpperPianoStaff" not in types:
                    types.append("so:UpperPianoStaff")
                if staff_idx == 2 and "so:LowerPianoStaff" not in types:
                    types.append("so:LowerPianoStaff")
                staff_node["@type"] = types
                staff_node["so:staffIndex"] = staff_idx

            staff_ids_for_movement.append({"@id": staff_id})
            staff_nodes_for_movement.append(staff_node)

        # --- Link SonataMovement to PianoStaff and Movement to Staff ---
        for sid_ref in staff_ids_for_movement:
            staff_id = sid_ref["@id"]
            # Generic relation Movement -> Staff
            movement_node["so:movementHasStaff"] = append_unique_id_ref(
                movement_node.get("so:movementHasStaff"), staff_id
            )
            # Specific relation SonataMovement -> PianoStaff
            movement_node["so:sonataMovementHasPianoStaff"] = append_unique_id_ref(
                movement_node.get("so:sonataMovementHasPianoStaff"), staff_id
            )

        # --- Measures (also StructuralElement) ---
        measure_ids_for_movement: List[Dict[str, str]] = []

        for i in range(start_idx, end_idx):
            meas_el = measures[i]
            raw_number = meas_el.get("number")
            sanitized = sanitize_measure_number(raw_number, fallback_index=i + 1)

            measure_id = f"so:{work_local_id}_M{movement_index}_Measure_{sanitized}"

            measure_node = node_by_id.get(measure_id)
            if measure_node is None:
                value_for_number = parse_int_or_keep_string(raw_number) if raw_number else (i + 1)
                measure_node = {
                    "@id": measure_id,
                    "@type": ["mso:Measure", "so:StructuralElement"],
                    "so:number": value_for_number,
                    "so:isMeasureOfStaff": staff_ids_for_movement.copy(),
                }
                graph.append(measure_node)
                node_by_id[measure_id] = measure_node
            else:
                types = measure_node.get("@type", [])
                if isinstance(types, str):
                    types = [types]
                for t in ["mso:Measure", "so:StructuralElement"]:
                    if t not in types:
                        types.append(t)
                measure_node["@type"] = types

                current_staff_refs = measure_node.get("so:isMeasureOfStaff")
                for sid_ref in staff_ids_for_movement:
                    measure_node["so:isMeasureOfStaff"] = append_unique_id_ref(
                        current_staff_refs, sid_ref["@id"]
                    )
                    current_staff_refs = measure_node["so:isMeasureOfStaff"]

            measure_ids_for_movement.append({"@id": measure_id})

        # Movement -> Measures
        for mid_ref in measure_ids_for_movement:
            movement_node["so:movementHasMeasure"] = append_unique_id_ref(
                movement_node.get("so:movementHasMeasure"), mid_ref["@id"]
            )

        # Staff -> Measures
        for staff_node in staff_nodes_for_movement:
            for mid_ref in measure_ids_for_movement:
                staff_node["so:staffHasMeasure"] = append_unique_id_ref(
                    staff_node.get("so:staffHasMeasure"), mid_ref["@id"]
                )

        has_movement_list.append({"@id": movement_id})

    # Work -> Movements
    for mref in has_movement_list:
        work_node["so:hasMovement"] = append_unique_id_ref(
            work_node.get("so:hasMovement"), mref["@id"]
        )

    jsonld_obj["@graph"] = graph
    return jsonld_obj


# ====================================================
# Main
# ====================================================

if __name__ == "__main__":
    xml_path = MUSICXML_PATH
    if len(sys.argv) > 1:
        xml_path = sys.argv[1]

    if not os.path.isfile(xml_path):
        raise FileNotFoundError(f"MusicXML file not found: {xml_path}")

    jsonld_obj = extend_metadata_with_structure(xml_path)

    ids = derive_work_ids(xml_path)
    work_local_id = ids["work_local_id"]

    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        base_dir = os.getcwd()

    output_dir = os.path.join(base_dir, OUTPUT_JSONLD_DIR)
    os.makedirs(output_dir, exist_ok=True)

    output_jsonld_path = os.path.join(output_dir, work_local_id + ".jsonld")

    with open(output_jsonld_path, "w", encoding="utf-8") as f:
        json.dump(jsonld_obj, f, indent=2, ensure_ascii=False)

    print(f"JSON-LD written to: {output_jsonld_path}")
