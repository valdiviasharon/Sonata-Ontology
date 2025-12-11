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
    """
    Derive the local work identifier and compact IRI from the filename.

    Example: 'Beethoven_Op002No1-01.xml' ->
        work_local_id = 'Beethoven_Op002No1-01'
        work_iri      = 'so:Beethoven_Op002No1-01'
    """
    base_name = os.path.splitext(os.path.basename(xml_path))[0]
    work_local_id = base_name
    work_iri = f"so:{work_local_id}"
    return {"work_local_id": work_local_id, "work_iri": work_iri}


def detect_movements(measures: List[ET.Element]) -> List[Dict[str, int]]:
    """
    Detect movements based on MusicXML <measure> @number.

    Strategy:
      - Every measure whose @number == "1" starts a new movement.
      - A movement ends right before the next such index, or at the end.

    If no measure with @number == "1" is found, assume a single movement.
    """
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
    """
    Sanitize the MusicXML measure 'number' attribute.

    If raw_number is None or empty, use the fallback_index (1-based).
    Otherwise, replace any non-alphanumeric characters by underscore.
    """
    if not raw_number:
        raw_number = str(fallback_index)
    return "".join(ch if ch.isalnum() else "_" for ch in raw_number)


def parse_int_or_keep_string(value: Optional[str]):
    """
    Try to parse a string as integer. If it fails, return the original string.
    Useful for values that are usually numeric but can contain suffixes.
    """
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return value


def append_unique_id_ref(list_value: Any, new_id: str) -> List[Dict[str, str]]:
    """
    Append {"@id": new_id} to a property that can be:
      - missing (None),
      - a single object,
      - or a list of objects.

    It returns a list of {"@id": ...} without duplicates.
    """
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


def strip_ns(tag: str) -> str:
    """
    Strip XML namespace from a tag, returning the local name.
    """
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


# Loudness dynamic values we want to consider.
LOUDNESS_DYNAMIC_VALUES = {
    "ppp", "pp", "p", "mp", "mf", "f", "ff", "fff",
    "sf", "sfp", "fp", "pf"
}

# Optional heuristic mapping to a relative dynamic level.
DYNAMIC_LEVELS: Dict[str, int] = {
    "ppp": 1,
    "pp": 2,
    "p": 3,
    "mp": 4,
    "mf": 5,
    "f": 6,
    "ff": 7,
    "fff": 8,
    # approximations:
    "sf": 7,
    "sfp": 7,
    "fp": 6,
    "pf": 6,
}


def is_loudness_dynamic(value: str) -> bool:
    """
    Check if a dynamic value should be treated as a LoudnessDynamic.
    """
    return value.lower() in LOUDNESS_DYNAMIC_VALUES


def parse_direction_dynamics(direction_el: ET.Element) -> List[str]:
    """
    Parse <direction> to extract loudness-type dynamics (p, mf, ff, sf, sfp, etc.)
    from <direction-type><dynamics>.

    Returns a list of dynamic values (e.g., ["p"], ["ff"], ["sf"]).
    """
    result: List[str] = []

    dyn_parent = direction_el.find("./direction-type/dynamics")
    if dyn_parent is None:
        return result

    for child in list(dyn_parent):
        dyn_name = strip_ns(child.tag).lower()
        # Typical MusicXML dynamic tags: p, pp, mp, mf, f, ff, sf, sfp, etc.
        if dyn_name in LOUDNESS_DYNAMIC_VALUES:
            result.append(dyn_name)

    return result


def parse_note_dynamics(note_el: ET.Element) -> List[str]:
    """
    Parse a <note> element for embedded <notations><dynamics>.

    This is less common than <direction>-based dynamics, but possible.
    """
    result: List[str] = []

    notations = note_el.find("notations")
    if notations is None:
        return result

    dyn_parent = notations.find("dynamics")
    if dyn_parent is None:
        return result

    for child in list(dyn_parent):
        dyn_name = strip_ns(child.tag).lower()
        if dyn_name in LOUDNESS_DYNAMIC_VALUES:
            result.append(dyn_name)

    return result


def parse_note_articulations(note_el: ET.Element) -> List[Tuple[str, str]]:
    """
    Parse a <note> element for articulations under <notations><articulations>,
    and slurs (for legato).

    Returns a list of (articulationText, articulationClass) tuples, e.g.:
      [("staccato", "so:Staccato"), ("accent", "so:Accent")]
    """
    results: List[Tuple[str, str]] = []

    notations = note_el.find("notations")
    if notations is None:
        return results

    # Standard Articulations block
    arts_parent = notations.find("articulations")
    if arts_parent is not None:
        for child in list(arts_parent):
            art_name = strip_ns(child.tag).lower()
            if art_name == "staccato":
                results.append(("staccato", "so:Staccato"))
            elif art_name == "accent":
                results.append(("accent", "so:Accent"))
            elif art_name == "tenuto":
                results.append(("tenuto", "so:Tenuto"))
            # You can extend this mapping if needed.

    # Slurs: we approximate the start of a slur as a legato articulation.
    for slur_el in notations.findall("slur"):
        slur_type = slur_el.get("type", "").lower()
        if slur_type == "start":
            results.append(("legato", "so:Legato"))

    return results


# ====================================================
# Core: extend JSON-LD with expressive layer
# ====================================================

def extend_with_expression(xml_path: str) -> Dict[str, Any]:
    ids = derive_work_ids(xml_path)
    work_local_id = ids["work_local_id"]

    # --- Parse MusicXML ---
    tree = ET.parse(xml_path)
    root = tree.getroot()

    part_el = root.find("./part")
    if part_el is None:
        raise ValueError("No <part> element found in MusicXML file.")

    measures = part_el.findall("measure")
    if not measures:
        raise ValueError("No <measure> elements found in the first <part>.")

    movements_info = detect_movements(measures)

    # --- Load existing unified JSON-LD ---
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
            f"Please run metadata/structure/notation extraction first."
        )

    with open(jsonld_path, "r", encoding="utf-8") as f:
        jsonld_obj = json.load(f)

    # Ensure context
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

    # Index nodes by @id
    node_by_id: Dict[str, Dict[str, Any]] = {}
    for node in graph:
        if isinstance(node, dict) and "@id" in node:
            node_by_id[node["@id"]] = node

    def get_or_create_node(node_id: str, base_types: List[str]) -> Dict[str, Any]:
        """
        Get or create a node with the given @id and ensure it has at least the base_types.
        """
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

    # We must reproduce the same event indexing used in extract_notation:
    # - global_event_counter increases by 1 for each <note> visited,
    #   scanning measures inside each movement in document order.
    global_event_counter = 1

    # Local counters to generate unique IDs per event
    event_dynamic_counts: Dict[str, int] = {}
    event_articulation_counts: Dict[str, int] = {}

    for m_info in movements_info:
        movement_index = m_info["movement_index"]
        start_idx = m_info["start_idx"]
        end_idx = m_info["end_idx"]

        for i in range(start_idx, end_idx):
            meas_el = measures[i]
            raw_number = meas_el.get("number")
            sanitized_number = sanitize_measure_number(raw_number, fallback_index=i + 1)

            measure_id = f"so:{work_local_id}_M{movement_index}_Measure_{sanitized_number}"

            # State: dynamics from <direction> that should apply to the next note on each staff.
            pending_dynamics_by_staff: Dict[int, List[str]] = {}

            # Iterate measure children in document order so that <direction> and <note>
            # can be interleaved in time, but notes are still visited in the same order
            # as in extract_notation (one increment of global_event_counter per <note>).
            for child in list(meas_el):
                tag_name = strip_ns(child.tag)

                # 1) Direction-based dynamics
                if tag_name == "direction":
                    dyn_values = parse_direction_dynamics(child)
                    if dyn_values:
                        # Determine staff index; default = 1
                        staff_index = 1
                        staff_el = child.find("staff")
                        if staff_el is not None and staff_el.text:
                            try:
                                staff_index = int(staff_el.text.strip())
                            except ValueError:
                                pass

                        # Store all dynamic values to apply to the next note on this staff
                        current = pending_dynamics_by_staff.get(staff_index, [])
                        current.extend(dyn_values)
                        pending_dynamics_by_staff[staff_index] = current

                # 2) Notes: create links to existing SymbolicEvents and attach expression
                elif tag_name == "note":
                    note_el = child

                    # Staff index (default 1)
                    staff_index = 1
                    staff_el = note_el.find("staff")
                    if staff_el is not None and staff_el.text:
                        try:
                            staff_index = int(staff_el.text.strip())
                        except ValueError:
                            pass

                    # Compute event_id as in extract_notation.py
                    event_index_str = f"{global_event_counter:06d}"
                    global_event_counter += 1

                    event_id = (
                        f"so:{work_local_id}_M{movement_index}_Measure_"
                        f"{sanitized_number}_Event_{event_index_str}"
                    )

                    # Get or create the SymbolicEvent node (it should already exist).
                    event_node = get_or_create_node(
                        event_id,
                        base_types=["ho:SymbolicEvent", "so:MusicNotationElement"],
                    )

                    # --------------------------------------------------
                    # 2.a Dynamics from pending <direction> on this staff
                    # --------------------------------------------------
                    dyn_values_from_direction = pending_dynamics_by_staff.get(staff_index, [])
                    if dyn_values_from_direction:
                        # Once we attach them to this note, clear the pending list
                        pending_dynamics_by_staff[staff_index] = []

                        for dyn_value in dyn_values_from_direction:
                            dyn_value_lower = dyn_value.lower()
                            # Determine index for this event to generate a unique ID
                            dyn_count = event_dynamic_counts.get(event_id, 0) + 1
                            event_dynamic_counts[event_id] = dyn_count

                            dyn_id = f"{event_id}_Dyn_{dyn_count}"

                            dyn_node = get_or_create_node(
                                dyn_id,
                                base_types=["mso:Dynamic", "so:ExpressiveElement"],
                            )
                            dyn_node["so:dynamicValue"] = dyn_value_lower

                            # Optional: assign numeric dynamicLevel heuristic
                            if dyn_value_lower in DYNAMIC_LEVELS:
                                dyn_node["so:dynamicLevel"] = DYNAMIC_LEVELS[dyn_value_lower]

                            # Mark as LoudnessDynamic if appropriate
                            if is_loudness_dynamic(dyn_value_lower):
                                dyn_types = dyn_node.get("@type", [])
                                if isinstance(dyn_types, str):
                                    dyn_types = [dyn_types]
                                if "so:LoudnessDynamic" not in dyn_types:
                                    dyn_types.append("so:LoudnessDynamic")
                                dyn_node["@type"] = dyn_types

                            # Link Dynamic <-> SymbolicEvent
                            dyn_node["so:isDynamicOf"] = {"@id": event_id}
                            event_node["so:hasDynamic"] = append_unique_id_ref(
                                event_node.get("so:hasDynamic"), dyn_id
                            )

                    # --------------------------------------------------
                    # 2.b Dynamics embedded in this <note> (if any)
                    # --------------------------------------------------
                    note_dyn_values = parse_note_dynamics(note_el)
                    for dyn_value in note_dyn_values:
                        dyn_value_lower = dyn_value.lower()
                        dyn_count = event_dynamic_counts.get(event_id, 0) + 1
                        event_dynamic_counts[event_id] = dyn_count

                        dyn_id = f"{event_id}_Dyn_{dyn_count}"

                        dyn_node = get_or_create_node(
                            dyn_id,
                            base_types=["mso:Dynamic", "so:ExpressiveElement"],
                        )
                        dyn_node["so:dynamicValue"] = dyn_value_lower

                        if dyn_value_lower in DYNAMIC_LEVELS:
                            dyn_node["so:dynamicLevel"] = DYNAMIC_LEVELS[dyn_value_lower]

                        if is_loudness_dynamic(dyn_value_lower):
                            dyn_types = dyn_node.get("@type", [])
                            if isinstance(dyn_types, str):
                                dyn_types = [dyn_types]
                            if "so:LoudnessDynamic" not in dyn_types:
                                dyn_types.append("so:LoudnessDynamic")
                            dyn_node["@type"] = dyn_types

                        dyn_node["so:isDynamicOf"] = {"@id": event_id}
                        event_node["so:hasDynamic"] = append_unique_id_ref(
                            event_node.get("so:hasDynamic"), dyn_id
                        )

                    # --------------------------------------------------
                    # 2.c Articulations for this <note>
                    # --------------------------------------------------
                    articulations = parse_note_articulations(note_el)
                    for art_text, art_class in articulations:
                        art_text_lower = art_text.lower()
                        art_count = event_articulation_counts.get(event_id, 0) + 1
                        event_articulation_counts[event_id] = art_count

                        art_id = f"{event_id}_Art_{art_count}"

                        art_node = get_or_create_node(
                            art_id,
                            base_types=["mso:Articulation", "so:ExpressiveElement"],
                        )
                        art_node["so:articulationText"] = art_text_lower

                        # Add specific articulation class if provided (Accent, Staccato, Tenuto, Legato)
                        if art_class is not None:
                            art_types = art_node.get("@type", [])
                            if isinstance(art_types, str):
                                art_types = [art_types]
                            if art_class not in art_types:
                                art_types.append(art_class)
                            art_node["@type"] = art_types

                        # Link Articulation <-> SymbolicEvent
                        art_node["so:isArticulationOf"] = {"@id": event_id}
                        event_node["so:hasArticulation"] = append_unique_id_ref(
                            event_node.get("so:hasArticulation"), art_id
                        )

    jsonld_obj["@graph"] = graph
    return jsonld_obj


# ====================================================
# Main
# ====================================================

if __name__ == "__main__":
    xml_path = MUSICXML_PATH

    if not os.path.isfile(xml_path):
        raise FileNotFoundError(f"MusicXML file not found: {xml_path}")

    jsonld_obj = extend_with_expression(xml_path)

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
