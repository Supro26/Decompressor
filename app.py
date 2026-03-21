#!/usr/bin/env python3

import os
import uuid
import shutil
import zipfile
from flask import (
    Flask, request, render_template,
    send_file, jsonify
)
from decompressor import recursive_decompress


app = Flask(__name__)

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
EXTRACT_FOLDER = os.path.join(BASE_DIR, "extracted")

app.config["UPLOAD_FOLDER"]      = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024   # 200 MB upload limit

# Make sure required directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(EXTRACT_FOLDER, exist_ok=True)


@app.route("/")
def index():
    """Render the upload page."""
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():

    if "file" not in request.files:
        return jsonify({"error": "No file part in the request."}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "No file selected."}), 400

    # Create a unique session directory to avoid collisions between requests
    session_id     = uuid.uuid4().hex
    session_upload = os.path.join(UPLOAD_FOLDER, session_id)
    session_output = os.path.join(EXTRACT_FOLDER, session_id)

    os.makedirs(session_upload, exist_ok=True)
    os.makedirs(session_output, exist_ok=True)

    try:
        # Save the uploaded file
        upload_path = os.path.join(session_upload, file.filename)
        file.save(upload_path)

        # Run recursive decompression into the session output folder
        log_lines = recursive_decompress(upload_path, session_output)

        # Bundle everything in the output folder into a single ZIP for download
        zip_path = os.path.join(session_upload, f"result_{session_id}.zip")
        _zip_directory(session_output, zip_path)

        # Stream the ZIP back to the user, then clean up
        response = send_file(
            zip_path,
            as_attachment=True,
            download_name="decompressed_result.zip",
            mimetype="application/zip"
        )

        # Attach session dirs to response so we can clean up after sending
        response.session_upload = session_upload
        response.session_output = session_output

        return response

    except Exception as exc:
        # Clean up on error
        shutil.rmtree(session_upload, ignore_errors=True)
        shutil.rmtree(session_output, ignore_errors=True)
        return jsonify({"error": str(exc)}), 500


@app.route("/upload/log", methods=["POST"])
def upload_log():

    #Same as /upload but returns JSON progress log 

    if "file" not in request.files:
        return jsonify({"error": "No file part."}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected."}), 400

    session_id     = uuid.uuid4().hex
    session_upload = os.path.join(UPLOAD_FOLDER, session_id)
    session_output = os.path.join(EXTRACT_FOLDER, session_id)

    os.makedirs(session_upload, exist_ok=True)
    os.makedirs(session_output, exist_ok=True)

    try:
        upload_path = os.path.join(session_upload, file.filename)
        file.save(upload_path)

        log_lines = recursive_decompress(upload_path, session_output)

        zip_path = os.path.join(session_upload, f"result_{session_id}.zip")
        _zip_directory(session_output, zip_path)

        return jsonify({
            "log"         : log_lines,
            "download_url": f"/download/{session_id}"
        })

    except Exception as exc:
        shutil.rmtree(session_upload, ignore_errors=True)
        shutil.rmtree(session_output, ignore_errors=True)
        return jsonify({"error": str(exc)}), 500


@app.route("/download/<session_id>")
def download(session_id: str):
    # Basic validation — session_id must be a hex string

    if not session_id.isalnum():
        return jsonify({"error": "Invalid session id."}), 400

    zip_path = os.path.join(UPLOAD_FOLDER, session_id, f"result_{session_id}.zip")

    if not os.path.exists(zip_path):
        return jsonify({"error": "Result not found. It may have already been downloaded."}), 404

    return send_file(
        zip_path,
        as_attachment=True,
        download_name="decompressed_result.zip",
        mimetype="application/zip"
    )



def _zip_directory(source_dir: str, output_zip_path: str) -> None:

    with zipfile.ZipFile(output_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(source_dir):
            for fname in files:
                abs_path = os.path.join(root, fname)
                rel_path = os.path.relpath(abs_path, source_dir)
                zf.write(abs_path, rel_path)



if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)

