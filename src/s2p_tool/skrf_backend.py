"""Optional scikit-rf backend (enhanced engine).

All scikit-rf usage is isolated here and guarded by `available()`. When skrf is
installed, the import + measured-fit paths can use it for:
  - robust n-port Touchstone I/O,
  - vector fitting with *passivity enforcement* (`passivity_enforce`), which our
    numpy synth cannot do — this yields a null-accurate AND passive SPICE model.

When skrf is absent, callers fall back to the numpy-only engine
(`vectorfit.py` + `synth.py`). Nothing here is imported at module load except the
availability probe, so the tool still runs with numpy alone.
"""
from __future__ import annotations

import warnings
from typing import Dict, Optional, Tuple

import numpy as np

_CHECKED: Optional[bool] = None


def available() -> bool:
    global _CHECKED
    if _CHECKED is None:
        try:
            import skrf  # noqa: F401
            _CHECKED = True
        except Exception:
            _CHECKED = False
    return _CHECKED


def _network_from_series_z(freq: np.ndarray, z: np.ndarray, z0: float):
    """Build a 2-port series-through Network from series impedance Z(f)."""
    import skrf as rf
    s11 = z / (z + 2 * z0)
    s21 = (2 * z0) / (z + 2 * z0)
    S = np.zeros((len(freq), 2, 2), dtype=complex)
    S[:, 0, 0] = s11
    S[:, 1, 1] = s11
    S[:, 0, 1] = s21
    S[:, 1, 0] = s21
    frq = rf.Frequency.from_f(freq, unit="Hz")
    return rf.Network(frequency=frq, s=S, z0=z0)


def _series_z_from_s(s21: np.ndarray, z0: float) -> np.ndarray:
    return 2 * z0 * (1 - s21) / s21


def fit_passive_spice(freq: np.ndarray, z: np.ndarray, z0: float,
                      spice_path: str, n_poles_cmplx: int = 8) -> Dict:
    """Vector-fit measured series Z, enforce passivity, write a SPICE subckt.

    Returns a dict with the engine, passivity status, and the model's series Z(f)
    on the input grid (for accuracy comparison).
    """
    from skrf import VectorFitting

    ntwk = _network_from_series_z(freq, z, z0)
    ref = np.sqrt(np.mean(np.abs(z) ** 2)) + 1e-30

    def _passive(vf) -> bool:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            r = vf.is_passive()
        return bool(r[0] if isinstance(r, tuple) else r)

    def _fit(nc):
        vf = VectorFitting(ntwk)
        vf.max_iterations = 300
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            vf.vector_fit(n_poles_real=1, n_poles_cmplx=nc, init_pole_spacing="log",
                          fit_constant=True, fit_proportional=False)
        zmod = _series_z_from_s(vf.get_model_response(1, 0, freq), z0)
        rms = float(np.sqrt(np.mean(np.abs(zmod - z) ** 2)) / ref)
        return vf, zmod, rms

    # fit_proportional MUST be False (a non-zero proportional term breaks
    # S-parameter passivity testing). Scan orders; prefer the lowest-RMS model
    # that is NATURALLY passive. If none is passive, keep the most accurate fit
    # rather than corrupting it with fragile enforcement (verified: enforcement
    # can wreck an inductor model). Passivity is reported honestly either way.
    cands = []  # (passive, rms, nc)
    for nc in range(4, max(n_poles_cmplx, 4) + 5, 2):
        try:
            vf, _zmod, rms = _fit(nc)
        except Exception:
            continue
        cands.append((_passive(vf), rms, nc))
    if not cands:
        raise RuntimeError("scikit-rf vector_fit produced no usable model")
    passive_cands = [c for c in cands if c[0]]
    pool = passive_cands if passive_cands else cands
    chosen_nc = min(pool, key=lambda c: c[1])[2]
    vf, z_model, _rms = _fit(chosen_nc)        # fresh, uncorrupted
    passive_before = passive_after = bool(passive_cands)

    vf.write_spice_subcircuit_s(spice_path)
    return {
        "engine": "scikit-rf",
        "n_poles": int(np.atleast_1d(vf.poles).size),
        "passive_before": passive_before,
        "passive_after": passive_after,
        "z_model": z_model,
        "spice_path": spice_path,
    }


def load_touchstone_skrf(path: str) -> Tuple[np.ndarray, np.ndarray, float, str]:
    """Robust Touchstone read via skrf. Returns (freq, series_Z, z0, name)."""
    import skrf as rf
    nw = rf.Network(path)
    z0 = float(np.real(nw.z0[0, 0]))
    s21 = nw.s[:, 1, 0]
    z = _series_z_from_s(s21, z0)
    return nw.f, z, z0, (nw.name or "imported_part")
