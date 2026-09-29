# Tetris Web Edition

A browser-based Tetris demo with human and AI play modes. The AI layer supports
three pluggable backends that all share the same design: the **server**
enumerates every legal placement for the current piece, and the model only has
to **pick one** — it never simulates a drop or reasons about geometry.

- **OpenJev / TypeSafe** — System One model, one typed `choice` request per piece.
- **OpenAI / ChatGPT** — one numbered-choice request per piece via the Chat Completions API.
- **Local heuristic** — a Dellacherie-style evaluation function, no external API calls.

With no valid API key configured, the game automatically falls back to the
local heuristic, so it runs out of the box with no setup beyond Python.

See [`DESIGN.md`](DESIGN.md) for the full design and architecture.

## Table of Contents

- [Security Notice](#security-notice)
- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [Controls](#controls-human-mode)
- [AI Mode & Configuration](#ai-mode--configuration)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Implementation Status](#implementation-status)
- [Contributing](#contributing)
- [License](#license)

## ⚠️ Security Notice

`config.py` now reads all API keys (TypeSafe, OpenJev, OpenAI) exclusively
from environment variables, with no hardcoded fallback values — confirmed by
searching the repository for the previously-committed key material, with no
matches left in source.

If this repository was ever pushed anywhere with the old hardcoded keys
present, remember that a later cleanup commit does **not** remove them from
git history: rotate/revoke those keys with their providers if they were real,
and purge them from history (e.g. `git filter-repo` / BFG Repo-Cleaner) before
treating the repo as safe to share.

This project also has **no `LICENSE` file** yet — see [License](#license).

## Features

- Full Tetris game engine in the frontend (movement, rotation, line clears,
  scoring, adjustable drop speed)
- Human and AI play modes
- Three interchangeable AI backends behind one interface, with automatic
  fallback to a local heuristic when no API key is configured
- Live AI decision panel showing candidate placements and scores
- I18N: English, Español, 中文

## Requirements

- Python 3.10+
- pip

## Installation

```bash
git clone <repository-url>
cd JevTetris
python3 -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

```bash
python server.py
```

Then open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

The host/port can be overridden with the `HOST` and `PORT` environment
variables (defaults: `127.0.0.1:5000`).

## Controls (human mode)

| Key | Action |
|-----|--------|
| ← / → | Move left / right |
| ↑ | Rotate |
| ↓ | Soft drop |
| Space | Hard drop |
| P | Pause / resume |

## AI Mode & Configuration

The active backend is chosen by the `AI_BACKEND` environment variable:

| Value | Behavior |
|-------|----------|
| `auto` | Tries `openai` → `jev` → `openjev` → `heuristic`, in order, using the first one with a valid key |
| `openai` | Force OpenAI/ChatGPT (falls back to heuristic if no key) |
| `jev` | Force TypeSafe System One (falls back to heuristic if no key) |
| `openjev` | Force OpenJev System One (falls back to heuristic if no key) |
| `heuristic` | Always use the local heuristic, no external calls |

> `config.py`'s built-in default when `AI_BACKEND` is unset is currently
> `"jev"`, not `"auto"`. Set `AI_BACKEND=auto` explicitly if you want the
> documented fallback order.

**OpenJev / TypeSafe** (System One `choice` model):

```bash
export AI_BACKEND=openjev
export OPENJEV_API_KEY="your-real-key"   # or TYPESAFE_API_KEY for the "jev" provider
python server.py
```

Defaults: OpenJev endpoint/model `https://api.openjev.sh/v1/systemone` /
`openjev` (override via `OPENJEV_API_URL` / `OPENJEV_MODEL`); TypeSafe
`https://api.typesafe.ai/v1/systemone` / `jev-latest` (override via
`JEV_API_URL` / `JEV_MODEL`). On failure this path falls back to the local
heuristic.

**OpenAI / ChatGPT**:

```bash
export AI_BACKEND=openai
export OPENAI_API_KEY="sk-..."
python server.py
```

The model receives all legal placements as numbered options (each already
showing the resulting board + metrics) and replies with `{"choice": <number>}`.
Defaults: `https://api.openai.com/v1/chat/completions` / `gpt-6-luna`
(override via `OPENAI_API_URL` / `OPENAI_MODEL`). Unlike the Jev path, a
failure here does **not** fall back — no decision is returned and the piece
drops by gravity, so the failure stays visible instead of being hidden.

**Local heuristic** — used automatically when no key is set, or with
`AI_BACKEND=heuristic`.

> API keys are read server-side in `config.py` and never reach the browser.
> Set them via environment variables — see [Security Notice](#security-notice)
> for why the current hardcoded values in `config.py` must be removed before
> this repo is shared or made public.

AI decisions are a **race against gravity**: a decision request fires when a
piece spawns, while the piece keeps falling. If gravity locks the piece before
the response returns, that decision is discarded.

## Project Structure

```
JevTetris/
├── DESIGN.md              # Full design document
├── README.md              # This file
├── requirements.txt       # Python dependencies (flask, requests)
├── config.py              # Configuration: API keys, URLs, models, AI_BACKEND
├── server.py              # Flask entry point: static hosting + /api/decide
├── ai/                    # AI decision package
│   ├── base.py            # AiDecider interface, DecisionResult/Decision types
│   ├── factory.py         # Backend selection (build_decider)
│   ├── heuristic.py       # Local heuristic decider
│   ├── jev_client.py      # TypeSafe / OpenJev System One decider
│   ├── openai_client.py   # OpenAI / ChatGPT decider
│   ├── board_state.py     # Board representation helpers
│   └── placement_options.py  # Legal-placement enumeration
├── static/                # Frontend (served as-is by Flask)
│   ├── index.html
│   ├── js/                # Game engine, rendering, input, AI controller, i18n
│   ├── css/
│   └── locales/           # en / es / zh translation strings
└── tests/                 # Pytest unit tests (board state, heuristic)
```

## Testing

```bash
pip install pytest
pytest
```

## Implementation Status

- [x] Frontend game engine (human play, rendering, scoring, speed)
- [x] Flask server: static hosting + `/api/decide`
- [x] AI decision logic (OpenJev/TypeSafe + OpenAI + local heuristic)
- [x] AI mode UI + decision panel
- [x] I18N (English / 中文 / Español)

Out of scope for this demo: user accounts, persisted scores, multiplayer,
leaderboards, mobile touch controls.

## Contributing

This is a personal demo project; issues and pull requests are welcome. Please
run `pytest` before submitting a change, and never commit real API keys (see
[Security Notice](#security-notice)).

## License

No `LICENSE` file is currently included in this repository. Add one (for
example the [MIT License](https://choosealicense.com/licenses/mit/)) before
publishing or accepting external contributions, so usage rights are explicit.
