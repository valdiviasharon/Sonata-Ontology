# Sonata Ontology – Processing and Instantiation Pipeline

This repository contains the processing pipeline and resources used to instantiate **Sonata Ontology** from a corpus of piano sonatas encoded in `MusicXML`.

**Sonata Ontology** is a domain ontology designed to represent, in a structured and interoperable way:

- Work-level metadata (title, composer, opus, etc.),
- Formal structure (movements, sections, measures),
- Symbolic notation (notes, rests, durations, clefs, key signatures, time signatures, tempi),
- Harmonic and melodic information,
- Expressive markings (dynamics, articulations),
- And a dedicated **Technical Complexity Profile**:
  - local complexity by measure (Local Complexity Index, LCI),
  - and global complexity by movement (Global Complexity Index, GCI).

The pipeline in this repository converts raw `MusicXML` scores into enriched **RDF graphs** that conform to Sonata Ontology, passing through an intermediate **JSON-LD** representation.

---

## High-level Workflow

At a high level, the processing workflow is:

1. **Input**: a set of piano sonatas in `MusicXML` format.
2. **Incremental enrichment in JSON-LD**:  
   Several Python scripts read each `MusicXML` file and progressively enrich a corresponding `JSON-LD` file with:
   - metadata,
   - structural information,
   - musical notation,
   - expressive markings,
   - and technical complexity metrics.
3. **Export to RDF/Turtle**:  
   Once the JSON-LD representation is complete, it is converted into `TTL` (Turtle) files, which can be loaded into a triplestore (e.g., GraphDB) and queried with SPARQL.

The repository also includes **example JSON-LD and TTL files**, illustrating the final structure of the instantiated data for a sample sonata.

---

## Main Components

### Input Scores

- **MusicXML scores directory**  
  A folder containing piano sonatas in `*.xml` format (e.g., the Beethoven Piano Sonata Dataset).
  Each file corresponds to a single work (one sonata or one movement, depending on the encoding).

---

### JSON-LD Enrichment Scripts

All JSON-LD files are stored in a directory such as `JSON_LD/`.  
Each Python script below is responsible for one “layer” of information:

#### `extract_metadata.py`

- Reads a `MusicXML` file.
- Creates or updates a JSON-LD document for the score.
- Adds **work-level metadata**, such as:
  - title,
  - composer name,
  - opus number or catalogue identifier,
  - high-level work identifiers.
- Instantiates the main `so:Sonata` and its relationship to `mo:MusicalWork`.

#### `extract_structure.py`

- Enriches the JSON-LD file with **formal structure**:
  - movements (instances of `so:SonataMovement`),
  - measures (instances of `mso:Measure`),
  - links between work, movements and measures.
- Ensures that each measure is uniquely identified and associated with its movement.

#### `extract_music_notation.py`

- Adds **symbolic notation** to the JSON-LD graph:
  - notes and rests as symbolic events,
  - durations (note types and their values),
  - clefs, key signatures, and time signatures,
  - tempi associated to measures where relevant.
- Connects these elements with the appropriate measures and staves, following the structure defined in Sonata Ontology and related vocabularies (e.g., MSO, MTO, HaMSE).

#### `extract_expression.py`

- Focuses on **expressive information**:
  - dynamic markings (e.g., `p`, `f`, `ff`, `sf`, `sfp`, etc.),
  - articulations (in particular, `staccato` in the current version).
- Associates each expressive marking with the corresponding symbolic event and measure.
- Populates classes such as `so:LoudnessDynamic` and `so:Staccato`, and their linking properties.

#### `extract_technical_complexity_profile.py`

- Computes and encodes the **Technical Complexity Profile** for each measure and movement.
- For every `mso:Measure`, it calculates raw metrics such as:
  - `so:noteCount` (number of notes),
  - `so:measureAccidentalCount` (number of accidentals),
  - `so:subdivisionIndex` (rhythmic subdivision relative to the beat),
  - `so:minNoteValue` (smallest note value in the measure),
  - `so:dynamicCount` (number of dynamic markings),
  - `so:articulationCount` (number of relevant articulations).
- These metrics are normalized and combined into a **Local Complexity Index** (`so:LCIvalue`), stored in a `so:LocalComplexityIndex` instance linked to each measure.
- For each `so:SonataMovement`, it averages the LCIs across its measures to obtain a **Global Complexity Index** (`so:globalComplexityIndex`), encapsulated in a `so:GlobalComplexityProfile` instance.

The result of running all these scripts is an enriched JSON-LD graph for each score, containing both structural/expressive information and computed complexity indices.

---

### RDF Export

#### `jsonld_to_ttl.py`

- Reads all `.jsonld` files from the `JSON_LD/` directory.
- Uses `rdflib` (or equivalent) to parse JSON-LD into an RDF graph.
- Serializes each graph as Turtle (`.ttl`) into the `TTL/` directory.
- The produced TTL files are ready to be:
  - loaded into GraphDB (or another RDF store),
  - queried with SPARQL,
  - and used for analysis (e.g., identifying the most complex measures or comparing movements by difficulty).

---

## Example Files

The repository includes:

- An **example JSON-LD file** showing the enriched representation of a processed sonata (including metadata, structure, notation, expression and technical complexity metrics).
- An **example TTL file** showing the final RDF/Turtle encoding of the same work.

These examples can be used as:

- a reference to understand how Sonata Ontology is instantiated,
- a template for building SPARQL queries,
- and a sanity check when modifying or extending the pipeline.

---

## Installation and Basic Usage

1. **Create and activate a virtual environment** (recommended):

   ```bash
   
   python3 -m venv venv_sonata
   source venv_sonata/bin/activate

2. **Install dependencies**:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
3. **Run the pipeline** (conceptually):

   - For each `MusicXML` file:
     1. Run `extract_metadata.py`.
     2. Run `extract_structure.py`.
     3. Run `extract_music_notation.py`.
     4. Run `extract_expression.py`.
     5. Run `extract_technical_complexity_profile.py`.
   - Then call `jsonld_to_ttl.py` to convert all `JSON_LD/*.jsonld` into `TTL/*.ttl`.

A convenience shell script (e.g., `process_sonata.sh`) is provided to orchestrate these steps in batch over a directory of scores, but the core logic resides in the Python scripts described above.

---

## Using the Resulting RDF Data

Once the TTL files are generated, they can be imported into a triplestore such as **GraphDB**. From there, Sonata Ontology supports:

- Queries about **global information** (key, tempi, time signatures, number of measures),
- Queries about **local technical difficulty** (e.g., measures with highest LCI, measures with many accidentals or dense rhythms),
- Queries about **expressivity** (distribution of dynamics and articulations),
- And combined views that relate formal structure, notation, expression and complexity.

This RDF representation provides a reproducible, structured and extensible basis for further research, pedagogical tools, and interactive applications built on top of Sonata Ontology.
