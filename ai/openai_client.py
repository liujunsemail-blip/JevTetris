"""ChatGPT / OpenAI integration — choice-mode decider.

LLMs are poor at spatial simulation (asked openly for a rotation+column, GPT
misreads piece shapes — e.g. L vs T — and cannot mentally simulate a drop). So
this works exactly like the Jev path: code enumerates all legal landings and
computes each one's resulting board + metrics (shared placement_options), and
GPT only PICKS a numbered option. The chosen number maps back to a real legal
placement, so the model never has to recognise a shape or produce coordinates.

On any failure we do NOT fall back to another decider — we return an error
result (decision=None) so the failure is visible; the piece then falls by
gravity. The API key stays server-side.
"""

from __future__ import annotations

import json
import logging
import time
from typing import List, Optional

import requests

import config

from .base import AiDecider, Decision, DecisionResult
from .board_state import apply_and_measure, render_board_with_piece
from .placement_options import CHOICE_INSTRUCTIONS, build_options, build_records

logger = logging.getLogger("openai")


class OpenAiDecider(AiDecider):
    source = "openai"

    def __init__(self, api_key: str, api_url: str, model: str, timeout: float = 30.0) -> None:
        self.api_key = api_key
        self.api_url = api_url
        self.model = model
        self.timeout = timeout

    def _prompt(self, board, piece_type: str, criteria: dict, next_piece: Optional[str]) -> str:
        board_with_piece = render_board_with_piece(board, piece_type)
        nxt = (f"\nNEXT PIECE (spawns after this one): {next_piece}. Consider it so "
               "this placement leaves a good spot for it.") if next_piece else ""
        # Render the numbered options as text.
        opts = "\n\n".join(f"OPTION {label}:\n{text}" for label, text in criteria.items())
        return (
            "You are playing Tetris on a 10-column (0-9), 20-row board.\n"
            "GRID: '#' = a locked block, '_' = empty, '@' = the CURRENT piece drawn "
            "at the top in its spawn orientation. Row 0 is the TOP, row 19 the "
            "BOTTOM. Columns 0-9 left to right.\n\n"
            f"{board_with_piece}\n"
            f"Current piece: {piece_type}.{nxt}\n\n"
            "Below are ALL the legal placements, each already showing the move, the "
            "resulting board, and its metrics — you do NOT need to simulate anything, "
            "just compare the given results and pick the best option.\n\n"
            f"{CHOICE_INSTRUCTIONS}\n\n"
            f"{opts}\n\n"
            "Respond with ONLY a JSON object naming the option number you pick:\n"
            '{"choice": <the option number>}\n'
            "No prose, no explanation."
        )

    def _call(self, prompt: str) -> Optional[dict]:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a Tetris-playing agent. Reply with JSON only."},
                {"role": "user", "content": prompt},
            ],
            # No 'temperature': newer models (gpt-5, gpt-6-luna, ...) reject a
            # non-default temperature with a 400, and we don't need determinism.
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        attempts = 4
        for attempt in range(attempts):
            resp = requests.post(self.api_url, json=payload, headers=headers, timeout=self.timeout)
            if resp.status_code in (429, 529) and attempt < attempts - 1:
                retry_after = resp.headers.get("retry-after")
                try:
                    wait_s = float(retry_after) if retry_after else None
                except ValueError:
                    wait_s = None
                if wait_s is None:
                    wait_s = min(10.0, 1.0 * (2 ** attempt))
                logger.warning(
                    "OpenAI %d (rate-limited); retry %d/%d after %.1fs",
                    resp.status_code, attempt + 1, attempts - 1, wait_s,
                )
                time.sleep(wait_s)
                continue
            resp.raise_for_status()
            return resp.json()
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _parse_choice(data: dict) -> str:
        content = data["choices"][0]["message"]["content"]
        obj = json.loads(content)
        # Accept {"choice": 3} or {"choice": "3"}.
        return str(obj["choice"])

    def decide(self, board: List[List[int]], current_piece: str,
               next_piece: Optional[str] = None) -> DecisionResult:
        placements, labels, criteria = build_options(board, current_piece)
        if not placements:
            return DecisionResult(source=self.source, decision=None, reason="no legal placement")

        t0 = time.perf_counter()
        try:
            prompt = self._prompt(board, current_piece, criteria, next_piece)
            data = self._call(prompt)
            latency_ms = int((time.perf_counter() - t0) * 1000)
            chosen_label = self._parse_choice(data or {})
            if chosen_label not in labels:
                raise ValueError(f"unexpected choice: {chosen_label!r}")
            best_idx = labels.index(chosen_label)
        except Exception as exc:  # noqa: BLE001 - no fallback: surface the failure
            latency_ms = int((time.perf_counter() - t0) * 1000)
            logger.warning(
                "OpenAI decision failed after %sms (%s: %s); NO fallback",
                latency_ms, type(exc).__name__, exc,
            )
            return DecisionResult(
                source=self.source,
                decision=None,
                reason=f"OpenAI error ({type(exc).__name__}): {exc}",
                latency_ms=latency_ms,
            )

        logger.info(
            "OpenAI decision: piece=%s placements=%d chose=%s latency=%dms",
            current_piece, len(placements), chosen_label, latency_ms,
        )

        best_p = placements[best_idx]
        best_m = apply_and_measure(board, best_p.cells)
        records = build_records(board, placements, labels, best_idx)
        return DecisionResult(
            source=self.source,
            decision=Decision(
                rotation=best_p.rotation,
                column=best_p.left_col,
                confidence=1.0,
                origin_column=best_p.column,
            ),
            records=records,
            reason=(
                f"ChatGPT chose option {chosen_label}: clears {best_m.lines_cleared}, "
                f"holes {best_m.holes} ({latency_ms}ms)"
            ),
            latency_ms=latency_ms,
        )
