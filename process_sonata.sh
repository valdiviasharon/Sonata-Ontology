#!/bin/bash

# Stop on errors in this script (but we manejamos errores de cada paso con "if ! cmd; then ...; fi")
set -u

# Directory MusicXML scores
XML_DIR="/mnt/c/PFC 3/Sonata Ontology/Beethoven_Piano_Sonata_Dataset_v2/RawData/score_musicxml"

# Python interpreter inside the Linux virtual environment
VENV_PYTHON="/mnt/c/PFC 3/Sonata Ontology/venv_sonata_wsl/bin/python"

# Directories
JSONLD_DIR="JSON_LD"  
TTL_DIR="TTL"

mkdir -p "$JSONLD_DIR"
mkdir -p "$TTL_DIR"

xml_files=("$XML_DIR"/*.xml)

for xmlfile in "${xml_files[@]}"; do
    filename=$(basename -- "$xmlfile")
    base="${filename%.*}"

    echo "-----------------------------------------------------"
    echo "Processing score:"
    echo "       File name : $filename"
    echo "       Base name : $base"
    echo "       XML path  : $xmlfile"

    # 1) Metadata
    echo "[1/7] Metadata..."
    if ! "$VENV_PYTHON" "extract_metadata.py" "$xmlfile"; then
        echo "[ERROR] Metadata step failed for $filename, skipping rest of steps."
        continue
    fi

    # 2) Structure (movements, staves, measures)
    echo "[2/7] Structure..."
    if ! "$VENV_PYTHON" "extract_structure.py" "$xmlfile"; then
        echo "[ERROR] Structure step failed for $filename, skipping rest of steps."
        continue
    fi

    # 3) Music notation (clefs, durations, notes/rests, tempo, time signatures, etc.)
    echo "[3/7] Music notation..."
    if ! "$VENV_PYTHON" "extract_music_notation.py" "$xmlfile"; then
        echo "[ERROR] Music-notation step failed for $filename, skipping rest of steps."
        continue
    fi

    # 4) Expression (dynamics and articulations)
    echo "[6/7] Expression..."
    if ! "$VENV_PYTHON" "extract_expression.py" "$xmlfile"; then
        echo "[ERROR] Expression step failed for $filename, skipping rest of steps."
        continue
    fi

    # 5) Technical complexity
    echo "[7/7] Technical complexity..."
    if ! "$VENV_PYTHON" "extract_technical_complexity_profile.py" "$xmlfile"; then
        echo "[ERROR] Technical-complexity step failed for $filename, skipping rest of steps."
        continue
    fi

    echo "[OK] Finished JSON-LD enrichment for: $filename"
done

echo "-----------------------------------------------------"
echo "Converting all JSON-LD files to TTL..."

# jsonld_to_ttl.py is written to read JSON_LD/ and write TTL/ directly (no args)
if ! "$VENV_PYTHON" "jsonld_to_ttl.py"; then
    echo "[ERROR] JSON-LD → TTL conversion failed."
else
    echo "[OK] TTL files generated in directory: $TTL_DIR"
fi

echo "====================================================="
echo "Batch processing finished for all scores"
echo "====================================================="
