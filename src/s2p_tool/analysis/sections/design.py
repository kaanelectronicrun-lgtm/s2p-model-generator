"""DesignSection — design requirements + design-procedure narration.

Reuses the proven text extractors (``text_extract``): the example Design
Requirements table and each numbered design-procedure step with its intent and
'where' variable glossary. The procedure headings are component-specific and
come from the detected profile. Formulae are narrated, never fabricated.
"""
from __future__ import annotations

from .base import Section, SectionResult
from .. import text_extract


class DesignSection(Section):
    key, label = "design", "Tasarım Gereksinimleri & Hesapları"

    def extract(self, ctx, res: SectionResult) -> None:
        text = ctx.deep_text
        proc_heads = getattr(ctx.component, "proc_heads", text_extract.PROC_HEADS)
        res.data = {
            "requirements": text_extract.design_requirements(text),
            "procedure": text_extract.design_procedure(text, proc_heads),
        }

    def score(self, ctx, res: SectionResult) -> None:
        d = res.data or {}
        req, proc = d.get("requirements", []), d.get("procedure", [])
        if proc and req:
            res.confidence = "high"
            res.reason = f"{len(req)} gereksinim + {len(proc)} tasarım adımı"
        elif proc or req:
            res.confidence = "med"
            res.reason = f"{len(req)} gereksinim, {len(proc)} adım"
        else:
            res.confidence = "none"
            res.reason = "tasarım gereksinimi/prosedürü bulunamadı"

    def interpret(self, ctx, res: SectionResult) -> None:
        d = res.data or {}
        finds = []
        if d.get("requirements"):
            finds.append("Örnek tasarım gereksinimleri çıkarıldı: "
                         + ", ".join(lab for lab, _ in d["requirements"]))
        for step in d.get("procedure", []):
            if step.get("intent"):
                finds.append(f"{step['step']}: {step['intent']}")
        res.interpretation = finds
