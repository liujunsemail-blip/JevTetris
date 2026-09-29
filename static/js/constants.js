/**
 * Game constants: board dimensions, tetromino shapes, and colors.
 *
 * Each tetromino is defined by its four rotation states. A rotation state is a
 * list of [row, col] offsets relative to the piece's top-left origin cell.
 */

const BOARD_COLS = 10;
const BOARD_ROWS = 20;
const CELL_SIZE = 38; // pixels; canvas is BOARD_COLS*CELL_SIZE by BOARD_ROWS*CELL_SIZE

// Color per piece type. Index 0 (empty) is null.
const PIECE_COLORS = {
  I: '#22d3ee', // cyan
  O: '#facc15', // yellow
  T: '#a855f7', // purple
  S: '#22c55e', // green
  Z: '#ef4444', // red
  J: '#3b82f6', // blue
  L: '#f97316', // orange
};

const PIECE_TYPES = ['I', 'O', 'T', 'S', 'Z', 'J', 'L'];

/**
 * Rotation states as [row, col] offsets. All shapes fit within a 4x4 box.
 * States are ordered 0 -> 1 -> 2 -> 3 (clockwise).
 */
const PIECE_SHAPES = {
  I: [
    [[1, 0], [1, 1], [1, 2], [1, 3]],
    [[0, 2], [1, 2], [2, 2], [3, 2]],
    [[2, 0], [2, 1], [2, 2], [2, 3]],
    [[0, 1], [1, 1], [2, 1], [3, 1]],
  ],
  O: [
    [[0, 1], [0, 2], [1, 1], [1, 2]],
    [[0, 1], [0, 2], [1, 1], [1, 2]],
    [[0, 1], [0, 2], [1, 1], [1, 2]],
    [[0, 1], [0, 2], [1, 1], [1, 2]],
  ],
  T: [
    [[0, 1], [1, 0], [1, 1], [1, 2]],
    [[0, 1], [1, 1], [1, 2], [2, 1]],
    [[1, 0], [1, 1], [1, 2], [2, 1]],
    [[0, 1], [1, 0], [1, 1], [2, 1]],
  ],
  S: [
    [[0, 1], [0, 2], [1, 0], [1, 1]],
    [[0, 1], [1, 1], [1, 2], [2, 2]],
    [[1, 1], [1, 2], [2, 0], [2, 1]],
    [[0, 0], [1, 0], [1, 1], [2, 1]],
  ],
  Z: [
    [[0, 0], [0, 1], [1, 1], [1, 2]],
    [[0, 2], [1, 1], [1, 2], [2, 1]],
    [[1, 0], [1, 1], [2, 1], [2, 2]],
    [[0, 1], [1, 0], [1, 1], [2, 0]],
  ],
  J: [
    [[0, 0], [1, 0], [1, 1], [1, 2]],
    [[0, 1], [0, 2], [1, 1], [2, 1]],
    [[1, 0], [1, 1], [1, 2], [2, 2]],
    [[0, 1], [1, 1], [2, 0], [2, 1]],
  ],
  L: [
    [[0, 2], [1, 0], [1, 1], [1, 2]],
    [[0, 1], [1, 1], [2, 1], [2, 2]],
    [[1, 0], [1, 1], [1, 2], [2, 0]],
    [[0, 0], [0, 1], [1, 1], [2, 1]],
  ],
};

// Line-clear scoring: index by number of lines cleared at once.
const LINE_SCORES = { 1: 100, 2: 300, 3: 500, 4: 800 };

// Speed: slider level (1..MAX) maps to a gravity interval in ms.
const SPEED_MIN_LEVEL = 1;
const SPEED_MAX_LEVEL = 10;
const SPEED_MAX_INTERVAL_MS = 800; // level 1 (slowest)
const SPEED_MIN_INTERVAL_MS = 80; // level 10 (fastest)

// Lock delay: once a piece is grounded (cannot fall further), the engine waits
// this long before locking it. During the window the piece can still be rotated
// or moved sideways (subject to collisions); if it manages to move down again,
// the window is cancelled and normal gravity resumes. Movement/rotation do NOT
// reset the timer, so a piece cannot be stalled indefinitely.
const LOCK_DELAY_MS = 500;

/** Convert a speed level (1..10) to a gravity interval in milliseconds. */
function speedLevelToInterval(level) {
  const clamped = Math.max(SPEED_MIN_LEVEL, Math.min(SPEED_MAX_LEVEL, level));
  const t = (clamped - SPEED_MIN_LEVEL) / (SPEED_MAX_LEVEL - SPEED_MIN_LEVEL);
  return Math.round(SPEED_MAX_INTERVAL_MS + t * (SPEED_MIN_INTERVAL_MS - SPEED_MAX_INTERVAL_MS));
}
