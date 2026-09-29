"""Flask server for Tetris Web Edition.

Responsibilities (per DESIGN.md section 2):
1. Static file hosting -- serve the ``static/`` directory (the frontend game).
2. Jev decision proxy -- ``POST /api/decide``.

This step wires up static hosting and a placeholder ``/api/decide`` so the
server runs and the game is playable in the browser. The real Jev / heuristic
decision logic is added in the next iteration.
"""

from __future__ import annotations

import logging
import os

from flask import Flask, jsonify, request, send_from_directory

import config
from ai.factory import build_decider

# Emit INFO logs (includes the "jev" logger's per-decision latency lines).
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

app = Flask(__name__, static_folder=None)

# One decider instance for the process: chosen per config.AI_BACKEND.
decider = build_decider()

# Announce which AI is actually active (source + endpoint/model when applicable).
_ai_source = getattr(decider, "source", "unknown")
_ai_url = getattr(decider, "api_url", None)
_ai_model = getattr(decider, "model", None)
if _ai_url:
    logging.getLogger("server").info(
        "AI backend: %s (requested=%s, model=%s, url=%s)",
        _ai_source, config.AI_BACKEND, _ai_model, _ai_url,
    )
else:
    logging.getLogger("server").info(
        "AI backend: %s (requested=%s)", _ai_source, config.AI_BACKEND,
    )


@app.route("/")
def index():
    """Serve the game's entry page."""
    return send_from_directory(STATIC_DIR, "index.html")


@app.route("/<path:filename>")
def static_files(filename: str):
    """Serve any static asset (js/css/locales/...)."""
    return send_from_directory(STATIC_DIR, filename)


@app.route("/api/health")
def health():
    """Simple health check; reports whether Jev mode is active."""
    return jsonify({"status": "ok", "jev_enabled": config.is_jev_enabled()})


@app.route("/api/decide", methods=["POST"])
def decide():
    """Return an AI placement decision for the given board state.

    Delegates to the configured decider (Jev when a real key is set, else the
    local heuristic). Both return the same JSON shape.
    """
    data = request.get_json(silent=True) or {}
    board = data.get("board")
    current_piece = data.get("current_piece")
    next_piece = data.get("next_piece")

    if not isinstance(board, list) or not current_piece:
        return jsonify({"error": "invalid request: 'board' (list) and 'current_piece' required"}), 400

    result = decider.decide(board, current_piece, next_piece)
    return jsonify(result.to_dict())


if __name__ == "__main__":
    print(f"Tetris server on http://{config.HOST}:{config.PORT}  "
          f"(AI backend: {getattr(decider, 'source', 'unknown')}, requested={config.AI_BACKEND})")
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
