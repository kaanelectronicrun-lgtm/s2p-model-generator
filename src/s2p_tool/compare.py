"""Compare extracted parameters across several measured Touchstone files.

Primary use: DC-bias / temperature derating studies for Class-II MLCCs (X5R/X7R),
where capacitance drops as DC bias rises. Each file is imported, real parameters
are extracted, and the shift vs the first (reference) file is tabulated.
"""
from __future__ import annotations

import os
import re
from typing import List

from . import importer


def _bias_label(path: str) -> str:
    """Pull a human label like 'DC0V' / 'DC6V3' / '85degC' from the filename."""
    name = os.path.basename(path)
    m = re.search(r"DC[\dV_]+|[\d]+degC", name)
    return m.group(0) if m else name


def compare_measured(paths: List[str], kind: str) -> str:
    rows = []
    for path in paths:
        m = importer.load_touchstone(path)
        if kind == "capacitor":
            p = importer.extract_capacitor(m)
            rows.append((_bias_label(path), p["capacitance_f"], p["esr_ohm"],
                         p["esl_h"], p["srf_hz"]))
        else:
            p = importer.extract_inductor(m)
            rows.append((_bias_label(path), p["inductance_h"], p["dcr_ohm"],
                         p["cp_f"], p["srf_hz"]))

    ref = rows[0]
    out: List[str] = []
    if kind == "capacitor":
        out.append(f"{'Condition':<12}{'C [nF]':>10}{'dC%':>8}"
                   f"{'ESR [mohm]':>11}{'ESL [nH]':>10}{'SRF [MHz]':>11}")
        out.append("-" * 61)
        for label, c, esr, esl, srf in rows:
            dc = (c - ref[1]) / ref[1] * 100
            out.append(f"{label:<12}{c*1e9:>10.3f}{dc:>+8.1f}"
                       f"{esr*1e3:>11.2f}{esl*1e9:>10.4f}{srf/1e6:>11.2f}")
        out.append("")
        out.append("Note: C drop vs reference = X7R/X5R DC-bias derating (Class-II).")
    else:
        out.append(f"{'Condition':<12}{'L [uH]':>10}{'dL%':>8}"
                   f"{'DCR [mohm]':>11}{'Cp [pF]':>10}{'SRF [MHz]':>11}")
        out.append("-" * 61)
        for label, l, dcr, cp, srf in rows:
            dl = (l - ref[1]) / ref[1] * 100
            out.append(f"{label:<12}{l*1e6:>10.4f}{dl:>+8.1f}"
                       f"{dcr*1e3:>11.2f}{cp*1e12:>10.3f}{srf/1e6:>11.2f}")
    return "\n".join(out)
