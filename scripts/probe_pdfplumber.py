"""Scout probe: can pdfplumber recover MIN/TYP/MAX columns from real regulator
Electrical Characteristics tables across vendors (TI / onsemi / ADI)?

Not wired into s2p — a throwaway validation of the adopt-pdfplumber decision.
Run: py -3.12 scripts/probe_pdfplumber.py
"""
import re
import sys

import pdfplumber

PDFS = {
    "TI TPS61088": r"C:\Users\Excalibur\Desktop\OBS_KAAN\Kaan AKCAN\Projeler\Wearable BLE fitness tracker system architecture\Altium Proje Dosyaları\Qi_RX_Engineering_Package_RevA_v0.3_LCSC_TUNE\tps61088.pdf",
    "TI TPS62743": r"C:\Users\Excalibur\Desktop\OBS_KAAN\Kaan AKCAN\Projeler\Wearable BLE fitness tracker system architecture\Component_Files\Datasheets\TPS62743YFPR.pdf",
    "onsemi NCP164": r"C:\Users\Excalibur\Desktop\OBS_KAAN\Kaan AKCAN\Projeler\Wearable BLE fitness tracker system architecture\Component_Files\Datasheets\NCP164PST33T2.pdf",
    "ADI LTC3780": r"C:\Users\Excalibur\Desktop\OBS_KAAN\Kaan AKCAN\Projeler\Wearable BLE fitness tracker system architecture\real_kicad_reference\LTC3780\LTC3780.pdf",
}

# Header words that mark an Electrical-Characteristics numeric table.
HDR = re.compile(r"\b(MIN|TYP|MAX|NOM|UNIT|PARAMETER|SYMBOL)\b", re.I)
NUMRX = re.compile(r"^[±+\-]?\d*\.?\d+$")


def find_spec_tables(pdf, max_pages=30):
    """Yield (page_no, table_rows) for tables whose header row carries MIN & MAX."""
    for pno, page in enumerate(pdf.pages[:max_pages], 1):
        # Try both strategies pdfplumber offers.
        for settings in (
            {"vertical_strategy": "lines", "horizontal_strategy": "lines"},
            {"vertical_strategy": "text", "horizontal_strategy": "text"},
        ):
            try:
                tables = page.extract_tables(settings)
            except Exception:
                continue
            for t in tables:
                flat = " ".join(str(c) for row in t[:3] for c in row if c).upper()
                if "MIN" in flat and "MAX" in flat:
                    yield pno, t, settings
                    break


def summarize_table(t, limit=8):
    """Compact print: header + first data rows, showing column split."""
    out = []
    # find header row index
    hidx = 0
    for i, row in enumerate(t[:4]):
        cells = [str(c or "").upper() for c in row]
        if any("MIN" in c for c in cells) and any("MAX" in c for c in cells):
            hidx = i
            break
    hdr = [str(c or "").strip() for c in t[hidx]]
    out.append("   HDR: " + " | ".join(hdr))
    shown = 0
    for row in t[hidx + 1:]:
        cells = [str(c or "").strip() for c in row]
        if not any(cells):
            continue
        nums = [c for c in cells if NUMRX.match(c)]
        if not nums:
            continue
        out.append("   ROW: " + " | ".join(cells))
        shown += 1
        if shown >= limit:
            break
    return "\n".join(out)


def main():
    L = []
    for name, path in PDFS.items():
        L.append("=" * 78)
        L.append(name)
        L.append("=" * 78)
        try:
            with pdfplumber.open(path) as pdf:
                got = list(find_spec_tables(pdf))
                if not got:
                    L.append("  (MIN/MAX'li tablo bulunamadi ilk 30 sayfada)")
                    L.append("")
                    continue
                seen_pages = set()
                for pno, t, settings in got:
                    if pno in seen_pages:
                        continue
                    seen_pages.add(pno)
                    strat = settings["vertical_strategy"]
                    L.append(f"  -- p{pno} ({len(t)} satir, strateji={strat}) --")
                    L.append(summarize_table(t))
                    L.append("")
                    if len(seen_pages) >= 2:
                        break
        except Exception as e:
            L.append(f"  HATA: {e}")
        L.append("")
    out = "\n".join(L)
    with open("scripts/probe_out.txt", "w", encoding="utf-8") as fh:
        fh.write(out)
    print("wrote scripts/probe_out.txt (%d chars)" % len(out))


if __name__ == "__main__":
    sys.exit(main())
