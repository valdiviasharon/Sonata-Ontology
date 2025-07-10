#!/bin/bash

# Path to xml files
XML_DIR="./Beethoven_Piano_Sonata_Dataset_v2/RawData/score_xml_repetitions"

# Path to scripts
SCRIPT_DIR="./Scripts"

VENV_PYTHON="./venv_sonata/Scripts/python.exe"

JSON_DIR="./JSONs"

PREFIX_SO='http://example.org/sonata#'


TTL_DIR="./TTL"

mkdir -p "$JSON_DIR"
mkdir -p "$TTL_DIR"

for xmlfile in "$XML_DIR"/*.xml; do
    # Get filename
    filename=$(basename -- "$xmlfile")
    base="${filename%.*}"

    # Create a folder for each sonata
    subdir="$JSON_DIR/$base"x
    mkdir -p "$subdir"

    # Metadata
    "$VENV_PYTHON" "$SCRIPT_DIR/metadata.py" "$xmlfile" "$subdir/metadata.json"

    # Notes, Chords, Rest, Measure, Key, Tempo, Time Signature, Dynamics, Clefs, 
    "$VENV_PYTHON" "$SCRIPT_DIR/xml_to_elements_json.py" "$xmlfile" "$subdir/metadata.json" "$subdir/elements.json"

    # Structure - PHRASES
    "$VENV_PYTHON" "$SCRIPT_DIR/structure_analysis.py" "$subdir/elements.json" "$subdir/phrases.json"

    #JSON TO RDF - data.ttl per each sonata
    "$VENV_PYTHON" "$SCRIPT_DIR/json_to_rdf.py" "$subdir" "$PREFIX_SO" "$TTL_DIR/$base.ttl"

    echo "Processed: $base"

done

echo "All files have been processed"
