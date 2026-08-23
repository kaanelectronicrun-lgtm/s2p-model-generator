"""Vendor profiles — the *how* of extraction, kept separate from the *what*.

A ``Section`` decides what to pull out of a datasheet and how to judge it; a
``VendorProfile`` encodes one manufacturer's layout conventions (part-number
shape, spec-table header wording, subscript rendering quirks). The generic
profile handles the common bordered-table case (proven to work on TI + onsemi);
a vendor profile overrides only the spots where that manufacturer differs, so
we never re-implement a whole extractor per vendor.
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple


class VendorProfile:
    key = "generic"
    label = "Genel"
    # Part-number prefixes typical of this vendor (anchored, case-insensitive).
    part_patterns: Tuple[str, ...] = ()
    # Free-text markers (company name etc.) that appear on the first pages.
    text_markers: Tuple[str, ...] = ()

    def clean_param_name(self, name: str) -> str:
        """Normalise a parameter/symbol cell: collapse intra-cell newlines and
        rejoin subscript fragments split onto their own line (e.g. a symbol
        rendered as 'V\\nIN_UVLO'). Generic rule; vendors may tighten it."""
        if not name:
            return ""
        # A lone 1-2 letter token followed by a newline then more letters is a
        # symbol whose subscript wrapped: glue them ("V\nIN" -> "VIN").
        s = re.sub(r"\b([A-Z]{1,2})\s*\n\s*([A-Z0-9])", r"\1\2", name)
        s = re.sub(r"\s*\n\s*", " ", s)          # remaining newlines -> space
        s = re.sub(r"\s{2,}", " ", s).strip()
        return s

    def spec_table_settings(self) -> dict:
        """pdfplumber table-extraction settings. Bordered datasheets extract
        best with the ruled-line strategy."""
        return {"vertical_strategy": "lines", "horizontal_strategy": "lines"}

    def spec_rows_override(self, ctx) -> Optional[Tuple[List[dict], List[int]]]:
        """Full-custom spec extraction for a vendor whose table layout defeats
        the generic ruled-line path. Return (rows, pages) to override, or None
        to use the generic pdfplumber strategy. Part of the contract so every
        vendor advertises the hook; default is 'no override'."""
        return None


class TIProfile(VendorProfile):
    key, label = "ti", "Texas Instruments"
    part_patterns = (r"^TPS\d", r"^LM\d", r"^TLV\d", r"^LMR\d", r"^TPD\d",
                     r"^BQ\d", r"^UCC\d", r"^INA\d", r"^OPA\d")
    text_markers = ("Texas Instruments", "www.ti.com", "SLVS", "SLUS")

    def spec_rows_override(self, ctx):
        """TI subscript wrap shifts pdfplumber cells → extract by word geometry
        instead. Returns (rows, pages) or None to fall back to the generic path."""
        from . import ti_spec
        rows, pages = ti_spec.extract_ti_spec_rows(ctx, ctx.max_pages)
        return (rows, pages) if rows else None


class OnsemiProfile(VendorProfile):
    key, label = "onsemi", "onsemi"
    part_patterns = (r"^NCP\d", r"^NCV\d", r"^FAN\d", r"^LC\d", r"^MC\d{4}")
    text_markers = ("ON Semiconductor", "onsemi", "www.onsemi.com")


class ADIProfile(VendorProfile):
    key, label = "adi", "Analog Devices / Linear"
    part_patterns = (r"^LT\d", r"^LTC\d", r"^LTM\d", r"^AD[A-Z]?\d", r"^MAX\d")
    text_markers = ("Analog Devices", "Linear Technology", "www.analog.com",
                    "Maxim Integrated")


class STProfile(VendorProfile):
    key, label = "st", "STMicroelectronics"
    part_patterns = (r"^L\d{4}", r"^ST\d", r"^LD\d", r"^TSV\d", r"^STM\d")
    text_markers = ("STMicroelectronics", "www.st.com")


class InfineonProfile(VendorProfile):
    key, label = "infineon", "Infineon"
    part_patterns = (r"^IR\d", r"^BSC\d", r"^IRLML", r"^TLE\d", r"^IFX\d",
                     r"^IRF\d")
    text_markers = ("Infineon", "www.infineon.com")


class MPSProfile(VendorProfile):
    key, label = "mps", "Monolithic Power Systems"
    part_patterns = (r"^MP\d", r"^MPQ\d", r"^MPM\d")
    # NB: no bare "MPS" marker — it substring-matches "samples"/"amps".
    text_markers = ("Monolithic Power", "www.monolithicpower.com")


_PROFILES: List[VendorProfile] = [
    TIProfile(), OnsemiProfile(), ADIProfile(), STProfile(),
    InfineonProfile(), MPSProfile(),
]
_GENERIC = VendorProfile()


def detect_vendor(part: str, text: str) -> Tuple[VendorProfile, float, str]:
    """Resolve the vendor from the part number (strong signal) and first-page
    text markers (confirmation). Returns (profile, score, reason)."""
    part = (part or "").upper()
    low = (text or "")
    best, best_score, best_reason = _GENERIC, 0.0, "eşleşme yok → genel profil"
    for p in _PROFILES:
        score = 0.0
        hits = []
        for rx in p.part_patterns:
            if re.search(rx, part, re.I):
                score += 3.0
                hits.append(f"part~{rx}")
                break
        # Word-boundary match so short markers don't fire inside other words
        # (e.g. an "MPS" marker hitting "samples"/"amps").
        mk = sum(1 for m in p.text_markers
                 if re.search(r"\b" + re.escape(m) + r"\b", low, re.I))
        if mk:
            score += min(mk, 3) * 1.0
            hits.append(f"{mk} marker")
        if score > best_score:
            best, best_score, best_reason = p, score, ", ".join(hits)
    return best, best_score, best_reason


def get_profile(key: str) -> Optional[VendorProfile]:
    if key == "generic":
        return _GENERIC
    return next((p for p in _PROFILES if p.key == key), None)
