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
# Set CORS origins from environment variable, fallback to localhost for development
frontend_origin = os.environ.get("FRONTEND_ORIGIN", "*")
print(f"Setting CORS origin to: {frontend_origin}")
CORS(app, origins=[frontend_origin], supports_credentials=True)

BASE_DIR = os.path.dirname(__file__)
REQUESTS_DIR = os.path.join(BASE_DIR, "requests")
TMP_DIR = os.path.join(BASE_DIR, "tmp")
TEMPLATE_SMD = os.path.join(BASE_DIR, "micropub_templates", "base_template.smd")

# GitHub info
GITHUB_REPO = "GusEllerm/CoastSat-micropublication"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

# Paths
CRATE_ZIP_PATH = os.path.join(BASE_DIR, "publication_crate.zip")
CRATE_VERSION_FILE = os.path.join(BASE_DIR, "crate_version.txt")
PUBLICATION_CRATE = os.path.join(BASE_DIR, "publication.crate")

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
        final_path = f"{base}.html"
        subprocess.run([
            "python",
            os.path.join(PUBLICATION_CRATE, "micropublication_logic.py"),
            p_id,
            "--output",
            final_path
        ], check=True)
        if os.path.exists(final_path):
            print(f"✅ Micropublication generated: tmp/{unique_id}.html")
            print(f"🌐 Accessible at: http://localhost:8765/tmp/{unique_id}.html")
            return f"{unique_id}.html"
        else:
            print(f"❌ HTML output not found at {final_path}")
            return None
    except subprocess.CalledProcessError as e:
        print(f"❌ Error in Stencila pipeline for {p_id}: {e}")
        return None

@app.route("/request", methods=["POST", "OPTIONS"])
def handle_request():
    """
    Accepts a POST request with JSON body {"id": "..."} and writes a new request file
    to micro_integration/requests/ to trigger the watcher.
    """
    if request.method == "OPTIONS":
        return '', 204  # Preflight response

    data = request.get_json()
    p_id = data.get("id")
    if not p_id:
        return jsonify({"error": "Missing 'id' field"}), 400

    unique_id = f"{p_id}_{uuid.uuid4().hex}"
    filename = run_stencila_pipeline(p_id, unique_id)
    if filename:
        return jsonify({"filename": filename}), 200
    else:
        return jsonify({"error": "Failed to generate micropublication"}), 500


# --- Flask route to serve generated micropublication HTML files ---
@app.route("/tmp/<path:filename>")
def serve_tmp_file(filename):
    """
    Serves generated HTML files from the tmp/ directory.
    """
    return send_from_directory(TMP_DIR, filename)

# --- Flask route to delete generated micropublication HTML files ---
@app.route("/delete/<filename>", methods=["DELETE"])
def delete_tmp_file(filename):
    """
    Deletes a specified HTML file and its associated intermediate files from the tmp/ directory.
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
            crate_path = os.path.join(BASE_DIR, "publication.crate")
            if current_tag == latest_tag and os.path.exists(crate_path):
                print(f"📦 Local crate is up-to-date ({latest_tag})")
                return
            else:
                print(f"📦 Updating crate from {current_tag} → {latest_tag}")
        else:
            print(f"📥 No local crate found, downloading {latest_tag}")

        zip_asset = next((a for a in assets if a["name"].endswith(".zip")), None)
        if not zip_asset:
            print("❌ No zip asset found in the release.")
            return

        zip_url = zip_asset["browser_download_url"]
        zip_resp = requests.get(zip_url)
        zip_resp.raise_for_status()

        with zipfile.ZipFile(BytesIO(zip_resp.content)) as z:
            # Clear old crate directory if it exists
            crate_path = os.path.join(BASE_DIR, "publication.crate")
            if os.path.exists(crate_path):
                for filename in os.listdir(crate_path):
                    file_path = os.path.join(crate_path, filename)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                    elif os.path.isdir(file_path):
                        import shutil
                        shutil.rmtree(file_path)
            z.extractall(BASE_DIR)

        # Save version
        with open(CRATE_VERSION_FILE, "w") as f:
            f.write(latest_tag)

        print(f"✅ Downloaded and extracted crate: {latest_tag}")

    except Exception as e:
        print(f"❌ Failed to check/download publication.crate: {e}")

@app.after_request
def apply_cors_headers(response):
    origin = request.headers.get("Origin")
    allowed_origins = ["http://localhost:8000", "http://127.0.0.1:8000", "http://130.216.216.92"]
    if origin in allowed_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
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

    print(f"👀 Watching for micropublication requests in '{REQUESTS_DIR}'...")
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