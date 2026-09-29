/**
 * Game: the engine. Owns the board, the active piece, gravity, and scoring.
 *
 * The engine is decoupled from input: it exposes a set of action commands
 * (moveLeft/moveRight/rotate/softDrop/hardDrop) that any input source — human
 * keyboard or AI controller — calls. The engine's own gravity loop advances the
 * piece downward independently of those commands.
 */

const GameState = {
  READY: 'ready',
  RUNNING: 'running',
  PAUSED: 'paused',
  OVER: 'over',
};

class Game {
  /**
   * @param {object} callbacks Optional hooks:
   *   onUpdate(game)       — called after any state change (for rendering).
   *   onScore(score, best) — called when the score changes.
   *   onPieceSpawned(game) — called when a new active piece appears.
   *   onGameOver(game)     — called when the game ends.
   */
  constructor(callbacks = {}) {
    this.board = new Board();
    this.bag = new PieceBag();
    this.active = null;
    this.nextType = null;
    this.pieceId = 0;
    this.score = 0;
    this.best = 0;
    this.linesCleared = 0;
    this.state = GameState.READY;
    this.gravityInterval = speedLevelToInterval(SPEED_MAX_LEVEL - 5);
    this._accumulator = 0;
    // Lock delay: when the active piece is grounded (cannot fall), we accumulate
    // time here instead of locking immediately. Rotation/side moves stay legal
    // during the window; a successful downward move cancels it.
    this._grounded = false;
    this._lockTimer = 0;
    this._lastFrame = 0;
    this._rafId = null;
    this.callbacks = callbacks;
  }

  // --- lifecycle -----------------------------------------------------------

  /** Start the game. Behavior by state:
   *   RUNNING -> ignored (a repeated start must not spin up a second gravity
   *              loop, which would run gravity/lock timing twice and double the
   *              speed).
   *   PAUSED  -> RESUME from where it was paused; the board/score are kept.
   *   OVER / READY -> start a brand-new game.
   */
  start() {
    if (this.state === GameState.RUNNING) {
      return;
    }
    if (this.state === GameState.PAUSED) {
      // Resume: restart the loop without touching the board or score. Reset the
      // frame clock so the paused wall-time doesn't count as one huge dt.
      this._stopLoop();
      this.state = GameState.RUNNING;
      this._lastFrame = performance.now();
      this._loop(this._lastFrame);
      this._emitUpdate();
      return;
    }
    this._stopLoop();
    this.board.reset();
    this.score = 0;
    this.linesCleared = 0;
    this.active = null;
    this.nextType = this.bag.peek();
    this.state = GameState.RUNNING;
    this._spawn();
    this._accumulator = 0;
    this._grounded = false;
    this._lockTimer = 0;
    this._lastFrame = performance.now();
    this._emitScore();
    this._loop(this._lastFrame);
  }

  /** Force a brand-new game from ANY state (RUNNING, PAUSED, OVER, READY).
   * Unlike start(), this is not gated — it stops any running loop, then begins
   * a fresh game. Used by the Start/Restart button while a game is live. */
  restart() {
    this._stopLoop();
    this.state = GameState.OVER; // drop any guard so start() runs the fresh-game path
    this.start();
  }

  /** Reset everything to the initial READY state from ANY state: stop the loop,
   * clear the board/score/lines, drop the active piece, rebuild a fresh piece
   * bag (so the "next" preview is empty too), and DO NOT start playing. The
   * engine sits idle showing an empty board until start() is called. Preferences
   * (mode/language/speed) and the best score are NOT touched here. */
  reset() {
    this._stopLoop();
    this.board.reset();
    this.bag = new PieceBag(); // fresh 7-bag: no carried-over queue
    this.score = 0;
    this.linesCleared = 0;
    this.active = null;
    this.nextType = null; // clear the next-piece preview
    this._accumulator = 0;
    this._grounded = false;
    this._lockTimer = 0;
    this.state = GameState.READY;
    this._emitScore();
    this._emitUpdate();
  }

  /** Pause a running game. Ignored if already PAUSED or if the game is OVER
   * (or READY) — this only pauses, it does not resume. To resume from PAUSED,
   * call start(), which resumes without resetting the board. */
  togglePause() {
    if (this.state === GameState.RUNNING) {
      this.state = GameState.PAUSED;
      this._stopLoop();
    }
    this._emitUpdate();
  }

  /** Stop the game entirely and mark it over. */
  stop() {
    this._stopLoop();
    this.state = GameState.OVER;
    this._emitUpdate();
  }

  // --- action commands (called by input sources) --------------------------
  //
  // Each accepts an OPTIONAL pieceId. When provided (e.g. by the AI, which
  // decided for a specific piece), the command is IGNORED if it no longer
  // matches the active piece — so a late AI action can never drive the wrong
  // piece. Human input omits pieceId and is never gated this way.

  /** True if the command may act: game running, a piece active, and (if a
   * pieceId was supplied) it still matches the active piece. */
  _actionAllowed(pieceId) {
    if (!this._canAct()) return false;
    if (pieceId !== undefined && pieceId !== this.pieceId) return false;
    return true;
  }

  moveLeft(pieceId) {
    if (!this._actionAllowed(pieceId)) return false;
    return this._tryMove(0, -1);
  }

  moveRight(pieceId) {
    if (!this._actionAllowed(pieceId)) return false;
    return this._tryMove(0, 1);
  }

  /** Move down one row; returns true if it moved, false if blocked/ignored. */
  softDrop(pieceId) {
    if (!this._actionAllowed(pieceId)) return false;
    return this._tryMove(1, 0);
  }

  /** Drop straight to the bottom and lock immediately. */
  hardDrop(pieceId) {
    if (!this._actionAllowed(pieceId)) return;
    while (this._tryMove(1, 0)) {
      // keep falling
    }
    this._lockAndNext();
  }

  rotate(pieceId) {
    if (!this._actionAllowed(pieceId) || !this.active) return;
    const next = this.active.nextRotation();
    // Basic wall kick: try in place, then nudge left/right by 1-2 columns.
    for (const dc of [0, -1, 1, -2, 2]) {
      const test = this.active.clone();
      test.col += dc;
      if (!this.board.collides(test, next)) {
        this.active.col += dc;
        this.active.rotation = next;
        if (this._grounded) this._refreshGrounded();
        this._emitUpdate();
        return;
      }
    }
  }

  /** Move the active piece so its ORIGIN column reaches targetCol, one step at a
   * time, stopping if blocked. Intended for the AI (it decides a whole column at
   * once); humans use single-step moveLeft/moveRight. Ignored if pieceId does
   * not match the active piece. Returns the origin column actually reached. */
  moveToColumn(pieceId, targetCol) {
    if (!this._actionAllowed(pieceId) || !this.active) return null;
    let guard = 0;
    while (this.active.col !== targetCol && guard < BOARD_COLS + 4) {
      const dc = this.active.col < targetCol ? 1 : -1;
      if (!this._tryMove(0, dc)) break; // blocked: stop where we are
      guard += 1;
    }
    return this.active ? this.active.col : null;
  }

  // --- speed ---------------------------------------------------------------

  /** Set gravity speed from a slider level (1..10). */
  setSpeedLevel(level) {
    this.gravityInterval = speedLevelToInterval(level);
  }

  // --- internals -----------------------------------------------------------

  _canAct() {
    return this.state === GameState.RUNNING && this.active !== null;
  }

  _tryMove(dr, dc) {
    if (!this._canAct()) return false;
    const test = this.active.clone();
    test.row += dr;
    test.col += dc;
    if (!this.board.collides(test)) {
      this.active.row += dr;
      this.active.col += dc;
      if (this._grounded) this._refreshGrounded();
      this._emitUpdate();
      return true;
    }
    return false;
  }

  _spawn() {
    const type = this.bag.next();
    this.nextType = this.bag.peek();
    this.active = spawnTetromino(type);
    // Monotonic id identifying THIS spawned piece. Lets an async input source
    // (the AI) detect that a late decision refers to a piece that has already
    // locked, so it can discard that decision instead of acting on the wrong one.
    this.pieceId = (this.pieceId || 0) + 1;
    // Game over if the fresh piece already collides.
    if (this.board.collides(this.active)) {
      this.active = null;
      this._gameOver();
      return;
    }
    if (this.callbacks.onPieceSpawned) {
      this.callbacks.onPieceSpawned(this);
    }
    this._emitUpdate();
  }

  _lockAndNext() {
    this.board.lock(this.active);
    // Snapshot what actually locked, for UI logging (independent of any AI call).
    const lockedCells = this.active.cells();
    const lockedInfo = {
      type: this.active.type,
      rotation: this.active.rotation,
      column: Math.min(...lockedCells.map(([, c]) => c)), // leftmost occupied column
      pieceId: this.pieceId, // identity of the piece that just locked
    };
    const cleared = this.board.clearLines();
    if (cleared > 0) {
      this.linesCleared += cleared;
      this.score += LINE_SCORES[cleared] || 0;
      if (this.score > this.best) {
        this.best = this.score;
      }
      this._emitScore();
    }
    lockedInfo.linesCleared = cleared;
    if (this.callbacks.onPieceLocked) {
      this.callbacks.onPieceLocked(lockedInfo);
    }
    this.active = null;
    // Clear the lock-delay window for the piece that just locked; the next
    // piece starts falling fresh.
    this._grounded = false;
    this._lockTimer = 0;
    this._accumulator = 0;
    this._spawn();
  }

  _gameOver() {
    this._stopLoop();
    this.state = GameState.OVER;
    if (this.callbacks.onGameOver) {
      this.callbacks.onGameOver(this);
    }
    this._emitUpdate();
  }

  _loop(now) {
    if (this.state !== GameState.RUNNING) return;
    const dt = now - this._lastFrame;
    this._lastFrame = now;

    if (this._grounded) {
      // Piece is resting on the stack: run the lock-delay clock instead of
      // gravity. Rotation/side moves during this window may free it (see
      // _tryMove / rotate, which clear _grounded when the piece can fall again).
      this._lockTimer += dt;
      if (this._lockTimer >= LOCK_DELAY_MS) {
        this._lockAndNext();
      }
    } else {
      this._accumulator += dt;
      while (this._accumulator >= this.gravityInterval) {
        this._accumulator -= this.gravityInterval;
        this._gravityStep();
        if (this.state !== GameState.RUNNING || this._grounded) break;
      }
    }
    this._rafId = requestAnimationFrame((t) => this._loop(t));
  }

  _gravityStep() {
    if (!this.active) return;
    // Try to fall one row. If blocked, the piece is grounded: start (or keep)
    // the lock-delay window rather than locking immediately, so it can still be
    // rotated or nudged sideways before it locks.
    const moved = this._tryMove(1, 0);
    if (!moved) {
      this._grounded = true;
    }
  }

  /** Re-evaluate whether the active piece is still resting on something.
   * Called after a rotation or side move during the lock-delay window: if the
   * piece can now fall, cancel the window and resume gravity; the timer is NOT
   * reset otherwise, so moves cannot stall the lock indefinitely. */
  _refreshGrounded() {
    if (!this.active) return;
    const test = this.active.clone();
    test.row += 1;
    if (!this.board.collides(test)) {
      this._grounded = false;
      this._lockTimer = 0;
    }
  }

  _stopLoop() {
    if (this._rafId !== null) {
      cancelAnimationFrame(this._rafId);
      this._rafId = null;
    }
  }

  _emitUpdate() {
    if (this.callbacks.onUpdate) this.callbacks.onUpdate(this);
  }

  _emitScore() {
    if (this.callbacks.onScore) this.callbacks.onScore(this.score, this.best);
  }
}
