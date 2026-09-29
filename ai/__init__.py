"""AI decision package for Tetris.

Exposes a common ``AiDecider`` interface with two implementations:
- ``HeuristicDecider``: local, no external calls (default fallback).
- ``JevDecider``: calls the Jev / TypeSafe System One API when a key is set.
"""
