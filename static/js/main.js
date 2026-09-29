/**
 * main.js: wires the engine, renderer, input sources (keyboard + AI), i18n, and
 * the AI decision panel to the DOM.
 *
 * Modes:
 *   - "ai" (default): the AiController drives the piece via /api/decide; the
 *     decision panel is shown and each decision is logged.
 *   - "human": keyboard drives the piece; the decision panel is hidden.
 * Switching mode swaps the active input source; the engine is unchanged.
 */

const MODE_STORAGE_KEY = 'tetris.mode';

async function main() {
  await i18n.load();

  const el = (id) => document.getElementById(id);
  const canvas = el('board');
  const nextCanvas = el('next');
  const scoreEl = el('score');
  const bestEl = el('best');
  const linesEl = el('lines');
  const speedSlider = el('speed');
  const speedValueEl = el('speed-value');
  const startBtn = el('btn-start');
  const pauseBtn = el('btn-pause');
  const resetBtn = el('btn-reset');
  const languageSelect = el('language');
  const modeSelect = el('mode');
  const aiPanel = el('ai-panel');
  const aiLog = el('ai-log');
  const sourceBadge = el('source-badge');

  const renderer = new Renderer(canvas, nextCanvas);

  let mode = localStorage.getItem(MODE_STORAGE_KEY) || 'ai';

  const game = new Game({
    onUpdate: (g) => {
      renderer.render(g);
      updatePauseLabel(g);
      updateStartLabel(g);
    },
    onScore: (score, best) => {
      scoreEl.textContent = score;
      bestEl.textContent = best;
      linesEl.textContent = game.linesCleared;
    },
    onPieceSpawned: () => {
      if (mode === 'ai') ai.onPieceSpawned();
    },
    onPieceLocked: (info) => {
      // The AI controller owns logging. It logs a piece at whichever comes
      // first: its decision returning in time, or the piece locking here.
      if (mode === 'ai') ai.onPieceLocked(info);
    },
  });

  const keyboard = new KeyboardInput(game);
  const ai = new AiController(game, {
    onLog: (entry) => logEntry(entry),
  });

  // --- dynamic (translated) text ---
  const updateSpeedLabel = () => {
    speedValueEl.textContent = i18n.t('speed.level', { level: Number(speedSlider.value) });
  };
  const updatePauseLabel = (g) => {
    pauseBtn.textContent =
      g.state === GameState.PAUSED ? i18n.t('btn.resume') : i18n.t('btn.pause');
  };
  const updateStartLabel = (g) => {
    // Once a game is live (running or paused) the Start button acts as Restart.
    const live = g.state === GameState.RUNNING || g.state === GameState.PAUSED;
    startBtn.textContent = live ? i18n.t('btn.restart') : i18n.t('btn.start');
  };
  const updateModeOptions = () => {
    modeSelect.options[0].textContent = i18n.t('mode.ai');
    modeSelect.options[1].textContent = i18n.t('mode.human');
  };

  const applySpeed = () => {
    game.setSpeedLevel(Number(speedSlider.value));
    updateSpeedLabel();
  };
  speedSlider.addEventListener('input', applySpeed);

  // --- AI decision panel (driven by the AI controller's onLog) ---
  function logEntry(entry) {
    // entry.inTime: AI returned before the piece locked (normal). Otherwise the
    // piece locked first (AI too late) — or an in-time attempt that failed.
    const aiPlaced = !!(entry.inTime && !entry.failed);

    if (entry.source) {
      sourceBadge.textContent = entry.source;
      sourceBadge.className = `source-badge ${entry.source}`;
    }

    const card = document.createElement('div');
    card.className = aiPlaced ? 'ai-card' : 'ai-card ai-card-late';

    const rot = (entry.rotation != null) ? entry.rotation : '-';
    const col = (entry.column != null) ? entry.column : '-';
    const latencyLine = (entry.latency_ms != null)
      ? `<div class="ai-card-line ai-latency">${i18n.t('panel.latency')}: ${entry.latency_ms} ms</div>`
      : '';
    const clearsLine = (entry.linesCleared > 0)
      ? `<div class="ai-card-line">${i18n.t('panel.clears')}: ${entry.linesCleared}</div>`
      : '';

    // Mark pieces the AI did not place in time (or a failed in-time attempt).
    let noteBadge = '';
    let noteLine = '';
    if (!aiPlaced) {
      noteBadge = `<span class="ai-late-badge">⏱ ${i18n.t('panel.late')}</span>`;
      if (entry.reason) {
        noteLine = `<div class="ai-card-line ai-note">${entry.reason}</div>`;
      }
    }

    card.innerHTML = `
      <div class="ai-card-top">
        <span class="ai-idx">#${entry.index}</span>
        <span class="ai-piece">${i18n.t('panel.piece')}: ${entry.piece}</span>
        ${noteBadge}
      </div>
      <div class="ai-card-line">${i18n.t('panel.rotation')} ${rot} · ${i18n.t('panel.column')} ${col}</div>
      ${clearsLine}
      ${latencyLine}
      ${noteLine}
    `;
    aiLog.prepend(card);
    while (aiLog.children.length > 40) aiLog.removeChild(aiLog.lastChild);
  }

  function clearDecisionLog() {
    aiLog.innerHTML = '';
    ai.reset();
    sourceBadge.textContent = '—';
    sourceBadge.className = 'source-badge';
  }

  // --- mode switching ---
  function applyMode() {
    modeSelect.value = mode;
    if (mode === 'ai') {
      aiPanel.style.display = '';
      keyboard.disable();
      ai.enable();
    } else {
      aiPanel.style.display = 'none';
      ai.disable();
      keyboard.enable();
    }
  }
  modeSelect.addEventListener('change', (e) => {
    mode = e.target.value;
    localStorage.setItem(MODE_STORAGE_KEY, mode);
    applyMode();
  });

  // --- language selector ---
  languageSelect.value = i18n.lang;
  updateModeOptions();
  i18n.apply();
  i18n.onChange(() => {
    updateSpeedLabel();
    updatePauseLabel(game);
    updateStartLabel(game);
    updateModeOptions();
    modeSelect.value = mode;
    renderer.render(game);
  });
  languageSelect.addEventListener('change', (e) => i18n.setLanguage(e.target.value));

  // --- controls ---
  const startGame = () => {
    clearDecisionLog();
    applyMode(); // ensure the correct input source is active
    game.start();
  };
  const restartGame = () => {
    clearDecisionLog();
    applyMode(); // ensure the correct input source is active
    game.restart(); // force a fresh game (and start playing) from any state
  };
  const resetGame = () => {
    clearDecisionLog();
    applyMode(); // ensure the correct input source is active
    game.reset(); // back to the initial READY state; does NOT start playing
  };
  startBtn.addEventListener('click', () => {
    // Reads "Start" before a game is live and "Restart" once it is. Dispatch to
    // match: from READY/OVER begin a fresh game; while RUNNING/PAUSED restart
    // (a fresh game that starts playing immediately).
    if (game.state === GameState.RUNNING || game.state === GameState.PAUSED) {
      restartGame(); // acts as Restart: clears log + fresh game, starts playing
    } else {
      startGame();
    }
  });
  resetBtn.addEventListener('click', resetGame);
  pauseBtn.addEventListener('click', () => {
    // Button reads "Pause" while RUNNING and "Resume" while PAUSED. Dispatch to
    // match: pause a running game, resume a paused one. Resume calls start()
    // directly (NOT startGame) so it does not clear the decision log — resuming
    // keeps this game's history. No-op in OVER/READY.
    if (game.state === GameState.PAUSED) {
      game.start(); // resumes from PAUSED without resetting board/score/log
    } else {
      game.togglePause();
    }
  });

  // --- initial paint ---
  applyMode();
  applySpeed();
  updatePauseLabel(game);
  updateStartLabel(game);
  renderer.render(game);
}

main();
