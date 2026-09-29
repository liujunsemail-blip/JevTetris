/**
 * Renderer: draws the board, the active piece, a ghost drop preview, and
 * overlays (paused / game over) onto a canvas. Also renders the "next" preview.
 */

class Renderer {
  /**
   * @param {HTMLCanvasElement} canvas Main board canvas.
   * @param {HTMLCanvasElement} nextCanvas Small next-piece preview canvas.
   */
  constructor(canvas, nextCanvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.nextCanvas = nextCanvas;
    this.nextCtx = nextCanvas ? nextCanvas.getContext('2d') : null;
  }

  /** Draw a single cell with a subtle bevel. */
  _drawCell(ctx, col, row, color, size = CELL_SIZE) {
    const x = col * size;
    const y = row * size;
    ctx.fillStyle = color;
    ctx.fillRect(x, y, size, size);
    // inner highlight
    ctx.fillStyle = 'rgba(255,255,255,0.18)';
    ctx.fillRect(x, y, size, size * 0.18);
    // inner shadow
    ctx.fillStyle = 'rgba(0,0,0,0.25)';
    ctx.fillRect(x, y + size * 0.82, size, size * 0.18);
    // border
    ctx.strokeStyle = 'rgba(0,0,0,0.35)';
    ctx.lineWidth = 1;
    ctx.strokeRect(x + 0.5, y + 0.5, size - 1, size - 1);
  }

  _drawGrid() {
    const { ctx, canvas } = this;
    ctx.strokeStyle = 'rgba(255,255,255,0.05)';
    ctx.lineWidth = 1;
    for (let c = 0; c <= BOARD_COLS; c += 1) {
      ctx.beginPath();
      ctx.moveTo(c * CELL_SIZE + 0.5, 0);
      ctx.lineTo(c * CELL_SIZE + 0.5, canvas.height);
      ctx.stroke();
    }
    for (let r = 0; r <= BOARD_ROWS; r += 1) {
      ctx.beginPath();
      ctx.moveTo(0, r * CELL_SIZE + 0.5);
      ctx.lineTo(canvas.width, r * CELL_SIZE + 0.5);
      ctx.stroke();
    }
  }

  /** Full render of the current game state. */
  render(game) {
    const { ctx, canvas } = this;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = '#0b0f1a';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    this._drawGrid();

    // locked cells
    for (let r = 0; r < game.board.rows; r += 1) {
      for (let c = 0; c < game.board.cols; c += 1) {
        const type = game.board.grid[r][c];
        if (type) this._drawCell(ctx, c, r, PIECE_COLORS[type]);
      }
    }

    // ghost + active piece
    if (game.active) {
      const ghost = game.active.clone();
      while (true) {
        ghost.row += 1;
        if (game.board.collides(ghost)) {
          ghost.row -= 1;
          break;
        }
      }
      ctx.globalAlpha = 0.25;
      for (const [r, c] of ghost.cells()) {
        if (r >= 0) this._drawCell(ctx, c, r, PIECE_COLORS[game.active.type]);
      }
      ctx.globalAlpha = 1;
      for (const [r, c] of game.active.cells()) {
        if (r >= 0) this._drawCell(ctx, c, r, PIECE_COLORS[game.active.type]);
      }
    }

    if (game.state === GameState.PAUSED) this._overlay(i18n.t('overlay.paused'));
    if (game.state === GameState.OVER) {
      this._overlay(i18n.t('overlay.gameover'), i18n.t('overlay.finalScore', { score: game.score }));
    }

    this._renderNext(game.nextType);
  }

  _renderNext(type) {
    if (!this.nextCtx) return;
    const ctx = this.nextCtx;
    const { width, height } = this.nextCanvas;
    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = '#0b0f1a';
    ctx.fillRect(0, 0, width, height);
    if (!type) return;
    const size = 26;
    const cells = PIECE_SHAPES[type][0];
    // center the shape in the preview box
    const rows = cells.map(([r]) => r);
    const cols = cells.map(([, c]) => c);
    const minR = Math.min(...rows);
    const minC = Math.min(...cols);
    const spanR = Math.max(...rows) - minR + 1;
    const spanC = Math.max(...cols) - minC + 1;
    const offX = (width - spanC * size) / 2;
    const offY = (height - spanR * size) / 2;
    for (const [r, c] of cells) {
      const x = offX + (c - minC) * size;
      const y = offY + (r - minR) * size;
      ctx.fillStyle = PIECE_COLORS[type];
      ctx.fillRect(x, y, size, size);
      ctx.strokeStyle = 'rgba(0,0,0,0.35)';
      ctx.strokeRect(x + 0.5, y + 0.5, size - 1, size - 1);
    }
  }

  _overlay(text, subtitle = null) {
    const { ctx, canvas } = this;
    ctx.fillStyle = 'rgba(5,8,16,0.78)';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = '#22d3ee';
    ctx.font = 'bold 34px system-ui, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(text, canvas.width / 2, canvas.height / 2 - 10);
    if (subtitle !== null) {
      ctx.fillStyle = '#e5e7eb';
      ctx.font = '18px system-ui, sans-serif';
      ctx.fillText(subtitle, canvas.width / 2, canvas.height / 2 + 24);
    }
    ctx.textAlign = 'start';
  }
}
