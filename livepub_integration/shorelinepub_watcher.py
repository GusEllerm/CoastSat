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
REQUESTS_DIR = os.path.join(BASE_DIR, "shoreline_requests")
TMP_DIR = os.path.join(BASE_DIR, "shoreline_tmp")

# Ensure required directories exist
os.makedirs(REQUESTS_DIR, exist_ok=True)
os.makedirs(TMP_DIR, exist_ok=True)

# GitHub info
GITHUB_REPO = "GusEllerm/CoastSat-shorelinepublication"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

# Service-specific paths (shoreline publication service)
SERVICE_NAME = "shorelinepub"
CRATE_ZIP_PATH = os.path.join(BASE_DIR, f"{SERVICE_NAME}_crate.zip")
CRATE_VERSION_FILE = os.path.join(BASE_DIR, f"{SERVICE_NAME}_crate_version.txt")
PUBLICATION_CRATE = os.path.join(BASE_DIR, f"{SERVICE_NAME}_publication.crate")

# TODO: Add some logic that cleans up old requests and temp files. There are currently some cases in which the watcher will not delete files.

class ShorelinePubHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory or not event.src_path.endswith(".json"):
            return

        print(f"📥 New shoreline publication request: {event.src_path}")
        with open(event.src_path, "r") as f:
            request = json.load(f)

        site_id = request.get("id")
        if not site_id:
            print("⚠️  No 'id' field in request.")
            return

def run_stencila_pipeline(site_id, unique_id):
    base = os.path.join(TMP_DIR, unique_id)
    try:
        print("🧪 Running Stencila pipeline for shoreline publication...")
        final_path = f"{base}.html"
        subprocess.run([
            "python",
            os.path.join(PUBLICATION_CRATE, "publication_logic.py"),
            site_id,
            "--output",
            final_path
        ], check=True)
        if os.path.exists(final_path):
            print(f"✅ Shoreline publication generated: shoreline_tmp/{unique_id}.html")
            print(f"🌐 Accessible at: http://localhost:8766/tmp/{unique_id}.html")
            return f"{unique_id}.html"
        else:
            print(f"❌ HTML output not found at {final_path}")
            return None
    except subprocess.CalledProcessError as e:
        print(f"❌ Error in Stencila pipeline for {site_id}: {e}")
        return None

@app.route("/request", methods=["POST", "OPTIONS"])
def handle_request():
    """
    Accepts a POST request with JSON body {"id": "..."} and writes a new request file
    to livepub_integration/shoreline_requests/ to trigger the watcher.
    """
    if request.method == "OPTIONS":
        return '', 204  # Preflight response

    data = request.get_json()
    site_id = data.get("id")
    if not site_id:
        return jsonify({"error": "Missing 'id' field"}), 400

    unique_id = f"{site_id}_{uuid.uuid4().hex}"
    filename = run_stencila_pipeline(site_id, unique_id)
    if filename:
        return jsonify({"filename": filename}), 200
    else:
        return jsonify({"error": "Failed to generate shoreline publication"}), 500


# --- Flask route to serve generated shoreline publication HTML files ---
@app.route("/tmp/<path:filename>")
def serve_tmp_file(filename):
    """
    Serves generated HTML files from the shoreline_tmp/ directory.
    """
    return send_from_directory(TMP_DIR, filename)

# --- Flask route to delete generated shoreline publication HTML files ---
@app.route("/delete/<filename>", methods=["DELETE"])
def delete_tmp_file(filename):
    """
    Deletes a specified HTML file and its associated intermediate files from the shoreline_tmp/ directory.
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
        print(f"🗑️ Deleted shoreline publication files: {', '.join(deleted_files)}")
        return jsonify({"status": "deleted", "files": deleted_files}), 200
    else:
        return jsonify({"error": "Files not found"}), 404

def check_and_download_latest_crate():
    print(f"🔍 Checking for latest {SERVICE_NAME} publication.crate release...")

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

    print(f"🚀 Starting {SERVICE_NAME} watcher service...")
    print(f"📁 Crate directory: {PUBLICATION_CRATE}")
    print(f"👀 Watching for shoreline publication requests in '{REQUESTS_DIR}'...")
    event_handler = ShorelinePubHandler()
    observer = Observer()
    observer.schedule(event_handler, path=REQUESTS_DIR, recursive=False)
    observer.start()

    # Run on different port (8766) to avoid conflict with micropub service (8765)
    server_thread = Thread(target=app.run, kwargs={"host": "0.0.0.0", "port": 8766})
    server_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
