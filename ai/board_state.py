"""Pure board logic shared by the AI deciders (no framework dependencies).

Mirrors the frontend's board/piece model so the backend can simulate landing a
piece and measure the resulting board. Coordinates: row 0 is the top.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

BOARD_ROWS = 20
BOARD_COLS = 10

# Rotation states as [row, col] offsets, matching static/js/constants.js.
PIECE_SHAPES: Dict[str, List[List[Tuple[int, int]]]] = {
    "I": [
        [(1, 0), (1, 1), (1, 2), (1, 3)],
        [(0, 2), (1, 2), (2, 2), (3, 2)],
        [(2, 0), (2, 1), (2, 2), (2, 3)],
        [(0, 1), (1, 1), (2, 1), (3, 1)],
    ],
    "O": [
        [(0, 1), (0, 2), (1, 1), (1, 2)],
        [(0, 1), (0, 2), (1, 1), (1, 2)],
        [(0, 1), (0, 2), (1, 1), (1, 2)],
        [(0, 1), (0, 2), (1, 1), (1, 2)],
    ],
    "T": [
        [(0, 1), (1, 0), (1, 1), (1, 2)],
        [(0, 1), (1, 1), (1, 2), (2, 1)],
        [(1, 0), (1, 1), (1, 2), (2, 1)],
        [(0, 1), (1, 0), (1, 1), (2, 1)],
    ],
    "S": [
        [(0, 1), (0, 2), (1, 0), (1, 1)],
        [(0, 1), (1, 1), (1, 2), (2, 2)],
        [(1, 1), (1, 2), (2, 0), (2, 1)],
        [(0, 0), (1, 0), (1, 1), (2, 1)],
    ],
    "Z": [
        [(0, 0), (0, 1), (1, 1), (1, 2)],
        [(0, 2), (1, 1), (1, 2), (2, 1)],
        [(1, 0), (1, 1), (2, 1), (2, 2)],
        [(0, 1), (1, 0), (1, 1), (2, 0)],
    ],
    "J": [
        [(0, 0), (1, 0), (1, 1), (1, 2)],
        [(0, 1), (0, 2), (1, 1), (2, 1)],
        [(1, 0), (1, 1), (1, 2), (2, 2)],
        [(0, 1), (1, 1), (2, 0), (2, 1)],
    ],
    "L": [
        [(0, 2), (1, 0), (1, 1), (1, 2)],
        [(0, 1), (1, 1), (2, 1), (2, 2)],
        [(1, 0), (1, 1), (1, 2), (2, 0)],
        [(0, 0), (0, 1), (1, 1), (2, 1)],
    ],
}

Grid = List[List[int]]  # 0 = empty, non-zero = occupied


@dataclass
class Placement:
    """A candidate final resting position for a piece."""

    rotation: int
    column: int  # origin column of the piece's 4x4 bounding box (may be negative)
    cells: List[Tuple[int, int]] = field(default_factory=list)  # absolute [row, col]
    left_col: int = 0  # actual leftmost occupied column (0..9), for prompt/UI


@dataclass
class PlacementMetrics:
    """Features measured on the board after a placement lands."""

    lines_cleared: int
    aggregate_height: int
    holes: int
    bumpiness: int
    landing_height: int = 0
    max_height: int = 0
    # The board after the piece locks and full rows are removed (0/1 grid,
    # BOARD_ROWS x BOARD_COLS). Lets callers render the resulting board.
    grid_after: Grid = field(default_factory=list)
    # Per-column heights (length BOARD_COLS) of the result, left to right.
    heights: List[int] = field(default_factory=list)


def _normalize_grid(board: Grid) -> Grid:
    """Coerce input to a BOARD_ROWS x BOARD_COLS int grid (0/1)."""
    grid = [[0] * BOARD_COLS for _ in range(BOARD_ROWS)]
    for r in range(min(BOARD_ROWS, len(board))):
        row = board[r]
        for c in range(min(BOARD_COLS, len(row))):
            grid[r][c] = 1 if row[c] else 0
    return grid


def _piece_cells(piece_type: str, rotation: int, row: int, col: int) -> List[Tuple[int, int]]:
    return [(row + dr, col + dc) for dr, dc in PIECE_SHAPES[piece_type][rotation]]


def _collides(grid: Grid, cells: List[Tuple[int, int]]) -> bool:
    for r, c in cells:
        if c < 0 or c >= BOARD_COLS or r >= BOARD_ROWS:
            return True
        if r >= 0 and grid[r][c]:
            return True
    return False


def enumerate_placements(board: Grid, piece_type: str) -> List[Placement]:
    """Return every legal final resting placement for the piece on the board.

    For each rotation and horizontal offset, drop the piece as far as it goes
    and record where it lands (if the landing is legal).
    """
    grid = _normalize_grid(board)
    placements: List[Placement] = []
    seen = set()
    rotations = PIECE_SHAPES[piece_type]
    for rot in range(len(rotations)):
        # Column range: any origin col from far left to far right; illegal ones filtered.
        for col in range(-2, BOARD_COLS + 1):
            # start above the board and drop until the next step would collide
            row = -4
            # ensure the starting position itself isn't already colliding sideways
            start_cells = _piece_cells(piece_type, rot, row, col)
            if any(c < 0 or c >= BOARD_COLS for _, c in start_cells):
                continue
            landing_row = None
            while True:
                cells = _piece_cells(piece_type, rot, row + 1, col)
                if _collides(grid, cells):
                    landing_row = row
                    break
                row += 1
                if row > BOARD_ROWS:
                    break
            if landing_row is None:
                continue
            final_cells = _piece_cells(piece_type, rot, landing_row, col)
            if _collides(grid, final_cells):
                continue
            if any(r < 0 for r, _ in final_cells):
                continue  # landed partly off the top => invalid / game over spot
            key = tuple(sorted(final_cells))
            if key in seen:
                continue
            seen.add(key)
            left_col = min(c for _, c in final_cells)
            placements.append(
                Placement(rotation=rot, column=col, cells=final_cells, left_col=left_col)
            )
    return placements


def render_piece_shape(piece_type: str, rotation: int) -> str:
    """Render one rotation state of a piece as a tight 2D grid of '#' and '.'.

    Trimmed to the piece's occupied bounding box so the shape is unambiguous
    without the model needing to know what 'O' or 'L' means.
    """
    offsets = PIECE_SHAPES[piece_type][rotation]
    rows = [r for r, _ in offsets]
    cols = [c for _, c in offsets]
    r0, r1 = min(rows), max(rows)
    c0, c1 = min(cols), max(cols)
    occupied = set(offsets)
    lines = []
    for r in range(r0, r1 + 1):
        lines.append("".join("#" if (r, c) in occupied else "_" for c in range(c0, c1 + 1)))
    return "\n".join(lines)


def render_board_with_piece(board: Grid, piece_type: str) -> str:
    """Render the board with the CURRENT piece drawn at its spawn position on top.

    The active piece (rotation 0, spawn column) is marked with '@' so the model
    sees it as a distinct, just-spawned piece sitting above the stack. Already
    locked blocks are '#', empty is '_'. Row 0 is the top. Columns 0-9.
    """
    grid = _normalize_grid(board)
    # Spawn cells: rotation 0 at row 0, using the piece's own column offsets.
    spawn_cells = set(PIECE_SHAPES[piece_type][0])  # (r, c) offsets, rows 0-1ish
    header = "   " + "".join(str(c) for c in range(BOARD_COLS))
    lines = [header]
    for r in range(BOARD_ROWS):
        chars = []
        for c in range(BOARD_COLS):
            if (r, c) in spawn_cells:
                chars.append("@")
            elif grid[r][c]:
                chars.append("#")
            else:
                chars.append("_")
        lines.append(f"{r:2d} {''.join(chars)}")
    return "\n".join(lines)


def render_board_ascii(board: Grid) -> str:
    """Render the current board as an ASCII grid for the model.

    Row 0 is the top. 'X' = filled, '.' = empty. Columns are 0..9 left to right.
    """
    grid = _normalize_grid(board)
    header = "   " + "".join(str(c) for c in range(BOARD_COLS))
    lines = [header]
    for r in range(BOARD_ROWS):
        row = "".join("#" if grid[r][c] else "_" for c in range(BOARD_COLS))
        lines.append(f"{r:2d} {row}")
    return "\n".join(lines)


def describe_placement(piece_type: str, placement: "Placement") -> str:
    """Human-readable semantics for one candidate placement.

    Spells out the clockwise rotation count and exactly which columns/rows the
    piece's four cells occupy after it lands, so the model has no ambiguity
    about what the option means.
    """
    cols = sorted({c for _, c in placement.cells})
    rows = sorted({r for r, _ in placement.cells})
    col_span = f"columns {cols[0]}-{cols[-1]}" if len(cols) > 1 else f"column {cols[0]}"
    rot_desc = {
        0: "no rotation (spawn orientation)",
        1: "rotated clockwise once (90°)",
        2: "rotated clockwise twice (180°)",
        3: "rotated clockwise three times (270°)",
    }[placement.rotation]
    return (
        f"piece {piece_type} {rot_desc}, occupying {col_span} "
        f"(leftmost column {cols[0]}), landing across rows {rows[0]}-{rows[-1]}"
    )


def apply_and_measure(board: Grid, cells: List[Tuple[int, int]]) -> PlacementMetrics:
    """Lock the given cells into a copy of the board and measure features."""
    grid = _normalize_grid(board)
    for r, c in cells:
        if 0 <= r < BOARD_ROWS and 0 <= c < BOARD_COLS:
            grid[r][c] = 1

    # line clears
    surviving = [row for row in grid if not all(row)]
    lines_cleared = BOARD_ROWS - len(surviving)
    cleared_grid = [[0] * BOARD_COLS for _ in range(lines_cleared)] + surviving

    # column heights
    heights = [0] * BOARD_COLS
    for c in range(BOARD_COLS):
        for r in range(BOARD_ROWS):
            if cleared_grid[r][c]:
                heights[c] = BOARD_ROWS - r
                break

    aggregate_height = sum(heights)
    max_height = max(heights) if heights else 0

    # holes: empty cell with a filled cell somewhere above it in the same column
    holes = 0
    for c in range(BOARD_COLS):
        block_seen = False
        for r in range(BOARD_ROWS):
            if cleared_grid[r][c]:
                block_seen = True
            elif block_seen:
                holes += 1

    # bumpiness: sum of abs height diffs between adjacent columns
    bumpiness = sum(abs(heights[c] - heights[c + 1]) for c in range(BOARD_COLS - 1))

    # landing height: how high the piece came to rest (higher = worse).
    # Measured from the placed cells before line clears, as height-from-bottom.
    placed_rows = [r for r, _ in cells if 0 <= r < BOARD_ROWS]
    landing_height = (BOARD_ROWS - min(placed_rows)) if placed_rows else 0

    return PlacementMetrics(
        lines_cleared=lines_cleared,
        aggregate_height=aggregate_height,
        holes=holes,
        bumpiness=bumpiness,
        landing_height=landing_height,
        max_height=max_height,
        grid_after=cleared_grid,
        heights=heights,
    )


def render_grid_ascii(grid: Grid) -> str:
    """Render a 0/1 grid as rows of '#'/'_', top to bottom, with row/col headers.

    Used to show the model the board that RESULTS from a candidate placement.
    """
    header = "   " + "".join(str(c) for c in range(BOARD_COLS))
    lines = [header]
    for r in range(BOARD_ROWS):
        row = grid[r] if r < len(grid) else [0] * BOARD_COLS
        lines.append(f"{r:2d} " + "".join("#" if row[c] else "_" for c in range(BOARD_COLS)))
    return "\n".join(lines)
