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


def _part_number(doc) -> str:
    """Best-effort part number from PDF metadata title or the first heading."""
    title = (doc.metadata or {}).get("title") or ""
    m = re.search(r"\b([A-Z]{2,}\d[\w\-]*)\b", title)
    if m:
        return m.group(1)
    for line in doc[0].get_text().splitlines():
        m = re.search(r"\b([A-Z]{2,}\d[\w\-]*)\b", line.strip())
        if m:
            return m.group(1)
    return "component"


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


def _design_requirements(text: str) -> List[Tuple[str, str]]:
    """Parse the 'Design Requirements' example table (Table 8-x)."""
    pats = [
        ("Giriş gerilimi aralığı",
         r"Input voltage(?:\s*range)?\s*[\n:]\s*([\d.]+\s*to\s*[\d.]+\s*V|[\d.]+\s*V)"),
        ("Çıkış gerilimi", r"Output voltage\s*[\n:]\s*([\d.]+\s*V)\b"),
        ("Çıkış ripple", r"Output voltage ripple\s*[\n:]\s*([^\n]+)"),
        ("Çıkış akımı", r"Output current(?:\s*rating)?\s*[\n:]\s*([\d.]+\s*A)"),
        ("Çalışma frekansı", r"Operating frequency\s*[\n:]\s*([\d.]+\s*[kMG]?Hz)"),
        ("Hafif-yük modu", r"Operation mode at light load\s*[\n:]\s*(\w+)"),
    ]
    out = []
    for label, pat in pats:
        v = _first(text, pat)
        if v:
            out.append((label, re.sub(r"\s+", " ", v).strip()))
    return out


_PROC_HEADS = (
    ("Anahtarlama frekansı ayarı (RFSW)", r"Setting Switching Frequency"),
    ("Tepe akım limiti ayarı (RILIM)", r"Setting Peak Current Limit"),
    ("İndüktör seçimi", r"Inductor Selection"),
    ("Çıkış kapasitörü seçimi", r"Output Capacitor Selection"),
    ("Giriş kapasitörü seçimi", r"Input Capacitor Selection"),
    ("Soft-start ayarı", r"(?:Programmable\s+)?Soft.?Start"),
    ("Geri-besleme / çıkış gerilimi ayarı",
     r"Setting (?:the )?Output Voltage|Output Voltage Setting|"
     r"Feedback Resistor"),
)


def _design_procedure(text: str) -> List[Dict]:
    """Extract each design-procedure step: heading, one-line intent, and the
    'where' variable/constant glossary. Exact TI formula glyphs do not survive
    text extraction, so we narrate the procedure (intent + variables +
    constants) rather than fabricate an equation."""
    steps = []
    for label, head_rx in _PROC_HEADS:
        m = re.search(r"\d+\.\d+(?:\.\d+)*\s+(?:" + head_rx + r")", text, re.I)
        if not m:
            continue
        start = m.end()
        # Section runs until the next numbered sub-heading or ~1.2k chars.
        tail = text[start:start + 1400]
        nxt = re.search(r"\n\s*\d+\.\d+\.\d+", tail)
        body = tail[:nxt.start()] if nxt else tail
        # First descriptive sentence.
        sent = ""
        ms = re.search(r"([A-Z][^.]{15,240}\.)", body)
        if ms:
            sent = re.sub(r"\s+", " ", ms.group(1)).strip()
        # 'where' glossary: "<VAR> is <definition>".
        glossary = []
        seen = set()
        for gm in re.finditer(
                r"(?:^|\n)\W*([A-Za-z\u0192][\w()]{0,12})\s+is\s+([^\n]+)", body):
            var = gm.group(1).strip()
            defn = re.sub(r"\s+", " ", gm.group(2)).strip().rstrip(".")
            if var.lower() in seen or len(defn) < 3:
                continue
            seen.add(var.lower())
            glossary.append(f"{var} = {defn}")
        if sent or glossary:
            steps.append({"step": label, "intent": sent, "vars": glossary[:8]})
    return steps


def _layout_guidelines(text: str) -> List[str]:
    """Split the datasheet's own '§ Layout Guidelines' prose into a checklist."""
    m = re.search(r"Layout Guidelines[ \t]*\n\s*([A-Z][\s\S]+?)"
                  r"(?:Layout Example|\n\s*10\.2|Thermal Considerations|\Z)",
                  text, re.I)
    if not m:
        return []
    prose = re.sub(r"\s+", " ", m.group(1)).strip()
    out = []
    for s in re.split(r"(?<=[.])\s+", prose):
        s = s.strip()
        if len(s) > 25 and not s.lower().startswith("as for all"):
            out.append(s)
    return out[:10]


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

# ---------------------------------------------------------------------------
# Analyzer plugin base + registry
# ---------------------------------------------------------------------------
class Analyzer:
    key: str = "component"
    label: str = "Komponent"
    keywords: Tuple[str, ...] = ()
    curve_targets: Tuple[Tuple[str, str, str, str, str], ...] = ()

    def matches(self, text: str) -> float:
        low = text.lower()
        return float(sum(low.count(k) for k in self.keywords))

    def extract_specs(self, text: str) -> List[Tuple[str, str]]:
        return []

    def analyze(self, pdf_path: str, doc, text: str) -> Dict:
        specs = self.extract_specs(text)
        curves = {}
        if self.curve_targets:
            wanted = [(t[0], t[1]) for t in self.curve_targets]
            raw = pdfcurves.extract_labeled_curves(pdf_path, wanted)
            meta_by_key = {t[0]: t for t in self.curve_targets}
            for k, tup in meta_by_key.items():
                r = raw.get(k)
                if not r:
                    continue
                curves[k] = {
                    "caption": r["caption"],
                    "unit_x": tup[2], "unit_y": tup[3], "desc": tup[4],
                    "confidence": r["confidence"],
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
        result = {
            "type": self.key,
            "type_label": self.label,
            "part": _part_number(doc),
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
    keywords = (
        "boost converter", "buck converter", "buck-boost", "step-up",
        "step-down", "switching converter", "dc-dc", "dc/dc", "regulator",
        "ldo", "low-dropout", "pmic", "synchronous", "converter",
        "voltage regulator", "current limit", "switching frequency",
    )
    curve_targets = (
        ("efficiency", r"efficiency", "Output Current (A)",
         "Efficiency (%)", "Verim eğrisi"),
        ("current_limit_vs_r", r"current limit", "R_SET (kΩ)",
         "Current Limit (A)", "Akım limiti vs ayar direnci"),
        ("fsw_vs_r", r"switching frequency|frequency vs", "R_SET (kΩ)",
         "fSW (kHz)", "Anahtarlama frekansı vs ayar direnci"),
        ("vref_vs_temp", r"reference voltage", "Sıcaklık (°C)",
         "Vref (V)", "Referans gerilimi vs sıcaklık"),
        ("iq_vs_temp", r"quiescent current", "Sıcaklık (°C)",
         "Iq (µA)", "Sükunet akımı vs sıcaklık"),
        ("ishutdown_vs_temp", r"shutdown current", "Sıcaklık (°C)",
         "I_SD (µA)", "Kapalı-durum akımı vs sıcaklık"),
    )

    def extract_specs(self, text: str) -> List[Tuple[str, str]]:
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

    @staticmethod
    def _interp(x, xs, ys):
        """Linear interpolation at x over sorted (xs, ys)."""
        for i in range(1, len(xs)):
            if xs[i - 1] <= x <= xs[i] or xs[i] <= x <= xs[i - 1]:
                x0, x1, y0, y1 = xs[i - 1], xs[i], ys[i - 1], ys[i]
                if x1 == x0:
                    return y0
                return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
        return None

    def interpret_curves(self, curves: Dict) -> List[str]:
        """Turn high-confidence digitized curves into plain-language findings —
        the 'grafiklerin yorumlanması' step. Low-confidence curves are skipped."""
        out: List[str] = []
        for key, c in curves.items():
            if key == "_log" or not isinstance(c, dict):
                continue
            if c.get("confidence") != "high":
                continue
            traces = c.get("traces")
            if traces:
                # Colour-separated multi-trace plot: summarise each trace's
                # y-range (the x-axis usually indexes an operating condition).
                segs = []
                for tr in traces:
                    tys = [p[1] for p in tr["curve"]]
                    segs.append(f"{tr['label']}: {min(tys):.3g}…{max(tys):.3g}")
                out.append(
                    f"{c['desc']}: {len(traces)} iz renk bazlı ayrıştırıldı "
                    f"({c['unit_y']}) — " + "; ".join(segs)
                    + ". Her iz ayrı CSV sütununda.")
                continue
            pts = c["curve"]
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            lo, hi = min(xs), max(xs)
            ylo, yhi = min(ys), max(ys)
            mid = sorted(ys)[len(ys) // 2]
            if key == "vref_vs_temp":
                drift = (yhi - ylo) * 1000.0
                out.append(
                    f"Vref ≈ {mid:.3f} V; {lo:.0f}…{hi:.0f} °C aralığında toplam "
                    f"sapma ~{drift:.1f} mV → referans çok kararlı.")
            elif key == "iq_vs_temp":
                trend = "artıyor" if ys[-1] > ys[0] else "azalıyor"
                out.append(
                    f"Sükunet akımı Iq {ylo:.0f}…{yhi:.0f} µA; sıcaklıkla {trend} "
                    f"({lo:.0f}→{hi:.0f} °C).")
            elif key == "ishutdown_vs_temp":
                out.append(f"Kapalı-durum akımı {ylo:.2g}…{yhi:.2g} µA aralığında.")
            elif key == "current_limit_vs_r":
                paired = sorted(zip(xs, ys))
                sx = [p[0] for p in paired]; sy = [p[1] for p in paired]
                samples = []
                for rq in (100, 250, 360):
                    iv = self._interp(rq, sx, sy)
                    if iv is not None:
                        samples.append(f"R={rq}kΩ→{iv:.1f}A")
                trend = "azalıyor" if sy[-1] < sy[0] else "artıyor"
                s = (f"Akım limiti ayar direnciyle {trend} "
                     f"({sx[0]:.0f}→{sx[-1]:.0f} kΩ, {sy[0]:.1f}→{sy[-1]:.1f} A).")
                if samples:
                    s += " Eğriden: " + ", ".join(samples) + "."
                out.append(s)
            elif key == "fsw_vs_r":
                out.append(
                    f"Anahtarlama frekansı ayar direnciyle değişiyor "
                    f"({lo:.0f}→{hi:.0f} kΩ, {ylo:.0f}→{yhi:.0f}).")
            else:
                out.append(f"{c['desc']}: {ylo:.3g}…{yhi:.3g} {c['unit_y']} "
                           f"({lo:.3g}…{hi:.3g} {c['unit_x']}).")
        return out


ANALYZERS: List[Analyzer] = [RegulatorAnalyzer()]


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
                out_dir: Optional[str] = None) -> Dict:
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
                    "part": _part_number(doc),
                    "detect_scores": scores,
                    "error": f"'{key}' türü için analyzer yok. "
                             f"Mevcut: {[a.key for a in ANALYZERS]}"}
        result = analyzer.analyze(pdf_path, doc, text)
        result["detect_scores"] = scores
        result["source_pdf"] = os.path.abspath(pdf_path)
    finally:
        doc.close()

    if out_dir:
        result["outputs"] = _write_outputs(result, out_dir)
    return result


def _write_outputs(result: Dict, out_dir: str) -> Dict[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    part = re.sub(r"[^\w\-]", "_", result.get("part", "component"))
    written: Dict[str, str] = {}

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
    md_path = os.path.join(out_dir, f"{part}_analysis.md")
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(_render_report(result, written))
    written["report"] = md_path
    return written


def _render_report(result: Dict, written: Dict[str, str]) -> str:
    L: List[str] = []
    part = result.get("part", "component")
    L.append(f"# Datasheet Analizi — {part}\n")
    L.append(f"**Tür:** {result.get('type_label', result.get('type'))}  ")
    if result.get("source_pdf"):
        L.append(f"**Kaynak:** {os.path.basename(result['source_pdf'])}\n")
    if result.get("description"):
        L.append("## Açıklama\n")
        L.append(result["description"] + "\n")

    pins = result.get("pinout", [])
    if pins:
        L.append("## Pinout (Pin Fonksiyonları)\n")
        L.append("| Pin | No | I/O | Açıklama |")
        L.append("|---|---|---|---|")
        for p in pins:
            L.append(f"| {p['name']} | {p['number']} | {p['io']} | {p['desc']} |")
        L.append("")

    specs = result.get("specs", [])
    L.append("## Elektriksel Özellikler\n")
    if specs:
        L.append("| Parametre | Değer |")
        L.append("|---|---|")
        for lab, val in specs:
            L.append(f"| {lab} | {val} |")
        L.append("")
    else:
        L.append("_Metinden yapısal spec çıkarılamadı._\n")

    feats = result.get("features", [])
    if feats:
        L.append("## Özellikler (Features)\n")
        for f in feats:
            L.append(f"- {f}")
        L.append("")

    curves = result.get("curves", {})
    data_curves = {k: v for k, v in curves.items()
                   if k != "_log" and isinstance(v, dict) and "npoints" in v}
    if data_curves:
        L.append("## Çıkarılan Karakteristik Eğriler\n")
        L.append("| Eğri | Güven | İz | Nokta | X | Y | CSV |")
        L.append("|---|---|---|---|---|---|---|")
        for k, c in data_curves.items():
            conf = "✅ yüksek" if c["confidence"] == "high" else "⚠️ düşük"
            csv_name = os.path.basename(written.get(f"csv:{k}", ""))
            ntr = c.get("ntraces", 1)
            npts = (sum(t["npoints"] for t in c["traces"])
                    if c.get("traces") else c["npoints"])
            L.append(f"| {c['desc']} | {conf} | {ntr} | {npts} | "
                     f"{c['unit_x']} | {c['unit_y']} | {csv_name} |")
        L.append("")
        L.append("> ⚠️ 'düşük' güvenli eğriler kalibrasyon/çoklu-iz nedeniyle "
                 "güvenilmez; doğrulanmadan kullanmayın.\n")
    else:
        L.append("## Karakteristik Eğriler\n")
        L.append("_Vektör grafikten güvenilir eğri çıkarılamadı._\n")

    interp = result.get("curve_interpretation", [])
    if interp:
        L.append("## Grafik Yorumu\n")
        for s in interp:
            L.append(f"- {s}")
        L.append("")

    req = result.get("design_requirements", [])
    if req:
        L.append("## Tasarım Gereksinimleri (datasheet örnek tasarımı)\n")
        L.append("| Parametre | Değer |")
        L.append("|---|---|")
        for lab, val in req:
            L.append(f"| {lab} | {val} |")
        L.append("")

    proc = result.get("design_procedure", [])
    if proc:
        L.append("## Tasarım Hesapları (Detailed Design Procedure)\n")
        L.append("> Denklemlerin birebir glyph'i PDF metninden güvenilir "
                 "çıkmaz; her adımın amacı + değişken/sabit sözlüğü aşağıda.\n")
        for s in proc:
            L.append(f"### {s['step']}")
            if s["intent"]:
                L.append(s["intent"])
            for g in s["vars"]:
                L.append(f"- {g}")
            L.append("")

    lay = result.get("layout_guidelines", [])
    if lay:
        L.append("## Layout Önerileri (datasheet §Layout Guidelines)\n")
        for s in lay:
            L.append(f"- {s}")
        L.append("")
        L.append("> Not: Gerçek şematik/PCB *üretimi* bu aracın kapsamı dışı — "
                 "`kicad`/`eda-agent` skill'leri ile yapılır.\n")

    return "\n".join(L)
