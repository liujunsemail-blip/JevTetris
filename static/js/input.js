/**
 * KeyboardInput: a human input source. Translates key events into engine action
 * commands. The engine does not know or care that input comes from a keyboard.
 *
 *   Arrow Left / Right : move
 *   Arrow Up           : rotate
 *   Arrow Down         : soft drop
 *   Space              : hard drop
 *   P                  : pause / resume
 */

class KeyboardInput {
  /**
   * @param {Game} game The engine to drive.
   */
  constructor(game) {
    this.game = game;
    this._handler = this._onKeyDown.bind(this);
    this._enabled = false;
  }

  enable() {
    if (this._enabled) return;
    window.addEventListener('keydown', this._handler);
    this._enabled = true;
  }

  disable() {
    if (!this._enabled) return;
    window.removeEventListener('keydown', this._handler);
    this._enabled = false;
  }

  _onKeyDown(event) {
    switch (event.key) {
      case 'ArrowLeft':
        this.game.moveLeft();
        event.preventDefault();
        break;
      case 'ArrowRight':
        this.game.moveRight();
        event.preventDefault();
        break;
      case 'ArrowUp':
        this.game.rotate();
        event.preventDefault();
        break;
      case 'ArrowDown':
        this.game.softDrop();
        event.preventDefault();
        break;
      case ' ':
        this.game.hardDrop();
        event.preventDefault();
        break;
      case 'p':
      case 'P':
        // Dispatch by state so P mirrors the Pause/Resume button: pause a
        // running game, resume a paused one (start() resumes from PAUSED
        // without resetting the board). No-op in OVER/READY.
        if (this.game.state === GameState.PAUSED) {
          this.game.start();
        } else {
          this.game.togglePause();
        }
        event.preventDefault();
        break;
      default:
        break;
    }
  }
}
