from __future__ import annotations
import os
import sys
import json
from math import ceil
from typing import Dict, Any, List, Optional, Set


JSONLD_DIR = "JSON_LD"

SO_PREFIX = "so:"
MSO_PREFIX = "mso:"
MTO_PREFIX = "mto:"
HO_PREFIX = "ho:"


# ============================
# Weights for LCI computation
# ============================

# All weights must be >= 0. They will be normalized to sum = 1.
LOCAL_COMPLEXITY_WEIGHTS = {
    "noteCount": 3.06,
    "measureAccidentalCount": 4.31,
    "subdivisionIndex": 3.75,
    "minNoteValue": 3.68,
    "dynamicCount": 3.68,
    "articulationCount": 4.43,
}


# ---------------------------
# Helpers
# ---------------------------

def get_base_dir() -> str:
    """
    Return the base directory of this script.
    """
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except NameError:
        return os.getcwd()


def xml_to_jsonld_path(xml_path: str) -> str:
    """
    Given a MusicXML path, return the expected JSON-LD path based on the
    shared base name and JSONLD_DIR.

    Example:
        Beethoven_Op002No1-01.xml -> JSON_LD/Beethoven_Op002No1-01.jsonld
    """
    base_dir = get_base_dir()
    base_name = os.path.splitext(os.path.basename(xml_path))[0]
    jsonld_dir = os.path.join(base_dir, JSONLD_DIR)
    return os.path.join(jsonld_dir, base_name + ".jsonld")


def get_ref_id(value: Any) -> Optional[str]:
    """
    Extract an '@id' from a JSON-LD reference that may be a dict, list or string.
    """
    if value is None:
        return None
    if isinstance(value, dict):
        return value.get("@id")
    if isinstance(value, list) and value:
        first = value[0]
        if isinstance(first, dict):
            return first.get("@id")
    if isinstance(value, str):
        return value
    return None


def normalize_types(node: Dict[str, Any]) -> List[str]:
    """
    Ensure @type is returned as a list of strings.
    """
    types = node.get("@type", [])
    if isinstance(types, str):
        return [types]
    return types


# Mapping MusicXML note-type -> denominator of the fraction of the whole note.
# This is used to derive minNoteValue and rhythmic subdivision.
NOTE_BASE_DENOMINATORS: Dict[str, int] = {
    "maxima": 0,
    "long": 0,
    "breve": 0,
    "whole": 1,    # 1/1
    "half": 2,     # 1/2
    "quarter": 4,  # 1/4
    "eighth": 8,   # 1/8
    "16th": 16,
    "32nd": 32,
    "64th": 64,
    "128th": 128,
    "256th": 256,
}


def safe_minmax(values: List[float]) -> (float, float):
    """
    Return (min, max) for a list of values, handling empty lists.
    """
    if not values:
        return 0.0, 0.0
    return min(values), max(values)


def safe_normalize(value: float, vmin: float, vmax: float) -> float:
    """
    Min-max normalization to [0, 1]. If vmax == vmin, return 0.0.
    """
    if vmax <= vmin:
        return 0.0
    return (value - vmin) / float(vmax - vmin)


# ---------------------------
# Core calculation
# ---------------------------

def compute_technical_complexity_profiles(jsonld_obj: Dict[str, Any]) -> Dict[str, Any]:
    """
    Given the unified JSON-LD object, compute technical complexity profiles:

      - For each mso:Measure:
          * Compute raw metrics:
              - so:noteCount
              - so:measureAccidentalCount
              - so:subdivisionIndex
              - so:minNoteValue
              - so:dynamicCount
              - so:articulationCount
          * Compute so:LCIvalue (normalized weighted sum).
          * Create or update a so:LocalComplexityIndex instance and link it
            via so:hasLocalComplexityIndex.

      - For each so:SonataMovement:
          * Compute so:globalComplexityIndex as the average LCIvalue across
            its measures.
          * Create or update a so:GlobalComplexityProfile instance and link it
            via so:hasGlobalComplexityProfile.

    Returns the modified JSON-LD object.
    """
    graph: List[Dict[str, Any]] = jsonld_obj.get("@graph", [])
    node_by_id: Dict[str, Dict[str, Any]] = {}

    # Index nodes by @id
    for node in graph:
        if isinstance(node, dict) and "@id" in node:
            node_by_id[node["@id"]] = node

    # Collect measures and movements
    measure_ids: Set[str] = set()
    movement_ids: Set[str] = set()

    # Map from event -> measure
    event_measure: Dict[str, str] = {}

    # Notes per measure (event ids)
    measure_notes: Dict[str, List[str]] = {}

    # Build indices from existing nodes
    for node_id, node in node_by_id.items():
        types = normalize_types(node)

        # Identify measures
        if f"{MSO_PREFIX}Measure" in types:
            measure_ids.add(node_id)

        # Identify sonata movements
        if f"{SO_PREFIX}SonataMovement" in types:
            movement_ids.add(node_id)

        # Symbolic events and their parent measures
        if f"{HO_PREFIX}SymbolicEvent" in types:
            measure_ref = node.get("so:isInMeasure")
            measure_id = get_ref_id(measure_ref)
            if measure_id is not None:
                event_measure[node_id] = measure_id

                # Note events
                if f"{MSO_PREFIX}Note" in types:
                    measure_notes.setdefault(measure_id, []).append(node_id)

    # Time signature per measure (numerator, denominator)
    measure_timesig: Dict[str, Dict[str, int]] = {}

    for measure_id in measure_ids:
        mnode = node_by_id.get(measure_id, {})
        ts_ref = mnode.get("so:hasTimeSignature")
        ts_id = get_ref_id(ts_ref)

        num = None
        den = None

        if ts_id is not None and ts_id in node_by_id:
            ts_node = node_by_id[ts_id]
            num = ts_node.get("so:numerator")
            den = ts_node.get("so:denominator")

        # Default to 4/4 if missing
        try:
            num_int = int(num) if num is not None else 4
        except (ValueError, TypeError):
            num_int = 4

        try:
            den_int = int(den) if den is not None else 4
        except (ValueError, TypeError):
            den_int = 4

        measure_timesig[measure_id] = {"numerator": num_int, "denominator": den_int}

    # Initialize counts per measure
    dynamic_count: Dict[str, int] = {mid: 0 for mid in measure_ids}
    articulation_count: Dict[str, int] = {mid: 0 for mid in measure_ids}

    # Iterate dynamics and articulations
    for node_id, node in node_by_id.items():
        types = normalize_types(node)

        # LoudnessDynamic -> dynamicCount
        if f"{SO_PREFIX}LoudnessDynamic" in types:
            event_ref = node.get("so:isDynamicOf")
            event_id = get_ref_id(event_ref)
            if event_id is not None:
                measure_id = event_measure.get(event_id)
                if measure_id in dynamic_count:
                    dynamic_count[measure_id] += 1

        # Staccato articulations -> articulationCount
        if f"{SO_PREFIX}Staccato" in types:
            event_ref = node.get("so:isArticulationOf")
            event_id = get_ref_id(event_ref)
            if event_id is not None:
                measure_id = event_measure.get(event_id)
                if measure_id in articulation_count:
                    articulation_count[measure_id] += 1

    # Metrics per measure (raw values)
    note_count_by_measure: Dict[str, int] = {}
    acc_count_by_measure: Dict[str, int] = {}
    subdiv_index_by_measure: Dict[str, int] = {}
    min_note_value_by_measure: Dict[str, int] = {}

    # Compute raw metrics for each measure
    for measure_id in measure_ids:
        ts_info = measure_timesig.get(measure_id, {"numerator": 4, "denominator": 4})
        num_beats = ts_info["numerator"]
        beat_den = ts_info["denominator"]

        note_event_ids = measure_notes.get(measure_id, [])
        n_notes = len(note_event_ids)

        # noteCount: total number of notes in the measure
        note_count = n_notes

        # measureAccidentalCount
        accidental_count = 0

        # minNoteValue & subdivisionIndex
        note_denominators: List[int] = []
        subdivisions: List[int] = []

        for ev_id in note_event_ids:
            ev_node = node_by_id.get(ev_id, {})

            # Pitch / accidental
            pitch_ref = ev_node.get("so:hasPitch")
            pitch_id = get_ref_id(pitch_ref)
            if pitch_id is not None and pitch_id in node_by_id:
                pitch_node = node_by_id[pitch_id]
                if "so:hasAccidental" in pitch_node:
                    accidental_count += 1

            # Duration / noteType
            dur_ref = ev_node.get("so:hasDuration")
            dur_id = get_ref_id(dur_ref)
            if dur_id is None or dur_id not in node_by_id:
                continue

            dur_node = node_by_id[dur_id]
            note_type_text = dur_node.get("so:noteType")
            if not isinstance(note_type_text, str):
                continue

            base_den = NOTE_BASE_DENOMINATORS.get(note_type_text, 0)
            if base_den <= 0:
                continue

            note_denominators.append(base_den)

            # Subdivision relative to beat denominator (for rhythmic fineness)
            if beat_den > 0:
                ratio = base_den / float(beat_den)
                subdivisions.append(int(ceil(ratio)))
            else:
                subdivisions.append(base_den)

        if note_denominators:
            min_note_value = max(note_denominators)
        else:
            min_note_value = 0

        if subdivisions:
            subdivision_index = max(subdivisions)
        else:
            subdivision_index = 0

        # Store raw metrics
        note_count_by_measure[measure_id] = note_count
        acc_count_by_measure[measure_id] = accidental_count
        subdiv_index_by_measure[measure_id] = subdivision_index
        min_note_value_by_measure[measure_id] = min_note_value

    # ---------------------------
    # Compute LCIvalue (normalized)
    # ---------------------------

    # Gather raw values for min-max normalization
    nc_values = list(note_count_by_measure.values())
    acc_values = list(acc_count_by_measure.values())
    sub_values = list(subdiv_index_by_measure.values())
    minv_values = list(min_note_value_by_measure.values())
    dyn_values = [dynamic_count[m] for m in measure_ids]
    art_values = [articulation_count[m] for m in measure_ids]

    nc_min, nc_max = safe_minmax(nc_values)
    acc_min, acc_max = safe_minmax(acc_values)
    sub_min, sub_max = safe_minmax(sub_values)
    minv_min, minv_max = safe_minmax(minv_values)
    dyn_min, dyn_max = safe_minmax(dyn_values)
    art_min, art_max = safe_minmax(art_values)

    # Normalize weights to sum to 1
    w = LOCAL_COMPLEXITY_WEIGHTS
    w_sum = sum(max(v, 0.0) for v in w.values())
    if w_sum <= 0.0:
        w_nc = w_acc = w_sub = w_minv = w_dyn = w_art = 1.0 / 6.0
    else:
        w_nc  = max(w["noteCount"],              0.0) / w_sum
        w_acc = max(w["measureAccidentalCount"], 0.0) / w_sum
        w_sub = max(w["subdivisionIndex"],       0.0) / w_sum
        w_minv= max(w["minNoteValue"],           0.0) / w_sum
        w_dyn = max(w["dynamicCount"],           0.0) / w_sum
        w_art = max(w["articulationCount"],      0.0) / w_sum

    # Map measure -> LCIvalue (needed later for global complexity)
    lci_value_by_measure: Dict[str, float] = {}

    # Create/update LocalComplexityIndex nodes and link measures
    for measure_id in measure_ids:
        mnode = node_by_id[measure_id]

        nc   = note_count_by_measure.get(measure_id, 0)
        acc  = acc_count_by_measure.get(measure_id, 0)
        sub  = subdiv_index_by_measure.get(measure_id, 0)
        minv = min_note_value_by_measure.get(measure_id, 0)
        dyn  = dynamic_count.get(measure_id, 0)
        art  = articulation_count.get(measure_id, 0)

        # Normalized metrics
        nc_n   = safe_normalize(nc,   nc_min,   nc_max)
        acc_n  = safe_normalize(acc,  acc_min,  acc_max)
        sub_n  = safe_normalize(sub,  sub_min,  sub_max)
        minv_n = safe_normalize(minv, minv_min, minv_max)
        dyn_n  = safe_normalize(dyn,  dyn_min,  dyn_max)
        art_n  = safe_normalize(art,  art_min,  art_max)

        # Weighted sum -> LCIvalue
        lci_value = (
            w_nc  * nc_n
            + w_acc * acc_n
            + w_sub * sub_n
            + w_minv * minv_n
            + w_dyn * dyn_n
            + w_art * art_n
        )

        lci_value_by_measure[measure_id] = lci_value

        # LocalComplexityIndex node id, e.g.:
        # so:Beethoven_Op002No1-01_M1_Measure_50_LCI
        lci_id = measure_id + "_LCI"

        # Reuse existing LCI node if present; otherwise create a new one
        lci_node = node_by_id.get(lci_id)
        if lci_node is None:
            lci_node = {
                "@id": lci_id,
                "@type": [
                    "so:LocalComplexityIndex",
                    "so:TechnicalComplexityProfile",
                ],
            }
            graph.append(lci_node)
            node_by_id[lci_id] = lci_node
        else:
            # Ensure the required types are present
            types = set(normalize_types(lci_node))
            types.add("so:LocalComplexityIndex")
            types.add("so:TechnicalComplexityProfile")
            lci_node["@type"] = list(types)

        # Clean old noteDensity if it was present (legacy)
        lci_node.pop("so:noteDensity", None)

        # Attach metrics to the LCI node
        lci_node["so:noteCount"] = nc
        lci_node["so:measureAccidentalCount"] = acc
        lci_node["so:subdivisionIndex"] = sub
        lci_node["so:minNoteValue"] = minv
        lci_node["so:dynamicCount"] = dyn
        lci_node["so:articulationCount"] = art
        lci_node["so:LCIvalue"] = round(lci_value, 4)

        # Link measure -> LCI
        mnode["so:hasLocalComplexityIndex"] = {"@id": lci_id}

    # ---------------------------
    # Global complexity per movement
    # ---------------------------

    # Movement -> measures mapping
    movement_measures: Dict[str, List[str]] = {mid: [] for mid in movement_ids}

    for movement_id in movement_ids:
        mv_node = node_by_id[movement_id]
        meas_refs = mv_node.get("so:movementHasMeasure")
        # meas_refs can be dict or list or None
        if isinstance(meas_refs, dict):
            meas_refs = [meas_refs]
        if isinstance(meas_refs, list):
            for ref in meas_refs:
                mid = get_ref_id(ref)
                if mid in measure_ids:
                    movement_measures[movement_id].append(mid)

    # For each movement, compute globalComplexityIndex as the average LCIvalue
    for movement_id, mlist in movement_measures.items():
        if not mlist:
            # No measures found for this movement; skip GCP creation
            continue

        lci_values: List[float] = []
        for mid in mlist:
            val = lci_value_by_measure.get(mid)
            if val is not None:
                lci_values.append(val)

        if not lci_values:
            # No LCI values for these measures; skip
            continue

        gci = sum(lci_values) / float(len(lci_values))

        # GlobalComplexityProfile node id, e.g.:
        # so:Beethoven_Op002No1-01_M1_GlobalProfile
        gcp_id = movement_id + "_GCP"

        gcp_node = node_by_id.get(gcp_id)
        if gcp_node is None:
            gcp_node = {
                "@id": gcp_id,
                "@type": [
                    "so:GlobalComplexityProfile",
                    "so:TechnicalComplexityProfile",
                ],
            }
            graph.append(gcp_node)
            node_by_id[gcp_id] = gcp_node
        else:
            types = set(normalize_types(gcp_node))
            types.add("so:GlobalComplexityProfile")
            types.add("so:TechnicalComplexityProfile")
            gcp_node["@type"] = list(types)

        gcp_node["so:globalComplexityIndex"] = round(gci, 4)

        # Link movement -> GlobalComplexityProfile
        mv_node = node_by_id[movement_id]
        mv_node["so:hasGlobalComplexityProfile"] = {"@id": gcp_id}

    jsonld_obj["@graph"] = graph
    return jsonld_obj


# ---------------------------
# File processing helper
# ---------------------------

def process_jsonld_file(jsonld_path: str) -> None:
    """
    Load a JSON-LD file, compute technical complexity profiles,
    and overwrite the file with the updated content.
    """
    if not os.path.isfile(jsonld_path):
        raise FileNotFoundError(f"JSON-LD file not found: {jsonld_path}")

    with open(jsonld_path, "r", encoding="utf-8") as f:
        jsonld_obj = json.load(f)

    jsonld_obj = compute_technical_complexity_profiles(jsonld_obj)

    with open(jsonld_path, "w", encoding="utf-8") as f:
        json.dump(jsonld_obj, f, indent=2, ensure_ascii=False)

    print(f"[OK] Technical complexity profiles written into: {jsonld_path}")


# ---------------------------
# Main
# ---------------------------

if __name__ == "__main__":
    """
    Usage options:

      1) No arguments:
         - Process all .jsonld files found in JSON_LD/ relative to this script.

      2) One argument:
         a) JSON-LD file:
              python extract_technical_complexity_profile.py JSON_LD/Beethoven_Op002No1-01.jsonld
         b) Directory:
              python extract_technical_complexity_profile.py JSON_LD
              (processes all .jsonld files inside that directory)
         c) MusicXML file:
              python extract_technical_complexity_profile.py Beethoven_Op002No1-01.xml
              (infers JSON_LD/Beethoven_Op002No1-01.jsonld and processes it)
    """
    base_dir = get_base_dir()

    if len(sys.argv) == 1:
        # No arguments: process all JSON-LD files in JSONLD_DIR
        jsonld_dir = os.path.join(base_dir, JSONLD_DIR)
        if not os.path.isdir(jsonld_dir):
            raise FileNotFoundError(f"JSON-LD directory not found: {jsonld_dir}")

        files = sorted(
            f for f in os.listdir(jsonld_dir)
            if f.lower().endswith(".jsonld")
        )
        if not files:
            print(f"No .jsonld files found in {jsonld_dir}")
            sys.exit(0)

        print(f"Processing {len(files)} JSON-LD files in {jsonld_dir} ...")
        for fname in files:
            path = os.path.join(jsonld_dir, fname)
            process_jsonld_file(path)

    elif len(sys.argv) == 2:
        arg = sys.argv[1]

        # Case: directory -> process all .jsonld inside
        if os.path.isdir(arg):
            jsonld_dir = arg
            files = sorted(
                f for f in os.listdir(jsonld_dir)
                if f.lower().endswith(".jsonld")
            )
            if not files:
                print(f"No .jsonld files found in directory {jsonld_dir}")
                sys.exit(0)

            print(f"Processing {len(files)} JSON-LD files in {jsonld_dir} ...")
            for fname in files:
                path = os.path.join(jsonld_dir, fname)
                process_jsonld_file(path)

        # Case: file
        elif os.path.isfile(arg):
            # If it is a JSON-LD file, process directly
            if arg.lower().endswith(".jsonld"):
                process_jsonld_file(arg)
            # If it is a MusicXML file, infer the JSON-LD path and process it
            elif arg.lower().endswith(".xml"):
                jsonld_path = xml_to_jsonld_path(arg)
                process_jsonld_file(jsonld_path)
            else:
                raise ValueError(
                    f"Unsupported file extension for '{arg}'. "
                    f"Expected .jsonld or .xml."
                )

        else:
            # Argument is neither an existing file nor a directory
            raise FileNotFoundError(f"Path not found: {arg}")

    else:
        sys.exit(1)
