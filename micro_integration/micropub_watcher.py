import os
import time
import json
import subprocess
import uuid
from threading import Thread
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS, cross_origin

app = Flask(__name__)
# NOTE: For production deployment, update the CORS origins to reflect your deployed frontend's domain.
# Allow only requests from localhost:8000 during development
CORS(app, origins=["http://localhost:8000"], supports_credentials=True)

BASE_DIR = os.path.dirname(__file__)
REQUESTS_DIR = os.path.join(BASE_DIR, "requests")
TMP_DIR = os.path.join(BASE_DIR, "tmp")
TEMPLATE_SMD = os.path.join(BASE_DIR, "micropub_templates", "base_template.smd")

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
        subprocess.run(["stencila", "convert", TEMPLATE_SMD, f"{base}.json"], check=True)
        subprocess.run(["stencila", "render", f"{base}.json", f"{base}_eval.json", "--force-all", "--pretty"], check=True)
        subprocess.run(["stencila", "convert", f"{base}_eval.json", f"{base}.html", "--pretty"], check=True)
        final_path = f"{base}.html"
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

@app.route("/request", methods=["POST"])
def handle_request():
    """
    Accepts a POST request with JSON body {"id": "..."} and writes a new request file
    to micro_integration/requests/ to trigger the watcher.
    """
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

if __name__ == "__main__":
    os.makedirs(REQUESTS_DIR, exist_ok=True)
    os.makedirs(TMP_DIR, exist_ok=True)

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

    server_thread = Thread(target=app.run, kwargs={"port": 8765})
    server_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()