"""Model-vs-measured error analysis.

Compares a candidate Z(f) against a measured Touchstone reference and reports the
relative error  |Z_model - Z_meas| / |Z_meas|  per frequency band. Used to show
how much accuracy improves as the model tier rises (datasheet -> calibrated
lumped -> vector fit).
"""
from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np

# Frequency bands that matter for a decoupling MLCC.
_BANDS: List[Tuple[str, float, float]] = [
    ("LF capacitive (<1 MHz)", 0.0, 1e6),
    ("approach (1-10 MHz)", 1e6, 1e7),
    ("near SRF (10-40 MHz)", 1e7, 4e7),
    ("HF inductive (>40 MHz)", 4e7, 1e12),
]


def rel_error(z_model: np.ndarray, z_meas: np.ndarray) -> np.ndarray:
    return np.abs(z_model - z_meas) / (np.abs(z_meas) + 1e-30)


def band_table(f: np.ndarray, rel: np.ndarray) -> List[Tuple[str, float, float]]:
    """Return [(band_label, mean_pct, max_pct), ...]."""
    rows = []
    for label, lo, hi in _BANDS:
        m = (f >= lo) & (f < hi)
        if m.any():
            rows.append((label, float(rel[m].mean() * 100), float(rel[m].max() * 100)))
        else:
            rows.append((label, float("nan"), float("nan")))
    return rows


def overall_pct(rel: np.ndarray) -> Tuple[float, float]:
    """RMS and worst-case relative error in percent."""
    return float(np.sqrt(np.mean(rel ** 2)) * 100), float(rel.max() * 100)


def write_error_csv(path: str, f: np.ndarray, curves: Dict[str, np.ndarray]) -> None:
    keys = list(curves)
    with open(path, "w", encoding="ascii") as fh:
        fh.write("freq_Hz," + ",".join(f"relerr_{k}" for k in keys) + "\n")
        for i in range(len(f)):
            vals = ",".join(f"{curves[k][i]:.6e}" for k in keys)
            fh.write(f"{f[i]:.6e},{vals}\n")
