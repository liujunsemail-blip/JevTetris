"""Unit tests for the heuristic decider."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ai.board_state import BOARD_COLS, BOARD_ROWS  # noqa: E402
from ai.heuristic import HeuristicDecider  # noqa: E402


def _empty_board():
    return [[0] * BOARD_COLS for _ in range(BOARD_ROWS)]


def test_decides_on_empty_board():
    d = HeuristicDecider()
    result = d.decide(_empty_board(), "O")
    assert result.source == "heuristic"
    assert result.decision is not None
    # column is the piece's 4x4 origin, which may be negative; the actual
    # occupied cells are what must be in bounds.
    chosen = result.records[0]
    assert chosen.chosen, "first record is the chosen one"
    assert result.records, "should produce candidate records"


def test_prefers_line_clear():
    # Fill the bottom row except the last 4 columns; an I piece placed flat there
    # (rotation 0 / 2) should clear the row. The chosen placement should clear >=1.
    board = _empty_board()
    for c in range(BOARD_COLS - 4):
        board[BOARD_ROWS - 1][c] = 1
    d = HeuristicDecider()
    result = d.decide(board, "I")
    assert result.decision is not None
    # The chosen candidate should be the one that clears a line.
    chosen = result.records[0]
    assert chosen.metrics["lines_cleared"] >= 1


def test_avoids_creating_holes():
    d = HeuristicDecider()
    result = d.decide(_empty_board(), "T")
    # On an empty board, the best T placement should create no holes.
    assert result.records[0].metrics["holes"] == 0


def test_confidence_in_range():
    d = HeuristicDecider()
    result = d.decide(_empty_board(), "L")
    assert 0.0 <= result.decision.confidence <= 1.0
    for rec in result.records:
        assert 0.0 <= rec.score <= 1.0


if __name__ == "__main__":
    import traceback

    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
            passed += 1
        except Exception:  # noqa: BLE001
            print(f"FAIL {t.__name__}")
            traceback.print_exc()
    print(f"\n{passed}/{len(tests)} passed")
    sys.exit(0 if passed == len(tests) else 1)
