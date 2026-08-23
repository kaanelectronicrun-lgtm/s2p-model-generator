"""PinoutSection — pin-function table extraction.

Pin tables are bordered, so pdfplumber's line strategy reads them directly; the
work is role-mapping columns that vary by vendor and header shape:

  * TI splits the header across two rows ("PIN" spanning NAME+NUMBER above,
    then "NAME | NUMBER" below, plus I/O and DESCRIPTION);
  * onsemi uses one header row but two package-specific number columns
    ("Pin No. TSOP-5 | Pin No. WDFN6 | Pin Name | Description") and no I/O.

We fold the leading header rows together, assign each column a role from its
combined text, then read data rows into {name, number, io, description}. Honest
confidence: a table that yields no named+numbered pins comes back low/none.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from .base import Evidence, Section, SectionResult

# A pin-number cell: 1 · A2 (ball) · "4, 5, 6, 7" · "4 / −" · "− / 4".
_PINNO = re.compile(r"^[\s−–\-]*[A-Za-z]?\d[\w/,\s−–\-]*$")
# A pin NAME: an optional sign / channel-index prefix (op-amp pins are named
# "1IN–", "2OUT", "+IN", "V+"), then a letter, then name chars incl. ±/–/− so a
# channel-prefixed or signed pin isn't dropped. Must hold at least one letter so
# a bare number is never taken as a name.
_NAME = re.compile(r"^[+\-–−]?\d{0,2}[A-Za-z][A-Za-z0-9_/+\-–−]{0,11}$")


def _role(text: str) -> Optional[str]:
    u = re.sub(r"\s+", " ", text).upper().strip()
    if not u:
        return None
    if "DESCRIPTION" in u or "FUNCTION" in u:
        return "description"
    if "NAME" in u or "SIGNAL" in u:
        return "name"
    if "NUMBER" in u or re.search(r"\bNO\b|NO\.", u) or u == "PIN":
        return "number"
    if "I/O" in u or u == "IO" or "TYPE" in u:
        return "io"
    return None


def _looks_pin_number(s: str) -> bool:
    s = (s or "").strip()
    return bool(s) and len(s) < 20 and bool(_PINNO.match(s)) and any(
        ch.isdigit() for ch in s)


class PinoutSection(Section):
    key, label = "pinout", "Pinout (Pin Fonksiyonları)"

    def extract(self, ctx, res: SectionResult) -> None:
        if not ctx.have_plumber:
            res.reason = "pdfplumber yok"
            return
        if not ctx.is_text_pdf():
            res.reason = "PDF metin katmanı yok → OCR gerekir"
            res.issues.append("no-text-layer")
            return
        settings = ctx.vendor.spec_table_settings()
        pins: List[Dict] = []
        for pno, page in enumerate(ctx.plumber.pages[:ctx.max_pages], 1):
            try:
                tables = page.extract_tables(settings)
            except Exception:
                continue
            for t in tables:
                got = self._parse_pin_table(t, ctx.vendor)
                if got:
                    pins.extend(got)
                    res.evidence.append(Evidence(page=pno, note="pin table"))
                    break                       # one pin table per page is plenty
            if pins:
                break                           # first page with a pin table wins
        res.data = pins

    def _parse_pin_table(self, table, profile=None) -> List[Dict]:
        if not table or len(table) < 2:
            return []
        # Find the first data row: a row carrying a pin-number-looking cell.
        data_start = None
        for i, row in enumerate(table[:5]):
            if any(_looks_pin_number(str(c or "")) for c in row):
                data_start = i
                break
        if data_start in (None, 0):
            # Either no data or no header — require a header block above data.
            if data_start is None:
                return []
        header_rows = table[:data_start]
        if not header_rows:
            return []
        ncol = max(len(r) for r in table)
        # Combine header text per column -> role.
        role_by_idx: Dict[int, str] = {}
        for c in range(ncol):
            combined = " ".join(str(hr[c]) for hr in header_rows
                                if c < len(hr) and hr[c])
            role = _role(combined)
            if role:
                role_by_idx[c] = role
        # A multi-package part (TI SOIC/SOT/SC70, onsemi TSOP-5/WDFN6) puts the
        # pin number under a spanning "PIN" header with a *package name* per
        # sub-column, so none reads as "NO." — data-sniff the still-unroled
        # columns and treat the leftmost whose cells are pin numbers as NUMBER.
        if "number" not in role_by_idx.values():
            for c in range(ncol):
                if c in role_by_idx:
                    continue
                vals = [str(r[c]).strip() for r in table[data_start:]
                        if c < len(r) and str(r[c] or "").strip()]
                if vals and sum(_looks_pin_number(v) for v in vals) \
                        >= 0.6 * len(vals):
                    role_by_idx[c] = "number"
                    break
        if "name" not in role_by_idx.values() \
                or "description" not in role_by_idx.values():
            return []
        pins = []
        for row in table[data_start:]:
            cells = [str(c or "").strip() for c in row]
            fields = {"name": "", "number": "", "io": "", "description": ""}
            for idx, val in enumerate(cells):
                role = role_by_idx.get(idx)
                if role and not fields[role]:        # first column of a role wins
                    # Rejoin a subscript that wrapped onto its own line
                    # ("V\nIN" -> "VIN") on the name so it isn't dropped as an
                    # invalid two-token name; other cells just collapse spaces.
                    if role == "name" and profile is not None:
                        fields[role] = profile.clean_param_name(val)
                    else:
                        fields[role] = re.sub(r"\s+", " ", val).strip()
            if not fields["name"] or not _NAME.match(fields["name"]):
                continue
            pins.append(fields)
        return pins

    # --- V&V -------------------------------------------------------------
    def validate(self, ctx, res: SectionResult) -> None:
        pins = res.data or []
        seen = set()
        for p in pins:
            if not p["number"]:
                res.issues.append(f"{p['name']}: pin numarası yok")
            key = (p["name"], p["number"])
            if key in seen:
                res.issues.append(f"{p['name']}: tekrar eden pin")
            seen.add(key)

    def score(self, ctx, res: SectionResult) -> None:
        pins = res.data or []
        named = [p for p in pins if p["name"] and p["number"]]
        if not pins:
            res.confidence = "none"
            res.reason = res.reason or "pin tablosu bulunamadı"
        elif len(named) >= 3 and len(res.issues) <= max(1, len(pins) // 5):
            res.confidence = "high"
            res.reason = f"{len(named)} pin (isim+no), {len(res.issues)} sorun"
        elif len(named) >= 2:
            res.confidence = "med"
            res.reason = f"{len(named)} pin, {len(res.issues)} sorun"
        else:
            res.confidence = "low"
            res.reason = f"{len(pins)} satır, çok az geçerli pin"

    def interpret(self, ctx, res: SectionResult) -> None:
        pins = res.data or []
        if not pins:
            return
        def has(*names):
            return [p["name"] for p in pins
                    if any(n in p["name"].upper() for n in names)]
        power = has("VIN", "VCC", "VDD", "VBAT", "AVDD")
        gnd = has("GND", "VSS", "PGND", "AGND")
        finds = [f"{len(pins)} pin çıkarıldı."]
        if power:
            finds.append("Güç girişleri: " + ", ".join(sorted(set(power))))
        if gnd:
            finds.append("Toprak: " + ", ".join(sorted(set(gnd))))
        res.interpretation = finds
