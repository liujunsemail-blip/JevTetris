/**
 * Tetromino: an active falling piece with a type, rotation state, and position.
 *
 * Position (row, col) is the top-left origin of the piece's 4x4 bounding box.
 * The absolute cells occupied are derived from the shape offsets for the
 * current rotation.
 */

class Tetromino {
  /**
   * @param {string} type One of PIECE_TYPES.
   * @param {number} row Origin row (can be negative while spawning).
   * @param {number} col Origin column.
   * @param {number} rotation Rotation state 0..3.
   */
  constructor(type, row, col, rotation = 0) {
    this.type = type;
    this.row = row;
    this.col = col;
    this.rotation = rotation;
  }

  /** Return the absolute [row, col] cells this piece occupies. */
  cells(rotation = this.rotation) {
    return PIECE_SHAPES[this.type][rotation].map(([r, c]) => [this.row + r, this.col + c]);
  }

  /** Return a copy of this piece. */
  clone() {
    return new Tetromino(this.type, this.row, this.col, this.rotation);
  }

  /** Next clockwise rotation index. */
  nextRotation() {
    return (this.rotation + 1) % 4;
  }
}

/** Create a new piece of the given type, spawned centered at the top. */
function spawnTetromino(type) {
  // Spawn so the 4x4 box is horizontally centered; row 0 at the top.
  const col = Math.floor((BOARD_COLS - 4) / 2);
  return new Tetromino(type, 0, col, 0);
}

/**
 * A simple 7-bag randomizer: each bag contains all 7 types shuffled, so the
 * player never sees long droughts or floods of one piece.
 */
class PieceBag {
  constructor() {
    this._queue = [];
  }

  _refill() {
    const bag = [...PIECE_TYPES];
    for (let i = bag.length - 1; i > 0; i -= 1) {
      const j = Math.floor(Math.random() * (i + 1));
      [bag[i], bag[j]] = [bag[j], bag[i]];
    }
    this._queue.push(...bag);
  }

  /** Peek at the next type without consuming it. */
  peek() {
    if (this._queue.length === 0) {
      this._refill();
    }
    return this._queue[0];
  }

  /** Take the next type from the bag. */
  next() {
    if (this._queue.length === 0) {
      this._refill();
    }
    return this._queue.shift();
  }
}
