"""Clean per-section datasheet analysis (parallel to the legacy monolithic
``component_analysis``). Each heading is an independent, self-assessed Section;
vendor layout quirks live in ``vendors``. Wired opt-in so the existing path is
untouched while the new system is proven section by section.
"""
from .context import AnalysisContext
from . import vendors, components
from .sections import (Section, SectionResult, SpecSection, PinoutSection,
                       CurvesSection, DesignSection, LayoutSection)

# Sections that make up a full analysis, in report order.
SECTIONS = [PinoutSection, SpecSection, CurvesSection, DesignSection,
            LayoutSection]


def analyze(pdf_path: str, max_pages: int = 30) -> dict:
    """Run every registered Section over one shared parse; return a dict of
    ``{section_key: SectionResult.to_dict()}`` plus vendor detection info."""
    with AnalysisContext(pdf_path, max_pages=max_pages) as ctx:
        out = {
            "part": ctx.part,
            "vendor": {"key": ctx.vendor.key, "label": ctx.vendor.label,
                       "score": ctx.vendor_score, "reason": ctx.vendor_reason},
            "component": {"key": ctx.component.key, "label": ctx.component.label,
                          "scores": ctx.component_scores},
            "is_text_pdf": ctx.is_text_pdf(),
            "sections": {},
        }
        for sect_cls in SECTIONS:
            r = sect_cls().run(ctx)
            out["sections"][r.key] = r.to_dict()
        return out


__all__ = ["AnalysisContext", "analyze", "vendors",
           "Section", "SectionResult", "SpecSection", "PinoutSection"]
