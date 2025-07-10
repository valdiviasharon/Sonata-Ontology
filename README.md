# Sonata-Ontology
This repository provides a complete pipeline for converting Beethoven piano sonata scores in MusicXML format into a rich RDF (Resource Description Framework) representation, suitable for semantic analysis, knowledge extraction, and ontological modeling of musical structure. The pipeline processes raw scores through a series of Python scripts, extracting metadata, detailed musical elements, structural information, and exporting everything as RDF/Turtle files using a custom ontology named SONATA ONTOLOGY.

## Requirements

- Python 3.8+
- [music21](https://web.mit.edu/music21/)  
- [rdflib](https://rdflib.readthedocs.io/)

Install dependencies with:
```bash
pip install -r requirements.txt
```
## Processing Pipeline

All steps are automated by the `process_sonata.sh` Bash script. The pipeline for each MusicXML score is as follows:

1. **Extract Metadata**  
   Script: `metadata.py`  
   Reads the MusicXML file and generates basic metadata: title, instrument, total measures.  
   ```bash
   python metadata.py <input_xml> <output_metadata.json>
   ```

2. **Extract Elements**  
   Script: `xml_to_elements_json.py`  
   Extracts notes, rests, chords, measures, keys, dynamics, clefs, tempos, time signatures, and more. Also enriches metadata with global key and tonality analysis.  
   ```bash
   python xml_to_elements_json.py <input_xml> <metadata_json> <output_elements.json>
   ```

3. **Detect Phrases (Structure Analysis)**  
   Script: `structure_analysis.py`  
   Detects musical phrase boundaries using a novelty function (based on changes in musical content per measure) and exports a list of phrases.  
   ```bash
   python structure_analysis.py <elements.json> <phrases.json>
   ```

4. **Export to RDF (Turtle)**  
   Script: `json_to_rdf.py`  
   Converts the extracted metadata, elements, and phrase structure into RDF/Turtle format using a custom namespace.  
   ```bash
   python json_to_rdf.py <json_dir> <namespace_prefix_url> <output.ttl>
   ```

## Automated Processing

To process all XML files in bulk, use:
```bash
bash process_sonata.sh
```
This will:
- Create all necessary output folders.
- Process every XML file, extracting data and exporting one `.ttl` RDF file per score into the `TTL/` directory.
- The namespace prefix used is customizable in the script.

## Scripts Reference

### `metadata.py`
Extracts basic metadata from an XML score, such as title, instrument, and number of measures.

### `xml_to_elements_json.py`
Performs detailed analysis of the score, including:
- All measures, notes, chords, rests
- Structural and expressive elements (dynamics, articulations, key changes, time signatures)
- Computes and registers global key and tonality

### `structure_analysis.py`
Segments the score into musical phrases based on novelty detection (change points in the music), outputting their locations as a list.

### `json_to_rdf.py`
Integrates all the extracted data (metadata, elements, structure) and serializes it into an RDF graph using the [rdflib](https://rdflib.readthedocs.io/) library and a custom ontology.

### `process_sonata.sh`
Runs the complete pipeline for all XML files, generating the final RDF output for each piece.

## Output

For each score, the pipeline produces:
- `metadata.json` — Basic metadata
- `elements.json` — Full musical structure and content
- `phrases.json` — Locations of musical phrases
- `<score_name>.ttl` — RDF/Turtle representation with all data, suitable for SPARQL queries and ontological analysis

## Customization

- **Namespace:**  
  Change the `PREFIX_SO` variable in `process_sonata.sh` to set your own ontology URL prefix.
- **Input/output paths:**  
  Modify the paths at the top of the script for custom datasets.
