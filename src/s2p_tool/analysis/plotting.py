"""Render digitized characteristic curves back into plot images.

The datasheet presents these as graphs; once ``CurvesSection`` digitizes them to
points we can re-plot them, which both makes the output a visual document and is
honest proof of what we captured. One PNG per high-confidence curve (multi-trace
curves get one line per colour-separated trace). Optional: skips cleanly when
matplotlib is absent.
"""
from __future__ import annotations

import os
from typing import Dict

from . import i18n

try:
    import matplotlib
    matplotlib.use("Agg")               # headless: render to file, no display
    import matplotlib.pyplot as plt
    _HAVE = True
except Exception:  # pragma: no cover
    _HAVE = False

_ACCENT = "#3F51B5"
_PALETTE = ["#3F51B5", "#E53935", "#43A047", "#FB8C00", "#8E24AA", "#00ACC1"]

_STYLE_DONE = False


def _apply_style() -> None:
    """Set legible, consistent typography once — Segoe UI when present, else the
    Turkish-safe DejaVu Sans — with larger defaults than matplotlib's."""
    global _STYLE_DONE
    if _STYLE_DONE or not _HAVE:
        return
    fam = "DejaVu Sans"
    try:
        from matplotlib import font_manager as _fm
        seg = r"C:\Windows\Fonts\segoeui.ttf"
        if os.path.exists(seg):
            _fm.fontManager.addfont(seg)
            fam = _fm.FontProperties(fname=seg).get_name()
    except Exception:
        pass
    try:
        plt.rcParams.update({
            "font.family": fam,
            "font.size": 11,
            "axes.titlesize": 12,
            "axes.titleweight": "bold",
            "axes.labelsize": 10.5,
            "xtick.labelsize": 9.5,
            "ytick.labelsize": 9.5,
            "axes.edgecolor": "#546E7A",
            "figure.dpi": 130,
            "savefig.dpi": 130,
        })
    except Exception:
        pass
    _STYLE_DONE = True


def available() -> bool:
    return _HAVE


def render_curves(curves: Dict, out_dir: str, part: str,
                  lang: str = "tr") -> Dict[str, str]:
    """Render each digitized curve to ``<part>_<key>.png``. Returns
    ``{key: png_path}``. Low-confidence curves ARE plotted too so no digitized
    graph is silently dropped — but they carry a clear title suffix and a
    watermark so they are never mistaken for trustworthy data. Each curve is
    rendered independently: one failure never blocks the others."""
    if not _HAVE or not curves:
        return {}
    _apply_style()
    os.makedirs(out_dir, exist_ok=True)
    written: Dict[str, str] = {}
    for key, c in curves.items():
        if key == "_log" or not isinstance(c, dict) or "curve" not in c:
            continue
        low = c.get("confidence") != "high"
        fig = None
        try:
            fig, ax = plt.subplots(figsize=(5.8, 3.6))
            traces = c.get("traces")
            if traces:
                for i, tr in enumerate(traces):
                    pts = tr["curve"]
                    ax.plot([p[0] for p in pts], [p[1] for p in pts],
                            marker=".", ms=4, lw=1.8,
                            alpha=0.55 if low else 1.0,
                            color=_PALETTE[i % len(_PALETTE)], label=tr["label"])
                ax.legend(fontsize=9)
            else:
                pts = c["curve"]
                ax.plot([p[0] for p in pts], [p[1] for p in pts],
                        marker=".", ms=4, lw=2.0,
                        color="#B0655B" if low else _ACCENT,
                        alpha=0.7 if low else 1.0)
            title = i18n.label(lang, c.get("desc", key))
            if low:
                title += i18n.t(lang, "curve_low_suffix")
            ax.set_title(title, fontsize=12, fontweight="bold",
                         color="#B71C1C" if low else "black")
            ax.set_xlabel(i18n.label(lang, c.get("unit_x", "")), fontsize=10.5)
            ax.set_ylabel(i18n.label(lang, c.get("unit_y", "")), fontsize=10.5)
            ax.grid(True, alpha=0.3)
            ax.tick_params(labelsize=9.5)
            if low:
                ax.text(0.5, 0.5, i18n.t(lang, "curve_low_watermark"),
                        transform=ax.transAxes, ha="center", va="center",
                        fontsize=26, color="#B71C1C", alpha=0.12,
                        rotation=24, zorder=0, fontweight="bold")
            fig.tight_layout()
            path = os.path.join(out_dir, f"{part}_{key}.png")
            fig.savefig(path)
            written[key] = path
        except Exception:
            pass
        finally:
            if fig is not None:
                plt.close(fig)
    return written


def render_pinout_table(pins, out_dir: str, part: str,
                        max_rows: int = 28, lang: str = "tr") -> str:
    """Render the pinout as a table image (Pin / No / I/O / Açıklama). Returns
    the PNG path or ''. Descriptions are wrapped/truncated to keep the table
    readable."""
    if not _HAVE or not pins:
        return ""
    _apply_style()
    pins = pins[:max_rows]
    cols = [i18n.t(lang, "col_pin"), i18n.t(lang, "col_no"),
            i18n.t(lang, "col_io"), i18n.t(lang, "col_desc")]
    cell = []
    for p in pins:
        desc = (p.get("desc") or p.get("description") or "")
        if len(desc) > 72:
            desc = desc[:69] + "…"
        cell.append([p.get("name", ""), str(p.get("number", "")),
                     p.get("io", "") or "—", desc])
    fig, ax = plt.subplots(figsize=(8.6, 0.44 * len(cell) + 0.7))
    ax.axis("off")
    tbl = ax.table(cellText=cell, colLabels=cols, loc="center",
                   cellLoc="left", colLoc="left")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9.5)
    tbl.scale(1, 1.6)
    # Column widths + header styling.
    widths = [0.10, 0.12, 0.07, 0.71]
    for (r, cidx), cellobj in tbl.get_celld().items():
        cellobj.set_width(widths[cidx])
        cellobj.set_edgecolor("#CFD8DC")
        if r == 0:
            cellobj.set_facecolor(_ACCENT)
            cellobj.set_text_props(color="white", fontweight="bold")
        elif r % 2 == 0:
            cellobj.set_facecolor("#F5F6FA")
    ax.set_title(i18n.t(lang, "pinout_title", part=part, n=len(pins)),
                 fontsize=12, fontweight="bold", pad=10)
    fig.tight_layout()
    path = os.path.join(out_dir, f"{part}_pinout_table.png")
    try:
        fig.savefig(path, bbox_inches="tight")
    finally:
        plt.close(fig)
    return path


def render_spec_ranges(spec_table, out_dir: str, part: str,
                       max_rows: int = 12, lang: str = "tr") -> str:
    """Render a horizontal MIN–TYP–MAX range chart for numeric spec rows that
    share a unit-agnostic normalized view. Returns the PNG path or ''.

    Each parameter is drawn on its own normalized row (its own MIN..MAX mapped to
    0..1) so wildly different units still read as one figure; TYP marked."""
    if not _HAVE or not spec_table:
        return ""
    _apply_style()
    rows = []
    for r in spec_table:
        def num(v):
            v = (v or "").replace("−", "-").replace("±", "").strip()
            try:
                return float(v)
            except ValueError:
                return None
        mn, ty, mx = num(r.get("min")), num(r.get("typ")), num(r.get("max"))
        if mn is not None and mx is not None and mx > mn:
            label = (r.get("symbol") or r.get("parameter") or "?")[:28]
            rows.append((label, mn, ty, mx, r.get("unit", "")))
        if len(rows) >= max_rows:
            break
    if not rows:
        return ""
    fig, ax = plt.subplots(figsize=(6.8, 0.52 * len(rows) + 1.1))
    for i, (label, mn, ty, mx, unit) in enumerate(rows):
        y = len(rows) - i
        ax.plot([0, 1], [y, y], color="#B0BEC5", lw=8, solid_capstyle="round")
        if ty is not None and mn <= ty <= mx:
            tn = (ty - mn) / (mx - mn)
            ax.plot([tn], [y], "o", color=_ACCENT, ms=8, zorder=3)
        ax.text(-0.02, y, f"{label}", ha="right", va="center", fontsize=9.5)
        ax.text(0.0, y + 0.32, f"{mn:g}", ha="center", va="bottom", fontsize=8,
                color="#607D8B")
        ax.text(1.0, y + 0.32, f"{mx:g}{(' ' + unit) if unit else ''}",
                ha="center", va="bottom", fontsize=8, color="#607D8B")
    ax.set_xlim(-0.35, 1.15)
    ax.set_ylim(0.3, len(rows) + 0.9)
    ax.set_title(i18n.t(lang, "spec_ranges_title"),
                 fontsize=12, fontweight="bold")
    ax.axis("off")
    fig.tight_layout()
    path = os.path.join(out_dir, f"{part}_spec_ranges.png")
    try:
        fig.savefig(path)
    finally:
        plt.close(fig)
    return path
