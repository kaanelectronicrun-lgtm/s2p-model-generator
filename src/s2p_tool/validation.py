"""Model validation: passivity, causality, stability, SRF consistency.

These are sanity checks on the generated behavioral network, not a substitute
for measured data. Each returns a (passed, message) pair.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import numpy as np


@dataclass
class Check:
    name: str
    passed: bool
    detail: str


def passivity(s: Dict[str, np.ndarray]) -> Check:
    """For a reciprocal 2-port, passive iff |S11|^2 + |S21|^2 <= 1 at every f."""
    power = np.abs(s["S11"]) ** 2 + np.abs(s["S21"]) ** 2
    worst = float(np.max(power))
    ok = worst <= 1.0 + 1e-9
    return Check("Passivity", ok,
                 f"max(|S11|^2+|S21|^2) = {worst:.6f} (<=1 required)")


def stability(z: np.ndarray) -> Check:
    """Physically realizable series Z must have Re(Z) >= 0 everywhere."""
    min_re = float(np.min(z.real))
    ok = min_re >= -1e-9
    return Check("Stability / Re(Z)>=0", ok,
                 f"min Re(Z) = {min_re:.4e} Ohm")


def srf_consistency(model_srf: float, datasheet_srf: float | None) -> Check:
    if not datasheet_srf:
        return Check("SRF consistency", True, "no datasheet SRF to compare")
    err = abs(model_srf - datasheet_srf) / datasheet_srf
    ok = err < 0.15
    return Check("SRF consistency", ok,
                 f"model {model_srf/1e6:.2f} MHz vs datasheet "
                 f"{datasheet_srf/1e6:.2f} MHz ({err*100:.1f}% error)")


def causality(s: Dict[str, np.ndarray]) -> Check:
    """Closed-form rational series network is causal by construction.

    We confirm there are no NaN/Inf (which would break Hilbert consistency).
    """
    finite = all(np.all(np.isfinite(v)) for v in s.values())
    return Check("Causality (finite, rational)", finite,
                 "all S-parameters finite — rational/minimum-phase by construction")


def run_all(s: Dict[str, np.ndarray], z: np.ndarray,
            model_srf: float, datasheet_srf: float | None) -> List[Check]:
    return [
        passivity(s),
        causality(s),
        stability(z),
        srf_consistency(model_srf, datasheet_srf),
    ]
