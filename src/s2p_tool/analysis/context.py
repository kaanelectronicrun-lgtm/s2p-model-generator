"""AnalysisContext — one shared parse of a datasheet, handed to every Section.

Opening the PDF and detecting the vendor once (instead of per section) keeps the
pipeline cheap and consistent. Both engines are exposed because they serve
different jobs: pymupdf for text/vector work (identity, curves), pdfplumber for
ruled-table reconstruction (specs, pinout). Both are optional at import time so
the rest of s2p still runs where they are absent.
"""
from __future__ import annotations

import os
import re
from typing import Dict, List, Optional

try:
    import pymupdf as fitz
    _HAVE_FITZ = True
except Exception:  # pragma: no cover
    try:
        import fitz  # type: ignore
        _HAVE_FITZ = True
    except Exception:
        _HAVE_FITZ = False

try:
    import pdfplumber
    _HAVE_PLUMBER = True
except Exception:  # pragma: no cover
    _HAVE_PLUMBER = False

from . import vendors
from . import components


class AnalysisContext:
    def __init__(self, pdf_path: str, max_pages: int = 30):
        if not _HAVE_FITZ:
            raise RuntimeError("PyMuPDF (pymupdf) gerekli — kurulu değil.")
        self.pdf_path = os.path.abspath(pdf_path)
        self.max_pages = max_pages
        self.doc = fitz.open(pdf_path)
        self.page_count = self.doc.page_count
        self._plumber = None
        self._text_cache: Dict[int, str] = {}
        self.part = self._part_number()
        self.full_text = self.text(6)
        self.vendor, self.vendor_score, self.vendor_reason = vendors.detect_vendor(
            self.part, self.full_text)
        # Component family (regulator, …) drives curve targets + design headings.
        self.deep_text = self.text(28)
        self.component, self.component_scores = components.detect_component(
            self.deep_text)

    # --- lifecycle -------------------------------------------------------
    def close(self) -> None:
        try:
            self.doc.close()
        except Exception:
            pass
        if self._plumber is not None:
            try:
                self._plumber.close()
            except Exception:
                pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # --- text ------------------------------------------------------------
    def page_text(self, i: int) -> str:
        if i not in self._text_cache:
            self._text_cache[i] = self.doc[i].get_text() if i < self.page_count else ""
        return self._text_cache[i]

    def text(self, n_pages: int) -> str:
        n = min(n_pages, self.page_count)
        return "\n".join(self.page_text(i) for i in range(n))

    # --- pdfplumber (lazy) ----------------------------------------------
    @property
    def have_plumber(self) -> bool:
        return _HAVE_PLUMBER

    @property
    def plumber(self):
        if not _HAVE_PLUMBER:
            return None
        if self._plumber is None:
            self._plumber = pdfplumber.open(self.pdf_path)
        return self._plumber

    def is_text_pdf(self) -> bool:
        """False for outlined/scanned PDFs (text drawn as vectors) — those need
        OCR and are out of scope for the text/table sections. Cheap check: any
        real text on the first few pages."""
        return any(self.page_text(i).strip() for i in range(min(4, self.page_count)))

    # --- identity --------------------------------------------------------
    def _part_number(self) -> str:
        """Part number, filename-first. The datasheet's filename is the most
        reliable signal (users name the file after the part); PDF title metadata
        often names a chip referenced in an application figure (e.g. an ADC the
        op-amp drives), which would then mis-drive vendor detection — so the
        title is only a fallback, and only when page 1 corroborates it. Kept in
        step with component_analysis._part_number so ctx.part and the report's
        part agree."""
        stem = os.path.splitext(os.path.basename(self.pdf_path))[0].strip()
        stem = re.sub(r"[\s_\-]*(datasheet|ds|rev[a-z]?|final)$", "", stem,
                      flags=re.I).strip()
        if re.fullmatch(r"[A-Za-z]{2,}[\w-]*\d[\w-]*", stem or ""):
            return stem.upper()
        page0 = self.doc[0].get_text()
        title = (self.doc.metadata or {}).get("title") or ""
        m = re.search(r"\b([A-Z]{2,}\d[\w\-]*)\b", title)
        if m and m.group(1) in page0:
            return m.group(1)
        for line in page0.splitlines():
            m = re.search(r"\b([A-Z]{2,}\d[\w\-]*)\b", line.strip())
            if m:
                return m.group(1)
        return "component"
