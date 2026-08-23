"""SpecSection — structured electrical-characteristics extraction.

Adopts pdfplumber's ruled-line table extraction (validated across TI + onsemi):
because the datasheet's own column rules separate MIN/TYP/MAX, we no longer
guess column boundaries geometrically — we read the table pdfplumber already
split, identify each column from its header word, and pull typed values. The
vendor profile only cleans manufacturer-specific quirks (e.g. TI subscript
wrap). Each row is a dict:

    {section, parameter, symbol, conditions, min, typ, max, unit}

Validation is honest: min<=max where both are numeric, typ within [min,max],
and a scored confidence so a mangled table is flagged, never trusted.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from .base import Evidence, Section, SectionResult

# Header tokens -> canonical column role.
_ROLE = {
    "parameter": "parameter", "parameters": "parameter",
    "symbol": "symbol", "sym": "symbol",
    "test conditions": "conditions", "conditions": "conditions",
    "condition": "conditions",
    "min": "min", "minimum": "min",
    "typ": "typ", "typical": "typ", "nom": "typ", "nominal": "typ",
    "max": "max", "maximum": "max",
    "unit": "unit", "units": "unit",
}
_NUMRX = re.compile(r"^[+\-]?\d*\.?\d+$")      # 2.7  -2  ±1  .5
_DASHES = "−–‒—‐‑"                              # assorted Unicode dashes -> '-'

# Thermal-resistance rows (RθJA, ψJT, °C/W …) are per-board figures, not
# MIN/TYP/MAX electricals — they masquerade as MIN>MAX and pollute the table.
_THERMAL = re.compile(
    r"θ|ψ|thermal\s+resistance|junction[- ]to[- ]|R\W?[Θθ]J|Psi\W?J", re.I)


def _is_thermal(row: dict) -> bool:
    unit = (row.get("unit") or "").replace(" ", "").lower()
    if "c/w" in unit or "°c/w" in unit or "k/w" in unit:
        return True
    blob = f"{row.get('parameter','')} {row.get('symbol','')}"
    return bool(_THERMAL.search(blob))


# Page furniture that a word-geometry sweep drags in as fake rows: the copyright
# line, the "Submit Document Feedback" footer, doc/product-folder boilerplate.
_JUNK = re.compile(
    r"copyright|submit\s*document|document\s*feedback|texas\s*instruments"
    r"|instruments\s*incorporated|product\s*folder|all\s*rights\s*reserved"
    r"|trademark|www\.", re.I)


def _is_junk_row(row: dict) -> bool:
    """True for a boilerplate/footer row that is not an electrical parameter."""
    blob = " ".join(str(row.get(k, "")) for k in
                    ("section", "parameter", "symbol", "conditions", "unit"))
    if _JUNK.search(blob):
        return True
    # A page footer swept into the value band: no real parameter, no unit/
    # conditions, just a lone small integer (the page number).
    param = (row.get("parameter") or "").strip()
    if len(param) < 3 and not (row.get("unit") or "").strip() \
            and not (row.get("conditions") or "").strip():
        vals = [str(row.get(k) or "").strip()
                for k in ("min", "typ", "max") if str(row.get(k) or "").strip()]
        if len(vals) == 1 and re.fullmatch(r"\d{1,3}", vals[0]):
            return True
    return False


def _num(s: str) -> Optional[float]:
    s = (s or "")
    for d in _DASHES:
        s = s.replace(d, "-")
    s = s.replace("±", "").strip()
    if _NUMRX.match(s):
        try:
            return float(s)
        except ValueError:
            return None
    return None


class SpecSection(Section):
    key, label = "specs", "Elektriksel Özellikler"

    def extract(self, ctx, res: SectionResult) -> None:
        if not ctx.have_plumber:
            res.reason = "pdfplumber yok"
            return
        if not ctx.is_text_pdf():
            res.reason = ("PDF metin katmanı yok (outline/raster) → tablo "
                          "çıkarılamaz, OCR gerekir")
            res.issues.append("no-text-layer")
            return
        profile = ctx.vendor
        # A vendor whose table layout defeats pdfplumber cell-indexing (TI's
        # wrapped subscripts shift the row cells) overrides extraction with its
        # own strategy; otherwise the generic ruled-line path is used.
        rows: List[Dict]
        pages_used: List[int]
        got = profile.spec_rows_override(ctx)   # base returns None -> generic
        if got is not None:
            rows, pages_used = got
        else:
            rows, pages_used = self._generic_plumber(ctx, profile)
        # Drop thermal-resistance rows (not MIN/TYP/MAX electricals) and page
        # furniture (copyright/footer/page-number rows) swept in by extraction.
        rows = [r for r in rows if not _is_thermal(r) and not _is_junk_row(r)]
        res.data = rows
        for p in pages_used:
            res.evidence.append(Evidence(page=p, note="spec table"))

    def _generic_plumber(self, ctx, profile) -> Tuple[List[Dict], List[int]]:
        """Ruled-line pdfplumber path: read the columns the datasheet already
        separated. Works where cells align with the header (proven on onsemi)."""
        settings = profile.spec_table_settings()
        rows: List[Dict] = []
        pages_used: List[int] = []
        pdf = ctx.plumber
        for pno, page in enumerate(pdf.pages[:ctx.max_pages], 1):
            try:
                tables = page.extract_tables(settings)
            except Exception:
                continue
            for t in tables:
                cols = self._column_roles(t)
                if cols is None:
                    continue
                hidx, role_by_idx = cols
                got = self._rows_from_table(t, hidx, role_by_idx, profile)
                if got:
                    rows.extend(got)
                    if pno not in pages_used:
                        pages_used.append(pno)
        return rows, pages_used

    # --- table parsing ---------------------------------------------------
    @staticmethod
    def _column_roles(table) -> Optional[Tuple[int, Dict[int, str]]]:
        """Find the header row (has MIN & MAX) and map column index -> role."""
        for hidx, row in enumerate(table[:4]):
            cells = [str(c or "").strip().lower() for c in row]
            has_min = any(c == "min" or c == "minimum" for c in cells)
            has_max = any(c == "max" or c == "maximum" for c in cells)
            if not (has_min and has_max):
                continue
            role_by_idx: Dict[int, str] = {}
            for idx, c in enumerate(cells):
                role = _ROLE.get(c)
                if role:
                    role_by_idx[idx] = role
            if "min" in role_by_idx.values() and "max" in role_by_idx.values():
                return hidx, role_by_idx
        return None

    def _rows_from_table(self, table, hidx: int, role_by_idx: Dict[int, str],
                         profile) -> List[Dict]:
        out: List[Dict] = []
        section = ""
        for row in table[hidx + 1:]:
            cells = [str(c or "").strip() for c in row]
            if not any(cells):
                continue
            fields = {"parameter": "", "symbol": "", "conditions": "",
                      "min": "", "typ": "", "max": "", "unit": ""}
            for idx, val in enumerate(cells):
                role = role_by_idx.get(idx)
                if role:
                    fields[role] = val
            # Leftover columns with no role but text -> fold into parameter
            # (some tables split the name across two unlabeled columns).
            if not fields["parameter"]:
                unroled = [cells[i] for i in range(len(cells))
                           if i not in role_by_idx and cells[i]]
                fields["parameter"] = " ".join(unroled[:2])
            fields["parameter"] = profile.clean_param_name(fields["parameter"])
            fields["symbol"] = profile.clean_param_name(fields["symbol"])
            fields["conditions"] = re.sub(r"\s*\n\s*", " ",
                                          fields["conditions"]).strip()
            has_num = any(_num(fields[k]) is not None
                          for k in ("min", "typ", "max"))
            # Section header row: a lone parameter, no numbers, no conditions.
            if not has_num:
                if fields["parameter"] and not fields["conditions"] \
                        and not fields["symbol"]:
                    section = fields["parameter"]
                continue
            fields["section"] = section
            out.append(fields)
        return out

    # --- V&V -------------------------------------------------------------
    def validate(self, ctx, res: SectionResult) -> None:
        rows = res.data or []
        for r in rows:
            vmin, vtyp, vmax = _num(r["min"]), _num(r["typ"]), _num(r["max"])
            label = r.get("symbol") or r.get("parameter") or "?"
            if vmin is not None and vmax is not None and vmin > vmax:
                res.issues.append(f"{label}: MIN>{'MAX'} ({vmin}>{vmax})")
            if vtyp is not None and vmin is not None and vmax is not None \
                    and not (vmin <= vtyp <= vmax):
                res.issues.append(
                    f"{label}: TYP={vtyp} ∉ [{vmin},{vmax}]")

    def score(self, ctx, res: SectionResult) -> None:
        rows = res.data or []
        if not rows:
            res.confidence = "none"
            res.reason = res.reason or "spec tablosu bulunamadı"
            return
        n = len(rows)
        bad = len(res.issues)
        # A real EC table yields many rows; a handful likely means a mis-parse.
        if n >= 8 and bad == 0:
            res.confidence = "high"
            res.reason = f"{n} satır, tutarsızlık yok (vendor={ctx.vendor.key})"
        elif n >= 4 and bad <= max(1, n // 10):
            res.confidence = "med"
            res.reason = f"{n} satır, {bad} tutarsızlık (vendor={ctx.vendor.key})"
        else:
            res.confidence = "low"
            res.reason = f"{n} satır, {bad} tutarsızlık — az/şüpheli"

    # --- interpretation --------------------------------------------------
    def interpret(self, ctx, res: SectionResult) -> None:
        rows = res.data or []
        if not rows:
            return
        finds: List[str] = []
        # Pull a few headline parameters if present.
        def find(*needles) -> Optional[Dict]:
            for r in rows:
                blob = (r.get("parameter", "") + " " + r.get("symbol", "")).lower()
                if all(nz in blob for nz in needles):
                    return r
            return None

        vin = find("input", "voltage") or find("vin")
        if vin and (_num(vin["min"]) is not None or _num(vin["max"]) is not None):
            finds.append(f"Giriş gerilimi ~ {vin['min'] or '?'}…{vin['max'] or '?'} "
                         f"{vin['unit']}")
        n_high = sum(1 for r in rows if _num(r["typ"]) is not None)
        finds.append(f"{len(rows)} parametre çıkarıldı, {n_high} tanesinde TYP değeri var.")
        res.interpretation = finds
