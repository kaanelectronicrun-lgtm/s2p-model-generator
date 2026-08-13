"""Extract derating curves (DC bias, temperature) straight from a datasheet PDF.

Datasheet capacitance-change plots are almost always *vector* graphics. Using
PyMuPDF (fitz) we, per target plot:

  1. locate the plot by its axis / caption text,
  2. calibrate a pixel->data transform from the numeric tick labels around the
     plot frame,
  3. digitize the plotted polyline and map it to ``[[x, dC_%], ...]``.

Best-effort and honest: each target returns either a calibrated curve or None
plus a reason. The caller falls back to the behavioral estimate when a curve is
not found — nothing is fabricated.

Requires PyMuPDF; ``available()`` reports whether it can run.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

try:
    import pymupdf as fitz  # PyMuPDF 1.24+ canonical name (bundles cleanly)
    _HAVE_FITZ = True
except Exception:  # pragma: no cover
    try:
        import fitz  # legacy shim
        _HAVE_FITZ = True
    except Exception:
        _HAVE_FITZ = False


def available() -> bool:
    return _HAVE_FITZ


# Each target plot: x-axis keyword, y-axis keyword, and a reject keyword so we
# don't pick a neighbouring plot. Curves come back as [[x, y], ...].
_TARGETS = {
    "dc_bias_curve": {
        "xkw": re.compile(r"dc\s*bias", re.I),
        "ykw": re.compile(r"(cap\w*\.?\s*change|change\s*rate|capacitance\s*change)", re.I),
        "reject": re.compile(r"temperature|impedance|\bESR\b", re.I),
    },
    "tcc_curve": {
        "xkw": re.compile(r"temperature", re.I),
        "ykw": re.compile(r"(cap\w*\.?\s*change|change\s*rate|capacitance\s*change)", re.I),
        "reject": re.compile(r"dc\s*bias|impedance|\bESR\b", re.I),
    },
    "impedance_curve": {
        "xkw": re.compile(r"freq", re.I),
        "ykw": re.compile(r"impedance|\|?\s*Z\s*\|?", re.I),
        "reject": re.compile(r"\bESR\b|change|bias", re.I),
    },
    "esr_curve": {
        "xkw": re.compile(r"freq", re.I),
        "ykw": re.compile(r"\bESR\b|equivalent\s*series", re.I),
        "reject": re.compile(r"impedance|change|bias", re.I),
    },
}

# SI-suffixed numeric tick labels: "-20", "0.1", "1k", "10M", "1G", "100m".
_SI = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "μ": 1e-6, "m": 1e-3,
       "k": 1e3, "K": 1e3, "M": 1e6, "G": 1e9, "T": 1e12, "": 1.0}
_TICK = re.compile(r"^([+\-]?\d+(?:\.\d+)?)\s*([pnuµμmkKMGT]?)$")


def _spans(page) -> List[Tuple[str, float, float, float, float]]:
    """Return (text, x0, y0, x1, y1) for every text span on the page."""
    out = []
    d = page.get_text("dict")
    for blk in d.get("blocks", []):
        for line in blk.get("lines", []):
            for sp in line.get("spans", []):
                t = sp.get("text", "").strip()
                if t:
                    x0, y0, x1, y1 = sp["bbox"]
                    out.append((t, x0, y0, x1, y1))
    return out


def _segments(page) -> List[Tuple[float, float, float, float]]:
    """Flatten vector drawings into line segments (beziers sampled to chords)."""
    segs: List[Tuple[float, float, float, float]] = []
    for dr in page.get_drawings():
        for it in dr.get("items", []):
            op = it[0]
            if op == "l":
                p1, p2 = it[1], it[2]
                segs.append((p1.x, p1.y, p2.x, p2.y))
            elif op == "c":
                pts = [it[1], it[2], it[3], it[4]]
                for a, b in zip(pts[:-1], pts[1:]):
                    segs.append((a.x, a.y, b.x, b.y))
            elif op == "re":
                r = it[1]
                segs.extend([
                    (r.x0, r.y0, r.x1, r.y0), (r.x1, r.y0, r.x1, r.y1),
                    (r.x1, r.y1, r.x0, r.y1), (r.x0, r.y1, r.x0, r.y0),
                ])
    return segs


def _plot_frame(segs, region) -> Optional[Tuple[float, float, float, float]]:
    """Largest axis-aligned rectangle (x0,y0,x1,y1) inside/near region."""
    rx0, ry0, rx1, ry1 = region
    # Collect long horizontal and vertical segments.
    horiz = [s for s in segs if abs(s[1] - s[3]) < 1.5 and abs(s[0] - s[2]) > 20]
    vert = [s for s in segs if abs(s[0] - s[2]) < 1.5 and abs(s[1] - s[3]) > 20]
    if not horiz or not vert:
        return None
    xs = sorted({round(s[0]) for s in vert} | {round(s[2]) for s in vert})
    ys = sorted({round(s[1]) for s in horiz} | {round(s[3]) for s in horiz})
    if len(xs) < 2 or len(ys) < 2:
        return None
    x0, x1 = xs[0], xs[-1]
    y0, y1 = ys[0], ys[-1]
    if (x1 - x0) < 30 or (y1 - y0) < 30:
        return None
    return (x0, y0, x1, y1)


def _lin_fit(px, vv):
    """Least-squares slope/intercept for pixel->value (numpy-free)."""
    n = len(px)
    sx = sum(px); sy = sum(vv); sxx = sum(p * p for p in px)
    sxy = sum(p * v for p, v in zip(px, vv))
    denom = n * sxx - sx * sx
    if abs(denom) < 1e-12:
        return None
    m = (n * sxy - sx * sy) / denom
    b = (sy - m * sx) / n
    ss_res = sum((v - (m * p + b)) ** 2 for p, v in zip(px, vv))
    ss_tot = sum((v - sy / n) ** 2 for v in vv) or 1e-30
    r2 = 1.0 - ss_res / ss_tot
    return m, b, r2


def _robust_lin(px, vv):
    """Least-squares fit that trims outlier ticks (merged/OCR-garbled labels).

    Drops the single worst-residual point and refits while r2 is poor, never
    discarding more than ~1/4 of the ticks or dropping below 3. Clean tick rows
    (r2 already ~1) are returned untouched, so the passive-component path is
    unaffected.
    """
    idx = list(range(len(px)))
    fit = _lin_fit(px, vv)
    if fit is None:
        return None
    m, b, r2 = fit
    floor = max(3, len(px) - len(px) // 4)
    while r2 < 0.9995 and len(idx) > floor:
        res = [(abs(vv[i] - (m * px[i] + b)), i) for i in idx]
        idx.remove(max(res)[1])
        fit = _lin_fit([px[i] for i in idx], [vv[i] for i in idx])
        if fit is None:
            break
        m, b, r2 = fit
    return m, b, r2


def _calibrate(ticks: List[Tuple[float, float]]):
    """Auto lin/log pixel->value transform from >=2 (pixel, value) pairs.

    Returns a callable f(pixel)->value, or None. Log is chosen when all values
    are positive AND a log fit is clearly better (datasheet |Z|/f axes are log).
    Outlier ticks are trimmed by a robust fit before choosing lin vs log.
    """
    ticks = sorted(set(ticks))
    if len(ticks) < 2:
        return None
    px = [p for p, _ in ticks]
    vv = [v for _, v in ticks]
    if max(px) - min(px) < 5:
        return None
    lin = _robust_lin(px, vv)
    if lin is None:
        return None
    lm, lb, lr2 = lin
    if all(v > 0 for v in vv) and (max(vv) / min(vv)) > 20:
        import math
        log = _robust_lin(px, [math.log10(v) for v in vv])
        if log and log[2] >= lr2:
            gm, gb, _ = log
            return lambda p: 10.0 ** (gm * p + gb)
    return lambda p: lm * p + lb


def _num(t: str) -> Optional[float]:
    """Parse a tick label to a value, honouring SI suffixes (k, M, G, m, ...)."""
    t = t.replace("\u2212", "-").replace("Ω", "").replace("Hz", "").strip()
    mm = _TICK.match(t)
    if not mm:
        return None
    return float(mm.group(1)) * _SI.get(mm.group(2), 1.0)


def _extract_one(page, spans, segs, target: str, cfg) -> Tuple[Optional[list], str]:
    """Digitize one target plot. Returns (curve|None, status)."""
    xkw, ykw, reject = cfg["xkw"], cfg["ykw"], cfg["reject"]
    y_lbl = [s for s in spans if ykw.search(s[0]) and not reject.search(s[0])]
    x_lbl = [s for s in spans if xkw.search(s[0]) and not reject.search(s[0])]
    if not y_lbl or not x_lbl:
        return None, f"{target}: axis label not found"

    last_status = f"{target}: no valid plot region"
    for xl in x_lbl:  # try every candidate x-axis label
        xl_cx, xl_cy = (xl[1] + xl[3]) / 2, (xl[2] + xl[4]) / 2
        yl = min(y_lbl, key=lambda s: abs((s[2] + s[4]) / 2 - xl_cy)
                 + 0.3 * abs((s[1] + s[3]) / 2 - xl_cx))
        region = (min(xl[1], yl[1]) - 5, min(yl[2], xl[2]) - 220,
                  max(xl[3], yl[3]) + 5, xl[4] + 5)
        frame = _plot_frame(segs, region)
        if not frame:
            last_status = f"{target}: plot frame not found"
            continue
        fx0, fy0, fx1, fy1 = frame

        # Tick labels: numeric spans just below frame (x) and just left (y).
        xt, yt = [], []
        for (t, sx0, sy0, sx1, sy1) in spans:
            val = _num(t)
            if val is None:
                continue
            cx, cy = (sx0 + sx1) / 2, (sy0 + sy1) / 2
            if fy1 - 3 <= cy <= fy1 + 22 and fx0 - 20 <= cx <= fx1 + 20:
                xt.append((cx, val))
            elif fx0 - 55 <= cx <= fx0 + 3 and fy0 - 8 <= cy <= fy1 + 8:
                yt.append((cy, val))
        xcal = _calibrate(xt)
        ycal = _calibrate(yt)
        if not xcal or not ycal:
            last_status = (f"{target}: axis calibration failed "
                           f"(x={len(set(xt))},y={len(set(yt))} ticks)")
            continue

        # Data curve: keep segments inside the frame, rejecting only LONG
        # axis-aligned runs (frame edges / gridlines). Short axis-aligned
        # segments are real curve data near an extremum (e.g. the SRF minimum).
        pad = 2.0
        fw, fh = (fx1 - fx0), (fy1 - fy0)
        pts = []
        for (ax, ay, bx, by) in segs:
            if not (fx0 - pad <= ax <= fx1 + pad and fx0 - pad <= bx <= fx1 + pad
                    and fy0 - pad <= ay <= fy1 + pad and fy0 - pad <= by <= fy1 + pad):
                continue
            dx, dy = abs(ax - bx), abs(ay - by)
            if dx < 0.5 and dy < 0.5:
                continue  # dot / degenerate
            if dy < 1.0 and dx > 0.3 * fw:
                continue  # long horizontal = gridline / frame
            if dx < 1.0 and dy > 0.3 * fh:
                continue  # long vertical = gridline / frame
            pts.append((ax, ay)); pts.append((bx, by))
        if len(pts) < 3:
            last_status = f"{target}: data curve not found ({len(pts)} pts)"
            continue

        # Map to data, sort by x, de-duplicate.
        data = sorted(((xcal(px), ycal(py)) for px, py in pts), key=lambda p: p[0])
        curve, last = [], None
        for x, y in data:
            if last is None or (abs(x) > 0 and abs(x - last) > abs(x) * 1e-4) \
               or (last == 0 and x != 0):
                curve.append([_sig(x), _sig(y)])
                last = x
        if len(curve) >= 2:
            return curve, f"{target}: {len(curve)} points from vector plot"
        last_status = f"{target}: <2 mapped points"
    return None, last_status


def _sig(v: float, n: int = 6) -> float:
    """Round to n significant figures (keeps small ESR and large freq precise)."""
    if v == 0:
        return 0.0
    import math
    d = n - 1 - int(math.floor(math.log10(abs(v))))
    return round(v, d)


def extract_curves(pdf_path: str, max_pages: int = 12) -> Dict:
    """Extract every known target curve from a datasheet PDF.

    Returns a dict with one key per target (``dc_bias_curve``, ``tcc_curve``,
    ``impedance_curve``, ``esr_curve``) — each a ``[[x, y], ...]`` list or None —
    plus a ``log`` of what happened.
    """
    out: Dict = {t: None for t in _TARGETS}
    out["log"] = []
    if not _HAVE_FITZ:
        out["log"].append("PyMuPDF not available - curve extraction skipped")
        return out
    doc = fitz.open(pdf_path)
    try:
        for pno in range(min(max_pages, doc.page_count)):
            page = doc[pno]
            spans = _spans(page)
            segs = _segments(page)
            for target, cfg in _TARGETS.items():
                if out[target] is not None:
                    continue
                curve, status = _extract_one(page, spans, segs, target, cfg)
                if curve:
                    out[target] = curve
                    out["log"].append(f"p{pno+1}: {status}")
    finally:
        doc.close()
    for target in _TARGETS:
        if out[target] is None:
            out["log"].append(f"{target}: not extracted")
    return out


# ---------------------------------------------------------------------------
# Caption-anchored, grid-aware extraction (for multi-plot datasheet pages such
# as regulator "Typical Characteristics" sections laid out as a 2x2/3x2 grid).
# Each plot is located from its "Figure N. <title>" caption instead of assuming
# a single plot per page, so neighbouring subplots no longer corrupt the
# frame/tick calibration.
# ---------------------------------------------------------------------------
_FIGCAP = re.compile(r"^\s*(?:Figure|Fig\.?)\s+[\dA-Za-z\-]+", re.I)


def _frame_above_caption(segs, cx, cap_y, col_x0, col_x1, max_h=275.0):
    """Inner axes rectangle of the plot sitting just above a caption.

    TI 'Typical Characteristics' pages stack subplots in a loose grid; the old
    bounding-box approach fused a plot with its neighbour (and with page-wide
    separator rules). Instead we lock onto the actual axes box: the plot border
    and its internal gridlines all share one horizontal extent, so we cluster
    horizontals by (x0, x1) extent, split each extent into vertical runs (a gap
    marks a different stacked plot), and keep the (extent, run) box whose bottom
    edge sits just above THIS caption. ``cx``/``cap_y`` are the caption centre-x
    and top-y; ``col_x0``/``col_x1`` bound a caption-centred window so a
    neighbouring subplot cannot bleed in. Returns (x0, y0, x1, y1) or None.
    """
    top_lim = cap_y - max_h
    H, V = [], []
    for (ax, ay, bx, by) in segs:
        xlo, xhi = min(ax, bx), max(ax, bx)
        ylo, yhi = min(ay, by), max(ay, by)
        if abs(ay - by) < 1.5 and (xhi - xlo) > 40:
            if col_x0 - 2 <= xlo and xhi <= col_x1 + 2 \
               and top_lim <= (ay + by) / 2 <= cap_y + 2:
                H.append((xlo, xhi, (ay + by) / 2))
        elif abs(ax - bx) < 1.5 and (yhi - ylo) > 30:
            if col_x0 - 2 <= (ax + bx) / 2 <= col_x1 + 2 \
               and top_lim - 6 <= ylo and yhi <= cap_y + 3:
                V.append(((ax + bx) / 2, ylo, yhi))
    if not H or not V:
        return None
    # Cluster horizontals by shared (x0, x1) extent (6px tol).
    groups = []  # [xlo, xhi, members_y]
    for xlo, xhi, y in sorted(H, key=lambda h: -(h[1] - h[0])):
        for g in groups:
            if abs(g[0] - xlo) <= 6 and abs(g[1] - xhi) <= 6:
                g[2].append(y)
                break
        else:
            groups.append([xlo, xhi, [y]])
    # Derive each box's HEIGHT from the vertical edges of its extent, not from
    # gaps between horizontals: a lone rectangle has only top+bottom borders
    # (a large gap) yet is one box, while two stacked plots that happen to
    # share an x-extent are bridged by NO vertical across the inter-plot gap.
    # A left/right border (or interior gridline) spans exactly one plot, so its
    # [ylo, yhi] is that plot's height.
    boxes = []  # (xlo, xhi, ytop, ybot)
    for xlo, xhi, ys in groups:
        if (xhi - xlo) <= 60:
            continue
        ev = [v for v in V if xlo - 4 <= v[0] <= xhi + 4]
        spans = []  # [ylo, yhi, count]
        for (_vx, vylo, vyhi) in ev:
            for s in spans:
                if abs(s[0] - vylo) <= 8 and abs(s[1] - vyhi) <= 8:
                    s[2] += 1
                    break
            else:
                spans.append([vylo, vyhi, 1])
        for (a, b, _c) in spans:
            if (b - a) <= 30:
                continue
            # confirm a top horizontal near a and a bottom near b at this extent
            if any(abs(y - a) <= 6 for y in ys) and any(abs(y - b) <= 6 for y in ys):
                boxes.append((xlo, xhi, a, b))
    boxes = [b for b in boxes if b[3] <= cap_y + 2]
    if not boxes:
        return None
    # Pick the box whose bottom is nearest above the caption; tie-break on the
    # box centre nearest the caption centre (side-by-side plots share a bottom).
    x0, x1, y0, y1 = min(
        boxes, key=lambda b: (abs(b[3] - cap_y), abs((b[0] + b[1]) / 2 - cx)))
    if (x1 - x0) < 30 or (y1 - y0) < 30:
        return None
    return (x0, y0, x1, y1)

def _calibrate_q(ticks: List[Tuple[float, float]]):
    """Like _calibrate but also returns fit quality: (fn, r2, n_ticks)."""
    ticks = sorted(set(ticks))
    if len(ticks) < 2:
        return None, 0.0, 0
    px = [p for p, _ in ticks]
    vv = [v for _, v in ticks]
    if max(px) - min(px) < 5:
        return None, 0.0, len(ticks)
    lin = _robust_lin(px, vv)
    if lin is None:
        return None, 0.0, len(ticks)
    lm, lb, lr2 = lin
    if all(v > 0 for v in vv) and (max(vv) / min(vv)) > 20:
        import math
        log = _robust_lin(px, [math.log10(v) for v in vv])
        if log and log[2] >= lr2:
            gm, gb, gr2 = log
            return (lambda p: 10.0 ** (gm * p + gb)), gr2, len(ticks)
    return (lambda p: lm * p + lb), lr2, len(ticks)


def _axis_ticks(spans, frame):
    """Locate x/y tick labels by clustering numeric spans within frame-relative
    bands. The x-axis row sits just below the frame bottom; the y-axis column
    sits strictly left of the frame. A span holding several space-separated
    numbers (labels that got merged during extraction, e.g. "0.1 0.2") is split
    and spread across the span so every tick is recovered. Keeping the y-band
    strictly left of the frame stops the x-axis label row from masquerading as
    y-ticks on plots whose axes touch.

    Returns (xt, yt) as lists of (pixel, value): xt keyed on cx, yt on cy.
    """
    fx0, fy0, fx1, fy1 = frame
    xcand, ycand = [], []
    for (t, sx0, sy0, sx1, sy1) in spans:
        nums = [nv for nv in (_num(tok) for tok in t.replace(",", " ").split())
                if nv is not None]
        if not nums:
            continue
        cx, cy = (sx0 + sx1) / 2, (sy0 + sy1) / 2
        w, h, n = (sx1 - sx0), (sy1 - sy0), len(nums)
        if fy1 - 2 <= cy <= fy1 + 34 and fx0 - 22 <= cx <= fx1 + 24:
            for i, nv in enumerate(nums):
                xcand.append(((sx0 + w * (i + 0.5) / n) if n > 1 else cx, cy, nv))
        if fx0 - 72 <= cx <= fx0 - 1 and fy0 - 8 <= cy <= fy1 + 8:
            for i, nv in enumerate(nums):
                ycand.append((cx, (sy0 + h * (i + 0.5) / n) if n > 1 else cy, nv))

    def _cluster(cand, idx, tol=4.0):
        groups = []  # each: [center, members]
        for c in sorted(cand, key=lambda z: z[idx]):
            for g in groups:
                if abs(g[0] - c[idx]) <= tol:
                    g[1].append(c)
                    g[0] = sum(z[idx] for z in g[1]) / len(g[1])
                    break
            else:
                groups.append([c[idx], [c]])
        return groups

    # X-axis: rows sharing cy, spread across x. Prefer the most-populated row
    # (tie: closest to the frame bottom).
    rows = [g for g in _cluster(xcand, 1)
            if len(g[1]) >= 3
            and max(z[0] for z in g[1]) - min(z[0] for z in g[1]) > 25]
    if rows:
        g = max(rows, key=lambda g: (len(g[1]), -abs(g[0] - fy1)))
        xt = [(z[0], z[2]) for z in g[1]]
    else:
        xt = []
    # Y-axis: columns sharing cx, spread across y. Prefer left-most populated.
    cols = [g for g in _cluster(ycand, 0)
            if len(g[1]) >= 3
            and max(z[1] for z in g[1]) - min(z[1] for z in g[1]) > 25]
    if cols:
        g = min(cols, key=lambda g: g[0])
        yt = [(z[1], z[2]) for z in g[1]]
    else:
        yt = []
    return xt, yt


def _multitrace_spread(curve):
    """Fraction of the y-range that overlapping traces smear across x. High
    when a single frame holds several curves (our digitizer cannot separate
    them), so callers can flag the result as low-confidence."""
    xs = [p[0] for p in curve]
    ys = [p[1] for p in curve]
    yspan = max(ys) - min(ys)
    if yspan <= 0 or len(curve) < 8:
        return 0.0
    lo, hi = min(xs), max(xs)
    if hi <= lo:
        return 1.0
    nb = 12
    bins = [[] for _ in range(nb)]
    for x, y in curve:
        i = min(nb - 1, int((x - lo) / (hi - lo) * nb))
        bins[i].append(y)
    spreads = [max(b) - min(b) for b in bins if len(b) >= 2]
    if not spreads:
        return 0.0
    spreads.sort()
    return spreads[len(spreads) // 2] / yspan  # median intra-bin spread


def _despike_once(curve):
    n = len(curve)
    if n < 7:
        return curve
    ys = [p[1] for p in curve]
    steps = sorted(abs(ys[i] - ys[i - 1]) for i in range(1, n))
    med = steps[len(steps) // 2] or 1e-30
    out = []
    for i in range(n):
        win = sorted(ys[max(0, i - 2):min(n, i + 3)])
        m = win[len(win) // 2]
        if abs(ys[i] - m) > 6 * med:
            continue
        out.append(curve[i])
    return out if len(out) >= 2 else curve


def _despike(curve):
    """Remove gross y-outliers (curve self-crossings, stray label vectors) with a
    moving-median filter, iterated so ADJACENT spikes (which would otherwise pull
    the window median toward themselves) are also removed. Clean smooth/monotonic
    curves are untouched."""
    cur = curve
    for _ in range(5):
        nxt = _despike_once(cur)
        if len(nxt) == len(cur):
            break
        cur = nxt
    return cur


def _color_segments(page):
    """Like ``_segments`` but tags each segment with its stroke colour tuple
    (r, g, b) rounded, or None. Used only to pull apart several traces sharing
    one plot frame — each trace is drawn in its own colour."""
    out = []
    for dr in page.get_drawings():
        col = dr.get("color")
        q = None if col is None else tuple(round(float(c), 2) for c in col)
        for it in dr.get("items", []):
            op = it[0]
            if op == "l":
                p1, p2 = it[1], it[2]
                out.append((p1.x, p1.y, p2.x, p2.y, q))
            elif op == "c":
                pts = [it[1], it[2], it[3], it[4]]
                for a, b in zip(pts[:-1], pts[1:]):
                    out.append((a.x, a.y, b.x, b.y, q))
    return out


def _frame_data_pts(segs, frame):
    """Endpoints of data-like segments inside the frame, dropping the border
    and axis-aligned gridlines. ``segs`` are 4-tuples (x0, y0, x1, y1)."""
    fx0, fy0, fx1, fy1 = frame
    pad = 2.0
    fw, fh = (fx1 - fx0), (fy1 - fy0)
    pts = []
    for (ax, ay, bx, by) in segs:
        if not (fx0 - pad <= ax <= fx1 + pad and fx0 - pad <= bx <= fx1 + pad
                and fy0 - pad <= ay <= fy1 + pad and fy0 - pad <= by <= fy1 + pad):
            continue
        dx, dy = abs(ax - bx), abs(ay - by)
        if dx < 0.5 and dy < 0.5:
            continue
        if dy < 1.0 and dx > 0.3 * fw:
            continue  # horizontal gridline / frame edge
        if dx < 1.0 and dy > 0.3 * fh:
            continue  # vertical gridline / frame edge
        pts.append((ax, ay)); pts.append((bx, by))
    return pts


def _pts_to_curve(pts, xcal, ycal):
    """Map pixel endpoints through the axis calibrations into a de-duplicated,
    de-spiked [[x, y], ...] curve sorted by x."""
    if len(pts) < 3:
        return []
    data = sorted(((xcal(px), ycal(py)) for px, py in pts), key=lambda p: p[0])
    curve, last = [], None
    for x, y in data:
        if last is None or (abs(x) > 0 and abs(x - last) > abs(x) * 1e-4) \
           or (last == 0 and x != 0):
            curve.append([_sig(x), _sig(y)])
            last = x
    if len(curve) < 2:
        return []
    return _despike(curve)


def _separate_traces(color_segs, frame, xcal, ycal):
    """Pull several curves out of one frame by stroke colour. Returns a list of
    clean traces (each {"color", "curve", "npoints", "spread"}), largest first.
    A colour group is kept only if it digitizes to a single low-spread trace
    that spans a real fraction of the x-axis — fills, gridlines and stray
    fragments are rejected by the spread and coverage gates."""
    fx0, _fy0, fx1, _fy1 = frame
    fw = fx1 - fx0
    groups: Dict = {}
    for (ax, ay, bx, by, col) in color_segs:
        groups.setdefault(col, []).append((ax, ay, bx, by))
    traces = []
    for col, gsegs in groups.items():
        pts = _frame_data_pts(gsegs, frame)
        if len(pts) < 10:
            continue
        pxs = [p[0] for p in pts]
        if max(pxs) - min(pxs) < 0.3 * fw:  # fragment, not a full trace
            continue
        curve = _pts_to_curve(pts, xcal, ycal)
        if len(curve) < 6:
            continue
        sp = _multitrace_spread(curve)
        if sp < 0.2:
            traces.append({"color": col, "curve": curve,
                           "npoints": len(curve), "spread": _sig(sp, 3)})
    traces.sort(key=lambda tr: -len(tr["curve"]))
    return traces


def _digitize_frame(spans, segs, frame, color_segs=None):
    """Calibrate axes from surrounding ticks and digitize the curve inside the
    frame. Returns (curve|None, status, meta). ``meta`` carries fit quality
    (xr2/yr2), tick counts and a multi-trace spread estimate; when the frame
    smears (several traces) and ``color_segs`` lets us pull >=2 clean traces
    apart by colour, ``meta['traces']`` holds them and ``curve`` is the largest
    trace (so single-curve consumers still get a real trace, not the blend)."""
    fx0, fy0, fx1, fy1 = frame
    meta = {"xr2": 0.0, "yr2": 0.0, "nx": 0, "ny": 0, "spread": 0.0}
    xt, yt = _axis_ticks(spans, frame)
    xcal, xr2, nx = _calibrate_q(xt)
    ycal, yr2, ny = _calibrate_q(yt)
    meta.update(xr2=xr2, yr2=yr2, nx=nx, ny=ny)
    if not xcal or not ycal:
        # Name the axis that yielded no usable ticks — on TI plots this is
        # typically an axis whose numbers are drawn as vectors, not text.
        miss = []
        if not xcal:
            miss.append(f"x-axis has no tick labels (found {nx})")
        if not ycal:
            miss.append(f"y-axis has no tick labels (found {ny})")
        return None, "calibration failed: " + "; ".join(miss), meta
    pts = _frame_data_pts(segs, frame)
    if len(pts) < 3:
        return None, f"data curve not found ({len(pts)} pts)", meta
    curve = _pts_to_curve(pts, xcal, ycal)
    if len(curve) < 2:
        return None, "<2 mapped points", meta
    meta["spread"] = _multitrace_spread(curve)
    # Smeared frame -> try to separate overlapping traces by colour.
    if meta["spread"] >= 0.2 and color_segs:
        traces = _separate_traces(color_segs, frame, xcal, ycal)
        if len(traces) >= 2:
            meta["traces"] = traces
            curve = traces[0]["curve"]
            return curve, f"{len(traces)} traces separated", meta
    return curve, f"{len(curve)} points", meta


def extract_labeled_curves(pdf_path: str, wanted, max_pages: int = 16) -> Dict:
    """Digitize plots identified by their figure caption (grid-page aware).

    ``wanted`` is a list of ``(key, caption_regex)`` pairs. Every caption on a
    page is matched; the plot frame directly above each matched caption is
    located within its grid column and digitized. Each
    result carries a ``confidence`` in {"high", "low"}: "high" means both axes
    calibrated cleanly (r2 >= 0.985, >=3 ticks) and the frame holds a single
    trace; "low" curves are still returned but flagged, never presented as
    trustworthy. Returns ``{key: {"curve", "caption", "status", "confidence",
    "meta"}}`` for the best match of each key, plus a ``log`` list.
    """
    out: Dict = {"log": []}
    if not _HAVE_FITZ:
        out["log"].append("PyMuPDF not available - curve extraction skipped")
        return out
    pats = [(k, re.compile(rx, re.I)) for k, rx in wanted]
    doc = fitz.open(pdf_path)
    try:
        for pno in range(min(max_pages, doc.page_count)):
            page = doc[pno]
            spans = _spans(page)
            segs = _segments(page)
            color_segs = _color_segments(page)
            caps = [s for s in spans if _FIGCAP.match(s[0])]
            if not caps:
                continue
            margin = 8.0
            for (t, x0, y0, x1, y1) in caps:
                key = next((k for k, rx in pats if rx.search(t)), None)
                if key is None:
                    continue
                cx = (x0 + x1) / 2
                # Caption-centred window: TI pages are not a clean 2-column
                # grid (a lone plot can straddle the page midline), so clip a
                # band around the caption instead of a fixed half-page column.
                # Wide enough for one axes box + its left y-labels, tight enough
                # to exclude a side-by-side neighbour.
                halfw = 140.0
                col_x0 = max(margin, cx - halfw)
                col_x1 = min(page.rect.width - margin, cx + halfw)
                frame = _frame_above_caption(segs, cx, y0, col_x0, col_x1)
                if not frame:
                    out["log"].append(f"p{pno+1} {key}: no frame above caption")
                    continue
                curve, status, meta = _digitize_frame(
                    spans, segs, frame, color_segs)
                if not curve:
                    out["log"].append(f"p{pno+1} {key}: {status}")
                    continue
                traces = meta.get("traces")
                # Multi-trace frames smear as one blend (high spread) but each
                # separated trace is clean -> trust them.
                good = (meta["xr2"] >= 0.985 and meta["yr2"] >= 0.985
                        and meta["nx"] >= 3 and meta["ny"] >= 3
                        and (meta["spread"] < 0.25 or bool(traces)))
                conf = "high" if good else "low"
                # Prefer high confidence; then more traces; then more points.
                prev = out.get(key)
                ntr = len(traces) if traces else 0
                pntr = len(prev["traces"]) if prev and prev.get("traces") else 0
                better = (prev is None
                          or (conf == "high" and prev["confidence"] != "high")
                          or (conf == prev["confidence"]
                              and (ntr, len(curve)) > (pntr, len(prev["curve"]))))
                if better:
                    rec = {"curve": curve, "caption": t.strip(),
                           "status": status, "confidence": conf, "meta": meta}
                    if traces:
                        rec["traces"] = traces
                    out[key] = rec
                out["log"].append(
                    f"p{pno+1} {key}: {status} conf={conf} "
                    f"(xr2={meta['xr2']:.3f} yr2={meta['yr2']:.3f} "
                    f"spread={meta['spread']:.2f}"
                    + (f" traces={ntr}" if ntr else "") + f") {t.strip()}")
    finally:
        doc.close()
    return out