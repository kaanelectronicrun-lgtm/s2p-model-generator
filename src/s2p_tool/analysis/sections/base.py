"""Section contract — each datasheet heading is its own evaluated unit.

The datasheet analysis is not one monolithic ``analyze()`` anymore: every
heading (identity, pinout, specs, curves, design procedure, layout) is an
independent ``Section`` that runs the same five-step pipeline and reports its
own quality, exactly like a RAF node carrying its own V&V gate:

    extract → validate → score(confidence + reason) → interpret → cite

A Section never presents a low-quality extraction as trustworthy: a garbled
table comes back ``confidence="low"`` with a stated reason, not as clean data.
The *how* of extraction (vendor layout quirks) lives in a ``VendorProfile``, so
a Section stays vendor-independent and only its strategy varies per manufacturer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Confidence ladder. "none" = nothing usable extracted (honest empty), distinct
# from "low" = extracted but not trustworthy.
CONFIDENCE = ("high", "med", "low", "none")


@dataclass
class Evidence:
    """Where a piece of data came from — page + optional bbox, for citation."""
    page: int
    bbox: Optional[tuple] = None
    note: str = ""


@dataclass
class SectionResult:
    key: str
    label: str
    data: Any = None                       # section-specific payload
    confidence: str = "none"               # one of CONFIDENCE
    reason: str = ""                       # why this confidence (always stated)
    evidence: List[Evidence] = field(default_factory=list)
    interpretation: List[str] = field(default_factory=list)  # plain-language findings
    issues: List[str] = field(default_factory=list)          # extraction problems

    def to_dict(self) -> Dict:
        return {
            "key": self.key,
            "label": self.label,
            "data": self.data,
            "confidence": self.confidence,
            "reason": self.reason,
            "evidence": [{"page": e.page, "bbox": e.bbox, "note": e.note}
                         for e in self.evidence],
            "interpretation": self.interpretation,
            "issues": self.issues,
        }


class Section:
    """Base class. A concrete section implements ``extract`` and usually
    ``validate``/``score``/``interpret``; ``run`` wires them together so every
    section produces a uniform, self-assessed ``SectionResult``."""

    key: str = "section"
    label: str = "Bölüm"

    def run(self, ctx) -> SectionResult:
        res = SectionResult(key=self.key, label=self.label)
        try:
            self.extract(ctx, res)
        except Exception as e:  # a section failing must not sink the whole run
            res.confidence = "none"
            res.reason = f"çıkarım hatası: {type(e).__name__}: {e}"
            res.issues.append(str(e))
            return res
        self.validate(ctx, res)
        self.score(ctx, res)
        self.interpret(ctx, res)
        return res

    # --- override points -------------------------------------------------
    def extract(self, ctx, res: SectionResult) -> None:
        """Fill res.data (+ evidence). Raise on hard failure."""
        raise NotImplementedError

    def validate(self, ctx, res: SectionResult) -> None:
        """Append sanity-check problems to res.issues. Default: no checks."""

    def score(self, ctx, res: SectionResult) -> None:
        """Set res.confidence + res.reason. Default: high if data present and no
        issues, med if data present with issues, none if empty."""
        if not res.data:
            res.confidence, res.reason = "none", res.reason or "veri çıkmadı"
        elif res.issues:
            res.confidence = "med"
            res.reason = res.reason or f"{len(res.issues)} tutarsızlık"
        else:
            res.confidence, res.reason = "high", res.reason or "temiz çıkarım"

    def interpret(self, ctx, res: SectionResult) -> None:
        """Turn res.data into plain-language findings in res.interpretation."""
