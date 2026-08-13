#!/usr/bin/env python3
"""Plot model-vs-measured: |Z| curves (top) + relative-error curves (bottom).

    python plot_error.py <measured.s2p> [out.png]

Builds the 4 model tiers (datasheet, calibrated lumped, vector-fit, weighted
vector-fit), overlays them on the measured |Z|, and shows where each tier's
error lives across frequency. Saves a PNG.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from s2p_tool import importer  # noqa: E402
from s2p_tool.vectorfit import vector_fit  # noqa: E402

path = sys.argv[1] if len(sys.argv) > 1 else \
    r"C:\Users\Excalibur\Downloads\GRM188R71C104KA01_DC0V_25degC_series.s2p"
out = sys.argv[2] if len(sys.argv) > 2 else "outputs/GRM188_error_curve.png"

m = importer.load_touchstone(path)
f, w, s, Zm = m.freq, 2 * np.pi * m.freq, 2j * np.pi * m.freq, m.z
p = importer.extract_capacitor(m)


def lumped(C, ESR, ESL):
    return ESR + 1j * (w * ESL - 1.0 / (w * C))


tiers = {
    "A datasheet+geom": (lumped(1.0e-7, 0.020, 0.70e-9), "#d98c00"),
    "B kalibre-lumped": (lumped(p["capacitance_f"], p["esr_ohm"], p["esl_h"]), "#1f9e6e"),
    "C vector-fit": (vector_fit(f, Zm, 6, 8, weighting="none").eval(s), "#1f6feb"),
    "D agirlikli VF": (vector_fit(f, Zm, 6, 8, weighting="rel").eval(s), "#da3633"),
}

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
fig.suptitle(f"Model vs Olcum — {m.part_number}", fontsize=12, fontweight="bold")

# Top: |Z| magnitude
ax1.loglog(f, np.abs(Zm), "k", lw=2.4, label="Olculen (.s2p) ★★★★★", zorder=5)
for name, (Z, c) in tiers.items():
    ax1.loglog(f, np.abs(Z), color=c, lw=1.3, alpha=0.9, label=name)
isrf = int(np.argmin(np.abs(Zm)))
ax1.axvline(f[isrf], color="grey", ls=":", lw=1)
ax1.annotate(f"SRF {f[isrf]/1e6:.1f} MHz\n|Z|={np.abs(Zm[isrf])*1e3:.0f} mohm",
             xy=(f[isrf], np.abs(Zm[isrf])), xytext=(f[isrf]*1.3, np.abs(Zm[isrf])*6),
             fontsize=8, arrowprops=dict(arrowstyle="->", color="grey"))
ax1.set_ylabel("|Z|  [ohm]")
ax1.grid(True, which="both", alpha=0.25)
ax1.legend(fontsize=8, loc="upper center", ncol=2)

# Bottom: relative error %
for name, (Z, c) in tiers.items():
    rel = np.abs(Z - Zm) / (np.abs(Zm) + 1e-30) * 100
    ax2.loglog(f, rel, color=c, lw=1.3, label=name)
ax2.axvline(f[isrf], color="grey", ls=":", lw=1)
ax2.axhline(1, color="grey", ls="--", lw=0.8, alpha=0.6)
ax2.text(f[1], 1.2, "%1 hata", fontsize=7, color="grey")
ax2.set_ylabel("Bagil hata  [%]")
ax2.set_xlabel("Frekans  [Hz]")
ax2.set_ylim(1e-3, 1e3)
ax2.grid(True, which="both", alpha=0.25)
ax2.legend(fontsize=8, loc="upper left", ncol=2)

fig.tight_layout(rect=(0, 0, 1, 0.97))
os.makedirs(os.path.dirname(out), exist_ok=True)
fig.savefig(out, dpi=130)
print(f"saved -> {out}")
