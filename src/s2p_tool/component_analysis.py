"""Datasheet component analysis — detect the part type, then extract identity,
electrical specifications and characteristic curves straight from a datasheet
PDF.

This is a separate axis from the passive s2p model path (``pipeline``): the
output here is a *structured analysis* of an arbitrary component, not a
Touchstone model. Each component family is handled by an ``Analyzer`` plugin
registered in ``ANALYZERS``; a new family = a new plugin, no other wiring. The
GUI builds one sub-tab per registered analyzer plus an auto-detect tab.

Curve digitization reuses the grid-aware vector engine in ``pdfcurves`` and
carries a per-curve ``confidence`` so low-quality extractions are flagged, never
presented as trustworthy.
"""
from __future__ import annotations

import csv
import json
import os
import re
from typing import Dict, List, Optional, Tuple

from . import pdfcurves

try:
    import pymupdf as fitz
    _HAVE_FITZ = True
except Exception:  # pragma: no cover
    try:
        import fitz  # type: ignore
        _HAVE_FITZ = True
    except Exception:
        _HAVE_FITZ = False


# ---------------------------------------------------------------------------
# Shared text helpers
# ---------------------------------------------------------------------------
def _full_text(doc, max_pages: int = 6) -> str:
    """First-pages text — identity, features and the spec table live up front."""
    n = min(max_pages, doc.page_count)
    return "\n".join(doc[i].get_text() for i in range(n))


def _part_number(doc, pdf_path: Optional[str] = None) -> str:
    """Best-effort part number. The datasheet's *filename* is the most reliable
    signal — users name the file after the part (opa2340.pdf → OPA2340) — so it
    wins when it looks part-like. PDF title metadata is unreliable (it often
    names a chip referenced in an application figure, e.g. an ADC driven by the
    op-amp), so it is only a fallback, and only when it also appears in the
    first-page text (guards against stray title metadata)."""
    def _partlike(tok: str) -> bool:
        # 2+ leading letters, then a digit somewhere — a real MPN, not a word.
        # '.' is allowed so a voltage-variant suffix survives (lm336-2.5 →
        # LM336-2.5) instead of the filename being rejected and a wrong family
        # sibling picked from the heading text.
        return bool(re.fullmatch(r"[A-Za-z]{2,}[\w.\-]*\d[\w.\-]*", tok or ""))

    if pdf_path:
        stem = os.path.splitext(os.path.basename(pdf_path))[0].strip()
        stem = re.sub(r"[\s_\-]*(datasheet|ds|rev[a-z]?|final)$", "", stem,
                      flags=re.I).strip()
        if _partlike(stem):
            return stem.upper()

    page0 = doc[0].get_text()
    title = (doc.metadata or {}).get("title") or ""
    m = re.search(r"\b([A-Z]{2,}\d[\w\-]*)\b", title)
    if m and m.group(1) in page0:          # trust the title only if page 1 agrees
        return m.group(1)
    for line in page0.splitlines():
        m = re.search(r"\b([A-Z]{2,}\d[\w\-]*)\b", line.strip())
        if m:
            return m.group(1)
    return "component"


_SI_PREFIX = "pnuµμmkMGT"


def _unit_base(u: str) -> str:
    """Strip a leading SI prefix so 'mA'/'µA'/'A' all compare as 'A'. Compound
    units (nV/√Hz, V/µs) are kept whole."""
    u = (u or "").strip().replace("u", "µ").replace("μ", "µ")
    if "/" in u:
        return u
    m = re.fullmatch(r"([" + _SI_PREFIX + r"µ]?)(.+)", u)
    return m.group(2) if m else u


def _relabel_unit(label: str, detected: Optional[str]) -> str:
    """Swap the parenthesized unit in ``label`` (e.g. 'Iq (mA)') for the one read
    off the datasheet axis (``detected``), but only for current/voltage axes
    where the tick numbers are bare and the SI scale lives in the axis title —
    exactly the case the hardcoded 'mA' got wrong. Frequency/temp/dB axes carry
    their scale in SI-suffixed ticks (already absolute), so they are left alone.
    No-op when nothing was detected or the dimension disagrees."""
    if not detected:
        return label
    m = re.search(r"\(([^()]*)\)", label)
    if not m:
        return label
    old = m.group(1)
    if _unit_base(old) != _unit_base(detected):
        return label                      # dimension mismatch — distrust
    if _unit_base(old) not in ("A", "V"):
        return label                      # only µ/m matters on I and V axes
    return label[:m.start(1)] + detected + label[m.end(1):]


def _description(text: str) -> str:
    """The prose paragraph under a 'Description' heading, if present."""
    m = re.search(r"\bDescription\b\s*(.+?)(?:\n\s*\n|\Z)", text,
                  re.S | re.I)
    if not m:
        return ""
    para = re.sub(r"\s+", " ", m.group(1)).strip()
    return para[:600]


def _features(text: str) -> List[str]:
    """Bullet list under 'Features' up to the next top-level heading."""
    m = re.search(r"\bFeatures\b(.+?)(?:\n\s*\d*\s*Applications\b|"
                  r"\n\s*\d*\s*Description\b)", text, re.S | re.I)
    if not m:
        return []
    out, buf = [], ""
    for raw in m.group(1).splitlines():
        s = raw.strip()
        if not s or s == "•":
            if buf:
                out.append(buf.strip()); buf = ""
            continue
        if s.startswith("•"):
            if buf:
                out.append(buf.strip())
            buf = s.lstrip("•").strip()
        else:
            buf = (buf + " " + s).strip() if buf else s
    if buf:
        out.append(buf.strip())
    # Drop empties / stray single glyphs.
    return [f for f in out if len(f) > 2][:20]


def _figure_captions(doc, max_pages: int = 16) -> List[str]:
    caps = []
    for i in range(min(max_pages, doc.page_count)):
        for ln in doc[i].get_text().splitlines():
            s = ln.strip()
            if re.match(r"^(?:Figure|Fig\.?)\s+[\dA-Za-z\-]+", s):
                caps.append(s)
    return caps


def _first(text: str, pattern: str, groups: int = 1):
    """Return the first regex match's group(s), or None. µ/Ω-tolerant."""
    m = re.search(pattern, text, re.I)
    if not m:
        return None
    if groups == 1:
        return m.group(1).strip()
    return tuple(g.strip() if g else g for g in m.groups()[:groups])


def _all_text(doc, max_pages: int = 28) -> str:
    """Deeper text sweep — design procedure & layout live mid-document."""
    n = min(max_pages, doc.page_count)
    return "\n".join(doc[i].get_text() for i in range(n))


def _pin_functions(doc, max_pages: int = 5) -> List[Dict]:
    """Extract the 'Pin Functions' table (name / number / I-O / description)."""
    if not _HAVE_FITZ:
        return []
    for i in range(min(max_pages, doc.page_count)):
        try:
            tabs = doc[i].find_tables()
        except Exception:
            continue
        for t in tabs.tables:
            rows = t.extract()
            if not rows:
                continue
            hdr = " ".join(str(c) for c in rows[0] if c).upper()
            if "PIN" not in hdr or "DESCRIPTION" not in hdr:
                continue
            out = []
            for r in rows[1:]:
                cells = [(c or "").strip() for c in r]
                if len(cells) < 4:
                    continue
                name, num, io, desc = cells[0], cells[1], cells[2], cells[3]
                if not name or name.upper() in ("NAME", "PIN"):
                    continue
                if not re.search(r"\d", num):
                    continue
                out.append({"name": name, "number": num, "io": io,
                            "desc": re.sub(r"\s+", " ", desc)})
            if out:
                return out
    return []




# Design/layout prose extractors moved to analysis.text_extract (single source
# of truth); re-exported here for backward compatibility.
from .analysis.text_extract import (  # noqa: E402
    PROC_HEADS as _PROC_HEADS,
    design_requirements as _design_requirements,
    design_procedure as _design_procedure,
    layout_guidelines as _layout_guidelines,
)
from .analysis.components import (  # noqa: E402
    RegulatorProfile as _RegulatorProfile,
    OpAmpProfile as _OpAmpProfile,
    DiodeProfile as _DiodeProfile,
    ResistorProfile as _ResistorProfile,
)


_SPEC_TABLE_HEADS = (
    (r"Absolute Maximum Ratings", "Absolute Maximum Ratings"),
    (r"ESD Ratings", "ESD Ratings"),
    (r"Recommended Operating Conditions", "Recommended Operating Conditions"),
    (r"Electrical Characteristics", "Electrical Characteristics"),
)


def _table_name_for(page, header_y: float) -> str:
    """Nearest spec-table heading printed above a numeric header row."""
    best, best_y = "Parametreler", -1.0
    for blk in page.get_text("dict").get("blocks", []):
        for line in blk.get("lines", []):
            txt = "".join(s.get("text", "") for s in line.get("spans", []))
            y = line["bbox"][1]
            if y >= header_y:
                continue
            for rx, name in _SPEC_TABLE_HEADS:
                if re.search(rx, txt) and y > best_y:
                    best, best_y = name, y
    return best


def _parametric_tables(doc, max_pages: int = 8) -> List[Dict]:
    """Reconstruct the §Specifications parametric tables by binning numeric
    words into MIN / TYP(or NOM) / MAX columns using the header word x-centres —
    PyMuPDF/find_tables collapse these numeric columns into one cell, losing the
    per-column value, so we recover it geometrically. Returns a flat list of
    {table, section, parameter, conditions, min, typ, max, unit}.
    """
    if not _HAVE_FITZ:
        return []
    numrx = re.compile(r"^[\u00b1+\-]?[\d.]+$")
    out: List[Dict] = []
    for pno in range(min(max_pages, doc.page_count)):
        page = doc[pno]
        words = [(w[0], w[1], w[2], w[3], w[4]) for w in page.get_text("words")]
        # Locate numeric-column header rows: a y where MIN and MAX both appear.
        marks: Dict[int, Dict[str, float]] = {}
        for x0, y0, x1, y1, t in words:
            if t in ("MIN", "MAX", "TYP", "NOM", "UNIT", "VALUE"):
                marks.setdefault(round(y0), {})[t] = (x0 + x1) / 2
        headers = sorted(y for y, m in marks.items()
                         if "MAX" in m and ("MIN" in m or "VALUE" in m))
        if not headers:
            continue
        for hi, hy in enumerate(headers):
            m = marks[hy]
            c_max = m["MAX"]
            c_min = m.get("MIN", c_max)
            c_mid = m.get("TYP", m.get("NOM"))
            c_unit = m.get("UNIT", c_max + 60)
            b_lo = (c_min + c_mid) / 2 if c_mid else (c_min + c_max) / 2
            b_hi = (c_mid + c_max) / 2 if c_mid else (c_min + c_max) / 2
            val_left = min(c_min, c_max) - 22
            unit_left = (c_max + c_unit) / 2
            table = _table_name_for(page, hy)
            y_end = headers[hi + 1] if hi + 1 < len(headers) else 1e9
            # Cluster words into rows below this header, above the next header.
            rows: Dict[int, List] = {}
            for x0, y0, x1, y1, t in words:
                if y0 <= hy + 2 or y0 >= y_end - 1:
                    continue
                rows.setdefault(round(y0 / 3) * 3, []).append((x0, x1, t))
            section = ""
            for ry in sorted(rows):
                cells = sorted(rows[ry], key=lambda z: z[0])
                param = " ".join(t for x0, x1, t in cells if (x0 + x1) / 2 < 260)
                cond = " ".join(t for x0, x1, t in cells
                                if 260 <= (x0 + x1) / 2 < val_left)
                nums = [(x0, x1, t) for x0, x1, t in cells
                        if (x0 + x1) / 2 >= val_left and numrx.match(t)]
                unit = " ".join(t for x0, x1, t in cells
                                if (x0 + x1) / 2 >= unit_left and not numrx.match(t))
                param = re.sub(r"\s+", " ", param).strip()
                cond = re.sub(r"\s+", " ", cond).strip()
                low = param.lower()
                if any(k in low for k in ("copyright", "submit document",
                                          "product folder", "www.ti.com")):
                    continue
                # Section header: all-caps parameter, no numbers, no conditions.
                if param and not nums and not cond and param.upper() == param \
                        and len(param) > 3:
                    section = param
                    continue
                if not nums:
                    continue
                vmin = vtyp = vmax = ""
                for x0, x1, t in nums:
                    cx = (x0 + x1) / 2
                    if c_mid and b_lo <= cx < b_hi:
                        vtyp = t
                    elif cx >= b_hi:
                        vmax = t
                    else:
                        vmin = t
                out.append({
                    "table": table, "section": section,
                    "parameter": param or "(devam)", "conditions": cond,
                    "min": vmin, "typ": vtyp, "max": vmax, "unit": unit,
                })
    return out


def _raster_curve_fallback(pdf_path: str, targets, curves: Dict) -> None:
    """For curve targets the vector engine missed, try the OCR/CV raster
    digitizer. Only HIGH-confidence results are accepted (verified axis
    calibration) so unreliable OCR output is never injected as clean data."""
    try:
        from .analysis import rastercurves as _rc
    except Exception:
        return
    if not _rc.available():
        return
    for key, cap_rx, ux, uy, desc in targets:
        if isinstance(curves.get(key), dict):
            continue                              # vector already captured it
        try:
            r = _rc.digitize_pdf_caption(pdf_path, cap_rx)
        except Exception:
            continue
        if r.get("confidence") == "high" and r.get("curve"):
            # Same dB-span sanity as the vector path (a flat "dB" trace is a bad
            # digitization, not a real roll-off).
            if pdfcurves.db_fragment(uy, r["curve"]):
                continue
            # The raster OCR reads tick *values* but not the axis *unit* string,
            # so a current axis keeps the target's default "mA". A quiescent
            # current plotted in the 1..1000 range is µA, not mA (no small-signal
            # part draws hundreds of mA of Iq) — relabel so it isn't off by 1000×
            # like the pre-fix vector path was.
            uy2 = uy
            if key in ("iq_temp", "iq_supply", "iq_vs_temp") and "(mA)" in uy:
                ys = [p[1] for p in r["curve"]]
                if ys and max(abs(v) for v in ys) < 1000:
                    uy2 = uy.replace("(mA)", "(µA)")
            curves[key] = {
                "caption": r.get("caption", ""), "unit_x": ux, "unit_y": uy2,
                "desc": desc, "confidence": "high", "npoints": r["npoints"],
                "curve": r["curve"], "source": "ocr",
            }

# ---------------------------------------------------------------------------
# Analyzer plugin base + registry
# ---------------------------------------------------------------------------
class Analyzer:
    key: str = "component"
    label: str = "Komponent"
    keywords: Tuple[str, ...] = ()
    curve_targets: Tuple[Tuple[str, str, str, str, str], ...] = ()
    curve_max_pages: int = 16

    def matches(self, text: str) -> float:
        low = text.lower()
        return float(sum(low.count(k) for k in self.keywords))

    def extract_specs(self, text: str, part: str = "") -> List[Tuple[str, str]]:
        return []

    def analyze(self, pdf_path: str, doc, text: str) -> Dict:
        part = _part_number(doc, pdf_path)
        specs = self.extract_specs(text, part)
        curves = {}
        if self.curve_targets:
            wanted = [(t[0], t[1]) for t in self.curve_targets]
            raw = pdfcurves.extract_labeled_curves(
                pdf_path, wanted, max_pages=self.curve_max_pages)
            meta_by_key = {t[0]: t for t in self.curve_targets}
            for k, tup in meta_by_key.items():
                r = raw.get(k)
                if not r:
                    continue
                # Prefer the unit read off the datasheet's own axis title over
                # the hardcoded target unit — an op-amp Iq plot is µA, not the
                # generic "mA" default. Only the unit token is swapped; the axis
                # quantity/label text (tup[2]/tup[3]) is kept for wording.
                meta = r.get("meta") or {}
                # Reject a semantic misfire: the caption matched but the plot's
                # x-axis is a different quantity than this target means (e.g. a
                # fsw-vs-R target catching a fsw-vs-junction-temperature plot).
                if pdfcurves.axis_dim_mismatch(tup[2], meta.get("ux")):
                    continue
                ux = _relabel_unit(tup[2], meta.get("ux"))
                uy = _relabel_unit(tup[3], meta.get("uy"))
                conf = r["confidence"]
                # A cleanly-calibrated dB curve that spans too few dB is a
                # fragment (axis-fit can't see this) — demote it so a bad PSRR
                # isn't presented as trustworthy.
                if conf == "high" and pdfcurves.db_fragment(uy, r["curve"]):
                    conf = "low"
                curves[k] = {
                    "caption": r["caption"],
                    "unit_x": ux, "unit_y": uy, "desc": tup[4],
                    "confidence": conf,
                    "npoints": len(r["curve"]),
                    "curve": r["curve"],
                }
                if r.get("traces"):
                    # One frame held several colour-separated curves; expose each
                    # as a labelled trace alongside the primary (largest) curve.
                    curves[k]["traces"] = [
                        {"label": f"iz {i + 1}", "color": t["color"],
                         "npoints": t["npoints"], "spread": t["spread"],
                         "curve": t["curve"]}
                        for i, t in enumerate(r["traces"])]
                    curves[k]["ntraces"] = len(r["traces"])
            curves["_log"] = raw.get("log", [])
            _raster_curve_fallback(pdf_path, self.curve_targets, curves)
        result = {
            "type": self.key,
            "type_label": self.label,
            "part": part,
            "description": _description(text),
            "features": _features(text),
            "figures": _figure_captions(doc),
            "pinout": _pin_functions(doc),
            "specs": specs,
            "curves": curves,
        }
        result.update(self.extra_sections(doc, text, curves))
        return result

    def extra_sections(self, doc, text: str, curves: Dict) -> Dict:
        """Type-specific extra analysis merged into the result. Base: none."""
        return {}


class RegulatorAnalyzer(Analyzer):
    key = "regulator"
    label = "Regülatör / DC-DC"
    # Type keywords + curve targets live once in analysis.components.
    keywords = _RegulatorProfile.keywords
    curve_targets = _RegulatorProfile.curve_targets

    def extract_specs(self, text: str, part: str = "") -> List[Tuple[str, str]]:
        out: List[Tuple[str, str]] = []

        def add(label, value):
            if value:
                out.append((label, value))

        vin = _first(text, r"([\d.]+)\s*-?\s*V?\s*to\s*([\d.]+)\s*-?\s*V"
                           r"\s*input\s*voltage", 2)
        if vin:
            add("Giriş gerilimi (VIN)", f"{vin[0]} V – {vin[1]} V")
        vout = _first(text, r"([\d.]+)\s*-?\s*V?\s*to\s*([\d.]+)\s*-?\s*V"
                            r"\s*output\s*voltage", 2)
        if vout:
            add("Çıkış gerilimi (VOUT)", f"{vout[0]} V – {vout[1]} V")
        isw = _first(text, r"([\d.]+)\s*-?\s*A\s*switch\s*current")
        if isw:
            add("Anahtar akım kapasitesi", f"{isw} A")
        fsw = _first(text, r"switching\s*frequency[:\s]*([\d.]+)\s*(kHz|MHz)"
                           r"\s*to\s*([\d.]+)\s*(kHz|MHz)", 4)
        if fsw:
            add("Anahtarlama frekansı", f"{fsw[0]} {fsw[1]} – {fsw[2]} {fsw[3]}")
        eff = _first(text, r"(?:up to\s*)?([\d.]+)\s*%\s*efficiency")
        if eff:
            add("Tepe verim", f"%{eff}")
        sd = _first(text, r"([\d.]+)\s*-?\s*[µuμ]A[^.\n]*shutdown")
        if not sd:
            sd = _first(text, r"shutdown[^.\n]*?([\d.]+)\s*-?\s*[µuμ]A")
        if sd:
            add("Kapalı-durum akımı (shutdown)", f"{sd} µA")
        ovp = _first(text, r"overvoltage\s*protection\s*at\s*([\d.]+)\s*V")
        if ovp:
            add("Aşırı gerilim koruma (OVP)", f"{ovp} V")
        rds = _first(text, r"([\d.]+)\s*-?\s*m[Ω\u2126\u03a9]\s*power\s*switch"
                           r"\s*and\s*a\s*([\d.]+)\s*-?\s*m[Ω\u2126\u03a9]\s*"
                           r"rectifier", 2)
        if rds:
            add("Anahtar direnci RDS(on)",
                f"{rds[0]} mΩ (HS) / {rds[1]} mΩ (rectifier)")
        pkg = _first(text, r"([\d.]+\s*-?mm\s*[x×]\s*[\d.]+\s*-?mm[^.\n]*?"
                           r"(?:VQFN|QFN|WSON|SON|DFN|package))")
        if pkg:
            add("Paket", re.sub(r"\s+", " ", pkg))
        # Control topology — descriptive.
        for phrase, lab in (
            (r"synchronous\s+boost", "Senkron boost"),
            (r"synchronous\s+buck", "Senkron buck"),
            (r"buck-boost", "Buck-boost"),
            (r"constant\s+off-?time", "Constant off-time peak-current kontrol"),
            (r"low-?dropout|LDO", "LDO (lineer)"),
        ):
            if re.search(phrase, text, re.I):
                add("Topoloji", lab)
                break
        return out

    def extra_sections(self, doc, text: str, curves: Dict) -> Dict:
        deep = _all_text(doc)
        return {
            "design_requirements": _design_requirements(deep),
            "design_procedure": _design_procedure(deep),
            "curve_interpretation": self.interpret_curves(curves),
            "layout_guidelines": _layout_guidelines(deep),
        }

    def interpret_curves(self, curves: Dict) -> List[str]:
        """Plain-language findings from high-confidence curves. Single source of
        truth: analysis.components.RegulatorProfile."""
        return _RegulatorProfile().interpret_curves(curves)


class OpAmpAnalyzer(Analyzer):
    key = "opamp"
    label = "Op-Amp / Operasyonel Yükselteç"
    keywords = _OpAmpProfile.keywords
    curve_targets = _OpAmpProfile.curve_targets
    curve_max_pages = 30

    def extract_specs(self, text: str, part: str = "") -> List[Tuple[str, str]]:
        out: List[Tuple[str, str]] = []

        def add(label, value):
            if value:
                out.append((label, value))

        sup = _first(text, r"([\d.]+)\s*V?\s*to\s*([\d.]+)\s*V\s*(?:supply|"
                           r"operating|power[- ]supply)", 2)
        if sup:
            add("Besleme gerilimi aralığı", f"{sup[0]} V – {sup[1]} V")
        gbw = _first(text, r"gain[- ]?bandwidth(?:\s*product)?[:\s]*"
                           r"(?:of\s*)?([\d.]+)\s*(kHz|MHz|GHz)", 2)
        if gbw:
            add("Kazanç-bant genişliği (GBW)", f"{gbw[0]} {gbw[1]}")
        sr = _first(text, r"slew\s*rate[:\s]*(?:of\s*)?([\d.]+)\s*(V/[µuμ]s)", 2)
        if sr:
            add("Yükselme hızı (slew rate)", f"{sr[0]} {sr[1]}")
        vos = _first(text, r"(?:input\s*)?offset\s*voltage[:\s]*(?:±\s*)?"
                           r"([\d.]+)\s*([µuμm]V)", 2)
        if vos:
            add("Giriş ofset gerilimi", f"±{vos[0]} {vos[1]}")
        iq = _first(text, r"quiescent\s*current[^.\n]*?([\d.]+)\s*([µuμm]A)", 2)
        if iq:
            add("Sükunet akımı (kanal başına)", f"{iq[0]} {iq[1]}")
        cmrr = _first(text, r"CMRR[^.\n]*?([\d.]+)\s*dB")
        if cmrr:
            add("CMRR", f"{cmrr} dB")
        ib = _first(text, r"input\s*bias\s*current[^.\n]*?([\d.]+)\s*"
                          r"(pA|nA|fA)", 2)
        if ib:
            add("Giriş bias akımı", f"{ib[0]} {ib[1]}")
        noise = _first(text, r"([\d.]+)\s*nV/\s*[√v]?\s*Hz")
        if noise:
            add("Giriş gerilim gürültüsü", f"{noise} nV/√Hz")
        for phrase, lab in ((r"\bquad\b", "4 (quad)"),
                            (r"\bdual\b", "2 (dual)"),
                            (r"\bsingle\b", "1 (single)")):
            if re.search(phrase, text, re.I):
                add("Kanal sayısı", lab)
                break
        pkg = _first(text, r"([\d.]+\s*-?mm\s*[x×]\s*[\d.]+\s*-?mm[^.\n]*?"
                           r"(?:SOT|SOIC|VSSOP|TSSOP|MSOP|QFN|package))")
        if pkg:
            add("Paket", re.sub(r"\s+", " ", pkg))
        return out

    def extra_sections(self, doc, text: str, curves: Dict) -> Dict:
        prof = _OpAmpProfile()
        sub_key, sub_label = prof.detect_subtype(text)
        return {
            "subtype": sub_key,
            "subtype_label": sub_label,
            "curve_interpretation": prof.interpret_curves(curves),
            "layout_guidelines": _layout_guidelines(_all_text(doc)),
        }


class DiodeAnalyzer(Analyzer):
    key = "diode"
    label = "Diyot"
    keywords = _DiodeProfile.keywords
    curve_targets = _DiodeProfile.curve_targets
    curve_max_pages = 20

    def extract_specs(self, text: str, part: str = "") -> List[Tuple[str, str]]:
        out: List[Tuple[str, str]] = []

        def add(label, value):
            if value:
                out.append((label, value))

        vf = _first(text, r"forward voltage[^.\n]*?([\d.]+)\s*(mV|V)\b", 2)
        if vf:
            add("İleri gerilim (VF)", f"{vf[0]} {vf[1]}")
        vz = _first(text, r"zener voltage[^.\n]*?([\d.]+)\s*V", 1)
        if vz:
            add("Zener gerilimi (VZ)", f"{vz} V")
        vc = _first(text, r"clamping voltage[^.\n]*?([\d.]+)\s*V", 1)
        if vc:
            add("Kenetleme gerilimi (VC)", f"{vc} V")
        vrwm = _first(text, r"(?:working voltage|reverse stand-?off|stand-?off "
                            r"voltage|V\W?RWM)[^.\n]*?([\d.]+)\s*V", 1)
        if vrwm:
            add("Çalışma/stand-off gerilimi (VRWM)", f"{vrwm} V")
        vbr = _first(text, r"(?:reverse )?breakdown voltage[^.\n]*?"
                           r"([\d.]+)\s*V", 1)
        if vbr:
            add("Kırılma gerilimi (VBR)", f"{vbr} V")
        ipp = _first(text, r"(?:peak pulse current|I\W?PP)[^.\n]*?([\d.]+)\s*"
                           r"(mA|A)\b", 2)
        if ipp:
            add("Tepe darbe akımı (IPP)", f"{ipp[0]} {ipp[1]}")
        vrrm = _first(text, r"(?:V\W?RRM|repetitive peak reverse|maximum "
                            r"repetitive reverse|reverse voltage)[^.\n]*?"
                            r"([\d.]+)\s*V", 1)
        if vrrm:
            add("Tepe ters gerilim (VRRM)", f"{vrrm} V")
        ifav = _first(text, r"(?:I\W?F\W?\(?AV\)?|average rectified[^.\n]*?"
                            r"forward current)[^.\n]*?([\d.]+)\s*(mA|A)\b", 2)
        if ifav:
            add("Ortalama ileri akım (IF(AV))", f"{ifav[0]} {ifav[1]}")
        ifsm = _first(text, r"(?:surge|non-?repetitive)[^.\n]*?([\d.]+)\s*A\b", 1)
        if ifsm:
            add("Tepe surge akımı (IFSM)", f"{ifsm} A")
        ir = _first(text, r"reverse (?:current|leakage)[^.\n]*?([\d.]+)\s*"
                          r"([µuμn]A)\b", 2)
        if ir:
            add("Ters kaçak akım (IR)", f"{ir[0]} {ir[1]}")
        trr = _first(text, r"reverse recovery[^.\n]*?([\d.]+)\s*(ns|µs|us|ps)", 2)
        if trr:
            add("Ters toparlanma süresi (trr)", f"{trr[0]} {trr[1]}")
        cj = _first(text, r"(?:junction )?capacitance[^.\n]*?([\d.]+)\s*"
                          r"(pF|nF)\b", 2)
        if cj:
            add("Jonksiyon kapasitansı (Cj)", f"{cj[0]} {cj[1]}")
        pd = _first(text, r"(?:total )?power dissipation[^.\n]*?([\d.]+)\s*"
                          r"(mW|W)\b", 2)
        if pd:
            add("Güç harcaması (PD)", f"{pd[0]} {pd[1]}")
        tj = _first(text, r"(?:junction temperature|operating[^.\n]*?"
                          r"temperature)[^.\n]*?([\-\d.]+)\s*(?:to|…|-)\s*"
                          r"([+\-\d.]+)\s*°?C", 2)
        if tj:
            add("Çalışma sıcaklığı", f"{tj[0]} °C … {tj[1]} °C")
        for phrase, lab in ((r"\bsingle\b", "1 (tekli)"),
                            (r"\bdual\b|common cathode|common anode",
                             "2 (ikili / ortak katot-anot)"),
                            (r"\barray\b|quad", "Dizi (array)")):
            if re.search(phrase, text, re.I):
                add("Konfigürasyon", lab)
                break
        pkg = _first(text, r"(SOD-?\d+|SOT-?\d+|SMA|SMB|SMC|DO-?\d+|"
                           r"TO-?\d+|DFN\d*|QFN\d*)", 1)
        if pkg:
            add("Paket", pkg.upper())
        return out

    def extra_sections(self, doc, text: str, curves: Dict) -> Dict:
        prof = _DiodeProfile()
        sub_key, sub_label = prof.detect_subtype(text)
        return {
            "subtype": sub_key,
            "subtype_label": sub_label,
            "curve_interpretation": prof.interpret_curves(curves),
            "layout_guidelines": _layout_guidelines(_all_text(doc)),
        }


class ResistorAnalyzer(Analyzer):
    key = "resistor"
    label = "Direnç (pasif)"
    keywords = _ResistorProfile.keywords
    curve_targets = _ResistorProfile.curve_targets
    curve_max_pages = 16

    # Chip-resistor case code (metric, from the part number) -> (imperial size,
    # typical rated power). Industry-standard across Samsung RC / Yageo RC /
    # Panasonic ERJ, so decoding the part number beats scraping a family table
    # that lists every size at once.
    _SIZE = {
        "0402": ("01005", "1/32 W"), "0603": ("0201", "1/20 W"),
        "1005": ("0402", "1/16 W"), "1608": ("0603", "1/10 W"),
        "2012": ("0805", "1/8 W"), "3216": ("1206", "1/4 W"),
        "3225": ("1210", "1/3 W"), "5025": ("2010", "1/2 W"),
        "6432": ("2512", "1 W"),
    }
    # EIA tolerance code letter -> value.
    _TOL = {"B": "±0.1%", "C": "±0.25%", "D": "±0.5%", "F": "±1%",
            "G": "±2%", "J": "±5%", "K": "±10%"}

    def extract_specs(self, text: str, part: str = "") -> List[Tuple[str, str]]:
        out: List[Tuple[str, str]] = []

        def add(label, value):
            if value:
                out.append((label, value))

        # 1) Decode the part number first — the reliable source of size /
        # tolerance / power on a family datasheet whose specs live in tables.
        # Prefer the filename-derived MPN (``part``): a generic family catalogue
        # lists every size in-text, so only the part number pins THIS one. No
        # trailing boundary — the tolerance letter is usually followed by the
        # resistance code ("RC1608J000CS"), so \b after it would never match.
        rx = r"\b[A-Z]{2}(" + "|".join(self._SIZE) + r")([BCDFGJK])"
        pn = _first(part, rx, 2) or _first(text, rx, 2)
        if pn:
            imp, pw = self._SIZE[pn[0]]
            add("Boyut", f"{pn[0]} (metrik) / {imp} (imperial)")
            add("Anma gücü (tipik)", pw)
            add("Tolerans", self._TOL.get(pn[1], pn[1]))

        # 2) Prose specs the part number doesn't carry (best-effort; family
        # datasheets keep most of these in tables, so absence is honest).
        rng = _first(text, r"resistance range[^.\n]*?"
                           r"([\d.]+\s*[mkMG]?\s*[Ωohm]+)[^.\n]*?"
                           r"(?:to|…|-|~)\s*([\d.]+\s*[mkMG]?\s*[Ωohm]+)", 2)
        if rng:
            add("Direnç aralığı", f"{rng[0]} – {rng[1]}")
        if not pn:
            tol = _first(text, r"(?:resistance )?tolerance[^.\n]*?"
                               r"(±?\s*[\d.]+\s*%)", 1)
            if tol:
                add("Tolerans", re.sub(r"\s+", "", tol))
        tcr = _first(text, r"(?:temperature coefficient|T\.?C\.?R\.?)[^.\n]*?"
                           r"(±?\s*[\d.]+\s*ppm)", 1)
        if tcr:
            add("Sıcaklık katsayısı (TCR)", re.sub(r"\s+", "", tcr) + "/°C")
        vmax = _first(text, r"(?:maximum working|max\.? working|rated|limiting "
                            r"element) voltage[^.\n]*?([\d.]+)\s*V", 1)
        if vmax:
            add("Maks. çalışma gerilimi", f"{vmax} V")
        tmp = _first(text, r"operating temperature[^.\n]*?([\-\d.]+)\s*"
                           r"(?:to|…|-)\s*([+\-\d.]+)\s*°?C", 2)
        if tmp:
            add("Çalışma sıcaklığı", f"{tmp[0]} °C … {tmp[1]} °C")
        return out

    def extra_sections(self, doc, text: str, curves: Dict) -> Dict:
        prof = _ResistorProfile()
        sub_key, sub_label = prof.detect_subtype(text)
        return {
            "subtype": sub_key,
            "subtype_label": sub_label,
            "curve_interpretation": prof.interpret_curves(curves),
        }


ANALYZERS: List[Analyzer] = [
    RegulatorAnalyzer(), OpAmpAnalyzer(), DiodeAnalyzer(), ResistorAnalyzer(),
]


def get_analyzer(key: str) -> Optional[Analyzer]:
    return next((a for a in ANALYZERS if a.key == key), None)


def detect_type(text: str) -> Tuple[str, Dict[str, float]]:
    """Score every analyzer against the text; return (best_key, all_scores)."""
    scores = {a.key: a.matches(text) for a in ANALYZERS}
    best = max(scores, key=scores.get) if scores else ""
    if not scores or scores[best] <= 0:
        return "unknown", scores
    return best, scores


# ---------------------------------------------------------------------------
# Top-level entry point + output writers
# ---------------------------------------------------------------------------
def analyze_pdf(pdf_path: str, type_hint: Optional[str] = None,
                out_dir: Optional[str] = None, lang: str = "tr") -> Dict:
    """Analyze a datasheet PDF. ``type_hint`` forces an analyzer; None or
    'auto' auto-detects. Writes ``<part>_analysis.json``, one CSV per
    high/low-confidence curve, and ``<part>_analysis.md`` when ``out_dir`` is
    given. Returns the analysis dict (plus written-file paths under 'outputs').
    """
    if not _HAVE_FITZ:
        raise RuntimeError("PyMuPDF (pymupdf) gerekli — kurulu değil.")
    doc = fitz.open(pdf_path)
    try:
        text = _full_text(doc)
        scores = {}
        if type_hint and type_hint not in ("auto", ""):
            key = type_hint
        else:
            key, scores = detect_type(text)
        analyzer = get_analyzer(key)
        if analyzer is None:
            return {"type": key, "type_label": "Bilinmiyor",
                    "part": _part_number(doc, pdf_path),
                    "detect_scores": scores,
                    "error": f"'{key}' türü için analyzer yok. "
                             f"Mevcut: {[a.key for a in ANALYZERS]}"}
        result = analyzer.analyze(pdf_path, doc, text)
        result["detect_scores"] = scores
        result["source_pdf"] = os.path.abspath(pdf_path)
    finally:
        doc.close()

    _enrich_with_sections(result, pdf_path)
    _translate_result(result, lang)
    result["lang"] = lang

    if out_dir:
        result["outputs"] = _write_outputs(result, out_dir)
    return result


def _enrich_with_sections(result: Dict, pdf_path: str) -> None:
    """Fold in the clean per-section engine (analysis.*): attach vendor
    detection, per-section confidence, the full MIN/TYP/MAX spec table, and
    upgrade the pinout with the higher-quality PinoutSection output. Degrades
    silently if pdfplumber/the package is unavailable — the legacy result stays
    valid on its own."""
    try:
        from .analysis import analyze as _section_analyze
    except Exception:
        return
    try:
        sec = _section_analyze(pdf_path)
    except Exception as e:  # never let enrichment break the legacy result
        result["section_error"] = f"{type(e).__name__}: {e}"
        return
    result["vendor"] = sec.get("vendor")
    sections = sec.get("sections", {})
    result["section_confidence"] = {
        k: {"confidence": v.get("confidence"), "reason": v.get("reason")}
        for k, v in sections.items()}
    specs_sec = sections.get("specs", {})
    if specs_sec.get("data"):
        result["spec_table"] = specs_sec["data"]
        result["spec_table_confidence"] = specs_sec.get("confidence")
    pin_sec = sections.get("pinout", {})
    if pin_sec.get("data") and pin_sec.get("confidence") in ("high", "med"):
        # Legacy consumers (report/excel/GUI) key pins on 'desc'.
        result["pinout"] = [
            {"name": p["name"], "number": p["number"], "io": p["io"],
             "desc": p.get("description", "")}
            for p in pin_sec["data"]]
        result["pinout_source"] = "analysis"


def _translate_result(result: Dict, lang: str = "tr") -> None:
    """Translate the English datasheet-sourced prose (description, features, pin
    descriptions, layout guidelines, design-procedure intents) into ``lang`` so
    a Turkish report reads fully in Turkish. Offline-first (Argos), DeepL as
    fallback; degrades to the original text when no backend is available. English
    output (``lang`` starting with 'en') is a no-op."""
    if not lang or lang.lower().startswith("en"):
        return
    try:
        from .analysis import translate as _tr
    except Exception:
        return
    tgt = "tr" if lang.lower().startswith("tr") else lang.lower()[:2]
    if not _tr.any_available("en", tgt):
        result["translation"] = {"applied": False,
                                 "reason": "çeviri backend'i yok (argos/deepl)"}
        return

    def tx(items):
        return _tr.translate(items, target=tgt, source="en")

    if result.get("description"):
        result["description"] = tx([result["description"]])[0]
    feats = result.get("features") or []
    if feats:
        result["features"] = tx(feats)
    pins = result.get("pinout") or []
    descs = [p.get("desc", "") for p in pins]
    if any(descs):
        for p, d in zip(pins, tx(descs)):
            p["desc"] = d
    lay = result.get("layout_guidelines") or []
    if lay:
        result["layout_guidelines"] = tx(lay)
    intents = [s.get("intent", "") for s in (result.get("design_procedure") or [])]
    if any(intents):
        for s, it in zip(result["design_procedure"], tx(intents)):
            if it:
                s["intent"] = it
    result["translation"] = {"applied": True, "lang": tgt,
                             "backend": _tr.active_backend("en", tgt)}


def _figure_caption_patterns(result: Dict) -> Tuple[List[str], List[str]]:
    """Schematic + layout figure-caption regexes from the detected component
    profile (falls back to the generic profile's patterns)."""
    from .analysis import components as _comp
    prof = _comp.get_component(result.get("type", "")) or _comp.ComponentProfile()
    return (list(prof.schematic_captions), list(prof.layout_captions))


def _write_outputs(result: Dict, out_dir: str) -> Dict[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    part = re.sub(r"[^\w\-]", "_", result.get("part", "component"))
    written: Dict[str, str] = {}

    # Full MIN/TYP/MAX spec table (per-section engine) as its own CSV.
    spec_table = result.get("spec_table")
    if spec_table:
        sp_path = os.path.join(out_dir, f"{part}_spec_table.csv")
        with open(sp_path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["section", "parameter", "symbol", "conditions",
                        "min", "typ", "max", "unit"])
            for r in spec_table:
                w.writerow([r.get(k, "") for k in ("section", "parameter",
                            "symbol", "conditions", "min", "typ", "max", "unit")])
        written["spec_table"] = sp_path

    # Per-curve CSVs (data curves only).
    curves = result.get("curves", {})
    for key, c in curves.items():
        if key == "_log" or not isinstance(c, dict) or "curve" not in c:
            continue
        path = os.path.join(out_dir, f"{part}_{key}.csv")
        traces = c.get("traces")
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            if traces:
                # Long format: one row per (trace, point) so N colour-separated
                # curves share one file.
                w.writerow(["trace", c.get("unit_x", "x"), c.get("unit_y", "y"),
                            f"confidence={c.get('confidence')}"])
                for tr in traces:
                    for x, y in tr["curve"]:
                        w.writerow([tr["label"], x, y])
            else:
                w.writerow([c.get("unit_x", "x"), c.get("unit_y", "y"),
                            f"confidence={c.get('confidence')}"])
                for x, y in c["curve"]:
                    w.writerow([x, y])
        written[f"csv:{key}"] = path

    # --- Visual renders: curves, pinout table, spec ranges, datasheet figures.
    # The datasheet presents these as graphics, so the output must too; each
    # render degrades to a no-op when matplotlib / PyMuPDF is absent.
    images: Dict[str, object] = {}
    try:
        from .analysis import plotting as _plot, figures as _figs
    except Exception:
        _plot = _figs = None
    if _plot is not None and _plot.available():
        lang = result.get("lang", "tr")
        try:
            curve_pngs = _plot.render_curves(curves, out_dir, part, lang)
            if curve_pngs:
                images["curves"] = curve_pngs
                for k, p in curve_pngs.items():
                    written[f"png:{k}"] = p
        except Exception as e:
            result.setdefault("render_errors", []).append(f"curves: {e}")
        try:
            pin_png = _plot.render_pinout_table(result.get("pinout", []),
                                                out_dir, part, lang=lang)
            if pin_png:
                images["pinout"] = pin_png
                written["png:pinout"] = pin_png
        except Exception as e:
            result.setdefault("render_errors", []).append(f"pinout: {e}")
        if spec_table:
            try:
                sr_png = _plot.render_spec_ranges(spec_table, out_dir, part,
                                                  lang=lang)
                if sr_png:
                    images["spec_ranges"] = sr_png
                    written["png:spec_ranges"] = sr_png
            except Exception as e:
                result.setdefault("render_errors", []).append(f"spec: {e}")
    if _figs is not None and _figs.available():
        try:
            sch_caps, lay_caps = _figure_caption_patterns(result)
            figs = _figs.extract_figures(result.get("source_pdf", ""),
                                         sch_caps, lay_caps, out_dir, part)
            for cat in ("schematic", "layout"):
                if figs.get(cat):
                    images[cat] = figs[cat]
                    for i, f in enumerate(figs[cat], 1):
                        written[f"fig:{cat}:{i}"] = f["path"]
        except Exception as e:
            result.setdefault("render_errors", []).append(f"figures: {e}")
    if images:
        result["images"] = images

    # JSON (curves compacted to metadata + point count; full points in CSV).
    json_path = os.path.join(out_dir, f"{part}_analysis.json")
    slim = dict(result)
    slim_curves = {}
    for key, c in curves.items():
        if key == "_log":
            slim_curves[key] = c
        elif isinstance(c, dict):
            sc = {k: v for k, v in c.items() if k != "curve"}
            if sc.get("traces"):
                # keep per-trace metadata, drop the heavy point arrays
                sc["traces"] = [{k: v for k, v in tr.items() if k != "curve"}
                                for tr in sc["traces"]]
            slim_curves[key] = sc
    slim["curves"] = slim_curves
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(slim, fh, indent=2, ensure_ascii=False)
    written["json"] = json_path

    # Markdown report.
    md_text = _render_report(result, written)
    md_path = os.path.join(out_dir, f"{part}_analysis.md")
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(md_text)
    written["report"] = md_path

    # Styled, readable HTML view (optional — needs the `markdown` package).
    html_path = _write_html_report(md_text, out_dir, part)
    if html_path:
        written["html"] = html_path
    return written


_HTML_CSS = """
* { box-sizing:border-box; }
body { font-family:'Segoe UI',system-ui,-apple-system,'Helvetica Neue',Arial,sans-serif;
  max-width:1000px; margin:0 auto; padding:32px 20px 80px; color:#1f2733;
  font-size:16px; line-height:1.65; background:#fafbfc; }
h1 { font-size:28px; font-weight:700; margin:0 0 4px; letter-spacing:-.01em; }
h2 { font-size:21px; font-weight:600; margin:36px 0 12px; padding-bottom:6px;
  border-bottom:2px solid #eceff3; }
h3 { font-size:17px; font-weight:600; margin:22px 0 8px; }
img { max-width:100%; height:auto; border:1px solid #d7dde5; border-radius:8px;
  margin:10px 0; box-shadow:0 1px 3px rgba(0,0,0,.06); background:#fff; }
em { display:block; color:#5b6b7b; font-size:14.5px; font-style:normal;
  margin:2px 0 18px; padding-left:10px; border-left:3px solid #c9d2dc; }
table { border-collapse:collapse; width:100%; margin:12px 0 22px; font-size:14.5px;
  background:#fff; box-shadow:0 1px 3px rgba(0,0,0,.05); }
th, td { border:1px solid #d7dde5; padding:8px 12px; text-align:left;
  vertical-align:top; }
th { background:#3F51B5; color:#fff; font-weight:600; }
tr:nth-child(even) td { background:#f5f7fa; }
tr:hover td { background:#eef2f8; }
blockquote { color:#7a4f00; background:#fff8e1; border-left:4px solid #ffb300;
  margin:14px 0; padding:10px 16px; border-radius:6px; font-size:14.5px; }
code { background:#eef1f5; padding:1px 5px; border-radius:4px; font-size:14px; }
"""


def _write_html_report(md_text: str, out_dir: str, part: str) -> str:
    """Render the Markdown report to a styled, readable standalone HTML file.
    Optional: returns '' when the ``markdown`` package is unavailable."""
    try:
        import markdown as _md
    except Exception:
        return ""
    try:
        body = _md.markdown(md_text, extensions=["tables", "sane_lists"])
        html = (f"<!doctype html><html lang='tr'><head><meta charset='utf-8'>"
                f"<meta name='viewport' content='width=device-width, "
                f"initial-scale=1'><title>Datasheet Analizi — {part}</title>"
                f"<style>{_HTML_CSS}</style></head><body>{body}</body></html>")
        path = os.path.join(out_dir, f"{part}_analysis.html")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(html)
        return path
    except Exception:
        return ""


def _curve_caption_map(result: Dict, curves: Dict, lang: str = "tr") -> Dict[str, str]:
    """Per-curve short explanation keyed by curve key (from the component
    profile), for placing next to each rendered graph."""
    from .analysis import components as _comp
    prof = _comp.get_component(result.get("type", "")) or _comp.ComponentProfile()
    try:
        return prof.curve_captions(curves, lang)
    except Exception:
        return {}


def _figure_note(caption: str, lang: str = "tr") -> str:
    """Short explanation for a schematic/layout figure, from its caption."""
    from .analysis import i18n as _i18n
    c = (caption or "").lower()
    if "block diagram" in c or "blok" in c:
        return _i18n.t(lang, "fig_block")
    if "layer" in c or "layout" in c or "placement" in c or "pcb" in c:
        return _i18n.t(lang, "fig_layout")
    if "converter" in c or "application" in c or "circuit" in c:
        return _i18n.t(lang, "fig_schematic")
    return _i18n.t(lang, "fig_generic")


def _render_report(result: Dict, written: Dict[str, str]) -> str:
    from .analysis import i18n as I
    lang = I.norm(result.get("lang", "tr"))
    L: List[str] = []
    part = result.get("part", "component")
    images = result.get("images", {})
    curves = result.get("curves", {})
    ccaps = _curve_caption_map(result, curves, lang)
    L.append(f"# {I.t(lang, 'title')} — {part}\n")
    L.append(f"**{I.t(lang, 'type')}:** "
             f"{I.label(lang, result.get('type_label', result.get('type')))}  ")
    if result.get("subtype") and result.get("subtype") != "general":
        L.append(f"**{I.t(lang, 'subtype')}:** "
                 f"{I.label(lang, result.get('subtype_label'))}  ")
    ven = result.get("vendor")
    if ven and ven.get("key") != "generic":
        L.append(f"**{I.t(lang, 'vendor')}:** {ven.get('label')} "
                 f"({I.t(lang, 'vendor_score')} {ven.get('score')})  ")
    if result.get("source_pdf"):
        L.append(f"**{I.t(lang, 'source')}:** "
                 f"{os.path.basename(result['source_pdf'])}\n")
    tr = result.get("translation")
    if tr and tr.get("applied"):
        L.append(f"> 🌐 Datasheet metni otomatik çevrildi ({tr.get('backend')} "
                 f"→ {tr.get('lang')}). Makine çevirisidir; kritik değerleri "
                 f"orijinalinden doğrulayın.\n")
    sc = result.get("section_confidence")
    if sc:
        L.append(f"## {I.t(lang, 'sec_summary')}\n")
        L.append(f"| {I.t(lang, 'col_section')} | {I.t(lang, 'col_conf')} "
                 f"| {I.t(lang, 'col_reason')} |")
        L.append("|---|---|---|")
        for k, v in sc.items():
            L.append(f"| {k} | {I.badge(lang, v.get('confidence'))} "
                     f"| {v.get('reason', '')} |")
        L.append("")
    if result.get("description"):
        L.append(f"## {I.t(lang, 'description')}\n")
        L.append(result["description"] + "\n")

    pins = result.get("pinout", [])
    if pins:
        L.append(f"## {I.t(lang, 'pinout_h')}\n")
        L.append(f"| {I.t(lang, 'col_pin')} | {I.t(lang, 'col_no')} "
                 f"| {I.t(lang, 'col_io')} | {I.t(lang, 'col_desc')} |")
        L.append("|---|---|---|---|")
        for p in pins:
            L.append(f"| {p['name']} | {p['number']} | {p['io']} | {p['desc']} |")
        L.append("")
    if images.get("pinout"):
        L.append(f"_{I.t(lang, 'pinout_img_cap')}_\n")
        L.append(f"![{I.t(lang, 'pinout_img_cap')}]"
                 f"({os.path.basename(images['pinout'])})\n")
        L.append(f"_{I.t(lang, 'pinout_img_note', n=len(pins))}_\n")

    specs = result.get("specs", [])
    L.append(f"## {I.t(lang, 'specs_h')}\n")
    if specs:
        L.append(f"| {I.t(lang, 'col_param')} | {I.t(lang, 'col_value')} |")
        L.append("|---|---|")
        for lab, val in specs:
            L.append(f"| {I.label(lang, lab)} | {val} |")
        L.append("")
    else:
        L.append(f"_{I.t(lang, 'specs_none')}_\n")

    spec_table = result.get("spec_table")
    if spec_table:
        conf = result.get("spec_table_confidence", "")
        L.append(f"## {I.t(lang, 'spectable_h', n=len(spec_table), conf=conf)}\n")
        L.append(f"| {I.t(lang, 'spectable_cols')} |")
        L.append("|---|---|---|---|---|---|---|---|")
        for r in spec_table:
            L.append("| {sec} | {p} | {sym} | {c} | {mn} | {ty} | {mx} | {u} |".format(
                sec=r.get("section", ""), p=r.get("parameter", ""),
                sym=r.get("symbol", ""), c=r.get("conditions", ""),
                mn=r.get("min", ""), ty=r.get("typ", ""),
                mx=r.get("max", ""), u=r.get("unit", "")))
        L.append("")
    if images.get("spec_ranges"):
        L.append(f"_{I.t(lang, 'spec_ranges_cap')}_\n")
        L.append(f"![{I.t(lang, 'spec_ranges_cap')}]"
                 f"({os.path.basename(images['spec_ranges'])})\n")
        L.append(f"_{I.t(lang, 'spec_ranges_note')}_\n")

    feats = result.get("features", [])
    if feats:
        L.append(f"## {I.t(lang, 'features_h')}\n")
        for f in feats:
            L.append(f"- {f}")
        L.append("")
    sch = images.get("schematic") or []
    if sch:
        L.append(f"## {I.t(lang, 'schematic_h')}\n")
        for f in sch:
            L.append(f"**{f['caption']}** ({I.t(lang, 'page_abbr')}{f['page']})\n")
            L.append(f"![{f['caption']}]({os.path.basename(f['path'])})")
            L.append(f"_{_figure_note(f['caption'], lang)}_\n")
        L.append("")

    data_curves = {k: v for k, v in curves.items()
                   if k != "_log" and isinstance(v, dict) and "npoints" in v}
    if data_curves:
        L.append(f"## {I.t(lang, 'curves_h')}\n")
        L.append(f"| {I.t(lang, 'curves_cols')} |")
        L.append("|---|---|---|---|---|---|---|")
        for k, c in data_curves.items():
            conf = (I.t(lang, "badge_high") if c["confidence"] == "high"
                    else I.t(lang, "badge_low"))
            csv_name = os.path.basename(written.get(f"csv:{k}", ""))
            ntr = c.get("ntraces", 1)
            npts = (sum(t["npoints"] for t in c["traces"])
                    if c.get("traces") else c["npoints"])
            L.append(f"| {I.label(lang, c['desc'])} | {conf} | {ntr} | {npts} | "
                     f"{I.label(lang, c['unit_x'])} | "
                     f"{I.label(lang, c['unit_y'])} | {csv_name} |")
        L.append("")
        cimgs = images.get("curves") or {}
        shown = [(k, c) for k, c in data_curves.items() if k in cimgs]
        if shown:
            L.append(f"_{I.t(lang, 'curves_replot_cap')}_\n")
            for k, c in shown:
                L.append(f"![{I.label(lang, c['desc'])}]"
                         f"({os.path.basename(cimgs[k])})")
                blurb = ccaps.get(k)
                L.append((f"_{blurb}_\n") if blurb else "")
        L.append(f"{I.t(lang, 'curves_warn')}\n")
    else:
        L.append(f"## {I.t(lang, 'curves_none_h')}\n")
        L.append(f"_{I.t(lang, 'curves_none')}_\n")

    interp = list(ccaps.values())
    if interp:
        L.append(f"## {I.t(lang, 'interp_h')}\n")
        for s in interp:
            L.append(f"- {s}")
        L.append("")

    req = result.get("design_requirements", [])
    if req:
        L.append(f"## {I.t(lang, 'req_h')}\n")
        L.append(f"| {I.t(lang, 'col_param')} | {I.t(lang, 'col_value')} |")
        L.append("|---|---|")
        for lab, val in req:
            L.append(f"| {I.label(lang, lab)} | {val} |")
        L.append("")

    proc = result.get("design_procedure", [])
    if proc:
        L.append(f"## {I.t(lang, 'proc_h')}\n")
        L.append(f"{I.t(lang, 'proc_note')}\n")
        for s in proc:
            L.append(f"### {I.label(lang, s['step'])}")
            if s["intent"]:
                L.append(s["intent"])
            for g in s["vars"]:
                L.append(f"- {g}")
            L.append("")

    lay = result.get("layout_guidelines", [])
    if lay:
        L.append(f"## {I.t(lang, 'layout_h')}\n")
        for s in lay:
            L.append(f"- {s}")
        L.append("")
        L.append(f"{I.t(lang, 'layout_note')}\n")
    lfg = images.get("layout") or []
    if lfg:
        L.append(f"## {I.t(lang, 'layout_img_h')}\n")
        for f in lfg:
            L.append(f"**{f['caption']}** ({I.t(lang, 'page_abbr')}{f['page']})\n")
            L.append(f"![{f['caption']}]({os.path.basename(f['path'])})")
            L.append(f"_{_figure_note(f['caption'], lang)}_\n")
        L.append("")

    return "\n".join(L)
