"""Datasheet PDF -> pre-filled JSON template (best-effort text extraction).

Pulls the unambiguous facts a datasheet states in text — capacitance/inductance,
voltage, dielectric, case — and writes a component JSON with them filled in.
SRF / ESR / ESL are NOT in most datasheet text (they live in impedance graphs or
SimSurfing), so they are left blank with a note: add an estimate, a case (for the
geometry ESL calc), or import a measured .s2p for sign-off accuracy.

Requires `pypdf`. Heuristic — always review the generated JSON before use.
"""
from __future__ import annotations

import json
import os
import re
from typing import Dict, Optional

_DIELECTRICS = ["C0G", "NP0", "X7R", "X5R", "X6S", "X7S", "X7T", "X8R",
                "Y5V", "Z5U", "U2J", "JB", "CH"]
_METRIC_TO_EIA = {"1005": "0402", "1608": "0603", "2012": "0805",
                  "3216": "1206", "3225": "1210", "4532": "1812"}
_MULT = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "μ": 1e-6, "m": 1e-3, "": 1.0}


def extract_text(path: str, max_pages: int = 4) -> str:
    from pypdf import PdfReader
    reader = PdfReader(path)
    pages = reader.pages[:max_pages]
    return "\n".join((p.extract_text() or "") for p in pages)


def _value(text: str, unit: str) -> Optional[float]:
    """First '<num><prefix>F' or '<num><prefix>H' occurrence -> SI value."""
    m = re.search(r"(\d+(?:\.\d+)?)\s*([pnuµμm]?)" + unit + r"\b", text)
    if not m:
        return None
    return float(m.group(1)) * _MULT.get(m.group(2), 1.0)


def _voltage(text: str) -> Optional[float]:
    m = (re.search(r"DC\s*(\d+(?:\.\d+)?)\s*V", text)
         or re.search(r"(\d+(?:\.\d+)?)\s*V\s*DC", text)
         or re.search(r"(\d+(?:\.\d+)?)\s*VDC", text))
    return float(m.group(1)) if m else None


def _dielectric(text: str) -> Optional[str]:
    up = text.upper()
    for d in _DIELECTRICS:
        if d in up:
            return "C0G/NP0" if d in ("C0G", "NP0") else d
    return None


def _case(text: str) -> Optional[str]:
    m = re.search(r"\b(0201|0402|0603|0805|1206|1210|1812)\b", text)
    if m:
        return m.group(1)
    m = re.search(r"\b(1005|1608|2012|3216|3225|4532)\b", text)
    return _METRIC_TO_EIA.get(m.group(1)) if m else None


def _part_number(text: str, fallback: str) -> str:
    """First token that looks like an MLCC/inductor part number (e.g. GRM188R71C104KA01)."""
    m = re.search(r"\b([A-Z]{2,4}\d{2}[A-Z0-9]{5,16})\b", text)
    return m.group(1) if m else fallback


def extract_capacitor(text: str) -> Dict:
    return {"capacitance_f": _value(text, "F"), "voltage_rating_v": _voltage(text),
            "dielectric": _dielectric(text), "case": _case(text)}


def extract_inductor(text: str) -> Dict:
    out: Dict = {"inductance_h": _value(text, "H")}
    m = re.search(r"Isat[^\d]*(\d+(?:\.\d+)?)\s*A", text, re.I)
    if m:
        out["isat_a"] = float(m.group(1))
    m = re.search(r"(?:Irms|Rated Current)[^\d]*(\d+(?:\.\d+)?)\s*A", text, re.I)
    if m:
        out["irms_a"] = float(m.group(1))
    return out


def pdf_to_template(path: str, kind: str, out_dir: str) -> str:
    """Write a pre-filled JSON template from a datasheet PDF. Returns its path."""
    text = extract_text(path)
    stem = os.path.splitext(os.path.basename(path))[0]
    part = _part_number(text, re.sub(r"[^A-Za-z0-9_.-]", "_", stem))
    found = extract_capacitor(text) if kind == "capacitor" else extract_inductor(text)
    data: Dict = {"kind": kind, "part_number": part}
    data.update({k: v for k, v in found.items() if v is not None})
    data["source"] = 5
    missing = [k for k, v in found.items() if v is None]
    data["notes"] = (f"Auto-extracted from datasheet PDF '{os.path.basename(path)}'. "
                     "REVIEW required. SRF/ESR/ESL not in datasheet text -> add an "
                     "estimate, or keep 'case' for the geometry ESL/SRF calc, or "
                     "import a measured .s2p. Missing here: "
                     + (", ".join(missing) or "none") + ".")

    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"{part}_from_pdf.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    return out
