import sys
import os
import json
from rdflib import Graph, Namespace, Literal
from rdflib.namespace import RDF, XSD

def convert_json_to_rdf(json_dir, ns_str, output_ttl):
    # Use the folder name as obra prefix
    obra_prefix = os.path.basename(os.path.normpath(json_dir)) + "_"
    EX = Namespace(ns_str)
    g = Graph()
    g.bind("", EX)

    # Paths
    metadata_file = os.path.join(json_dir, "metadata.json")
    elements_file = os.path.join(json_dir, "elements.json")
    phrases_file = os.path.join(json_dir, "phrases.json")

    # -- 1. METADATA --
    with open(metadata_file, encoding="utf-8") as f:
        meta = json.load(f)
    meta_uri = EX[f"{obra_prefix}metadata"]
    g.add((meta_uri, RDF.type, EX.Metadata))
    g.add((meta_uri, EX.title, Literal(meta["title"])))
    g.add((meta_uri, EX.instrument, Literal(meta["instrument"])))
    g.add((meta_uri, EX.total_measures, Literal(meta["total_measures"], datatype=XSD.integer)))
    g.add((meta_uri, EX.tonality, Literal(meta["tonality"])))
    g.add((meta_uri, EX.global_key, Literal(meta["global_key"])))

    # -- 2. PHRASES --
    with open(phrases_file, encoding="utf-8") as f:
        phrases = json.load(f)
    for ph in phrases:
        ph_uri = EX[f"{obra_prefix}{ph['id']}"]
        g.add((ph_uri, RDF.type, EX.Phrase))
        g.add((ph_uri, EX.start_measure, Literal(ph["start_measure"])))
        g.add((ph_uri, EX.end_measure, Literal(ph["end_measure"])))

    # -- 3. ELEMENTS --
    with open(elements_file, encoding="utf-8") as f:
        el = json.load(f)

    # Measures
    for m in el["measures"]:
        m_uri = EX[f"{obra_prefix}{m['id']}"]
        g.add((m_uri, RDF.type, EX.Measure))
        g.add((m_uri, EX.number, Literal(m["number"], datatype=XSD.integer)))
        for nid in m.get("notes", []):
            g.add((m_uri, EX.hasNote, EX[f"{obra_prefix}{nid}"]))
        for rid in m.get("rests", []):
            g.add((m_uri, EX.hasRest, EX[f"{obra_prefix}{rid}"]))
        for cid in m.get("chords", []):
            g.add((m_uri, EX.hasChord, EX[f"{obra_prefix}{cid}"]))
        for did in m.get("dynamics", []):
            g.add((m_uri, EX.hasDynamic, EX[f"{obra_prefix}{did}"]))

    # Notes
    for n in el["notes"]:
        n_uri = EX[f"{obra_prefix}{n['id']}"]
        g.add((n_uri, RDF.type, EX.Note))
        g.add((n_uri, EX.part, Literal(n["part"])))
        g.add((n_uri, EX.measure, Literal(n["measure"])))
        g.add((n_uri, EX.offset, Literal(n["offset"], datatype=XSD.float)))
        g.add((n_uri, EX.pitch, Literal(n["pitch"])))
        g.add((n_uri, EX.octave, Literal(n["octave"], datatype=XSD.integer)))
        g.add((n_uri, EX.duration, Literal(n["duration"])))
        if n.get("accidental"): g.add((n_uri, EX.accidental, Literal(n["accidental"])))
        if n.get("dynamic"): g.add((n_uri, EX.dynamic, Literal(n["dynamic"])))
        if n.get("articulation"): g.add((n_uri, EX.articulation, Literal(n["articulation"])))
        if n.get("tie"): g.add((n_uri, EX.tie, Literal(n["tie"])))
        if n.get("inChord"): g.add((n_uri, EX.inChord, EX[f"{obra_prefix}{n['inChord']}"]))
        if n.get("clef"): g.add((n_uri, EX.clef, EX[f"{obra_prefix}{n['clef']}"]))

    # Rests
    for r in el["rests"]:
        r_uri = EX[f"{obra_prefix}{r['id']}"]
        g.add((r_uri, RDF.type, EX.Rest))
        g.add((r_uri, EX.part, Literal(r["part"])))
        g.add((r_uri, EX.measure, Literal(r["measure"])))
        g.add((r_uri, EX.offset, Literal(r["offset"], datatype=XSD.float)))
        g.add((r_uri, EX.duration, Literal(r["duration"])))
        if r.get("clef"): g.add((r_uri, EX.clef, EX[f"{obra_prefix}{n['clef']}"]))

    # Chords
    for c in el["chords"]:
        c_uri = EX[f"{obra_prefix}{c['id']}"]
        g.add((c_uri, RDF.type, EX.Chord))
        g.add((c_uri, EX.measure, Literal(c["measure"])))
        g.add((c_uri, EX.offset, Literal(c["offset"], datatype=XSD.float)))
        for nid in c.get("hasNote", []):
            g.add((c_uri, EX.hasNote, EX[f"{obra_prefix}{nid}"]))
        if c.get("hasRomanNumeral"):
            g.add((c_uri, EX.hasRomanNumeral, EX[f"{obra_prefix}{c['hasRomanNumeral']}"]))
        if c.get("inversion"):
            g.add((c_uri, EX.inversion, Literal(c["inversion"], datatype=XSD.integer)))
        if c.get("bass"):
            g.add((c_uri, EX.bass, Literal(c["bass"])))
        if c.get("clef"):
            g.add((c_uri, EX.clef, EX[f"{obra_prefix}{n['clef']}"]))
        if c.get("symbol"):
            g.add((c_uri, EX.symbol, Literal(c["symbol"])))
        if c.get("commonName"):
            g.add((c_uri, EX.commonName, Literal(c["commonName"])))
        if c.get("pitchedCommonName"):
            g.add((c_uri, EX.pitchedCommonName, Literal(c["pitchedCommonName"])))
        if c.get("roman_figure"):
            g.add((c_uri, EX.figure, Literal(c["roman_figure"])))

    # Dynamics
    for d in el["dynamics"]:
        d_uri = EX[f"{obra_prefix}{d['id']}"]
        g.add((d_uri, RDF.type, EX.Dynamic))
        g.add((d_uri, EX.value, Literal(d["value"])))
        g.add((d_uri, EX.offset, Literal(d["offset"], datatype=XSD.float)))

    # Clefs
    for cl in el["clefs"]:
        cl_uri = EX[f"{obra_prefix}{cl['id']}"]
        g.add((cl_uri, RDF.type, EX.Clef))
        g.add((cl_uri, EX.sign, Literal(cl["sign"])))
        g.add((cl_uri, EX.line, Literal(cl["line"], datatype=XSD.integer)))

    # Tempos
    for t in el["tempos"]:
        t_uri = EX[f"{obra_prefix}{t['id']}"]
        g.add((t_uri, RDF.type, EX.Tempo))
        if t.get("bpm"): g.add((t_uri, EX.bpm, Literal(t["bpm"], datatype=XSD.float)))
        if t.get("text"): g.add((t_uri, EX.text, Literal(t["text"])))
        if t.get("measure_start"): g.add((t_uri, EX.measure, Literal(t["measure_start"])))

    # Key Signatures
    for k in el["key_signatures"]:
        k_uri = EX[f"{obra_prefix}{k['id']}"]
        g.add((k_uri, RDF.type, EX.KeySignature))
        if "fifths" in k: g.add((k_uri, EX.fifths, Literal(k["fifths"], datatype=XSD.integer)))
        if "mode" in k and k["mode"]: g.add((k_uri, EX.mode, Literal(k["mode"])))
        if "tonality" in k and k["tonality"]: g.add((k_uri, EX.tonality, Literal(k["tonality"])))
        if "measure_start" in k: g.add((k_uri, EX.measure, Literal(k["measure_start"])))

    # Time Signatures
    for ts in el["time_signatures"]:
        ts_uri = EX[f"{obra_prefix}{ts['id']}"]
        g.add((ts_uri, RDF.type, EX.TimeSignature))
        g.add((ts_uri, EX.numerator, Literal(ts["numerator"], datatype=XSD.integer)))
        g.add((ts_uri, EX.denominator, Literal(ts["denominator"], datatype=XSD.integer)))
        if ts.get("symbol"): g.add((ts_uri, EX.symbol, Literal(ts["symbol"])))
        if ts.get("measure_start"): g.add((ts_uri, EX.measure, Literal(ts["measure_start"])))

    # Keys (global)
    for k in el["keys"]:
        k_uri = EX[f"{obra_prefix}{k['id']}"]
        g.add((k_uri, RDF.type, EX.Key))
        if "tonic" in k: g.add((k_uri, EX.tonic, Literal(k["tonic"])))
        if "mode" in k: g.add((k_uri, EX.mode, Literal(k["mode"])))

    # Roman Numerals
    for r in el["romans"]:
        r_uri = EX[f"{obra_prefix}{r['id']}"]
        g.add((r_uri, RDF.type, EX.RomanNumeral))
        if "figure" in r: g.add((r_uri, EX.figure, Literal(r["figure"])))
        if "key" in r: g.add((r_uri, EX.key, Literal(r["key"])))
        if "mode" in r: g.add((r_uri, EX.mode, Literal(r["mode"])))
        if "inversion" in r: g.add((r_uri, EX.inversion, Literal(r["inversion"], datatype=XSD.integer)))
        if "bass" in r: g.add((r_uri, EX.bass, Literal(r["bass"])))

    # Export to TTL
    g.serialize(destination=output_ttl, format="turtle")
    print(f"[OK] {output_ttl} (prefix: {ns_str})")

def main():
    if len(sys.argv) < 4:
        print("Usage: python json_to_rdf.py <json_dir> <namespace_prefix_url> <output_ttl>")
        sys.exit(1)
    json_dir = sys.argv[1]
    ns_str = sys.argv[2]
    output_ttl = sys.argv[3]
    convert_json_to_rdf(json_dir, ns_str, output_ttl)

if __name__ == "__main__":
    main()
