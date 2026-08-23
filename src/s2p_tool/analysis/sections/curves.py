"""CurvesSection — characteristic-curve digitization in the Section contract.

Wraps the proven vector-graph engine (``pdfcurves.extract_labeled_curves``):
the *what to look for* comes from the detected component profile's
``curve_targets`` (regulator: efficiency, Vref/T, Iq/T, …), the *how* is the
grid-aware caption-anchored digitizer. Each curve keeps its own high/low
confidence; the section confidence reflects whether any curve came back
trustworthy, and interpretation is delegated to the component profile.
"""
from __future__ import annotations

from typing import Dict, List

from .base import Evidence, Section, SectionResult

try:
    from ... import pdfcurves  # s2p_tool.pdfcurves
except Exception:  # pragma: no cover - resolved at runtime via absolute import
    pdfcurves = None


def _load_pdfcurves():
    global pdfcurves
    if pdfcurves is None:
        from s2p_tool import pdfcurves as _pc
        pdfcurves = _pc
    return pdfcurves


class CurvesSection(Section):
    key, label = "curves", "Karakteristik Eğriler"

    def extract(self, ctx, res: SectionResult) -> None:
        targets = getattr(ctx.component, "curve_targets", ())
        if not targets:
            res.reason = f"'{ctx.component.label}' için tanımlı eğri hedefi yok"
            return
        pc = _load_pdfcurves()
        if pc is None or not pc.available():
            res.reason = "PyMuPDF yok — eğri çıkarımı atlandı"
            return
        wanted = [(t[0], t[1]) for t in targets]
        raw = pc.extract_labeled_curves(ctx.pdf_path, wanted)
        meta_by_key = {t[0]: t for t in targets}
        curves: Dict = {}
        for k, tup in meta_by_key.items():
            r = raw.get(k)
            if not r:
                continue
            # Drop a semantic misfire: caption matched but the x-axis quantity
            # differs from what this target means (unit-dimension disagreement).
            if pc.axis_dim_mismatch(tup[2], (r.get("meta") or {}).get("ux")):
                continue
            conf = r["confidence"]
            # Demote a cleanly-calibrated but too-flat dB curve (fragment).
            if conf == "high" and pc.db_fragment(tup[3], r["curve"]):
                conf = "low"
            entry = {
                "caption": r["caption"], "unit_x": tup[2], "unit_y": tup[3],
                "desc": tup[4], "confidence": conf,
                "npoints": len(r["curve"]), "curve": r["curve"],
            }
            if r.get("traces"):
                entry["traces"] = [
                    {"label": f"iz {i + 1}", "color": t["color"],
                     "npoints": t["npoints"], "spread": t["spread"],
                     "curve": t["curve"]}
                    for i, t in enumerate(r["traces"])]
                entry["ntraces"] = len(r["traces"])
            curves[k] = entry
        curves["_log"] = raw.get("log", [])
        res.data = curves

    def validate(self, ctx, res: SectionResult) -> None:
        curves = res.data or {}
        for k, c in curves.items():
            if k == "_log" or not isinstance(c, dict):
                continue
            if c.get("confidence") == "low":
                res.issues.append(f"{k}: düşük güven (kalibrasyon/çoklu-iz)")

    def score(self, ctx, res: SectionResult) -> None:
        curves = res.data or {}
        data = {k: v for k, v in curves.items()
                if k != "_log" and isinstance(v, dict)}
        if not data:
            res.confidence = "none"
            res.reason = res.reason or "vektör grafikten eğri çıkarılamadı"
            return
        highs = [k for k, v in data.items() if v.get("confidence") == "high"]
        if highs:
            res.confidence = "high"
            res.reason = f"{len(highs)}/{len(data)} eğri yüksek güvenli"
        else:
            res.confidence = "low"
            res.reason = f"{len(data)} eğri, hiçbiri yüksek güvenli değil"

    def interpret(self, ctx, res: SectionResult) -> None:
        curves = res.data or {}
        if curves:
            res.interpretation = ctx.component.interpret_curves(curves)
