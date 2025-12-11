from __future__ import annotations
import os
import sys
from typing import Optional

from rdflib import Graph

JSONLD_DIR = "JSON_LD"
TTL_DIR = "TTL"


def get_base_dir() -> str:
    """
    Return the base directory of this script.
    """
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except NameError:
        # Fallback for environments where __file__ is not defined
        return os.getcwd()


def jsonld_to_ttl(input_path: str, output_path: str) -> str:
    """
    Load a JSON-LD file into an RDF graph and serialize it as Turtle (.ttl).

    Parameters
    ----------
    input_path : str
        Path to the JSON-LD file.
    output_path : str
        Path to the Turtle file to write.

    Returns
    -------
    str
        The path of the written Turtle file.
    """
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"Input JSON-LD file not found: {input_path}")

    # Create RDFLib graph and parse JSON-LD
    g = Graph()
    # The 'json-ld' format is provided by rdflib-jsonld plugin
    g.parse(input_path, format="json-ld")

    # Serialize graph as Turtle
    g.serialize(destination=output_path, format="turtle")

    return output_path


def batch_convert_jsonld_to_ttl(jsonld_folder: str, ttl_folder: str) -> None:
    """
    Convert all .jsonld files found in jsonld_folder to .ttl,
    writing each Turtle file into ttl_folder (same base filename).

    Parameters
    ----------
    jsonld_folder : str
        Folder where JSON-LD files are located.
    ttl_folder : str
        Folder where Turtle files will be written.
    """
    if not os.path.isdir(jsonld_folder):
        raise NotADirectoryError(f"JSON-LD folder not found: {jsonld_folder}")

    # Ensure TTL folder exists
    os.makedirs(ttl_folder, exist_ok=True)

    files = sorted(
        f for f in os.listdir(jsonld_folder) if f.lower().endswith(".jsonld")
    )

    if not files:
        print(f"No .jsonld files found in folder: {jsonld_folder}")
        return

    print(f"Found {len(files)} JSON-LD files in: {jsonld_folder}")
    for fname in files:
        in_path = os.path.join(jsonld_folder, fname)

        base_name, _ = os.path.splitext(fname)
        out_fname = base_name + ".ttl"
        out_path = os.path.join(ttl_folder, out_fname)

        print(f"Converting: {fname} -> {out_fname}")
        ttl_path = jsonld_to_ttl(in_path, out_path)
        print(f"  OK: {ttl_path}")


if __name__ == "__main__":
    """
    Usage:

      python batch_jsonld_to_ttl.py
        -> uses default JSON_LD and TTL folders next to this script

      python batch_jsonld_to_ttl.py path/to/JSON_LD path/to/TTL
        -> uses the provided folders instead
    """
    base_dir = get_base_dir()

    if len(sys.argv) == 1:
        jsonld_dir = os.path.join(base_dir, JSONLD_DIR)
        ttl_dir = os.path.join(base_dir, TTL_DIR)
    elif len(sys.argv) == 3:
        jsonld_dir = sys.argv[1]
        ttl_dir = sys.argv[2]
    else:
        sys.exit(1)

    batch_convert_jsonld_to_ttl(jsonld_dir, ttl_dir)
