from rocrate.rocrate import ROCrate
from rocrate.model.contextentity import ContextEntity
import tempfile
import shutil
import subprocess
import argparse
from pathlib import Path
import requests
import json
import os
import re

def convert_to_raw_url(github_url: str) -> str:
    """
    Converts a GitHub blob URL to a raw.githubusercontent URL.
    """
    match = re.match(r"https://github\.com/(.+)/blob/([a-f0-9]+)/(.+)", github_url)
    if not match:
        raise ValueError("Invalid GitHub blob URL format.")
    user_repo, commit_hash, path = match.groups()
    return f"https://raw.githubusercontent.com/{user_repo}/{commit_hash}/{path}"

def query_by_link(crate, prop, target_id, match_substring=False):
    """
    Return entities (dict or ContextEntity) whose `prop` links to `target_id`.
    If `match_substring` is True, will return entities whose link includes `target_id` as a substring.
    """
    is_rocrate = hasattr(crate, "get_entities")
    entities = crate.get_entities() if is_rocrate else crate.get("@graph", [])
    out = []

    for e in entities:
        val = (e.properties().get(prop) if is_rocrate else e.get(prop))
        if val is None:
            continue
        vals = [val] if not isinstance(val, list) else val

        ids = [
            (x.id if hasattr(x, "id") else x.get("@id") if isinstance(x, dict) else x)
            for x in vals
        ]
        if match_substring:
            if any(target_id in _id for _id in ids if _id is not None and isinstance(_id, str) and target_id is not None):
                out.append(e)
        else:
            if target_id in ids:
                out.append(e)
    return out

def prepare_temp_directory(template_path, transect_id):
    temp_dir = tempfile.TemporaryDirectory()
    temp_dir_path = Path(temp_dir.name)

    shutil.copy(template_path, temp_dir_path / "micropublication.smd")
    
    # Get transect data and write it to data.json in the temp directory
    data_json_path = temp_dir_path / "data.json"
    
    # Get the crate and data paths
    script_dir = Path(__file__).parent
    if script_dir.name == "src":
        crate_path = script_dir.parent / "publication.crate"
    else:
        crate_path = script_dir
    
    data_path = get_data_path(crate_path)
    data = download_data_file(data_path)
    transect_feature = get_transect_by_id(data, transect_id)
    transect_data = transect_feature.get("properties", {})
    
    with open(data_json_path, "w", encoding="utf-8") as f:
        json.dump(transect_data, f, ensure_ascii=False, indent=2)

    # Write the coordinates to coordinates.json in the temp directory
    coordinates_json_path = temp_dir_path / "coordinates.json"
    coordinates = transect_feature.get("geometry")
    if coordinates and coordinates.get("coordinates"):
        # Use the first coordinate pair from the LineString
        coord_pair = coordinates["coordinates"][0]  # [lon, lat]
        coordinates_data = {"coordinates": [coord_pair]}
        with open(coordinates_json_path, "w", encoding="utf-8") as f:
            json.dump(coordinates_data, f, ensure_ascii=False, indent=2)

    # Determine the crate root based on where we're running from
    script_dir = Path(__file__).parent
    if script_dir.name == "src":
        # Running from source directory
        crate_root = script_dir.parent / "publication.crate"
    else:
        # Running from crate directory
        crate_root = script_dir
    
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

def evaluate_micropublication(temp_dir_path):
    smd_files = list(temp_dir_path.glob("*.smd"))
    if not smd_files:
        raise FileNotFoundError("No .smd template file found in temporary directory")
    template = smd_files[0]

    print(f"Template file: {template}")

    data_json = temp_dir_path / "data.json"
    if not data_json.exists():
        raise FileNotFoundError(f"data.json not found in {temp_dir_path}")
    
    # Run the stencila pipeline to generate the micropublication
    try:
        print("🧪 Running Stencila pipeline...")
        # Ensure pandas is installed in the subprocess environment
        subprocess.run(
            ["python", "-m", "pip", "install", "pandas", "rocrate"],
            cwd=temp_dir_path,
            check=True
        )
        
        dnf_json = f"{temp_dir_path}/DNF.json"
        subprocess.run(["stencila", "convert", template, dnf_json], check=True)
        
        dnf_eval_json = f"{temp_dir_path}/DNF_eval.json"
        subprocess.run(["stencila", "render", dnf_json, dnf_eval_json, "--force-all", "--pretty"], check=True)
        
        final_path = f"{temp_dir_path}/micropublication.html"
        subprocess.run(["stencila", "convert", dnf_eval_json, final_path, "--pretty"], check=True)
        
        # Return both the final HTML and the evaluated DNF document
        html_exists = os.path.exists(final_path)
        dnf_eval_exists = os.path.exists(dnf_eval_json)
        
        if html_exists and dnf_eval_exists:
            return final_path, dnf_eval_json
        elif html_exists:
            return final_path, None
        else:
            return None, None
    except subprocess.CalledProcessError as e:
        print(f"❌ Error in Stencila pipeline: {e}")
        return None, None

def populate_crate_with_generated_content(crate_path, generated_html_path, transect_id, dnf_eval_path=None):
    """
    Populate the publication crate with generated content and update metadata.
    
    Args:
        crate_path: Path to the publication.crate directory
        generated_html_path: Path to the generated HTML file
        transect_id: The transect ID used for generation
        dnf_eval_path: Optional path to the DNF evaluated document
    """
    print("🔧 Populating publication crate with generated content...")
    
    # Load the existing crate
    crate = ROCrate(crate_path)
    
    # Copy the generated HTML file into the crate directory
    # The generated file is always named micropublication.html
    html_filename = "micropublication.html"
    html_target_path = Path(crate_path) / html_filename
    
    # Remove existing file if it exists to avoid permission issues
    if html_target_path.exists():
        html_target_path.unlink()
    
    shutil.copy(generated_html_path, html_target_path)
    print(f"📄 Copied generated HTML to {html_target_path}")
    
    # Add the HTML file to the crate metadata
    html_file = crate.add_file(html_filename, properties={
        "@type": ["File", "CreativeWork"],
        "name": f"Micropublication for {transect_id}",
        "description": f"Generated micropublication for transect {transect_id}",
        "encodingFormat": "text/html"
    })
    
    # Handle DNF evaluated document if provided
    dnf_eval_file = None
    if dnf_eval_path and os.path.exists(dnf_eval_path):
        dnf_eval_filename = "DNF_eval.json"
        dnf_eval_target_path = Path(crate_path) / dnf_eval_filename
        
        # Remove existing file if it exists to avoid permission issues
        if dnf_eval_target_path.exists():
            dnf_eval_target_path.unlink()
        
        # First copy the file to the crate directory
        shutil.copy(dnf_eval_path, dnf_eval_target_path)
        print(f"📄 Copied DNF evaluated document to {dnf_eval_target_path}")
        
        # Add the DNF evaluated document to the crate metadata
        dnf_eval_file = crate.add_file(dnf_eval_filename, properties={
            "@type": ["File", "SoftwareSourceCode", "CreativeWork"],
            "name": f"Evaluated DNF Document for {transect_id}",
            "description": f"Evaluated dynamic narrative document for transect {transect_id}",
            "encodingFormat": "application/json"
        })
        
        # Update the existing DNF evaluated document entity to reference the actual file
        for entity in crate.get_entities():
            if entity.id == "#dnf-evaluated-document":
                entity["name"] = f"Evaluated DNF Document for {transect_id}"
                entity["description"] = f"Evaluated dynamic narrative document containing executed code and analysis for transect {transect_id}"
                entity["hasPart"] = [dnf_eval_file]
                print(f"✅ Updated DNF evaluated document entity to reference generated content for transect {transect_id}")
                break
    
    # Update the main research article entity to reference the generated content
    if crate.mainEntity:
        # Update the main entity properties to point to the actual generated content
        main_entity = crate.mainEntity
        main_entity["name"] = f"Dynamic Micropublication for Transect {transect_id}"
        main_entity["description"] = f"A dynamic and reproducible research micropublication for CoastSat shoreline analysis data from transect {transect_id}"
        main_entity["hasPart"] = [html_file]  # Include the HTML file as part of the article
        print(f"✅ Updated main entity to reference generated content for transect {transect_id}")
    
    # Write the updated crate back to disk (change to crate directory first)
    original_cwd = os.getcwd()
    try:
        os.chdir(crate_path)
        crate.write(".")
        print(f"💾 Updated publication crate metadata at {crate_path}")
    finally:
        os.chdir(original_cwd)

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

def get_data_path(crate_path):

    pub_crate = ROCrate(crate_path)

    interface_entity = next(
        (e for e in pub_crate.get_entities()
         if set(e.properties().get("@type", [])) >= {"RO-Crate", "Dataset"}),
        None
    )
    if not interface_entity:
        raise FileNotFoundError("Interface crate not found in publication.crate")

    interface_crate_path = Path(crate_path) / interface_entity.id
    if not interface_crate_path.exists():
        raise FileNotFoundError(f"interface.crate directory not found at {interface_crate_path}")

    interface_crate = ROCrate(interface_crate_path)

    for entity in interface_crate.get_entities():
        example_of_work = entity.properties().get("exampleOfWork", [])
        for item in example_of_work:
            # #fp-transects_extended_geojson is the formal param representing 
            # the final result file generated by make_xlsx in the Coastsat workflow. 
            if isinstance(item, dict) and item.get("@id") == "#fp-transectsextended-3":
                return entity.id

    raise FileNotFoundError("No data entity found with exampleOfWork = #fp-transectsextended-3")

def download_data_file(data_url):
    """
    Downloads a file from the given URL to a temp directory under Path(__file__).parent / 'data'.
    Supports direct file URLs and GitHub blob URLs (converts to raw).
    Returns the local file path.
    Only downloads if the file does not already exist.
    """
    data_dir = Path(__file__).parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Convert GitHub blob URL to raw URL if needed
    if data_url.startswith("https://github.com/") and "/blob/" in data_url:
        data_url = data_url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")

    local_filename = data_url.split("/")[-1]
    local_path = data_dir / local_filename

    if local_path.exists():
        print(f"File already exists: {local_path}")
        return local_path

    with requests.get(data_url, stream=True) as r:
        r.raise_for_status()
        with open(local_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    return local_path

def get_transect_by_id(geojson_path, transect_id):
    """
    Loads a GeoJSON file and returns the feature whose properties['id'] matches transect_id.
    Uses a generator expression for faster lookup.
    """
    with open(geojson_path, "r", encoding="utf-8") as f:
        geojson = json.load(f)
    feature = next(
        (feat for feat in geojson.get("features", [])
         if feat.get("properties", {}).get("id") == transect_id),
        None
    )
    if feature is None:
        raise ValueError(f"Transect with id '{transect_id}' not found in {geojson_path}")
    return feature

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a micropublication for a given transect ID.")
    parser.add_argument("transect_id", help="The transect ID to generate the micropublication for.")
    parser.add_argument("--output", help="Output file path for the generated micropublication HTML.", default="micropublication.html")
    parser.add_argument("--populate-crate", action="store_true", 
                       help="Populate the publication crate with generated content and update metadata")
    args = parser.parse_args()

    print("🔍 Getting template path...")

    # Detect if we're running from source (src/) or from crate (publication.crate/)
    script_dir = Path(__file__).parent
    if script_dir.name == "src":
        # Running from source directory
        template_path = script_dir / "templates" / "micropublication.smd"
        crate_path = script_dir.parent / "publication.crate"
        data_path = get_data_path(crate_path)
    else:
        # Running from crate directory
        template_path = script_dir / "micropublication.smd"
        crate_path = script_dir
        data_path = get_data_path(script_dir)

    print(f"🔍 Preparing micropublication for transect ID: {args.transect_id}")

    temp_dir_obj, temp_dir_path = prepare_temp_directory(template_path, args.transect_id)
    result = evaluate_micropublication(temp_dir_path)
    
    if result and result[0]:  # Check if we got a valid result and HTML path
        micropub_path, dnf_eval_path = result
        assert micropub_path is not None  # Type assertion for the type checker
        output_path = args.output if hasattr(args, "output") else "micropublication.html"
        shutil.copy(micropub_path, output_path)
        print(f"Micropublication written to {output_path}")
        
        # If populate-crate flag is set, update the crate with generated content
        if args.populate_crate:
            populate_crate_with_generated_content(crate_path, output_path, args.transect_id, dnf_eval_path)
            
    else:
        print("Failed to generate micropublication.")

    temp_dir_obj.cleanup()  # Clean up the temporary directory
    print("Temporary directory cleaned up.")
