"""TI-specific electrical-characteristics extraction by word geometry.

TI 'Electrical Characteristics' tables render parameter symbols with subscripts
on a separate baseline ("V" + "IN_UVLO"), which makes pdfplumber's cell rows
drift out of alignment with the header — values land in the wrong column. Rather
than trust cell indices, we place every word by its x-centre against the header
word centres (MIN / TYP / MAX / UNIT) and the column labels (PARAMETER / TEST
CONDITIONS), exactly where the value physically sits. This recovers TYP/MAX
(empty under the generic path) and keeps the row intact despite subscript wrap.

Returns rows in SpecSection's shape: {section, parameter, symbol, conditions,
min, typ, max, unit}. Uses pymupdf words (via the shared AnalysisContext.doc).
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

_NUM = re.compile(r"^[+\-]?\d*\.?\d+$")
_HDR_VAL = ("MIN", "MAX", "TYP", "NOM", "UNIT")
# The page-bottom furniture that marks the end of a table region — once a row's
# text hits this, the EC table is over and the rest of the sweep is page footer.
_FOOTER = re.compile(
    r"copyright|submit\s*document|document\s*feedback|texas\s*instruments"
    r"|product\s*folder|all\s*rights\s*reserved", re.I)
# TI (and others) render negatives/±ranges with assorted Unicode dashes.
_DASHES = {"−": "-", "–": "-", "‒": "-", "—": "-",
           "‐": "-", "‑": "-"}


def _norm_num(w: str) -> str:
    for d, h in _DASHES.items():
        w = w.replace(d, "-")
    return w.replace("±", "").strip()


def _is_num(w: str) -> bool:
    return bool(_NUM.match(_norm_num(w)))


def _join_symbol(s: str) -> str:
    """Reattach a subscript that wrapped onto its own word: glue a lone capital
    to a following ALL-CAPS / underscored token ('V IN_UVLO' -> 'VIN_UVLO'),
    but never to a Titlecase description word ('C Input' stays apart)."""
    prev = None
    while s != prev:
        prev = s
        s = re.sub(r"\b([A-Z])\s+([A-Z0-9]*_[A-Z0-9]+|[A-Z]{2,})\b",
                   r"\1\2", s)
    return re.sub(r"\s{2,}", " ", s).strip()


def _header_layout(words, hy) -> Optional[Dict]:
    """From words on (approximately) the header baseline hy, collect value-column
    x-centres and label-column x-lefts. Returns None if MIN & MAX aren't both
    present."""
    vals: Dict[str, float] = {}
    labels: Dict[str, float] = {}
    for (x0, y0, x1, y1, w, *_) in words:
        if abs(round(y0) - hy) > 2:
            continue
        wu = w.strip().upper()
        if wu in _HDR_VAL:
            vals[wu] = (x0 + x1) / 2
        elif wu in ("PARAMETER", "SYMBOL", "TEST", "CONDITIONS", "CONDITION"):
            labels[wu] = min(labels.get(wu, 1e9), x0)
    if "MIN" not in vals or "MAX" not in vals:
        return None
    return {"vals": vals, "labels": labels}


def extract_ti_spec_rows(ctx, max_pages: int = 30
                         ) -> Tuple[List[Dict], List[int]]:
    rows: List[Dict] = []
    pages: List[int] = []
    for pno in range(min(max_pages, ctx.page_count)):
        page = ctx.doc[pno]
        words = page.get_text("words")
        if not words:
            continue
        # Candidate header baselines: any y carrying both MIN and MAX.
        heads: Dict[int, Dict[str, float]] = {}
        for (x0, y0, x1, y1, w, *_) in words:
            wu = w.strip().upper()
            if wu in _HDR_VAL:
                heads.setdefault(round(y0), {})[wu] = (x0 + x1) / 2
        header_ys = sorted(y for y, m in heads.items()
                           if "MIN" in m and "MAX" in m)
        if not header_ys:
            continue
        for hi, hy in enumerate(header_ys):
            layout = _header_layout(words, hy)
            if layout is None:
                continue
            got = _rows_for_header(words, hy, layout,
                                   header_ys[hi + 1] if hi + 1 < len(header_ys)
                                   else 1e9)
            if got:
                rows.extend(got)
                if (pno + 1) not in pages:
                    pages.append(pno + 1)
    return rows, pages


def _rows_for_header(words, hy: float, layout: Dict, y_end: float) -> List[Dict]:
    vals, labels = layout["vals"], layout["labels"]
    c_min, c_max = vals["MIN"], vals["MAX"]
    c_typ = vals.get("TYP") or vals.get("NOM")
    c_unit = vals.get("UNIT", c_max + 40)
    if c_typ:
        b_lo, b_hi = (c_min + c_typ) / 2, (c_typ + c_max) / 2
        tol = 0.45 * (c_typ - c_min)
    else:
        b_lo = b_hi = (c_min + c_max) / 2
        tol = 0.45 * (c_max - c_min)
    val_x0 = c_min - tol                      # value band starts here
    unit_x0 = (c_max + c_unit) / 2
    cond_hdr = labels.get("TEST") or labels.get("CONDITIONS")
    cond_x0 = cond_hdr if cond_hdr else val_x0  # else no separate conditions

    # Cluster words into rows by y (3-pt buckets), between this header and next.
    band: Dict[int, List] = {}
    for (x0, y0, x1, y1, w, *_) in words:
        if y0 <= hy + 2 or y0 >= y_end - 1:
            continue
        band.setdefault(round(y0 / 3) * 3, []).append((x0, x1, w))

    out: List[Dict] = []
    section = ""
    for ry in sorted(band):
        cells = sorted(band[ry], key=lambda z: z[0])
        # Once the page footer starts, this table region is finished — stop so
        # the copyright/feedback line and page number aren't swept in as rows.
        if _FOOTER.search(" ".join(w for (_a, _b, w) in cells)):
            break
        param_w, cond_w, unit_w = [], [], []
        vmin = vtyp = vmax = ""
        for (x0, x1, w) in cells:
            cx = (x0 + x1) / 2
            if cx < val_x0:
                (cond_w if cx >= cond_x0 else param_w).append(w)
            elif cx >= unit_x0 and not _is_num(w):
                unit_w.append(w)
            elif _is_num(w):
                if c_typ and b_lo <= cx < b_hi:
                    vtyp = w
                elif cx >= b_hi:
                    vmax = w
                else:
                    vmin = w
            else:
                unit_w.append(w)     # stray non-numeric in value band = unit tail
        param = _join_symbol(" ".join(param_w))
        cond = re.sub(r"\s{2,}", " ", " ".join(cond_w)).strip()
        unit = " ".join(unit_w).strip()
        has_num = bool(vmin or vtyp or vmax)
        if not has_num:
            # Section header: caps-y text in the parameter zone, no values.
            if param and not cond and len(param) > 3 \
                    and param.upper() == param:
                section = param
            continue
        out.append({"section": section, "parameter": param, "symbol": "",
                    "conditions": cond, "min": vmin, "typ": vtyp, "max": vmax,
                    "unit": unit})
    return out
