"""Local heuristic AI (no external calls).

Scores each candidate placement with a classic weighted feature function and
picks the best. Used as the default when Jev is not configured.
"""

from __future__ import annotations

from typing import List, Optional

from .base import AiDecider, CandidateRecord, Decision, DecisionResult
from .board_state import apply_and_measure, enumerate_placements

# Weights tuned after inspection. Based on the Dellacherie-style feature set:
# holes dominate (heaviest penalty), landing height and bumpiness discourage
# stacking high/jagged, line clears are rewarded. These magnitudes matter — a
# too-weak holes penalty makes the AI stack over gaps, which looked "dumb".
DEFAULT_WEIGHTS = {
    "lines": 3.4,
    "landing_height": 4.5,
    "holes": 7.9,
    "bumpiness": 3.2,
    "aggregate_height": 0.6,
}


class HeuristicDecider(AiDecider):
    source = "heuristic"

    def __init__(self, weights: Optional[dict] = None) -> None:
        self.weights = {**DEFAULT_WEIGHTS, **(weights or {})}

    def _raw_score(self, m) -> float:
        w = self.weights
        return (
            w["lines"] * m.lines_cleared
            - w["landing_height"] * m.landing_height
            - w["holes"] * m.holes
            - w["bumpiness"] * m.bumpiness
            - w["aggregate_height"] * m.aggregate_height
        )

    def decide(self, board: List[List[int]], current_piece: str,
               next_piece: Optional[str] = None) -> DecisionResult:
        placements = enumerate_placements(board, current_piece)
        if not placements:
            return DecisionResult(source=self.source, decision=None, reason="no legal placement")

        scored = []
        for p in placements:
            metrics = apply_and_measure(board, p.cells)
            scored.append((p, metrics, self._raw_score(metrics)))

        # Normalize raw scores to [0, 1] for a UI-friendly confidence.
        raws = [s for _, _, s in scored]
        lo, hi = min(raws), max(raws)
        span = (hi - lo) or 1.0

        best_idx = max(range(len(scored)), key=lambda i: scored[i][2])

        records: List[CandidateRecord] = []
        for i, (p, m, raw) in enumerate(scored):
            norm = (raw - lo) / span
            records.append(
                CandidateRecord(
                    rotation=p.rotation,
                    column=p.left_col,
                    score=round(norm, 3),
                    metrics={
                        "lines_cleared": m.lines_cleared,
                        "holes": m.holes,
                        "aggregate_height": m.aggregate_height,
                        "bumpiness": m.bumpiness,
                        "landing_height": m.landing_height,
                    },
                    chosen=(i == best_idx),
                )
            )

        best_p, best_m, _ = scored[best_idx]
        best_norm = records[best_idx].score
        reason = f"Best placement: clears {best_m.lines_cleared}, holes {best_m.holes}"

        # Sort records so the chosen one is first, then by descending score.
        records.sort(key=lambda r: (not r.chosen, -r.score))

        return DecisionResult(
            source=self.source,
            decision=Decision(
                rotation=best_p.rotation,
                column=best_p.left_col,
                confidence=best_norm,
                origin_column=best_p.column,
            ),
            records=records,
            reason=reason,
        )
