from rocrate.rocrate import ROCrate
from rocrate.model.contextentity import ContextEntity
import tempfile
import shutil
import subprocess
import argparse
from pathlib import Path
import json
import os

def prepare_temp_directory(template_path, site_id):
    temp_dir = tempfile.TemporaryDirectory()
    temp_dir_path = Path(temp_dir.name)

    shutil.copy(template_path, temp_dir_path / "shoreline_publication.smd")
    
    # Write the simple site_id data to data.json in the temp directory
    data_json_path = temp_dir_path / "data.json"
    site_data = {"id": site_id}
    with open(data_json_path, "w", encoding="utf-8") as f:
        json.dump(site_data, f, ensure_ascii=False, indent=2)

    # Determine the crate root based on where we're running from
    script_parent = Path(__file__).parent
    if script_parent.name.endswith("publication.crate"):
        # Running from inside publication.crate
        crate_root = script_parent
    elif script_parent.name == "src":
        # Running from src directory (new structure)
        crate_root = script_parent.parent / "publication.crate"
    else:
        # Running from parent directory (legacy)
        crate_root = script_parent / "publication.crate"
    
    # Add top-level ro-crate-metadata.json
    top_level_manifest = crate_root / "ro-crate-metadata.json"
    if top_level_manifest.exists():
        shutil.copy(top_level_manifest, temp_dir_path / "ro-crate-metadata.json")

    # Recursively find and copy all nested ro-crate-metadata.json files
    for dirpath, dirnames, filenames in os.walk(crate_root):
        if "ro-crate-metadata.json" in filenames:
            full_manifest_path = Path(dirpath) / "ro-crate-metadata.json"
            relative_manifest_path = full_manifest_path.relative_to(crate_root)
            target_manifest_path = temp_dir_path / relative_manifest_path

            # Ensure parent directories exist
            target_manifest_path.parent.mkdir(parents=True, exist_ok=True)
            print(f"Copying {full_manifest_path} to {target_manifest_path}")
            shutil.copy(full_manifest_path, target_manifest_path)

    return temp_dir, temp_dir_path

def evaluate_shorelinepublication(temp_dir_path):
    smd_files = list(temp_dir_path.glob("*.smd"))
    if not smd_files:
        raise FileNotFoundError("No .smd template file found in temporary directory")
    template = smd_files[0]

    print(f"Template file: {template}")
    
    # Debug: Show template content
    with open(template, 'r') as f:
        content = f.read()
    print(f"Template content: '{content}'")

    data_json = temp_dir_path / "data.json"
    if not data_json.exists():
        raise FileNotFoundError(f"data.json not found in {temp_dir_path}")
    
    # Debug: Show data.json content
    with open(data_json, 'r') as f:
        data_content = f.read()
    print(f"Data.json content: {data_content}")
    
    # Run the stencila pipeline to generate the shoreline publication
    try:
        print("🧪 Running Stencila pipeline...")
        # Ensure pandas is installed in the subprocess environment
        subprocess.run(
            ["python", "-m", "pip", "install", "pandas", "rocrate"],
            cwd=temp_dir_path,
            check=True
        )
        
        dnf_json = f"{temp_dir_path}/DNF.json"
        print(f"Converting {template} to {dnf_json}")
        subprocess.run(["stencila", "convert", template, dnf_json], check=True)
        
        # Debug: Check DNF.json content
        if os.path.exists(dnf_json):
            print("✅ DNF.json created successfully")
            with open(dnf_json, 'r') as f:
                dnf_content = json.load(f)
            print(f"DNF content type: {dnf_content.get('type')}")
            print(f"DNF content length: {len(dnf_content.get('content', []))}")
        
        dnf_eval_json = f"{temp_dir_path}/DNF_eval.json"
        print(f"Rendering {dnf_json} to {dnf_eval_json}")
        subprocess.run(["stencila", "render", dnf_json, dnf_eval_json, "--force-all", "--pretty"], check=True)
        
        final_path = f"{temp_dir_path}/shorelinepublication.html"
        print(f"Converting {dnf_eval_json} to {final_path}")
        subprocess.run(["stencila", "convert", dnf_eval_json, final_path, "--pretty"], check=True)
        
        return final_path if os.path.exists(final_path) else None
    except subprocess.CalledProcessError as e:
        print(f"❌ Error in Stencila pipeline: {e}")
        return None

def get_template_path(crate_path):
    """
    Loads the RO-Crate manifest and locates the template file based on type.
    """
    crate = ROCrate(crate_path)
    for entity in crate.get_entities():
        entity_type = entity.properties().get("@type", [])
        if isinstance(entity_type, str):
            entity_type = [entity_type]
        if all(t in entity_type for t in ["File", "SoftwareSourceCode", "SoftwareApplication"]):
            return Path(crate_path) / entity.id
    raise FileNotFoundError("Template with specified type not found in publication.crate")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a shoreline publication for a given site ID.")
    parser.add_argument("site_id", help="The site ID to generate the shoreline publication for.")
    parser.add_argument("--output", help="Output file path for the generated shoreline publication HTML.", default="shorelinepublication.html")
    args = parser.parse_args()

    print("🔍 Getting template path...")
    
    # Detect if we're running from inside publication.crate or from src directory
    current_dir = Path(__file__).parent
    if current_dir.name.endswith("publication.crate"):
        # Running from inside publication.crate
        crate_path = current_dir
        print(f"📁 Running from inside publication.crate: {crate_path}")
    elif current_dir.name == "src":
        # Running from src directory (new structure)
        crate_path = current_dir.parent / "publication.crate"
        print(f"📁 Running from src directory, using: {crate_path}")
    else:
        # Running from parent directory (legacy)
        crate_path = current_dir / "publication.crate"
        print(f"📁 Running from parent directory, using: {crate_path}")
    
    template_path = get_template_path(crate_path)
    print(f"Template path: {template_path}")

    print(f"🔍 Preparing publication for site ID: {args.site_id}")

    temp_dir_obj, temp_dir_path = prepare_temp_directory(template_path, args.site_id)
    publication_path = evaluate_shorelinepublication(temp_dir_path)
    if publication_path:
        output_path = args.output if hasattr(args, "output") else "shorelinepublication.html"
        shutil.copy(publication_path, output_path)
        print(f"Shoreline publication written to {output_path}")
    else:
        print("Failed to generate shoreline publication.")

    temp_dir_obj.cleanup()  # Clean up the temporary directory
    print("Temporary directory cleaned up.")
