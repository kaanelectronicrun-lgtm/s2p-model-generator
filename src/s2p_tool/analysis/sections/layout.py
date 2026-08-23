"""LayoutSection — the datasheet's own §Layout Guidelines as a checklist.

Splits the manufacturer's layout-guidance prose into actionable items. Real
schematic/PCB *generation* is out of scope (that is the kicad/eda-agent job);
this only surfaces what the datasheet says.
"""
from __future__ import annotations

from .base import Section, SectionResult
from .. import text_extract


class LayoutSection(Section):
    key, label = "layout", "Layout Önerileri"

    def extract(self, ctx, res: SectionResult) -> None:
        res.data = text_extract.layout_guidelines(ctx.deep_text)

    def score(self, ctx, res: SectionResult) -> None:
        items = res.data or []
        if len(items) >= 3:
            res.confidence = "high"
            res.reason = f"{len(items)} layout önerisi"
        elif items:
            res.confidence = "med"
            res.reason = f"{len(items)} öneri (az)"
        else:
            res.confidence = "none"
            res.reason = "§Layout Guidelines bulunamadı"

    def interpret(self, ctx, res: SectionResult) -> None:
        items = res.data or []
        if items:
            res.interpretation = [f"{len(items)} layout kuralı checklist'e alındı."]
