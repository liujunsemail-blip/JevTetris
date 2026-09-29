"""Jev (OpenJev / TypeSafe System One) integration.

Choice-mode decision: code enumerates all LEGAL landings, computes each one's
resulting board + metrics (see placement_options), and asks Jev ONE `choice`
question to pick the best. Legality is decided in code, never by the model —
the model only chooses among placements already proven legal. On any failure we
fall back to the local heuristic. The API key stays server-side.
"""

from __future__ import annotations

import logging
import time
from typing import List, Optional

import requests

from .base import AiDecider, Decision, DecisionResult
from .board_state import apply_and_measure, render_board_with_piece
from .heuristic import HeuristicDecider
from .placement_options import (
    CHOICE_INSTRUCTIONS,
    build_options,
    build_records,
)

logger = logging.getLogger("jev")


class JevDecider(AiDecider):
    source = "jev"

    def __init__(self, api_key: str, api_url: str, model: str, timeout: float = 12.0,
                 source: str = "jev") -> None:
        self.api_key = api_key
        self.api_url = api_url
        self.model = model
        self.timeout = timeout
        self.source = source
        self._fallback = HeuristicDecider()

    def _build_state(self, board, piece_type: str, next_piece=None) -> str:
        """The board with the spawned piece drawn on top ('@'); options live in
        the questions object, not here."""
        board_with_piece = render_board_with_piece(board, piece_type)
        lines = [
            "You are playing Tetris. Choose where to drop the current piece.",
            "",
            "GRID: '#' = a locked block, '_' = empty, '@' = the CURRENT piece that",
            "just spawned at the top (it is the shape you must place, drawn in its",
            "spawn orientation for reference). Row 0 is the TOP, row 19 the BOTTOM.",
            "Columns are 0-9, left to right:",
            "",
            board_with_piece,
        ]
        if next_piece:
            lines += [
                "",
                f"NEXT PIECE (spawns after you place the current one): {next_piece}. "
                "Consider it when choosing, so this placement leaves a good spot for it.",
            ]
        return "\n".join(lines)

    def _questions(self, criteria: dict) -> dict:
        return {
            "best_placement": {
                "type": "choice",
                "instructions": CHOICE_INSTRUCTIONS,
                "criteria": criteria,
            }
        }

    def _call(self, state_text: str, questions: dict) -> Optional[dict]:
        payload = {"state": state_text, "model": self.model, "questions": questions}
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        resp = requests.post(self.api_url, json=payload, headers=headers, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def decide(self, board: List[List[int]], current_piece: str,
               next_piece: Optional[str] = None) -> DecisionResult:
        placements, labels, criteria = build_options(board, current_piece)
        if not placements:
            return DecisionResult(source=self.source, decision=None, reason="no legal placement")

        t0 = time.perf_counter()
        try:
            state_text = self._build_state(board, current_piece, next_piece)
            questions = self._questions(criteria)
            data = self._call(state_text, questions)
            latency_ms = int((time.perf_counter() - t0) * 1000)
            answers = (data or {}).get("answers") or {}
            ans = answers.get("best_placement") or {}
            chosen_label = ans.get("choice")
            probabilities = ans.get("probabilities") or {}
            confidence = float(ans.get("confidence", 0.0) or 0.0)
            if chosen_label is None or chosen_label not in labels:
                raise ValueError(f"unexpected choice: {chosen_label!r}")
            best_idx = labels.index(chosen_label)
        except Exception as exc:  # noqa: BLE001 - any failure => safe fallback
            latency_ms = int((time.perf_counter() - t0) * 1000)
            logger.warning(
                "Jev decision failed after %sms (%s: %s); falling back to heuristic",
                latency_ms, type(exc).__name__, exc,
            )
            result = self._fallback.decide(board, current_piece, next_piece)
            result.latency_ms = latency_ms
            result.reason = f"Jev unavailable ({type(exc).__name__}); used heuristic. " + result.reason
            return result

        logger.info(
            "Jev decision: piece=%s placements=%d chose=%s latency=%dms",
            current_piece, len(placements), chosen_label, latency_ms,
        )

        best_p = placements[best_idx]
        best_m = apply_and_measure(board, best_p.cells)
        records = build_records(board, placements, labels, best_idx, probabilities)
        return DecisionResult(
            source=self.source,
            decision=Decision(
                rotation=best_p.rotation,
                column=best_p.left_col,
                confidence=round(confidence, 3),
                origin_column=best_p.column,
            ),
            records=records,
            reason=(
                f"Jev chose {chosen_label}: clears {best_m.lines_cleared}, "
                f"holes {best_m.holes} (confidence {confidence:.2f}, {latency_ms}ms)"
            ),
            latency_ms=latency_ms,
        )
