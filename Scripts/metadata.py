import sys
import os
import json
from music21 import converter

def extract_metadata(xml_file, output_file):
    score = converter.parse(xml_file)
    title = os.path.splitext(os.path.basename(xml_file))[0]
    parts = score.parts
    instrument = None
    for p in parts:
        if hasattr(p, "partName") and p.partName:
            instrument = p.partName
            break
    if not instrument:
        instrument = "Unknown"
    max_measure_number = 0
    for p in parts:
        for m in p.getElementsByClass('Measure'):
            if m.measureNumber is not None:
                max_measure_number = max(max_measure_number, m.measureNumber)
    data = {
        "@type": "Metadata",
        "title": title,
        "instrument": instrument,
        "total_measures": max_measure_number,
        "tonality": None,       # left blank, to be filled by elements script
        "global_key": None      # left blank, to be filled by elements script
    }
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Metadata saved to {output_file}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python xml_to_metadata.py <input_xml_file> <output_json_file>")
        sys.exit(1)
    xml_path = sys.argv[1]
    output_path = sys.argv[2]
    extract_metadata(xml_path, output_path)
