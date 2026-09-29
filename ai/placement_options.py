"""Shared placement-option building for choice-mode deciders.

The key insight from testing: LLMs (Jev, GPT, ...) are poor at spatial
simulation — asked openly for a rotation+column they misread piece shapes and
cannot mentally simulate a drop. They ARE good at CHOOSING among options whose
consequences are already computed. So every model-backed decider works the same
way: code enumerates all legal landings deterministically, computes each one's
resulting board and metrics, and the model only picks a numbered option.

This module builds those numbered options (with pruning of obviously-bad ones)
and the shared instruction text, so JevDecider and OpenAiDecider share exactly
one option representation.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from .base import CandidateRecord
from .board_state import (
    BOARD_COLS,
    Placement,
    apply_and_measure,
    enumerate_placements,
    render_grid_ascii,
)

# Priority the model is asked to follow AND the pruning/record logic mirror:
# fewest holes, then lower height, then more lines cleared, then flatter.
CHOICE_INSTRUCTIONS = (
    "Each option gives the move ('rotation: R times, column: C' — rotate R times "
    "clockwise, slide the leftmost block to column C, then drop), the RESULTING "
    "board after the piece locks and full rows are removed ('#' locked, '_' "
    "empty), and metrics on that result: lines_cleared (rows this move clears), "
    "holes (empty cells trapped under blocks), max_height (tallest column), "
    "height_variance (how uneven the column heights are overall), bumpiness "
    "(surface unevenness between adjacent columns). Choose the option with the "
    "best result, applying this priority in order: FIRST fewest holes; then lower "
    "height (max_height, then height_variance); then more lines_cleared; then "
    "lower bumpiness. Always avoid game over (keep the stack low)."
)


def labels_for(n: int) -> List[str]:
    """Numeric option labels '1'..'n' — no upper bound, short and stable."""
    return [str(i) for i in range(1, n + 1)]


def prune_bad(board, placements: List[Placement]) -> List[Placement]:
    """Drop placements whose holes exceed the minimum available by >=2 — they are
    almost never good and just add noise/tokens. Keep a floor of 3 so the model
    always has a real choice."""
    if len(placements) <= 3:
        return placements
    holes_of = {id(p): apply_and_measure(board, p.cells).holes for p in placements}
    min_holes = min(holes_of.values())
    kept = [p for p in placements if holes_of[id(p)] <= min_holes + 1]
    return kept if len(kept) >= 3 else placements


def option_text(board, p: Placement) -> str:
    """One option's text: move, then metrics on the result, then the result board.
    Metrics precede the board deliberately (A/B: better rank at equal cost)."""
    m = apply_and_measure(board, p.cells)
    hs = m.heights or [0] * BOARD_COLS
    mean = sum(hs) / len(hs)
    height_variance = round(sum((h - mean) ** 2 for h in hs) / len(hs), 1)
    metrics = (
        f"result: lines_cleared={m.lines_cleared}, holes={m.holes}, "
        f"max_height={m.max_height}, height_variance={height_variance}, "
        f"bumpiness={m.bumpiness}"
    )
    move = f"rotation: {p.rotation} times, column: {p.left_col}"
    board_after = render_grid_ascii(m.grid_after)
    return f"{move}\n{metrics}\nresulting board (top row 0 to bottom row 19):\n{board_after}"


def build_options(board, piece_type: str, do_prune: bool = True
                  ) -> Tuple[List[Placement], List[str], dict]:
    """Return (placements, labels, criteria) for a board+piece.

    placements: the legal landings offered (after optional pruning), aligned with
    labels ('1'..'N'); criteria: {label: option_text} for the choice question.
    Returns ([], [], {}) when there is no legal placement.
    """
    placements = enumerate_placements(board, piece_type)
    if not placements:
        return [], [], {}
    if do_prune:
        placements = prune_bad(board, placements)
    labels = labels_for(len(placements))
    criteria = {lbl: option_text(board, p) for lbl, p in zip(labels, placements)}
    return placements, labels, criteria


def build_records(board, placements: List[Placement], labels: List[str],
                  best_idx: int, probabilities: Optional[dict] = None
                  ) -> List[CandidateRecord]:
    """Per-candidate records for the decision panel. If probabilities (label->p)
    are given (Jev), they become the surfaced score; otherwise the chosen option
    gets 1.0 and the rest 0.0."""
    probabilities = probabilities or {}
    records: List[CandidateRecord] = []
    for i, p in enumerate(placements):
        m = apply_and_measure(board, p.cells)
        if probabilities:
            score = round(float(probabilities.get(labels[i], 0.0) or 0.0), 3)
        else:
            score = 1.0 if i == best_idx else 0.0
        records.append(
            CandidateRecord(
                rotation=p.rotation,
                column=p.left_col,
                score=score,
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
    records.sort(key=lambda r: (not r.chosen, -r.score))
    return records
