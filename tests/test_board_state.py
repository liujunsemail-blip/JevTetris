"""Unit tests for board_state placement enumeration and measurement."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ai.board_state import (  # noqa: E402
    BOARD_COLS,
    BOARD_ROWS,
    apply_and_measure,
    enumerate_placements,
)


def _empty_board():
    return [[0] * BOARD_COLS for _ in range(BOARD_ROWS)]


def test_enumerate_nonempty_and_in_bounds():
    for piece in ["I", "O", "T", "S", "Z", "J", "L"]:
        placements = enumerate_placements(_empty_board(), piece)
        assert placements, f"{piece} should have placements"
        for p in placements:
            for r, c in p.cells:
                assert 0 <= r < BOARD_ROWS, f"{piece} row {r} out of bounds"
                assert 0 <= c < BOARD_COLS, f"{piece} col {c} out of bounds"


def test_o_piece_placement_count():
    # An O piece has one effective rotation; it can sit in 9 horizontal positions.
    placements = enumerate_placements(_empty_board(), "O")
    columns = {tuple(sorted(c for _, c in p.cells)) for p in placements}
    assert len(columns) == BOARD_COLS - 1  # 9 distinct 2-wide positions


def test_line_clear_measured():
    board = _empty_board()
    # Fill bottom row except column 0.
    for c in range(1, BOARD_COLS):
        board[BOARD_ROWS - 1][c] = 1
    # Drop a cell into column 0 bottom => clears the row.
    metrics = apply_and_measure(board, [(BOARD_ROWS - 1, 0)])
    assert metrics.lines_cleared == 1
    assert metrics.aggregate_height == 0  # row cleared => empty board
    assert metrics.holes == 0


def test_holes_measured():
    board = _empty_board()
    # Put a block at top of column 0, leave the cell below empty => 1 hole beneath.
    metrics = apply_and_measure(board, [(0, 0)])
    # column 0 has a block at row 0 and empties below => many holes counted below it
    assert metrics.holes == BOARD_ROWS - 1


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
