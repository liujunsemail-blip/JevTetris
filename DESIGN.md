# Tetris Web Edition — Design Document

## 1. Goals and Scope

A **demonstration** web-based Tetris game. Users play directly in the browser.

**Requirements mapping:**

| # | Requirement | Implementation |
|---|-------------|----------------|
| 1 | Web-based, browser access | Flask serves static pages; frontend renders with Canvas |
| 2 | Score tracking | Simplified to **in-memory** current score + best score for the session (cleared on refresh, not persisted) |
| 3 | Adjustable speed in UI | Speed slider controls gravity drop interval (tick in ms) |
| 4 | I18N (zh/en, default English, selectable) | Frontend `i18n.js` + `locales/{en,zh}.json`, language selector |
| 5 | Human / AI play (default AI) | Mode selector; AI mode integrates Jev; falls back to local heuristic when no key; UI shows AI decision log |
| 6 | Python 3, naming conventions, sound structure | Backend Python 3 + Flask; PEP 8 naming; layered modules |

**Explicitly out of scope:** user accounts, score persistence, multiplayer, leaderboards, mobile gestures.

## 2. Architecture

All game logic lives in the **frontend JS** (zero latency for manual play). The Python backend does only two things:

1. **Static file hosting** — serves the `static/` directory.
2. **AI decision proxy** — `POST /api/decide`: the frontend sends the board state, the backend enumerates the legal placements, asks the configured model to pick one, and returns the decision. **The API key stays on the backend and never reaches the browser.**

The active decider is chosen by `config.AI_BACKEND` (env `AI_BACKEND`): `auto`
(order `openai → jev → openjev → heuristic`) or a forced `openai` | `jev` |
`openjev` | `heuristic`. Three real backends share one `AiDecider` interface:

- **OpenJev / TypeSafe** (`JevDecider`) — System One `choice` model; on failure
  falls back to the local heuristic.
- **OpenAI / ChatGPT** (`OpenAiDecider`) — Chat Completions, JSON numbered
  choice; on failure returns no decision (no fallback) so the error is visible.
- **Local heuristic** (`HeuristicDecider`) — no external calls.

When a selected backend has no key set (its API key is empty), the
backend falls back to the **local heuristic**, so the project runs out of the box.

```
Browser (frontend JS)                Flask backend (Python 3)
┌─────────────────────┐            ┌──────────────────────────────┐
│ Game engine/render/  │            │ GET  /            static      │
│ input                │  fetch     │ GET  /<file>      assets      │
│ Human mode: keyboard │ ───────►   │ POST /api/decide  proxy       │
│ AI mode:             │            │   ├─ openai  → ChatGPT        │
│   request per piece  │ ◄───────   │   ├─ jev/openjev → System One │
│   animate + log      │  decision   │   └─ no key   → heuristic     │
└─────────────────────┘   JSON      └──────────────────────────────┘
```

## 3. Directory Structure

```
Game/
├── DESIGN.md                   # This document
├── README.md                   # Run instructions
├── requirements.txt            # flask, requests
├── config.py                   # Config: API keys (env-driven), URLs, models, AI_BACKEND selector
├── server.py                   # Flask entry: static hosting + /api/decide
├── ai/
│   ├── __init__.py
│   ├── base.py                 # AiDecider abstract interface + decision data structures
│   ├── factory.py              # build_decider(): picks the backend from config.AI_BACKEND
│   ├── jev_client.py           # OpenJev/TypeSafe System One (single `choice`; heuristic fallback)
│   ├── openai_client.py        # OpenAI/ChatGPT decider (numbered choice; NO fallback, surfaces errors)
│   ├── heuristic.py            # Local heuristic AI (fallback)
│   ├── placement_options.py    # Shared: build labeled/numbered options + candidate records for the model
│   └── board_state.py          # Pure logic: placement enumeration, ASCII render, candidate description, feature measurement
├── static/
│   ├── index.html
│   ├── css/
│   │   └── style.css
│   ├── js/
│   │   ├── constants.js        # Piece shapes, colors, board dimensions
│   │   ├── board.js            # Board state, collision, line clearing
│   │   ├── tetromino.js        # Piece generation and rotation
│   │   ├── game.js             # Game loop, gravity, scoring
│   │   ├── renderer.js         # Canvas rendering
│   │   ├── input.js            # Keyboard input (human mode)
│   │   ├── ai_controller.js    # AI mode: request /api/decide, execute placement, log
│   │   ├── i18n.js             # Language switching
│   │   └── main.js             # Wiring + UI controls (mode/language/speed/start/pause)
│   └── locales/
│       ├── en.json
│       ├── zh.json
│       └── es.json
└── tests/
    ├── test_heuristic.py       # Heuristic scoring unit tests
    └── test_board_state.py     # Placement enumeration / state parsing unit tests
```

## 4. `/api/decide` Contract

**Request (frontend → backend):**

```json
{
  "board": [[0,0,1,...], ...],   // 20 rows × 10 cols, 0=empty, non-zero=occupied (value = color index)
  "current_piece": "T",           // active piece type I/O/T/S/Z/J/L
  "next_piece": "L"               // next piece (optional, for lookahead)
}
```

**Response (backend → frontend):**

```json
{
  "source": "jev" | "openjev" | "openai" | "heuristic",  // decision source, UI labels accordingly
  "decision": {
    "rotation": 2,                // target rotation state 0-3
    "column": 4,                  // actual leftmost OCCUPIED column (0-9), for display
    "confidence": 0.87,           // confidence (model choice confidence; normalized score in heuristic mode)
    "origin_column": 3            // 4x4 bounding-box origin column used to DRIVE the engine (may be negative)
  },
  "records": [                    // candidate evaluations for the UI decision panel
    {
      "rotation": 2, "column": 4, // column here is also the actual leftmost occupied column (0-9)
      "score": 0.87,
      "metrics": { "lines_cleared": 1, "holes": 0, "aggregate_height": 12, "bumpiness": 3, "landing_height": 2 },
      "chosen": true
    }
  ],
  "reason": "Jev chose E: clears 1, holes 0 (confidence 0.87)",  // one-line explanation
  "latency_ms": 940             // model round-trip time in ms (null for heuristic / when not measured)
}
```

> **Column semantics.** `column` (outward, in both `decision` and `records`) is the
> piece's actual leftmost occupied column, always `0-9`, so the UI never shows a
> negative. `decision.origin_column` is the 4x4 bounding-box origin the engine uses
> to position the piece and *can* be negative (e.g. O spawns at origin -1). The AI
> controller drives toward `origin_column`; the panel displays `column`.

## 5. Jev Integration Design (single-choice)

Jev is a **System One model** — it does not generate move sequences; it answers
**typed questions** about a **state**, returning typed values + probabilities +
confidence. We use a single **`choice`** question per piece (revised from the
earlier per-candidate Composite-scoring approach, which cost one request per
candidate and was too slow — see §14):

1. The backend enumerates all **legal** placements for the current piece
   (`enumerate_placements`, rotation × column, deduped — typically 15-34, never
   the full 40). Legality (collision / bounds / drop / off-top) is decided
   **deterministically in code**, never by the model.
2. Render the real board as an **ASCII grid** (row 0 = top, `#` = locked block,
   `_` = empty, `@` = the current piece drawn in its spawn orientation for
   reference, columns 0-9) and label each legal candidate `A, B, C, …` (Jev) or
   number it (OpenAI) with clear semantics: clockwise rotation count + which
   columns the piece occupies + the rows it lands across, plus the resulting
   board and metrics.
3. Send **one** request with a single `choice` question (`best_placement`) whose
   `criteria` are the labeled candidates. The model picks the best label.
4. Map the chosen label back to its `(rotation, origin_column, left_col)` and
   return it. The model's per-option `probabilities` become each candidate's
   `score`, and `confidence` is surfaced to the UI.

The two System One providers share `JevDecider` and differ only in config:
OpenJev defaults to `https://api.openjev.sh/v1/systemone` / `openjev` (key
`OPENJEV_API_KEY`, override URL/model via `OPENJEV_API_URL` / `OPENJEV_MODEL`);
TypeSafe defaults to `https://api.typesafe.ai/v1/systemone` / `jev-latest` (key
`TYPESAFE_API_KEY`, override via `JEV_API_URL` / `JEV_MODEL`). Keys are read in
`config.py` and never sent to the browser.

> **Why single-choice.** The model chooses among placements we have already
> proven legal — code owns the geometry (what's legal), the model owns the
> judgment (which legal option is best). One request per piece keeps latency
> ~1s instead of ~7-15s. On any failure (network, bad response, unknown label)
> the decider falls back to the local heuristic so play never stalls.

### 5.1 OpenAI / ChatGPT Decider

`OpenAiDecider` (`ai/openai_client.py`) reuses the exact same enumerate-then-pick
design (shared `placement_options`), because LLMs are poor at spatial simulation —
asked openly for a rotation+column, GPT misreads shapes (L vs T) and cannot
mentally simulate a drop. So it is handed all legal placements as **numbered**
options (each already showing the resulting board + metrics) and replies with a
JSON object `{"choice": <number>}` via the Chat Completions API with
`response_format: json_object`. Rate-limit responses (429/529) are retried with
exponential backoff. Defaults: `https://api.openai.com/v1/chat/completions` /
`gpt-6-luna` (override via `OPENAI_API_URL` / `OPENAI_MODEL`).

> **No fallback (by design).** Unlike the Jev path, an OpenAI failure returns
> `decision: null` (reason carries the error) rather than falling back to the
> heuristic — the failure is surfaced, and the piece then drops by gravity.
> `confidence` is reported as `1.0` since the Chat API gives no probability.

## 6. Local Heuristic AI (no-key fallback)

A classic Tetris evaluation function (a Dellacherie-style scheme). For each candidate placement, compute:

- `lines_cleared` — number of cleared lines (positive)
- `landing_height` — how high the piece comes to rest (negative; discourages stacking high)
- `holes` — a cell that is empty but has a block above it (strongly negative — the dominant term)
- `bumpiness` — sum of height differences between adjacent columns (negative)
- `aggregate_height` — sum of all column heights (negative)

Combined score:

```
score = w_lines * lines_cleared
      - w_landing * landing_height
      - w_holes   * holes
      - w_bumpiness * bumpiness
      - w_height  * aggregate_height
```

Default weights (in `ai/heuristic.py::DEFAULT_WEIGHTS`, tunable):
`lines=3.4, landing_height=4.5, holes=7.9, bumpiness=3.2, aggregate_height=0.6`.
The heavy `holes` penalty is deliberate — an earlier too-weak value made the AI
stack over gaps and look "dumb"; adding `landing_height` and raising `holes`
turned self-play survival from a few pieces to ~300 pieces / ~100 lines.
Pick the placement with the highest score. The normalized score is used as
`confidence` for the UI, matching Jev's format so the frontend needs no branching.

## 7. Frontend Game Engine

- **Board**: 10 columns × 20 rows. `board.js` manages occupancy, collision detection, and line clearing.
- **Pieces**: 7 standard tetrominoes (I/O/T/S/Z/J/L), simplified SRS rotation. `tetromino.js`.
- **Game loop**: `requestAnimationFrame` + accumulated time; drops one row each time the gravity interval (set by the speed slider) is reached.
- **Scoring**: points per line clear (1/2/3/4 lines = 100/300/500/800); current score + session best kept in memory.
- **Human input**: ← → move, ↑ rotate, ↓ soft drop, space hard drop, P pause/resume.
- **AI mode (race + void)**: when a new piece spawns at the top, fire `/api/decide`
  **without blocking gravity** — the piece keeps falling while the request is in
  flight. The engine tags each spawn with a monotonic `pieceId`. When the decision
  returns: if the piece is still active (`pieceId` matches), drive it into place
  (rotate → move to `origin_column` → hard drop, using the same action commands a
  human uses) and append a card to the decision panel; if gravity already locked it
  (`pieceId` changed), the decision is **discarded** and never touches the next
  piece. Piece lock-and-spawn is strictly serialized: `lock → clear lines → score →
  spawn next`, so pieces never overlap.
- **Game state machine**: the engine is always in one of four states —
  `READY` (fresh, nothing spawned), `RUNNING`, `PAUSED`, `OVER`. Exactly one
  `requestAnimationFrame` loop runs at a time; every entry point that could
  start a loop first calls `_stopLoop()`, so a repeated Start can never spin up
  a second loop (which would double gravity/lock-delay speed). Transitions:

  | Trigger | READY | RUNNING | PAUSED | OVER |
  |---|---|---|---|---|
  | `start()` | new game → RUNNING | ignored | **resume** → RUNNING (board/score kept) | new game → RUNNING |
  | `togglePause()` | — | → PAUSED (stops loop) | ignored | — |
  | `restart()` | new game → RUNNING | new game → RUNNING | new game → RUNNING | new game → RUNNING |
  | `reset()` | → READY | → READY | → READY | → READY |
  | spawn collision | — | → OVER | — | — |

  `start()` only *resumes* from PAUSED (it does not reset the board); from
  READY/OVER it begins a fresh game and is ignored while RUNNING. `restart()`
  is an ungated fresh game from any state. `reset()` clears board, score, lines,
  the active piece, the next-piece preview, and rebuilds the 7-bag, returning to
  READY **without** starting play; it does not touch preferences (mode/language/
  speed) or the best score.
- **Controls → engine mapping** (`main.js`): the **Start** button reads "Start"
  in READY/OVER and "Restart" while RUNNING/PAUSED, dispatching to `start()` or
  `restart()` accordingly. The **Pause** button reads "Pause"/"Resume" and
  dispatches to `togglePause()` or `start()` (resume). The **Reset** button
  always calls `reset()`. The **P** key mirrors the Pause/Resume button.

## 8. I18N

- `locales/en.json`, `locales/zh.json`, and `locales/es.json` hold all UI text as key/value pairs.
- `i18n.js` provides `t(key, params)` (with `{placeholder}` substitution); switching via the language selector re-renders the text and persists the choice to `localStorage`.
- **Default English** (English / 中文 / Español). Adding a language = one JSON file + an entry in the supported list + one selector option.

## 9. UI Layout

Three independent columns (`.info` | `.game-area` | `.ai-panel`) inside a
top-bar + `.layout` flex row — see §13.2 for the annotated version:

```
┌──────────────────────────────────────────────────────────────┐
│  [Tetris]              Lang:[EN▾]        Mode:[AI▾]           │
├───────────────┬──────────────────────┬───────────────────────┤
│  SCORE 1200   │                      │  AI DECISIONS  [jev]  │
│  BEST  3400   │                      ├───────────────────────┤
│  LINES 8      │      Game canvas     │  #12  piece: T         │
│               │      (Canvas)        │  rotation 2 · column 4 │
│  NEXT  [▦]    │                      ├───────────────────────┤
│               │  [Start][Pause][Reset]│  #11  piece: L         │
│  SPEED Lv5    │                      │  rotation 0 · column 7 │
│  [====|----]  │                      │                        │
└───────────────┴──────────────────────┴───────────────────────┘
```

- **Left (`.info`)**: SCORE / BEST / LINES stat cards, NEXT preview canvas, SPEED
  slider with its level readout — each its own bordered card, stacked vertically.
- **Center (`.game-area`)**: the board canvas plus the Start / Pause / Reset
  button row and the keyboard-hint line beneath it.
- **Right (`.ai-panel`)**: shown only in AI mode; hidden entirely in human mode
  (the center column does not re-center to fill the gap). The panel source
  badge (`jev` / `openjev` / `openai` / `heuristic`) sits by the panel title.
  Each card is intentionally minimal — index, piece type, rotation, column —
  see §13.3 for the full card anatomy, including the confidence bar and the
  "decision arrived too late" variant.

## 10. Naming and Code Conventions

- **Python**: PEP 8, `snake_case` functions/variables, `PascalCase` classes, lowercase modules. Type annotations + docstrings.
- **JS**: `camelCase` variables/functions, `PascalCase` classes, `UPPER_SNAKE` constants. Organized as ES6 modules or IIFEs.
- Backend deciders (OpenJev/TypeSafe, OpenAI, heuristic) all implement the
  `AiDecider` abstract interface and return the same `DecisionResult`; `build_decider()`
  in `factory.py` picks the implementation from `config.AI_BACKEND` (falling back
  to the heuristic when the selected backend has no key).

## 11. Testing

- `test_heuristic.py`: build known boards, assert the heuristic selects the expected placement and that scoring is monotonic.
- `test_board_state.py`: assert placement enumeration counts, out-of-bounds filtering, and correct line-clear simulation.
- Frontend logic is verified mainly by manual smoke testing (demo project, no JS test framework for now).

## 12. Running

```bash
cd Game
pip install -r requirements.txt
python server.py            # default http://127.0.0.1:5000
```

Without a Jev key it runs in local heuristic mode automatically; with a real key
(`OPENJEV_API_KEY`, or `TYPESAFE_API_KEY` as a fallback), AI mode uses OpenJev.

## 13. UI Specification (detailed)

Expands on the layout sketch in Section 9. This is the visual contract for implementation.

### 13.1 Visual Style — Neon Dark

An arcade-style modern dark theme: bright pieces pop against a dark board, and the AI decision panel reads as a "data stream" with a tech feel.

- **Background**: dark blue-gray gradient (`#0f1420` → `#1a2035`).
- **Board**: solid dark base with thin grid lines.
- **Pieces**: 7 standard colors with a subtle highlight / inner shadow for depth —
  I = cyan, O = yellow, T = purple, S = green, Z = red, J = blue, L = orange.
- **Accent**: neon cyan (`#22d3ee`) for buttons, slider, and the current score.
- **Fonts**: sans-serif system UI stack; numbers use a monospace face so scores align.

### 13.2 Layout — Three Columns

```
┌──────────────────────────────────────────────────────────────┐
│  ▚ TETRIS            🌐 [English ▾]    🎮 [AI ▾]                 │  ← top bar
├───────────────┬──────────────────────┬───────────────────────┤
│  left info     │      game area        │   right AI panel       │
│               │                      │  (AI mode only)         │
│  SCORE 1200   │   ┌────────────┐     │  ┌─────────────────┐   │
│  BEST  3400   │   │  Canvas    │     │  │ AI DECISIONS [jev]│   │
│  LINES 8      │   │  10 × 20   │     │  │ #12 T  rot2 col4 │   │
│  NEXT  [▦]    │   └────────────┘     │  │ #11 L  rot0 col7 │   │
│  SPEED [==|]  │   [▶][⏸][↻]          │  │ #10 S  rot1 col3 │   │
└───────────────┴──────────────────────┴───────────────────────┘
```

- **Top bar**: title + language selector + mode selector (global controls).
- **Left column**: SCORE / BEST / LINES stat cards (large monospace numbers),
  NEXT preview (small canvas for the upcoming piece), SPEED slider with a
  current-level readout.
- **Center column**: game canvas (fixed 1:2 aspect, 10×20 cells) with a Start / Pause /
  Reset button row beneath it.
- **Right column**: AI decision panel — **shown only in AI mode**; hidden in
  human mode. The panel title is the generic, i18n'd "AI DECISIONS" (not
  hardcoded to any one backend), with a source badge next to it. Four sources
  are possible (`jev`, `openjev`, `openai`, `heuristic`); only `jev` and
  `heuristic` currently have dedicated badge colors (green / gray) — see
  §13.3. Hiding the panel does **not** re-center or reflow the other two
  columns; `.layout` centers the whole three-column row as a unit, so the
  center column keeps its fixed position when the right column disappears.

### 13.3 AI Decision Panel (requirement 5)

Each AI placement appends a card; newest on **top**; the list scrolls.

```
┌─────────────────────────┐
│ #12   piece: T   [LATE]  │   index + piece type (+ late badge, if discarded)
│ rotation 2 · column 4    │   final decision (column = actual leftmost, 0-9)
│ [███████░░░] 0.87        │   confidence bar (score/probability, 0-1)
│ lines:1 holes:0 h:12     │   candidate metrics, dimmed text
└─────────────────────────┘
```

- New cards fade/slide in (`aiCardIn` keyframe) so "the AI is thinking and
  deciding" is visible.
- The decision **source** is shown once as a badge by the panel title, not
  repeated on every card. Four values are possible: `jev` and `heuristic` have
  dedicated colors (green / gray via `.source-badge.jev` /
  `.source-badge.heuristic`); `openai` and `openjev` currently fall through to
  the same unstyled default badge look as an unrecognized source — add
  `.source-badge.openai` / `.source-badge.openjev` rules if they should read
  distinctly from `heuristic`.
- Each card shows a **confidence bar** (`.ai-conf` / `.ai-conf-bar`) — a
  filled bar sized by the decision's `confidence`/score, with the numeric
  value alongside it — plus a metrics line (`.ai-card-metrics`).
- A decision that arrived **after gravity already locked the piece** (see §7,
  race + void) is rendered as a **late card**: dashed amber border
  (`.ai-card-late`), a small "late" badge (`.ai-late-badge`), and an amber
  note line (`.ai-note`) instead of being silently dropped from the log —
  it is visually distinguished but still shown, so the panel reflects when
  the AI "lost the race" for a piece.
- `column` is the actual leftmost occupied column (0-9), never the internal
  bounding-box origin (see §4 column semantics).

### 13.4 Responsive

- Desktop (≥1024px): full three columns.
- Narrow (<1024px): stack vertically — top bar → canvas → info → AI panel. Demo targets
  desktop; narrow screens only need to avoid breaking layout.

### 13.5 Interaction Details

- Speed slider changes drop speed in real time, with a level readout (e.g. Level 5 / 300ms).
- Mode/language switches take effect immediately, no refresh; switching language re-renders all text.
- Game over: a semi-transparent overlay on the canvas + "GAME OVER" + final score. The Start button (reading "Start") begins a fresh game; Reset returns to the empty READY screen.
- Pause: a "PAUSED" overlay on the canvas. Resume via the Pause button (now reading "Resume"), the Start button, or the P key.
