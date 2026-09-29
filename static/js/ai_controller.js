/**
 * AiController: an AI input source, fully decoupled from the engine.
 *
 * The engine only offers three things this controller uses:
 *   - onPieceSpawned()  hook  -> we fire one AI decision request for the piece.
 *   - action commands rotate(pieceId)/moveLeft(pieceId)/moveRight(pieceId) which
 *     the engine IGNORES if pieceId no longer matches the active piece — so a
 *     late action can never drive the wrong piece.
 *   - onPieceLocked(info) hook -> tells us a piece has landed.
 *
 * Logging lives HERE (not in the engine). Each piece gets exactly ONE log entry,
 * emitted at whichever happens FIRST:
 *   1. AI returns before the piece locks  -> log immediately (in time), execute.
 *   2. The piece locks before AI returns   -> log immediately at lock (too late);
 *      when the API finally returns it is discarded (already logged).
 * A per-pieceId guard set makes this exactly-once.
 */

class AiController {
  /**
   * @param {Game} game The engine to drive.
   * @param {object} opts
   *   onLog(entry) — called with one UI log entry per piece.
   *   stepDelayMs  — ms between individual moves while animating a placement.
   */
  constructor(game, opts = {}) {
    this.game = game;
    this.onLog = opts.onLog || (() => {});
    this.stepDelayMs = opts.stepDelayMs ?? 60;
    this.enabled = false;
    this._logged = new Set(); // pieceIds already logged (exactly-once)
    this._counter = 0;
  }

  enable() { this.enabled = true; }
  disable() { this.enabled = false; }

  /** Reset per-game state (called on a fresh game). */
  reset() {
    this._logged.clear();
    this._counter = 0;
  }

  /** Serialize the board grid into the /api/decide request shape. */
  _serializeBoard() {
    return this.game.board.grid.map((row) => row.map((cell) => (cell === null ? 0 : 1)));
  }

  /** Emit exactly one log entry for a piece; ignores repeats. */
  _log(pieceId, entry) {
    if (this._logged.has(pieceId)) return;
    this._logged.add(pieceId);
    this._counter += 1;
    this.onLog({ index: this._counter, pieceId, ...entry });
  }

  /**
   * Engine hook: a piece locked. If the AI has not already logged this piece
   * (i.e. its decision did not arrive in time), log it NOW as gravity-placed.
   */
  onPieceLocked(info) {
    if (!this.enabled) return;
    if (this._logged.has(info.pieceId)) return; // AI already logged it in time
    this._log(info.pieceId, {
      piece: info.type,
      rotation: info.rotation,
      column: info.column,
      linesCleared: info.linesCleared,
      inTime: false, // AI did not return before the piece locked
    });
  }

  /**
   * Engine hook: a new piece spawned. Fire one AI decision request WITHOUT
   * blocking gravity. Whichever finishes first — this request or the piece
   * locking — produces the single log entry for this piece.
   */
  async onPieceSpawned() {
    if (!this.enabled || !this.game.active) return;
    const pieceType = this.game.active.type;
    const pieceId = this.game.pieceId;
    try {
      const res = await fetch('/api/decide', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          board: this._serializeBoard(),
          current_piece: pieceType,
          next_piece: this.game.nextType,
        }),
      });
      const data = await res.json();

      // The piece already locked (gravity won the race) OR we already logged it
      // at lock time: discard this decision — its log entry exists already.
      if (this._logged.has(pieceId) || !this.game.active || this.game.pieceId !== pieceId) {
        return;
      }

      // In time. Log it now (do not wait for the piece to land) and execute.
      if (data && data.decision) {
        this._log(pieceId, {
          piece: pieceType,
          rotation: data.decision.rotation,
          column: data.decision.column,
          source: data.source,
          latency_ms: data.latency_ms,
          reason: data.reason,
          inTime: true,
        });
        await this._execute(data.decision, pieceId);
      } else {
        // Backend returned no decision (e.g. error, no fallback). It arrived in
        // time but has nothing to execute; log it as a failed in-time attempt.
        this._log(pieceId, {
          piece: pieceType,
          source: data && data.source,
          latency_ms: data && data.latency_ms,
          reason: (data && data.reason) || 'no decision',
          inTime: true,
          failed: true,
        });
      }
    } catch (err) {
      if (!this._logged.has(pieceId)) {
        this._log(pieceId, {
          piece: pieceType,
          reason: `request failed: ${err && err.message ? err.message : err}`,
          inTime: true,
          failed: true,
        });
      }
      // eslint-disable-next-line no-console
      console.warn('AI decide failed:', err);
    }
  }

  _sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  /**
   * Drive the piece to the decided rotation + column using the engine's
   * pieceId-validated commands: rotate to the target orientation, slide it to
   * the target origin column, then HARD DROP so it locks immediately. All
   * commands are pieceId-gated, so if gravity locked the piece mid-way the
   * engine ignores them (and the hard drop cannot affect the next piece).
   */
  async _execute(decision, pieceId) {
    let guard = 0;
    while (this.game.pieceId === pieceId && this.game.active
           && this.game.active.rotation !== decision.rotation && guard < 4) {
      this.game.rotate(pieceId);
      guard += 1;
      await this._sleep(this.stepDelayMs);
    }
    // Slide to the target origin column, then drop and lock immediately.
    this.game.moveToColumn(pieceId, decision.origin_column);
    this.game.hardDrop(pieceId);
  }
}
