import os
import time
import json
import subprocess
import uuid
import requests
import zipfile
from io import BytesIO

from threading import Thread
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS, cross_origin

app = Flask(__name__)

BASE_DIR = os.path.dirname(__file__)
REQUESTS_DIR = os.path.join(BASE_DIR, "micropub_requests")
TMP_DIR = os.path.join(BASE_DIR, "micropub_tmp")
TEMPLATE_SMD = os.path.join(BASE_DIR, "micropub_templates", "base_template.smd")

# GitHub info
GITHUB_REPO = "GusEllerm/CoastSat-micropublication"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

# Service-specific paths (micropublication service)
SERVICE_NAME = "micropub"
CRATE_ZIP_PATH = os.path.join(BASE_DIR, f"{SERVICE_NAME}_crate.zip")
CRATE_VERSION_FILE = os.path.join(BASE_DIR, f"{SERVICE_NAME}_crate_version.txt")
PUBLICATION_CRATE = os.path.join(BASE_DIR, f"{SERVICE_NAME}_publication.crate")

# TODO: Add some logic that cleans up old requests and temp files. There are currently some cases in which the watcher will not delete files.

class MicroPubHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory or not event.src_path.endswith(".json"):
            return

        print(f"📥 New micropublication request: {event.src_path}")
        with open(event.src_path, "r") as f:
            request = json.load(f)

        p_id = request.get("id")
        if not p_id:
            print("⚠️  No 'id' field in request.")
            return

def run_stencila_pipeline(p_id, unique_id):
    base = os.path.join(TMP_DIR, unique_id)
    try:
        print("🧪 Running Stencila pipeline...")
        print(f"📁 TMP_DIR: {TMP_DIR}")
        print(f"🎯 Target base path: {base}")
        print(f"📦 PUBLICATION_CRATE: {PUBLICATION_CRATE}")
        print(f"📋 Publication crate exists: {os.path.exists(PUBLICATION_CRATE)}")
        
        final_path = f"{base}.html"
        print(f"📄 Final HTML path: {final_path}")
        
        # Check if the micropublication_logic.py exists
        logic_script = os.path.join(PUBLICATION_CRATE, "micropublication_logic.py")
        print(f"🐍 Logic script path: {logic_script}")
        print(f"🐍 Logic script exists: {os.path.exists(logic_script)}")
        
        if not os.path.exists(PUBLICATION_CRATE):
            print("❌ Publication crate directory not found!")
            return None
            
        if not os.path.exists(logic_script):
            print("❌ micropublication_logic.py not found in crate!")
            return None
        
        print(f"▶️ Running command: python {logic_script} {p_id} --output {final_path}")
        
        subprocess.run([
            "python",
            logic_script,
            p_id,
            "--output",
            final_path
        ], check=True)
        
        if os.path.exists(final_path):
            print(f"✅ Micropublication generated: micropub_tmp/{unique_id}.html")
            print(f"🌐 Accessible at: http://localhost:8765/tmp/{unique_id}.html")
            return f"{unique_id}.html"
        else:
            print(f"❌ HTML output not found at {final_path}")
            return None
    except subprocess.CalledProcessError as e:
        print(f"❌ Error in Stencila pipeline for {p_id}: {e}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error in pipeline: {e}")
        return None

@app.route("/request", methods=["POST", "OPTIONS"])
def handle_request():
    """
    Accepts a POST request with JSON body {"id": "..."} and writes a new request file
    to livepub_integration/micropub_requests/ to trigger the watcher.
    """
    if request.method == "OPTIONS":
        return '', 204  # Preflight response

    data = request.get_json()
    print(f"📨 Received request data: {data}")
    
    p_id = data.get("id")
    if not p_id:
        print("❌ Missing 'id' field in request")
        return jsonify({"error": "Missing 'id' field"}), 400

    print(f"🆔 Processing micropublication request for ID: {p_id}")
    
    unique_id = f"{p_id}_{uuid.uuid4().hex}"
    print(f"🔗 Generated unique_id: {unique_id}")
    
    filename = run_stencila_pipeline(p_id, unique_id)
    print(f"📄 Pipeline returned filename: {filename}")
    
    if filename:
        print(f"✅ Successfully generated micropublication: {filename}")
        return jsonify({"filename": filename}), 200
    else:
        print("❌ Pipeline failed to generate micropublication")
        return jsonify({"error": "Failed to generate micropublication"}), 500


# --- Flask route to serve generated micropublication HTML files ---
@app.route("/tmp/<path:filename>")
def serve_tmp_file(filename):
    """
    Serves generated HTML files from the micropub_tmp/ directory.
    """
    return send_from_directory(TMP_DIR, filename)

# --- Flask route to delete generated micropublication HTML files ---
@app.route("/delete/<filename>", methods=["DELETE"])
def delete_tmp_file(filename):
    """
    Deletes a specified HTML file and its associated intermediate files from the micropub_tmp/ directory.
    """
    html_path = os.path.join(TMP_DIR, filename)
    base_name = filename.replace(".html", "")
    json_path = os.path.join(TMP_DIR, f"{base_name}.json")
    eval_json_path = os.path.join(TMP_DIR, f"{base_name}_eval.json")

    deleted_files = []

    for path in [html_path, json_path, eval_json_path]:
        if os.path.exists(path):
            os.remove(path)
            deleted_files.append(os.path.basename(path))

    if deleted_files:
        print(f"🗑️ Deleted micropublication files: {', '.join(deleted_files)}")
        return jsonify({"status": "deleted", "files": deleted_files}), 200
    else:
        return jsonify({"error": "Files not found"}), 404

def check_and_download_latest_crate():
    print("🔍 Checking for latest publication.crate release...")

    try:
        response = requests.get(GITHUB_API_URL)
        response.raise_for_status()
        release_data = response.json()

        latest_tag = release_data["tag_name"]
        assets = release_data.get("assets", [])

        # Check local version
        if os.path.exists(CRATE_VERSION_FILE):
            with open(CRATE_VERSION_FILE, "r") as f:
                current_tag = f.read().strip()
            if current_tag == latest_tag and os.path.exists(PUBLICATION_CRATE):
                print(f"📦 Local {SERVICE_NAME} crate is up-to-date ({latest_tag})")
                return
            else:
                print(f"📦 Updating {SERVICE_NAME} crate from {current_tag} → {latest_tag}")
        else:
            print(f"📥 No local {SERVICE_NAME} crate found, downloading {latest_tag}")

        zip_asset = next((a for a in assets if a["name"].endswith(".zip")), None)
        if not zip_asset:
            print("❌ No zip asset found in the release.")
            return

        zip_url = zip_asset["browser_download_url"]
        zip_resp = requests.get(zip_url)
        zip_resp.raise_for_status()

        with zipfile.ZipFile(BytesIO(zip_resp.content)) as z:
            # Clear old crate directory if it exists
            if os.path.exists(PUBLICATION_CRATE):
                print(f"🧹 Clearing old {SERVICE_NAME} crate directory...")
                import shutil
                shutil.rmtree(PUBLICATION_CRATE)

            # Extract to temporary location first
            temp_extract_dir = os.path.join(BASE_DIR, "temp_extract")
            if os.path.exists(temp_extract_dir):
                import shutil
                shutil.rmtree(temp_extract_dir)
            
            z.extractall(temp_extract_dir)
            
            # Find the publication.crate directory in extracted content
            extracted_crate = os.path.join(temp_extract_dir, "publication.crate")
            if os.path.exists(extracted_crate):
                # Rename to service-specific directory
                import shutil
                shutil.move(extracted_crate, PUBLICATION_CRATE)
                print(f"📁 Moved publication.crate → {SERVICE_NAME}_publication.crate")
            else:
                print("❌ No publication.crate found in extracted zip")
                return
            
            # Clean up temporary directory
            if os.path.exists(temp_extract_dir):
                import shutil
                shutil.rmtree(temp_extract_dir)

        # Save version
        with open(CRATE_VERSION_FILE, "w") as f:
            f.write(latest_tag)

        print(f"✅ Downloaded and extracted {SERVICE_NAME} crate: {latest_tag}")
        print(f"📁 Crate location: {PUBLICATION_CRATE}")

    except Exception as e:
        print(f"❌ Failed to check/download {SERVICE_NAME} publication.crate: {e}")

@app.after_request
def apply_cors_headers(response):
    origin = request.headers.get("Origin")
    allowed_origins = ["http://localhost:8000", "http://127.0.0.1:8000", "http://130.216.216.92", "http://coastsat.livepublication.org", "https://coastsat.livepublication.org"]
    if origin in allowed_origins:
        print(f"🌐 CORS allowed for origin: {origin}")
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    else:
        print(f"🚫 CORS denied for origin: {origin}")
        response.headers["Access-Control-Allow-Origin"] = "null"
    return response

if __name__ == "__main__":
    os.makedirs(REQUESTS_DIR, exist_ok=True)
    os.makedirs(TMP_DIR, exist_ok=True)

    check_and_download_latest_crate()

    for dir_path in [REQUESTS_DIR, TMP_DIR]:
      for filename in os.listdir(dir_path):
        file_path = os.path.join(dir_path, filename)
        if os.path.isfile(file_path):
          os.remove(file_path)

    print(f"� Starting {SERVICE_NAME} watcher service...")
    print(f"📁 Crate directory: {PUBLICATION_CRATE}")
    print(f"�👀 Watching for micropublication requests in '{REQUESTS_DIR}'...")
    event_handler = MicroPubHandler()
    observer = Observer()
    observer.schedule(event_handler, path=REQUESTS_DIR, recursive=False)
    observer.start()

    server_thread = Thread(target=app.run, kwargs={"host": "0.0.0.0", "port": 8765})
    server_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()