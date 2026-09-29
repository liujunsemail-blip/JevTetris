"""Common AI interface and result structures.

Both the heuristic and Jev deciders return the same ``DecisionResult`` shape so
the frontend needs no branching (per DESIGN.md sections 4-6).
"""

from __future__ import annotations

import abc
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional


@dataclass
class CandidateRecord:
    """One evaluated candidate placement, surfaced to the UI decision panel."""

    rotation: int
    column: int  # actual leftmost occupied column (0..9), for display
    score: float
    metrics: Dict[str, int]
    chosen: bool = False


@dataclass
class Decision:
    rotation: int
    column: int  # actual leftmost occupied column (0..9), for display
    confidence: float
    origin_column: int = 0  # 4x4 bounding-box origin column used to drive the engine


@dataclass
class DecisionResult:
    source: str  # "jev" | "heuristic"
    decision: Optional[Decision]
    records: List[CandidateRecord] = field(default_factory=list)
    reason: str = ""
    latency_ms: Optional[int] = None  # Jev API round-trip time in ms (None if not measured)

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "decision": asdict(self.decision) if self.decision else None,
            "records": [asdict(r) for r in self.records],
            "reason": self.reason,
            "latency_ms": self.latency_ms,
        }


class AiDecider(abc.ABC):
    """Strategy interface: given a board and current piece, pick a placement."""

    source: str = "base"

    @abc.abstractmethod
    def decide(self, board: List[List[int]], current_piece: str,
               next_piece: Optional[str] = None) -> DecisionResult:
        """Return the chosen placement plus per-candidate records."""
        raise NotImplementedError
