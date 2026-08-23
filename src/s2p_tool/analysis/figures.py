"""Extract datasheet figure images (schematics + layout examples) as PNGs.

The datasheet draws its application/block schematic and its recommended board
layout as figures; the output document should *show* those figures, not just
name them. We locate a figure by its caption ("Figure N. ...") when the caption
text matches a schematic/layout pattern, union the vector drawings + raster
images sitting directly above the caption into the figure's bounding box, and
render that region to a PNG. Skips cleanly when PyMuPDF is absent.
"""
from __future__ import annotations

import os
import re
from typing import Dict, List, Optional, Tuple

try:
    import pymupdf as fitz               # PyMuPDF 1.24+ canonical name
    _HAVE = True
except Exception:  # pragma: no cover
    try:
        import fitz  # type: ignore
        _HAVE = True
    except Exception:
        _HAVE = False

# "Figure 1.", "Fig. 8-2", "Figure A1" -- the caption anchor.
_FIGCAP = re.compile(r"^\s*(?:Figure|Fig\.?)\s+[\dA-Za-z\-.]+", re.I)
_ZOOM = 2.0                              # 144 dpi render: crisp, not huge
_MAX_H = 360.0                           # tallest figure band above a caption
_MIN_AREA = 4000.0                       # px^2; ignore glyph/rule fragments
_HALF_W = 300.0                          # caption-centred column half-width
_PER_CAT = 3                             # max figures kept per category


def available() -> bool:
    return _HAVE


def _spans(page) -> List[Tuple[str, float, float, float, float]]:
    """(text, x0, y0, x1, y1) for every non-empty text span on the page."""
    out: List[Tuple[str, float, float, float, float]] = []
    for b in page.get_text("dict").get("blocks", []):
        for line in b.get("lines", []):
            for sp in line.get("spans", []):
                t = sp.get("text", "")
                if t.strip():
                    x0, y0, x1, y1 = sp["bbox"]
                    out.append((t, x0, y0, x1, y1))
    return out


def _content_rects(page) -> List[Tuple[float, float, float, float]]:
    """Bounding rects of vector drawings + raster images on the page."""
    rects: List[Tuple[float, float, float, float]] = []
    for dr in page.get_drawings():
        r = dr.get("rect")
        if r is not None:
            rects.append((r.x0, r.y0, r.x1, r.y1))
    try:
        for info in page.get_image_info():
            x0, y0, x1, y1 = info["bbox"]
            rects.append((x0, y0, x1, y1))
    except Exception:  # pragma: no cover - older PyMuPDF
        pass
    return rects


def _figure_box(rects, spans, cx, cap_y, page_w) -> Optional[Tuple[float, float, float, float]]:
    """Union of content rects sitting just above the caption within a column
    band centred on it. The top is raised to just below the nearest prose line
    so the paragraph above the figure is not swallowed. Returns
    ``(x0, y0, x1, y1)`` or None."""
    top_lim = cap_y - _MAX_H
    band_x0, band_x1 = cx - _HALF_W, cx + _HALF_W
    # A wide line of body text between top_lim and the caption marks the figure's
    # upper boundary -- raise top_lim to just under it.
    for (t, x0, y0, x1, y1) in spans:
        yc = (y0 + y1) / 2
        if top_lim < yc < cap_y - 8 and x0 < band_x1 and x1 > band_x0:
            if (x1 - x0) > 260 and len(t) > 40:
                top_lim = max(top_lim, y1 + 2)
    bx0 = by0 = 1e9
    bx1 = by1 = -1e9
    for (x0, y0, x1, y1) in rects:
        if (x1 - x0) * (y1 - y0) < 4.0:            # zero/near-zero fragment
            continue
        yc, xc = (y0 + y1) / 2, (x0 + x1) / 2
        if top_lim <= yc <= cap_y + 2 and band_x0 <= xc <= band_x1:
            bx0, by0 = min(bx0, x0), min(by0, y0)
            bx1, by1 = max(bx1, x1), max(by1, y1)
    if bx1 <= bx0 or by1 <= by0:
        return None
    if (bx1 - bx0) * (by1 - by0) < _MIN_AREA:
        return None
    pad = 4.0
    return (max(0.0, bx0 - pad), max(0.0, by0 - pad),
            min(page_w, bx1 + pad), min(cap_y, by1 + pad))


def extract_figures(pdf_path: str, schematic_caps, layout_caps,
                    out_dir: str, part: str, max_pages: int = 34) -> Dict[str, List[Dict]]:
    """Render datasheet figures whose caption matches a schematic/layout pattern.

    ``schematic_caps``/``layout_caps`` are lists of caption regex strings (from
    the component profile). Returns
    ``{"schematic": [{"caption", "path", "page"}, ...], "layout": [...]}``.
    Empty lists when nothing matches or PyMuPDF is absent.
    """
    out: Dict[str, List[Dict]] = {"schematic": [], "layout": []}
    if not _HAVE or not pdf_path or not os.path.isfile(pdf_path):
        return out
    os.makedirs(out_dir, exist_ok=True)
    cat_pats = [
        ("schematic", [re.compile(rx, re.I) for rx in schematic_caps]),
        ("layout", [re.compile(rx, re.I) for rx in layout_caps]),
    ]
    seen = set()                          # (page, rounded-box) -> dedupe regions
    doc = fitz.open(pdf_path)
    try:
        for pno in range(min(max_pages, doc.page_count)):
            page = doc[pno]
            spans = _spans(page)
            caps = [s for s in spans if _FIGCAP.match(s[0])]
            if not caps:
                continue
            rects = None                  # built lazily, once per page
            for (t, x0, y0, x1, y1) in caps:
                cat = next((c for c, pats in cat_pats
                            if any(p.search(t) for p in pats)), None)
                if cat is None or len(out[cat]) >= _PER_CAT:
                    continue
                if rects is None:
                    rects = _content_rects(page)
                box = _figure_box(rects, spans, (x0 + x1) / 2, y0, page.rect.width)
                if not box:
                    continue
                fx0, fy0, fx1, fy1 = box
                dkey = (pno, round(fx0), round(fy0), round(fx1), round(fy1))
                if dkey in seen:
                    continue
                seen.add(dkey)
                pix = page.get_pixmap(matrix=fitz.Matrix(_ZOOM, _ZOOM),
                                      clip=fitz.Rect(fx0, fy0, fx1, fy1))
                idx = len(out[cat]) + 1
                path = os.path.join(out_dir, f"{part}_{cat}_{idx}.png")
                pix.save(path)
                out[cat].append({"caption": t.strip(), "path": path,
                                 "page": pno + 1})
    finally:
        doc.close()
    return out
