"""Prose/text extractors for the design-procedure and layout sections.

These are the proven regex helpers from the legacy engine, moved into the
analysis package so the clean Section system owns them (the legacy
``component_analysis`` re-exports these names for backward compatibility). They
narrate a datasheet's design procedure and layout guidance rather than
fabricate equations — exact TI formula glyphs do not survive text extraction.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple


def _first(text: str, pattern: str, groups: int = 1):
    """First regex match's group(s), or None. µ/Ω-tolerant."""
    m = re.search(pattern, text, re.I)
    if not m:
        return None
    if groups == 1:
        return m.group(1).strip()
    return tuple(g.strip() if g else g for g in m.groups()[:groups])


def design_requirements(text: str) -> List[Tuple[str, str]]:
    """Parse the 'Design Requirements' example table (Table 8-x)."""
    pats = [
        ("Giriş gerilimi aralığı",
         r"Input voltage(?:\s*range)?\s*[\n:]\s*([\d.]+\s*to\s*[\d.]+\s*V|[\d.]+\s*V)"),
        ("Çıkış gerilimi", r"Output voltage\s*[\n:]\s*([\d.]+\s*V)\b"),
        ("Çıkış ripple", r"Output voltage ripple\s*[\n:]\s*([^\n]+)"),
        ("Çıkış akımı", r"Output current(?:\s*rating)?\s*[\n:]\s*([\d.]+\s*A)"),
        ("Çalışma frekansı", r"Operating frequency\s*[\n:]\s*([\d.]+\s*[kMG]?Hz)"),
        ("Hafif-yük modu", r"Operation mode at light load\s*[\n:]\s*(\w+)"),
    ]
    out = []
    for label, pat in pats:
        v = _first(text, pat)
        if v:
            out.append((label, re.sub(r"\s+", " ", v).strip()))
    return out


# Regulator design-procedure section headings (label -> heading regex).
PROC_HEADS: Tuple[Tuple[str, str], ...] = (
    ("Anahtarlama frekansı ayarı (RFSW)", r"Setting Switching Frequency"),
    ("Tepe akım limiti ayarı (RILIM)", r"Setting Peak Current Limit"),
    ("İndüktör seçimi", r"Inductor Selection"),
    ("Çıkış kapasitörü seçimi", r"Output Capacitor Selection"),
    ("Giriş kapasitörü seçimi", r"Input Capacitor Selection"),
    ("Soft-start ayarı", r"(?:Programmable\s+)?Soft.?Start"),
    ("Geri-besleme / çıkış gerilimi ayarı",
     r"Setting (?:the )?Output Voltage|Output Voltage Setting|"
     r"Feedback Resistor"),
)


def design_procedure(text: str, proc_heads=PROC_HEADS) -> List[Dict]:
    """Extract each design-procedure step: heading, one-line intent, and the
    'where' variable/constant glossary. Formulae are narrated, not fabricated."""
    steps = []
    for label, head_rx in proc_heads:
        m = re.search(r"\d+\.\d+(?:\.\d+)*\s+(?:" + head_rx + r")", text, re.I)
        if not m:
            continue
        start = m.end()
        tail = text[start:start + 1400]
        nxt = re.search(r"\n\s*\d+\.\d+\.\d+", tail)
        body = tail[:nxt.start()] if nxt else tail
        sent = ""
        ms = re.search(r"([A-Z][^.]{15,240}\.)", body)
        if ms:
            sent = re.sub(r"\s+", " ", ms.group(1)).strip()
        glossary = []
        seen = set()
        for gm in re.finditer(
                r"(?:^|\n)\W*([A-Za-zƒ][\w()]{0,12})\s+is\s+([^\n]+)", body):
            var = gm.group(1).strip()
            defn = re.sub(r"\s+", " ", gm.group(2)).strip().rstrip(".")
            if var.lower() in seen or len(defn) < 3:
                continue
            seen.add(var.lower())
            glossary.append(f"{var} = {defn}")
        if sent or glossary:
            steps.append({"step": label, "intent": sent, "vars": glossary[:8]})
    return steps


def layout_guidelines(text: str) -> List[str]:
    """Split the datasheet's own '§ Layout Guidelines' prose into a checklist."""
    m = re.search(r"Layout Guidelines[ \t]*\n\s*([A-Z][\s\S]+?)"
                  r"(?:Layout Example|\n\s*10\.2|Thermal Considerations|\Z)",
                  text, re.I)
    if not m:
        return []
    prose = re.sub(r"\s+", " ", m.group(1)).strip()
    out = []
    for s in re.split(r"(?<=[.])\s+", prose):
        s = s.strip()
        if len(s) > 25 and not s.lower().startswith("as for all"):
            out.append(s)
    return out[:10]
