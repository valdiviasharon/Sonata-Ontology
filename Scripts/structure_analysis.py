import json
import sys
import numpy as np
from scipy.signal import find_peaks
import matplotlib.pyplot as plt

def detect_phrases(measures, min_length=6, prominence=3):
    novelty = [
        len(m.get("notes", [])) + len(m.get("rests", [])) +
        len(m.get("chords", [])) + len(m.get("dynamics", []))
        for m in measures
    ]
    novelty = np.array(novelty)
    measure_ids = [m["id"] for m in measures]
    # Detect peaks in novelty (structural change points)
    peaks, _ = find_peaks(novelty, distance=min_length, prominence=prominence)
    boundaries = [0] + peaks.tolist() + [len(measure_ids)]
    phrase_objs = []
    for i in range(len(boundaries)-1):
        phrase_objs.append({
            "@type": "Phrase",
            "id": f"phrase_{i+1:03d}",
            "start_measure": measure_ids[boundaries[i]],
            "end_measure": measure_ids[boundaries[i+1]-1]
        })
    return phrase_objs, novelty, peaks, measure_ids

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python detect_phrases.py <input_elements.json> <output_phrases.json>")
        sys.exit(1)

    input_json = sys.argv[1]
    output_json = sys.argv[2]

    with open(input_json, "r") as f:
        data = json.load(f)

    measures = data.get("measures", [])
    phrases, novelty, peaks, measure_ids = detect_phrases(measures, min_length=6, prominence=3)

    # Save phrases
    with open(output_json, "w") as f:
        json.dump(phrases, f, indent=2)

    print(f"{len(phrases)} phrases written to {output_json}")

    # Figure
    plt.figure(figsize=(12, 5))
    plt.plot(novelty, label="Novelty Function")
    plt.scatter(peaks, novelty[peaks], color="red", label="Phrase Boundary (Peak)")
    for idx, peak in enumerate(peaks):
        plt.axvline(x=peak, color='red', linestyle='--', alpha=0.6)
    plt.title("Phrase Boundaries by Novelty Function")
    plt.xlabel("Measure Index")
    plt.ylabel("Novelty Score")
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_json.replace(".json", "_diagram.png"))
    plt.close()   
