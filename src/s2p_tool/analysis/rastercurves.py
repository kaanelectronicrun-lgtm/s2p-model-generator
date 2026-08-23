"""Digitize a rendered plot image with OpenCV + Tesseract OCR.

Fallback for plots the vector engine (``pdfcurves``) cannot calibrate — dense
multi-plot datasheet pages, unusual tick layouts. We render the plot region to a
high-DPI raster and recover the curve with image processing:

    frame detection -> axis-tick OCR calibration (auto lin/log) -> curve trace

Every result carries a ``confidence``: a plot whose axes cannot be calibrated
from OCR'd ticks comes back low, never as clean data. Optional at import — a
no-op when cv2 / pytesseract / the Tesseract binary is missing.
"""
from __future__ import annotations

import os
import re
import shutil
from typing import Dict, List, Optional, Tuple

try:
    import numpy as np
    import cv2
    import pytesseract
    _HAVE = True
except Exception:  # pragma: no cover
    _HAVE = False

try:
    import pymupdf as fitz
    _HAVE_FITZ = True
except Exception:  # pragma: no cover
    try:
        import fitz  # type: ignore
        _HAVE_FITZ = True
    except Exception:
        _HAVE_FITZ = False


def _tesseract_ok() -> bool:
    exe = shutil.which("tesseract")
    if not exe:
        for p in (r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                  r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"):
            if os.path.exists(p):
                exe = p
                break
    if not exe:
        return False
    try:
        pytesseract.pytesseract.tesseract_cmd = exe
        return True
    except Exception:
        return False


def available() -> bool:
    return _HAVE and _HAVE_FITZ and _tesseract_ok()


# SI-suffixed tick labels: "-20", "0.1", "1k", "10M", "100m".
_SI = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "μ": 1e-6, "m": 1e-3,
       "k": 1e3, "K": 1e3, "M": 1e6, "G": 1e9, "T": 1e12, "": 1.0}
_TICK = re.compile(r"^[±+]?(-?\d+(?:\.\d+)?)\s*([pnuµμmkKMGT]?)$")


def _num(t: str) -> Optional[float]:
    t = t.strip().replace("−", "-").replace(",", "")
    m = _TICK.match(t)
    if not m:
        return None
    return float(m.group(1)) * _SI.get(m.group(2), 1.0)


def _find_frame(gray) -> Optional[Tuple[int, int, int, int]]:
    """Isolate ONE plot cell on a (possibly dense multi-plot) crop. Each cell's
    border+gridlines form one contour; we keep cell-sized boxes and pick the one
    horizontally centred on the caption (crop centre) and nearest the bottom
    (the caption sits just below the crop). Falls back to the largest box."""
    h, w = gray.shape
    bw = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)[1]
    cnts, _ = cv2.findContours(bw, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    for c in cnts:
        x, y, ww, hh = cv2.boundingRect(c)
        a = ww * hh
        if not (0.04 * w * h <= a <= 0.75 * w * h):
            continue
        if not (0.22 * w <= ww <= 0.85 * w and 0.20 * h <= hh <= 0.9 * h):
            continue
        boxes.append((x, y, x + ww, y + hh))
    if not boxes:
        return None
    cxc = w / 2.0
    # Prefer boxes whose centre-x is near the crop centre; tie-break lowest bottom.
    best = min(boxes, key=lambda b: (abs((b[0] + b[2]) / 2 - cxc), -b[3]))
    return best


def _calibrate(ticks: List[Tuple[float, float]]):
    """(pixel, value) pairs -> (fn(pixel)->value, r2, n_kept). Auto lin/log.

    OCR mangles some tick labels (drops a decimal point: 1.5 -> 15), which a
    plain least-squares fit lets corrupt the whole scale. So the fit is robust:
    it drops up to a quarter of the ticks, worst residual first, as long as that
    keeps improving r2 — the misread outliers fall away and the true linear (or
    log) relation of the majority survives."""
    if len(ticks) < 2:
        return None, 0.0, len(ticks)
    px = np.array([t[0] for t in ticks], float)
    vv = np.array([t[1] for t in ticks], float)

    def fit(y, mask):
        A = np.vstack([px[mask], np.ones(int(mask.sum()))]).T
        m, b = np.linalg.lstsq(A, y[mask], rcond=None)[0]
        pred = m * px[mask] + b
        ss = ((y[mask] - pred) ** 2).sum()
        tot = ((y[mask] - y[mask].mean()) ** 2).sum() or 1e-9
        return m, b, 1.0 - ss / tot

    def robust(y):
        mask = np.ones(len(px), bool)
        m, b, r2 = fit(y, mask)
        n_min = max(3, int(np.ceil(len(px) * 0.75)))
        while int(mask.sum()) > n_min and r2 < 0.999:
            resid = np.abs(m * px + b - y)
            resid[~mask] = -1.0
            trial = mask.copy()
            trial[int(np.argmax(resid))] = False
            if int(trial.sum()) < 2:
                break
            m2, b2, r2b = fit(y, trial)
            if r2b <= r2:
                break
            mask, m, b, r2 = trial, m2, b2, r2b
        return m, b, r2, int(mask.sum())

    lm, lb, lr2, ln = robust(vv)
    if (vv > 0).all() and vv.max() / max(vv.min(), 1e-12) >= 100:
        gm, gb, gr2, gn = robust(np.log10(vv))
        if gr2 >= lr2:
            return (lambda p: 10.0 ** (gm * p + gb)), gr2, gn
    return (lambda p: lm * p + lb), lr2, ln


def _ocr_ticks(img_bgr, frame, axis: str) -> List[Tuple[float, float]]:
    """OCR numeric tick labels in the margin of ``axis`` ('x' or 'y'); return
    (pixel, value) pairs in full-image coordinates."""
    x0, y0, x1, y1 = frame
    if axis == "y":
        rx0, rx1 = max(0, x0 - 72), x0 - 1
        ry0, ry1 = max(0, y0 - 6), y1 + 6
    else:
        rx0, rx1 = max(0, x0 - 10), x1 + 10
        ry0, ry1 = y1 + 2, min(img_bgr.shape[0], y1 + 52)
    crop = img_bgr[ry0:ry1, rx0:rx1]
    if crop.size == 0:
        return []
    scale = 3
    crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    g = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    cfg = "--psm 6 -c tessedit_char_whitelist=0123456789.-+kKMGmµ"
    try:
        data = pytesseract.image_to_data(g, config=cfg,
                                         output_type=pytesseract.Output.DICT)
    except Exception:
        return []
    ticks: List[Tuple[float, float]] = []
    for i, txt in enumerate(data["text"]):
        v = _num(txt)
        if v is None:
            continue
        cx = rx0 + (data["left"][i] + data["width"][i] / 2) / scale
        cy = ry0 + (data["top"][i] + data["height"][i] / 2) / scale
        ticks.append((cy if axis == "y" else cx, v))
    return ticks


def _trace(img_bgr, frame, xcal, ycal) -> List[List[float]]:
    """Trace the darkest curve inside the frame, one median point per column."""
    x0, y0, x1, y1 = frame
    inset = 3
    sub = img_bgr[y0 + inset:y1 - inset, x0 + inset:x1 - inset]
    if sub.size == 0:
        return []
    g = cv2.cvtColor(sub, cv2.COLOR_BGR2GRAY)
    # Curve = dark pixels; gridlines are light gray, dropped by a hard threshold.
    mask = g < 110
    hsub = mask.shape[0]
    pts: List[List[float]] = []
    for cx in range(mask.shape[1]):
        rows = np.where(mask[:, cx])[0]
        if rows.size == 0 or rows.size > 0.5 * hsub:  # skip gridline/axis columns
            continue
        ry = float(np.median(rows)) + y0 + inset
        rx = cx + x0 + inset
        xv, yv = xcal(rx), ycal(ry)
        if xv is None or yv is None:
            continue
        pts.append([xv, yv])
    # De-dup on x, keep sorted.
    pts.sort(key=lambda p: p[0])
    out: List[List[float]] = []
    for p in pts:
        if out and abs(p[0] - out[-1][0]) < 1e-12:
            continue
        out.append([round(p[0], 6), round(p[1], 6)])
    return out


def digitize_image(img_bgr) -> Dict:
    """Digitize a single rendered plot image (BGR np.array). Returns
    ``{"curve", "confidence", "npoints", "meta"}`` or ``{"confidence": "none"}``."""
    if not _HAVE:
        return {"confidence": "none", "reason": "cv2/pytesseract yok"}
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    frame = _find_frame(gray)
    if not frame:
        return {"confidence": "none", "reason": "eksen çerçevesi bulunamadı"}
    xt = _ocr_ticks(img_bgr, frame, "x")
    yt = _ocr_ticks(img_bgr, frame, "y")
    xcalf, xr2, nx = _calibrate(xt)
    ycalf, yr2, ny = _calibrate(yt)
    if xcalf is None or ycalf is None:
        return {"confidence": "none",
                "reason": f"kalibrasyon yetersiz (x-tik={nx}, y-tik={ny})"}
    curve = _trace(img_bgr, frame, xcalf, ycalf)
    if len(curve) < 5:
        return {"confidence": "none", "reason": "eğri izlenemedi"}
    good = xr2 >= 0.98 and yr2 >= 0.98 and nx >= 3 and ny >= 3
    return {
        "curve": curve, "npoints": len(curve),
        "confidence": "high" if good else "low",
        "meta": {"xr2": round(xr2, 4), "yr2": round(yr2, 4),
                 "nx": nx, "ny": ny, "source": "ocr"},
    }


_FIGCAP = re.compile(r"^\s*(?:Figure|Fig\.?)\s+[\dA-Za-z\-.]+", re.I)


def digitize_pdf_caption(pdf_path: str, caption_rx: str, zoom: float = 3.0,
                         max_pages: int = 30, halfw: float = 150.0,
                         max_h: float = 300.0) -> Dict:
    """Find the first figure caption matching ``caption_rx``, render the plot
    region just above it to a raster, and digitize it. Returns the same shape as
    :func:`digitize_image` (plus ``caption``/``page``)."""
    if not available():
        return {"confidence": "none", "reason": "raster digitizer yok"}
    rx = re.compile(caption_rx, re.I)
    doc = fitz.open(pdf_path)
    try:
        for pno in range(min(max_pages, doc.page_count)):
            page = doc[pno]
            for b in page.get_text("dict").get("blocks", []):
                for line in b.get("lines", []):
                    txt = re.sub(
                        r"\s+", " ",
                        " ".join(s.get("text", "") for s in line.get("spans", []))
                    ).strip()
                    if not (_FIGCAP.match(txt) and rx.search(txt)):
                        continue
                    x0, y0, x1, y1 = line["bbox"]
                    cx = (x0 + x1) / 2
                    W = page.rect.width
                    clip = fitz.Rect(max(0, cx - halfw), max(0, y0 - max_h),
                                     min(W, cx + halfw), y0 - 2)
                    if clip.width < 40 or clip.height < 40:
                        continue
                    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=clip)
                    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                        pix.height, pix.width, pix.n)
                    if pix.n == 4:
                        arr = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
                    elif pix.n == 3:
                        arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
                    else:
                        arr = cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
                    res = digitize_image(arr)
                    if res.get("curve"):
                        res["caption"] = txt.strip()
                        res["page"] = pno + 1
                        return res
        return {"confidence": "none", "reason": "eşleşen grafik bulunamadı"}
    finally:
        doc.close()
