#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from rocrate.model.contextentity import ContextEntity
from rocrate.rocrate import ROCrate


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    crate = ROCrate()

    root = crate.root_dataset
    root["name"] = "CoastSat dashboard with LivePublication integration (fork)"
    root["description"] = (
        "A fork of CoastSat that integrates LivePublication outputs into an interactive "
        "dashboard/map UI for thesis Chapter 6."
    )
    root["version"] = "1.0.0"
    root["license"] = "https://spdx.org/licenses/MIT"

    software = crate.add(
        ContextEntity(
            crate,
            "#software",
            {
                "@type": "SoftwareSourceCode",
                "name": "CoastSat dashboard with LivePublication integration (fork)",
                "description": (
                    "Modified CoastSat fork focused on LivePublication-aware dashboard integration "
                    "and visualisation."
                ),
                "codeRepository": "https://github.com/GusEllerm/CoastSat",
                "version": "1.0.0",
                "license": "https://spdx.org/licenses/MIT",
                "author": {
                    "@type": "Person",
                    "@id": "https://orcid.org/0000-0001-8260-231X",
                    "givenName": "Augustus",
                    "familyName": "Ellerm",
                },
                "isBasedOn": "https://github.com/UoA-eResearch/CoastSat",
            },
        )
    )
    root["mainEntity"] = {"@id": software.id}

    key_files = [
        "README.MD",
        "LICENSE",
        "requirements.txt",
        "index.html",
        "new_sites.html",
        "batch_process_NZ.py",
        "update.sh",
        "micro_integration/glify_micropublication.js",
        "micro_integration/glify_micropublication.css",
        "micro_integration/micropub_watcher.py",
        "micro_integration/micropub_templates/base_template.smd",
        "CITATION.cff",
        "codemeta.json",
        ".zenodo.json",
        "scripts/generate_ro_crate.py",
        "scripts/validate_metadata.py",
    ]

    for rel_path in sorted(key_files):
        file_path = repo_root / rel_path
        if not file_path.exists():
            continue
        crate.add_file(
            file_path.as_posix(),
            dest_path=rel_path,
            properties={"name": rel_path},
        )

    crate.metadata["conformsTo"] = {"@id": "https://w3id.org/ro/crate/1.1"}

    with tempfile.TemporaryDirectory() as tmp_dir:
        crate.write(tmp_dir)
        generated = Path(tmp_dir) / "ro-crate-metadata.json"
        if not generated.exists():
            raise FileNotFoundError("ro-crate-metadata.json not generated")
        shutil.copyfile(generated, repo_root / "ro-crate-metadata.json")

    output_path = repo_root / "ro-crate-metadata.json"
    data = json.loads(output_path.read_text(encoding="utf-8"))
    output_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
