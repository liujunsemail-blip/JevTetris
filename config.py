"""Application configuration.

Values are read from environment variables when present, otherwise fall back to
safe defaults. A provider is enabled only when its API key is non-empty;
otherwise the backend runs in local-heuristic mode instead of calling that API.
"""

import os

# Jev (OpenJev System One) integration.
# --- Jev family (System One `choice` API) -------------------------------------
# Two providers speak the SAME System One protocol, so they share JevDecider and
# differ only in config (key / url / model):
#   - "jev"     : the hosted TypeSafe endpoint.
#   - "openjev" : the OpenJev endpoint.

# TypeSafe (jev):
JEV_API_KEY: str = os.environ.get("TYPESAFE_API_KEY", "")
JEV_API_URL: str = os.environ.get("JEV_API_URL", "https://api.typesafe.ai/v1/systemone")
JEV_MODEL: str = os.environ.get("JEV_MODEL", "jev-latest")

# OpenJev (openjev):
OPENJEV_API_KEY: str = os.environ.get("OPENJEV_API_KEY", "")
OPENJEV_API_URL: str = os.environ.get("OPENJEV_API_URL", "https://api.openjev.sh/v1/systemone")
OPENJEV_MODEL: str = os.environ.get("OPENJEV_MODEL", "openjev")

# OpenAI / ChatGPT integration (alternative decider).
# Set OPENAI_API_KEY to enable. Uses the Chat Completions API with JSON output.
OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")
OPENAI_API_URL: str = os.environ.get(
    "OPENAI_API_URL", "https://api.openai.com/v1/chat/completions"
)
OPENAI_MODEL: str = os.environ.get("OPENAI_MODEL", "gpt-6-luna")

# Which decider to use: "auto", or force one of
# "openai" | "jev" | "openjev" | "jev".
AI_BACKEND: str = os.environ.get("AI_BACKEND", "jev").lower()

# HTTP server.
HOST: str = os.environ.get("HOST", "127.0.0.1")
PORT: int = int(os.environ.get("PORT", "5000"))
DEBUG: bool = os.environ.get("FLASK_DEBUG", "1") == "1"


def is_jev_enabled() -> bool:
    """Return True when a TypeSafe key is set."""
    return bool(JEV_API_KEY)


def is_openjev_enabled() -> bool:
    """Return True when an OpenJev key is set."""
    return bool(OPENJEV_API_KEY)


def is_openai_enabled() -> bool:
    """Return True when an OpenAI/ChatGPT API key is set."""
    return bool(OPENAI_API_KEY)
