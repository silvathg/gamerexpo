from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from flask import Flask, Response, jsonify, render_template, request, send_file

from diagnostic import collect_diagnostic, save_report_files
from game_recommender import recommend_games


app = Flask(__name__)
LAST_DIAGNOSTIC: Dict[str, Any] = {}
LAST_FILES: Dict[str, str] = {}


@app.get("/")
def index() -> str:
    return render_template("index.html")


@app.post("/api/diagnostico")
def api_diagnostic() -> Response:
    global LAST_DIAGNOSTIC, LAST_FILES
    LAST_DIAGNOSTIC = collect_diagnostic()
    LAST_FILES = save_report_files(LAST_DIAGNOSTIC)
    return jsonify(LAST_DIAGNOSTIC)


@app.get("/api/salvar/<file_type>")
def api_download(file_type: str) -> Response:
    if file_type not in {"json", "txt"}:
        return jsonify({"error": "Formato invalido. Use json ou txt."}), 400

    if not LAST_FILES.get(file_type) or not Path(LAST_FILES[file_type]).exists():
        return jsonify({"error": "Nenhum diagnostico foi gerado ainda."}), 404

    return send_file(LAST_FILES[file_type], as_attachment=True)


@app.post("/api/recomendar-jogos")
def api_recommend_games() -> Response:
    payload = request.get_json(silent=True) or LAST_DIAGNOSTIC
    if not payload:
        return jsonify({"error": "Gere ou envie um diagnostico JSON primeiro."}), 400
    return jsonify(recommend_games(payload))


@app.post("/api/upload-json")
def api_upload_json() -> Response:
    if "file" not in request.files:
        return jsonify({"error": "Envie um arquivo JSON."}), 400

    uploaded = request.files["file"]
    try:
        payload = json.loads(uploaded.read().decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return jsonify({"error": "Arquivo JSON invalido."}), 400

    return jsonify(recommend_games(payload))


if __name__ == "__main__":
    app.run(debug=True)

