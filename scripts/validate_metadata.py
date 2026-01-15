#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = [
    "README.MD",
    "CITATION.cff",
    "codemeta.json",
    ".zenodo.json",
    "ro-crate-metadata.json",
    "scripts/generate_ro_crate.py",
]

EXPECTED_TITLE = "CoastSat dashboard with LivePublication integration (fork)"
EXPECTED_ORCID = "0000-0001-8260-231X"
EXPECTED_LICENSE = "MIT"
UPSTREAM_URL = "https://github.com/UoA-eResearch/CoastSat"


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml(path: Path) -> Dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def normalise_orcid(value: str) -> str:
    return value.replace("https://orcid.org/", "").strip()


def as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def main() -> int:
    errors: List[str] = []

    for rel_path in REQUIRED_FILES:
        if not (REPO_ROOT / rel_path).exists():
            errors.append(f"Missing required file: {rel_path}")

    if errors:
        print("Validation failed (missing files).")
        for err in errors:
            print(f"- {err}")
        return 1

    citation = load_yaml(REPO_ROOT / "CITATION.cff")
    codemeta = load_json(REPO_ROOT / "codemeta.json")
    zenodo = load_json(REPO_ROOT / ".zenodo.json")
    rocrate = load_json(REPO_ROOT / "ro-crate-metadata.json")

    if citation.get("title") != EXPECTED_TITLE:
        errors.append("CITATION.cff title does not match expected title.")
    if codemeta.get("name") != EXPECTED_TITLE:
        errors.append("codemeta.json name does not match expected title.")
    if zenodo.get("title") != EXPECTED_TITLE:
        errors.append(".zenodo.json title does not match expected title.")

    citation_orcid = None
    if citation.get("authors"):
        citation_orcid = citation["authors"][0].get("orcid")
    codemeta_orcid = None
    if codemeta.get("author"):
        codemeta_orcid = codemeta["author"][0].get("@id")
    zenodo_orcid = None
    if zenodo.get("creators"):
        zenodo_orcid = zenodo["creators"][0].get("orcid")

    for label, value in [
        ("CITATION.cff", citation_orcid),
        ("codemeta.json", codemeta_orcid),
        (".zenodo.json", zenodo_orcid),
    ]:
        if value is None:
            errors.append(f"Missing ORCID in {label}.")
        elif normalise_orcid(value) != EXPECTED_ORCID:
            errors.append(f"ORCID mismatch in {label}.")

    if citation.get("license") != EXPECTED_LICENSE:
        errors.append("CITATION.cff license does not match expected license.")
    if codemeta.get("license") != EXPECTED_LICENSE:
        errors.append("codemeta.json license does not match expected license.")
    if zenodo.get("license") != EXPECTED_LICENSE:
        errors.append(".zenodo.json license does not match expected license.")

    for label, value in [
        ("CITATION.cff abstract", citation.get("abstract", "")),
        ("codemeta.json description", codemeta.get("description", "")),
        (".zenodo.json description", zenodo.get("description", "")),
    ]:
        if "..." in value:
            errors.append(f"Ellipsis placeholder found in {label}.")

    readme_text = (REPO_ROOT / "README.MD").read_text(encoding="utf-8")
    if "Fork provenance" not in readme_text:
        errors.append("README.MD missing 'Fork provenance' section.")

    related = zenodo.get("related_identifiers", [])
    has_upstream = False
    for item in related:
        if (
            item.get("relation") == "isDerivedFrom"
            and item.get("identifier") == UPSTREAM_URL
        ):
            has_upstream = True
            break
    if not has_upstream:
        errors.append(".zenodo.json missing upstream isDerivedFrom related identifier.")

    graph = rocrate.get("@graph", [])
    root_dataset = next((e for e in graph if e.get("@id") == "./"), None)
    if root_dataset is None:
        errors.append("ro-crate-metadata.json missing root dataset (@id './').")
    metadata_entity = next(
        (e for e in graph if e.get("@id") == "ro-crate-metadata.json"), None
    )
    if metadata_entity is None:
        errors.append("ro-crate-metadata.json missing metadata descriptor entity.")
    else:
        conforms = as_list(metadata_entity.get("conformsTo"))
        conforms_ids = {c.get("@id") for c in conforms if isinstance(c, dict)}
        if "https://w3id.org/ro/crate/1.1" not in conforms_ids:
            errors.append("RO-Crate metadata descriptor missing conformsTo RO-Crate 1.1.")

    if root_dataset:
        has_part = as_list(root_dataset.get("hasPart"))
        part_ids = set()
        for part in has_part:
            if isinstance(part, dict) and "@id" in part:
                part_ids.add(part["@id"])
            elif isinstance(part, str):
                part_ids.add(part)
        if ".zenodo.json" not in part_ids:
            errors.append("RO-Crate root dataset missing .zenodo.json in hasPart.")

    if errors:
        print("Validation FAILED.")
        for err in errors:
            print(f"- {err}")
    else:
        print("Validation PASSED.")

    print("\nMaintainer checklist:")
    print("- Identify files/modules where LivePublication crates are read and update README + RO-Crate hasPart list.")
    print("- Choose release tag/version for Zenodo archival snapshot.")
    print("- After DOI minted: backfill DOI into README, CITATION, CodeMeta, RO-Crate.")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
