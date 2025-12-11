from __future__ import annotations
import os
import sys
import json
import xml.etree.ElementTree as ET
from typing import Dict, Any

# Intentar usar music21 para análisis de tonalidad
try:
    import music21
    MUSIC21_AVAILABLE = True
except ImportError:
    MUSIC21_AVAILABLE = False


# ====================================================
# Configuration
# ====================================================

# Default path to a single MusicXML file.
MUSICXML_PATH = r"C:\PFC 3\Sonata Ontology\Beethoven_Piano_Sonata_Dataset_v2\RawData\score_musicxml\Beethoven_Op002No1-01.xml"

# Folder (relative to this script) where JSON-LD files will be stored.
JSONLD_DIR = "JSON_LD"

# Namespace IRIs used in the JSON-LD context.
SO_IRI   = "https://github.com/valdiviasharon/Sonata-Ontology/sonata_ontology#"
MO_IRI   = "http://purl.org/ontology/mo/"
MTO_IRI  = "http://purl.org/ontology/mto/"
MSO_IRI  = "http://linkeddata.uni-muenster.de/ontology/musicscore#"
DCT_IRI  = "http://purl.org/dc/terms/"
RDFS_IRI = "http://www.w3.org/2000/01/rdf-schema#"

# Mapping from <fifths> to theoretical major / minor tonics.
FIFTHS_TO_MAJOR_TONIC = {
    -7: "C_flat", -6: "G_flat", -5: "D_flat", -4: "A_flat",
    -3: "E_flat", -2: "B_flat", -1: "F", 0: "C",
    1: "G", 2: "D", 3: "A", 4: "E", 5: "B",
    6: "F_sharp", 7: "C_sharp",
}

FIFTHS_TO_MINOR_TONIC = {
    -7: "A_flat", -6: "E_flat", -5: "B_flat", -4: "F",
    -3: "C", -2: "G", -1: "D", 0: "A",
    1: "E", 2: "B", 3: "F_sharp", 4: "C_sharp",
    5: "G_sharp", 6: "D_sharp", 7: "A_sharp",
}


# ====================================================
# Parse basic work metadata (title, composer, id)
# ====================================================

def parse_musicxml_metadata(xml_path: str) -> Dict[str, Any]:
    """
    Extract basic metadata from a MusicXML file.

    Returns a dictionary with:
        - work_local_id: local identifier derived from the filename
        - work_compact_iri: compact IRI (CURIE) for the work (e.g., "so:Beethoven_Op002No1-01")
        - file_name: basename of the XML file
        - title: work title (if found)
        - composer: composer name (if found)
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # ---- Title (so:title, domain mo:MusicalWork) ----
    work_title = None

    # Prefer <work><work-title>
    wt = root.find("./work/work-title")
    if wt is not None and wt.text:
        work_title = " ".join(wt.text.split())

    # Fallback: look into <credit> entries with credit-type "title"
    if not work_title:
        for credit in root.findall("credit"):
            ctype = credit.find("credit-type")
            cwords = credit.find("credit-words")
            if (
                ctype is not None and ctype.text == "title"
                and cwords is not None and cwords.text
            ):
                work_title = " ".join(cwords.text.split())
                break

    # ---- Composer (so:composer) ----
    composer = None

    # Prefer <identification><creator type="composer">
    creator = root.find("./identification/creator[@type='composer']")
    if creator is not None and creator.text:
        composer = " ".join(creator.text.split())

    # Fallback: <credit> entries with credit-type "composer"
    if not composer:
        for credit in root.findall("credit"):
            ctype = credit.find("credit-type")
            cwords = credit.find("credit-words")
            if (
                ctype is not None and ctype.text == "composer"
                and cwords is not None and cwords.text
            ):
                composer = " ".join(cwords.text.split())
                break

    # ---- Work identifier derived from the file name ----
    base_name = os.path.splitext(os.path.basename(xml_path))[0]
    # Example: "Beethoven_Op002No1-01" -> "Beethoven_Op002No1-01"
    work_local_id = base_name
    work_compact_iri = f"so:{work_local_id}"

    return {
        "work_local_id": work_local_id,
        "work_compact_iri": work_compact_iri,
        "file_name": os.path.basename(xml_path),
        "title": work_title,
        "composer": composer,
    }


# ====================================================
# Extract global key / key signature information
# ====================================================

def extract_initial_key_info(xml_path: str) -> Dict[str, Any]:
    """
    Extrae información de la tonalidad global de la obra.

    Estrategia:
      1. Intentar primero un análisis global con music21 (score.analyze('key')).
      2. Si falla o no da mayor/menor, caer a la primera etiqueta <key> del MusicXML.
      3. A partir de fifths y mode, mapear:
         - clase de armadura (so:KS_*),
         - tipo y número de alteraciones,
         - tónica teórica (FIFTHS_TO_MAJOR_TONIC / FIFTHS_TO_MINOR_TONIC),
         - clase de tonalidad (so:Key_F_minor, etc.).
    """
    fifths: int | None = None
    mode: str | None = None

    # ------------------------------------------------
    # 1) Intento principal: análisis con music21
    # ------------------------------------------------
    if MUSIC21_AVAILABLE:
        try:
            score = music21.converter.parse(xml_path)
            k = score.analyze("key")  # análisis global de tonalidad

            if k is not None:
                # music21 da el número de sostenidos (negativo = bemoles)
                fifths = int(k.sharps)
                if k.mode:
                    mode = k.mode.lower()  # "major" o "minor"
        except Exception:
            # Si algo falla, pasamos al fallback MusicXML
            fifths = None
            mode = None

    # ------------------------------------------------
    # 2) Fallback: usar la primera etiqueta <key> del MusicXML
    # ------------------------------------------------
    if fifths is None or mode not in {"major", "minor"}:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        key_el = root.find(".//key")
        if key_el is not None:
            fifths_el = key_el.find("fifths")
            mode_el = key_el.find("mode")

            if fifths is None and fifths_el is not None and fifths_el.text:
                try:
                    fifths = int(fifths_el.text.strip())
                except ValueError:
                    fifths = None

            if mode not in {"major", "minor"} and mode_el is not None and mode_el.text:
                mode_raw = mode_el.text.strip()
                mode = mode_raw.lower() if mode_raw else None

    # Si aún así no tenemos fifths, no podemos inferir tonalidad / armadura
    if fifths is None:
        return {
            "fifths": None,
            "mode": mode,
            "key_signature_class": None,
            "tonic": None,
            "key_class": None,
            "accidental_type": None,
            "accidental_count": None,
        }

    # ------------------------------------------------
    # 3) A partir de fifths y mode, construir la info
    # ------------------------------------------------
    key_signature_class = None
    accidental_type = None
    accidental_count = abs(fifths)

    # Clase de armadura y tipo de alteración
    if fifths == 0:
        key_signature_class = "so:KS_0"
        accidental_type = "none"
    elif fifths > 0:
        key_signature_class = f"so:KS_{fifths}sharps"
        accidental_type = "sharp"
    else:
        key_signature_class = f"so:KS_{abs(fifths)}flats"
        accidental_type = "flat"

    # Tónica y clase de tonalidad teórica
    tonic = None
    key_class = None

    if mode in {"major", "minor"}:
        if mode == "major":
            tonic = FIFTHS_TO_MAJOR_TONIC.get(fifths)
        else:
            tonic = FIFTHS_TO_MINOR_TONIC.get(fifths)

        if tonic:
            key_class = f"so:Key_{tonic}_{mode}"

    return {
        "fifths": fifths,
        "mode": mode,
        "key_signature_class": key_signature_class,
        "tonic": tonic,
        "key_class": key_class,
        "accidental_type": accidental_type,
        "accidental_count": accidental_count,
    }


# ====================================================
# Extract instrument information
# ====================================================

def extract_instrument_info(xml_path: str) -> Dict[str, Any]:
    """
    Extract instrument information from the MusicXML file.

    Strategy:
      1. Try <part-list><score-part><part-name>.
      2. Fallback to <score-part><score-instrument><instrument-name>.
      3. If nothing is found, assume "Piano" for this corpus.

    Returns a dictionary with:
        - label: human-readable instrument name (string)
        - instrument_class: compact IRI for the ontology class (e.g., "so:Piano")
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()

    instrument_label = None

    # Try <part-list><score-part><part-name>
    part_name_el = root.find("./part-list/score-part/part-name")
    if part_name_el is not None and part_name_el.text:
        instrument_label = " ".join(part_name_el.text.split())

    # Fallback: <score-part><score-instrument><instrument-name>
    if not instrument_label:
        instr_el = root.find("./part-list/score-part/score-instrument/instrument-name")
        if instr_el is not None and instr_el.text:
            instrument_label = " ".join(instr_el.text.split())

    # If still nothing, assume Piano (for this Beethoven piano sonata corpus)
    if not instrument_label:
        instrument_label = "Piano"

    # Map textual label to ontology class
    lower_label = instrument_label.lower()
    if "piano" in lower_label:
        instrument_class = "so:Piano"
    else:
        # Generic fallback: we at least know it is some kind of instrument
        instrument_class = "so:Instrument"

    return {
        "label": instrument_label,
        "instrument_class": instrument_class,
    }


# ====================================================
# Build JSON-LD document
# ====================================================

def build_metadata_jsonld(xml_path: str) -> Dict[str, Any]:
    """
    Build a JSON-LD document that describes:
      - one work instance (mo:MusicalWork / so:Sonata), also tagged as so:Metadata
      - its global key (mto:Key) if a <key> is found, also tagged as so:Metadata
      - its global key signature (mto:KeySignature) if a <key> is found, also tagged as so:Metadata
      - its instrument node and so:hasInstrument relation, instrument tagged as so:Metadata
    """
    meta = parse_musicxml_metadata(xml_path)
    key_info = extract_initial_key_info(xml_path)
    instrument_info = extract_instrument_info(xml_path)

    work_id = meta["work_compact_iri"]
    work_local_id = meta["work_local_id"]

    graph_nodes = []

    # ----- Work node -----
    work_node: Dict[str, Any] = {
        "@id": work_id,
        # Also consider the work as part of the metadata layer
        "@type": ["mo:MusicalWork", "so:Sonata", "so:Metadata"],
        "so:title": meta.get("title"),
        "so:composer": meta.get("composer"),
        "dct:source": meta.get("file_name"),
    }

    # ----- Instrument node -----
    instrument_node_id = f"so:{work_local_id}_Instrument"
    instrument_node: Dict[str, Any] = {
        "@id": instrument_node_id,
        # Instrument is a concrete instrument class + Metadata
        "@type": [instrument_info["instrument_class"], "so:Metadata"],
    }
    if instrument_info["label"]:
        instrument_node["rdfs:label"] = instrument_info["label"]

    # Link work to its instrument
    work_node["so:hasInstrument"] = {"@id": instrument_node_id}

    graph_nodes.append(work_node)
    graph_nodes.append(instrument_node)

    # ----- Key and KeySignature nodes (if we have <fifths>) -----
    if key_info["fifths"] is not None:
        key_node_id = f"so:{work_local_id}_GlobalKey"
        key_sig_node_id = f"so:{work_local_id}_GlobalKeySignature"

        # Link from work to its (global) key
        work_node["so:hasKey"] = {"@id": key_node_id}

        # Key node: use mso:Key so that it is under so:HarmonicElement in the TBox
        key_node: Dict[str, Any] = {
            "@id": key_node_id,
            "@type": ["mto:Key", "so:HarmonicElement"],
        }
        # Also type it with the specific so:Key_* class if we could infer it
        if key_info["key_class"]:
            key_node["@type"].append(key_info["key_class"])
        # Tonic and mode as data properties
        if key_info["tonic"]:
            key_node["so:hasTonic"] = key_info["tonic"]
        if key_info["mode"]:
            key_node["so:hasMode"] = key_info["mode"]

        # KeySignature node: use mto:KeySignature so that it is under so:MusicNotationElement
        key_sig_node: Dict[str, Any] = {
            "@id": key_sig_node_id,
            "@type": ["mto:KeySignature", "mto:Signature", "so:MusicNotationElement"],
        }
        # Also type it with the specific so:KS_* class if we could infer it
        if key_info["key_signature_class"]:
            key_sig_node["@type"].append(key_info["key_signature_class"])
        # Accidentals information
        if key_info["accidental_count"] is not None:
            key_sig_node["so:accidentalCount"] = key_info["accidental_count"]
        if key_info["accidental_type"]:
            key_sig_node["so:accidentalType"] = key_info["accidental_type"]
        # Link signature to key (so:representsKey)
        key_sig_node["so:representsKey"] = {"@id": key_node_id}

        graph_nodes.extend([key_node, key_sig_node])

    jsonld_obj: Dict[str, Any] = {
        "@context": {
            "so": SO_IRI,
            "mo": MO_IRI,
            "mto": MTO_IRI,
            "mso": MSO_IRI,
            "dct": DCT_IRI,
            "rdfs": RDFS_IRI,
        },
        "@graph": graph_nodes,
    }
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

    jsonld_obj = build_metadata_jsonld(xml_path)

    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        base_dir = os.getcwd()

    output_dir = os.path.join(base_dir, JSONLD_DIR)
    os.makedirs(output_dir, exist_ok=True)

    base_name = os.path.splitext(os.path.basename(xml_path))[0]
    # Use the original name with dash: Beethoven_Op002No1-01.jsonld
    output_jsonld_path = os.path.join(output_dir, base_name + ".jsonld")

    with open(output_jsonld_path, "w", encoding="utf-8") as f:
        json.dump(jsonld_obj, f, indent=2, ensure_ascii=False)

    print(f"JSON-LD metadata written to: {output_jsonld_path}")
