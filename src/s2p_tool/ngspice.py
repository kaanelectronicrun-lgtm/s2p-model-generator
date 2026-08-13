"""Optional real-ngspice backend for SPICE round-trip validation.

When an ngspice console binary is found, a 2-terminal series subckt is simulated
in actual ngspice (AC sweep, 1 A injection -> V = Z), giving the strongest possible
round-trip ("does the emitted netlist run in a real simulator and reproduce Z?").
Falls back to the pure-numpy nodal solver (`spicesim`) when ngspice is absent.

Discovery order: env var S2P_NGSPICE, then common install/Downloads locations.
"""
from __future__ import annotations

import glob
import os
import re
import subprocess
import tempfile
from typing import Optional, Tuple

import numpy as np

_PATH: Optional[str] = None
_SUBCKT = re.compile(r"^\.subckt\s+(\S+)\s+(\S+)\s+(\S+)", re.I | re.M)


def find_ngspice() -> Optional[str]:
    global _PATH
    if _PATH is not None:
        return _PATH or None
    env = os.environ.get("S2P_NGSPICE")
    cands = [env] if env else []
    home = os.path.expanduser("~")
    cands += glob.glob(os.path.join(home, "Downloads", "ngspice*", "**",
                                    "ngspice_con.exe"), recursive=True)
    cands += glob.glob(r"C:\Program Files*\*ngspice*\**\ngspice_con.exe",
                       recursive=True)
    cands += ["ngspice_con", "ngspice"]  # PATH
    for c in cands:
        if c and (os.path.isfile(c) or c in ("ngspice_con", "ngspice")):
            _PATH = c
            return c
    _PATH = ""
    return None


def available() -> bool:
    return find_ngspice() is not None


_CTRL_SRC = re.compile(r"^[GEFH]\w*\s", re.I | re.M)


def _is_sparam_subckt(cir_text: str) -> bool:
    """skrf S-parameter subckt uses controlled sources (G/E/F/H); the numpy
    Foster ladder is pure R/L/C. Detect which harness to use."""
    return bool(_CTRL_SRC.search(cir_text))


def simulate_z(cir_text: str, f_start: float, f_stop: float,
               points_per_decade: int = 60, z0: float = 50.0
               ) -> Tuple[np.ndarray, np.ndarray]:
    """Run ngspice and return the DUT's series impedance Z(f).

    Auto-detects netlist type:
      * 2-terminal series R/L/C subckt -> inject 1 A, Z = V(port1).
      * 2-port S-parameter subckt (skrf) -> VNA harness (source+z0 / z0 load),
        S21 = 2*V(p2), Z = 2*z0*(1-S21)/S21  (validated against measured data).
    """
    exe = find_ngspice()
    if not exe:
        raise RuntimeError("ngspice not found")
    m = _SUBCKT.search(cir_text)
    if not m:
        raise ValueError("no .subckt in netlist")
    name, pa, pb = m.group(1), m.group(2), m.group(3)
    sparam = _is_sparam_subckt(cir_text)

    if sparam:
        harness = (
            ".include dut.cir\n"
            f"Vg ng 0 AC 1\nRg ng {pa} {z0:g}\n"
            f"X1 {pa} {pb} {name}\nRl {pb} 0 {z0:g}\n"
            ".control\n"
            f"ac dec {points_per_decade} {f_start:g} {f_stop:g}\n"
            f"wrdata zout.txt v({pb})\n.endc\n.end\n")
    else:
        harness = (
            ".include dut.cir\n"
            f"X1 inp 0 {name}\nIin 0 inp AC 1\n"
            ".control\n"
            f"ac dec {points_per_decade} {f_start:g} {f_stop:g}\n"
            "wrdata zout.txt v(inp)\n.endc\n.end\n")

    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "dut.cir"), "w") as fh:
            fh.write(cir_text)
        with open(os.path.join(d, "harness.cir"), "w") as fh:
            fh.write(harness)
        res = subprocess.run([exe, "-b", "harness.cir"], cwd=d,
                             capture_output=True, text=True, timeout=120)
        zpath = os.path.join(d, "zout.txt")
        if not os.path.isfile(zpath):
            raise RuntimeError(f"ngspice produced no output:\n{res.stderr[-400:]}")
        data = np.loadtxt(zpath)
    freq, vp = data[:, 0], data[:, 1] + 1j * data[:, 2]
    if sparam:
        s21 = 2.0 * vp
        return freq, 2 * z0 * (1 - s21) / s21
    return freq, vp


# Backwards-compatible alias.
def simulate_series_z(cir_text, f_start, f_stop, points_per_decade=60):
    return simulate_z(cir_text, f_start, f_stop, points_per_decade)
