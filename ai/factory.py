"""Decider factory: pick the AI backend per ``config.AI_BACKEND``.

This lives in a neutral module (not inside any one decider) so it can depend on
all three implementations as peers, without a concrete decider module having to
know about its siblings.
"""

from __future__ import annotations

import config

from .base import AiDecider
from .heuristic import HeuristicDecider
from .jev_client import JevDecider
from .openai_client import OpenAiDecider


def build_decider() -> AiDecider:
    """Factory: pick the decider per config.AI_BACKEND.

    - "openai":    ChatGPT decider (requires OPENAI_API_KEY), else heuristic.
    - "jev":       TypeSafe System One decider (requires a key), else heuristic.
    - "openjev":   OpenJev System One decider (requires a key), else heuristic.
    - "heuristic": always the local heuristic.
    - "auto" (default order): openai -> jev -> openjev -> heuristic.
    """
    backend = getattr(config, "AI_BACKEND", "auto")

    def _openjev() -> AiDecider:
        return JevDecider(config.OPENJEV_API_KEY, config.OPENJEV_API_URL,
                          config.OPENJEV_MODEL, source="openjev")

    def _jev() -> AiDecider:
        return JevDecider(config.JEV_API_KEY, config.JEV_API_URL, config.JEV_MODEL,
                          source="jev")

    def _openai() -> AiDecider:
        return OpenAiDecider(config.OPENAI_API_KEY, config.OPENAI_API_URL, config.OPENAI_MODEL)

    if backend == "heuristic":
        return HeuristicDecider()
    if backend == "openai":
        return _openai() if config.is_openai_enabled() else HeuristicDecider()
    if backend == "jev":
        return _jev() if config.is_jev_enabled() else HeuristicDecider()
    if backend == "openjev":
        return _openjev() if config.is_openjev_enabled() else HeuristicDecider()

    # auto
    if config.is_openai_enabled():
        return _openai()
    if config.is_jev_enabled():
        return _jev()
    if config.is_openjev_enabled():
        return _openjev()
    return HeuristicDecider()
