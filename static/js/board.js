/**
 * Board: the static grid of locked cells, plus collision and line-clear logic.
 *
 * The grid is a 2D array of BOARD_ROWS x BOARD_COLS. Each cell is either null
 * (empty) or a piece type string (occupied, used for color).
 */

class Board {
  constructor(rows = BOARD_ROWS, cols = BOARD_COLS) {
    this.rows = rows;
    this.cols = cols;
    this.grid = Board._emptyGrid(rows, cols);
  }

  static _emptyGrid(rows, cols) {
    return Array.from({ length: rows }, () => new Array(cols).fill(null));
  }

  /** Reset the board to empty. */
  reset() {
    this.grid = Board._emptyGrid(this.rows, this.cols);
  }

  /** True if [row, col] is inside the board bounds. */
  inBounds(row, col) {
    return row >= 0 && row < this.rows && col >= 0 && col < this.cols;
  }

  /**
   * True if the piece at the given rotation collides with a wall, the floor,
   * or a locked cell.
   */
  collides(piece, rotation = piece.rotation) {
    for (const [r, c] of piece.cells(rotation)) {
      if (c < 0 || c >= this.cols || r >= this.rows) {
        return true; // wall or floor
      }
      if (r >= 0 && this.grid[r][c] !== null) {
        return true; // overlaps a locked cell
      }
    }
    return false;
  }

  /** Lock the piece's cells into the grid. */
  lock(piece) {
    for (const [r, c] of piece.cells()) {
      if (this.inBounds(r, c)) {
        this.grid[r][c] = piece.type;
      }
    }
  }

  /**
   * Clear any full rows and drop the rows above down.
   * @returns {number} the number of rows cleared.
   */
  clearLines() {
    const surviving = this.grid.filter((row) => row.some((cell) => cell === null));
    const cleared = this.rows - surviving.length;
    if (cleared > 0) {
      const empty = Board._emptyGrid(cleared, this.cols);
      this.grid = empty.concat(surviving);
    }
    return cleared;
  }
}
