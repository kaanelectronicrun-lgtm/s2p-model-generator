"""Hermetic self-tests for the per-section analysis backbone.

No external datasheets: every case builds a synthetic PDF with pymupdf so the
Section contract, the two-layer vendor strategy (generic pdfplumber vs the TI
word-geometry override), the honest no-text-layer rejection, and per-section
failure isolation are locked against regression.

Run:  py -3.12 tests/test_analysis_sections.py   (no pytest needed)
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def _have_deps() -> bool:
    try:
        import fitz  # noqa: F401
    except Exception:
        try:
            import pymupdf  # noqa: F401
        except Exception:
            return False
    try:
        import pdfplumber  # noqa: F401
    except Exception:
        return False
    return True


def _fitz():
    try:
        import pymupdf as f
        return f
    except Exception:
        import fitz as f
        return f


# ---------------------------------------------------------------------------
# Synthetic datasheet builders
# ---------------------------------------------------------------------------
def _make_bordered_ec_pdf(path):
    """A generic (non-TI) datasheet with a ruled Electrical-Characteristics grid,
    the layout pdfplumber's line strategy reads cell-by-cell."""
    fitz = _fitz()
    doc = fitz.open(); page = doc.new_page(width=612, height=460)
    page.insert_text(fitz.Point(40, 30), "ACME1234 Voltage Regulator", fontsize=11)
    page.insert_text(fitz.Point(40, 46), "Electrical Characteristics", fontsize=10)
    cols = [40, 150, 210, 330, 380, 430, 480, 545]     # 7 columns, 8 borders
    header = ["Parameter", "Symbol", "Test Conditions", "Min", "Typ", "Max", "Unit"]
    rows = [
        ["Input voltage", "VIN", "over temp", "2.7", "3.3", "5.5", "V"],
        ["SUPPLY", "", "", "", "", "", ""],            # section header row
        ["Reference voltage", "VREF", "Tj=25C", "1.19", "1.20", "1.21", "V"],
        ["Quiescent current", "IQ", "no load", "20", "35", "60", "uA"],
        ["Output accuracy", "VACC", "full range", "-2", "0", "2", "%"],
        ["Line regulation", "LNR", "", "", "0.5", "", "mV/V"],
        ["Load regulation", "LDR", "", "", "2", "", "mV"],
        ["Dropout voltage", "VDO", "IOUT=300mA", "", "170", "295", "mV"],
        ["Shutdown current", "ISD", "EN=0", "", "0.1", "1", "uA"],
        ["Thermal shutdown", "TSD", "", "150", "165", "180", "C"],
        # Thermal-resistance row: per-board figure, MIN>MAX if mis-read as
        # electricals — must be dropped by the thermal filter.
        ["Thermal resistance", "RthJA", "", "44", "", "36", "C/W"],
    ]
    y0, rh = 60, 18
    n = len(rows) + 1
    # grid lines
    for i, x in enumerate(cols):
        page.draw_line(fitz.Point(x, y0), fitz.Point(x, y0 + n * rh))
    for r in range(n + 1):
        yy = y0 + r * rh
        page.draw_line(fitz.Point(cols[0], yy), fitz.Point(cols[-1], yy))
    # text
    for c, txt in enumerate(header):
        page.insert_text(fitz.Point(cols[c] + 3, y0 + 13), txt, fontsize=8)
    for r, row in enumerate(rows, 1):
        for c, txt in enumerate(row):
            if txt:
                page.insert_text(fitz.Point(cols[c] + 3, y0 + r * rh + 13),
                                 txt, fontsize=8)
    doc.save(path); doc.close()


def _make_ti_ec_pdf(path):
    """A TI-style page: no ruled cells, subscripts wrapped onto their own word,
    en-dash negatives — the layout that defeats cell-indexing and needs the
    word-geometry override."""
    fitz = _fitz()
    doc = fitz.open(); page = doc.new_page(width=612, height=520)
    page.insert_text(fitz.Point(40, 28), "TPS12345 Synchronous Boost Converter",
                     fontsize=11)
    page.insert_text(fitz.Point(40, 44), "Texas Instruments   www.ti.com",
                     fontsize=9)
    page.insert_text(fitz.Point(40, 60), "Electrical Characteristics", fontsize=10)
    # header baseline
    hy = 90
    for txt, x in (("PARAMETER", 40), ("TEST", 200), ("CONDITIONS", 232),
                   ("MIN", 340), ("TYP", 392), ("MAX", 442), ("UNIT", 492)):
        page.insert_text(fitz.Point(x, hy), txt, fontsize=8)
    # data rows: (param-words[(txt,x)], cond-words, (min,typ,max at their x), unit)
    data = [
        ([("Input", 40), ("voltage", 72), ("V", 150), ("IN", 160)],
         [("over", 205), ("temp", 232)], ("2.7", "3.3", "5.5"), "V"),
        ([("Junction", 40), ("temperature", 82)],
         [], ("-40", "", "150"), "°C"),   # negative (ASCII; en-dash covered by _num unit test)
        ([("SUPPLY", 40)], [], ("", "", ""), ""),      # section header
        ([("Quiescent", 40), ("current", 92), ("I", 150), ("Q", 158)],
         [("EN", 205), ("high", 224)], ("", "35", "60"), "µA"),
        ([("Reference", 40), ("voltage", 92), ("V", 150), ("REF", 160)],
         [], ("1.19", "1.20", "1.21"), "V"),
        ([("Current", 40), ("limit", 82)], [("R=100k", 205)],
         ("8.0", "10.0", "12.0"), "A"),
        ([("Output", 40), ("accuracy", 82)], [], ("-2", "0", "2"), "%"),
        ([("Dropout", 40), ("voltage", 82)], [("IOUT=300mA", 205)],
         ("", "170", "295"), "mV"),
        ([("Shutdown", 40), ("current", 92)], [], ("", "0.1", "1"), "µA"),
    ]
    y = hy + 22
    xcol = {"min": 340, "typ": 392, "max": 442, "unit": 492}
    for pw, cw, (vmin, vtyp, vmax), unit in data:
        for txt, x in pw:
            page.insert_text(fitz.Point(x, y), txt, fontsize=8)
        for txt, x in cw:
            page.insert_text(fitz.Point(x, y), txt, fontsize=8)
        if vmin:
            page.insert_text(fitz.Point(xcol["min"], y), vmin, fontsize=8)
        if vtyp:
            page.insert_text(fitz.Point(xcol["typ"], y), vtyp, fontsize=8)
        if vmax:
            page.insert_text(fitz.Point(xcol["max"], y), vmax, fontsize=8)
        if unit:
            page.insert_text(fitz.Point(xcol["unit"], y), unit, fontsize=8)
        y += 22
    doc.save(path); doc.close()


def _make_pinout_pdf(path):
    """A datasheet with a ruled Pin Functions table using a TWO-ROW merged
    header ('PIN' spanning NAME+NUMBER, then NAME | NUMBER below) — the TI shape
    that forces header-row folding."""
    fitz = _fitz()
    doc = fitz.open(); page = doc.new_page(width=612, height=420)
    page.insert_text(fitz.Point(40, 30), "ACME1234 Regulator", fontsize=11)
    page.insert_text(fitz.Point(40, 46), "Pin Functions", fontsize=10)
    cols = [40, 130, 210, 270, 545]                # NAME | NUMBER | I/O | DESC
    header0 = ["PIN", "", "I/O", "DESCRIPTION"]
    header1 = ["NAME", "NUMBER", "", ""]
    rows = [
        ["VIN", "1", "PWR", "supply input"],
        ["GND", "2", "PWR", "ground"],
        ["EN", "3", "I", "enable logic input"],
        ["SW", "4, 5", "O", "switch node"],
        ["FB", "6", "I", "feedback"],
    ]
    y0, rh = 60, 18
    n = len(rows) + 2                              # two header rows
    for x in cols:
        page.draw_line(fitz.Point(x, y0), fitz.Point(x, y0 + n * rh))
    for r in range(n + 1):
        yy = y0 + r * rh
        page.draw_line(fitz.Point(cols[0], yy), fitz.Point(cols[-1], yy))
    for c, txt in enumerate(header0):
        if txt:
            page.insert_text(fitz.Point(cols[c] + 3, y0 + 13), txt, fontsize=8)
    for c, txt in enumerate(header1):
        if txt:
            page.insert_text(fitz.Point(cols[c] + 3, y0 + rh + 13), txt, fontsize=8)
    for r, row in enumerate(rows, 2):
        for c, txt in enumerate(row):
            page.insert_text(fitz.Point(cols[c] + 3, y0 + r * rh + 13),
                             txt, fontsize=8)
    doc.save(path); doc.close()


def _make_regulator_doc_pdf(path):
    """A regulator datasheet page carrying design-requirements + numbered
    design-procedure + layout-guidelines prose AND a captioned Vref-vs-Temp
    plot — exercises component detection + Curves/Design/Layout section wiring."""
    fitz = _fitz()
    doc = fitz.open(); page = doc.new_page(width=612, height=640)
    prose = (
        "TPS99999 Synchronous boost converter with adjustable switching "
        "frequency and current limit.\n"
        "8.2.1 Design Requirements\nTable 8-1. Design Parameters\n"
        "Input voltage range\n3.3 to 4.2 V\nOutput voltage\n9 V\n"
        "Output voltage ripple\n100 mV peak to peak\nOutput current rating\n3 A\n"
        "Operating frequency\n600 kHz\nOperation mode at light load\nPFM\n"
        "8.2.2 Detailed Design Procedure\n"
        "8.2.2.2 Setting Switching Frequency\n"
        "The switching frequency is set by a resistor between FSW and SW.\nwhere\n"
        "RFREQ is the resistance connected between the FSW pin and the SW pin\n"
        "CFREQ is 23 pF\n"
        "8.2.2.5 Inductor Selection\n"
        "Three important specs are the inductor value, saturation and DCR.\n"
        "10.1 Layout Guidelines\n"
        "Minimize the length and area of all traces connected to the SW pin. "
        "The input capacitor needs to be close to the VIN pin and GND pin. "
        "Use thermal vias underneath the thermal pad.\n10.2 Layout Example\n")
    page.insert_textbox(fitz.Rect(30, 26, 590, 300), prose, fontsize=7)
    # Captioned Vref-vs-Temperature plot (~1.204 V, gentle slope).
    LX0, LX1, LY0, LY1 = 100, 300, 360, 500
    page.draw_rect(fitz.Rect(LX0, LY0, LX1, LY1))
    fx = lambda T: LX0 + (LX1 - LX0) * (T + 40) / 160.0
    fy = lambda V: LY1 - (LY1 - LY0) * (V - 1.202) / 0.004
    for T in (-40, 0, 40, 80, 120):
        page.insert_text(fitz.Point(fx(T) - 6, LY1 + 14), str(T), fontsize=8)
    for V in (1.202, 1.204, 1.206):
        page.insert_text(fitz.Point(LX0 - 30, fy(V) + 3), f"{V:.3f}", fontsize=8)
    pts = [(fx(T), fy(1.205 - (T + 40) / 160.0 * 0.002)) for T in range(-40, 121, 8)]
    for a, b in zip(pts[:-1], pts[1:]):
        page.draw_line(fitz.Point(*a), fitz.Point(*b))
    page.insert_text(fitz.Point(LX0 + 6, LY1 + 34),
                     "Figure 1. Reference Voltage vs Temperature", fontsize=8)
    doc.save(path); doc.close()


def _make_no_text_pdf(path):
    """A page with only vector drawings and no text layer (outlined/scanned) —
    must be honestly rejected, not silently mis-parsed."""
    fitz = _fitz()
    doc = fitz.open(); page = doc.new_page(width=400, height=300)
    page.draw_rect(fitz.Rect(40, 40, 360, 260))
    page.draw_line(fitz.Point(40, 150), fitz.Point(360, 150))
    doc.save(path); doc.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_vendor_detection_by_part_and_marker():
    """Part-number prefix is the strong signal; text markers confirm. No PDF."""
    from s2p_tool.analysis import vendors
    p, s, _ = vendors.detect_vendor("TPS61088", "Texas Instruments www.ti.com")
    assert p.key == "ti" and s >= 4, (p.key, s)
    p, _, _ = vendors.detect_vendor("NCP164", "ON Semiconductor")
    assert p.key == "onsemi", p.key
    p, _, _ = vendors.detect_vendor("LTC3780", "Linear Technology")
    assert p.key == "adi", p.key
    p, _, _ = vendors.detect_vendor("ACME1234", "generic blurb")
    assert p.key == "generic", p.key
    # Loose short markers must not fire inside other words: 'MPS' in "samples"
    # / "amps" once broke this (BMI270 mis-detected as MPS).
    p, _, _ = vendors.detect_vendor("BMI270", "1600 samples per second, 20 mAmps")
    assert p.key == "generic", p.key
    # The override hook is part of the base contract (advertised, default None).
    assert hasattr(vendors.VendorProfile(), "spec_rows_override")
    assert vendors.VendorProfile().spec_rows_override(None) is None


def test_generic_bordered_specs():
    """Generic pdfplumber path reads a ruled EC table: values land in the right
    MIN/TYP/MAX column, sections are tracked, confidence is earned."""
    if not _have_deps():
        print("  (skipped: pymupdf/pdfplumber not installed)"); return
    from s2p_tool.analysis import analyze
    d = tempfile.mkdtemp(); pdf = os.path.join(d, "acme.pdf")
    _make_bordered_ec_pdf(pdf)
    res = analyze(pdf)
    assert res["vendor"]["key"] == "generic", res["vendor"]
    spec = res["sections"]["specs"]
    assert spec["confidence"] in ("high", "med"), spec["reason"]
    rows = {r["symbol"]: r for r in spec["data"] if r.get("symbol")}
    vin = rows.get("VIN")
    assert vin and vin["min"] == "2.7" and vin["typ"] == "3.3" \
        and vin["max"] == "5.5" and vin["unit"] == "V", vin
    # section header row became a section label, not a data row
    assert any(r.get("section") == "SUPPLY" for r in spec["data"]), \
        [r.get("section") for r in spec["data"]]
    # thermal-resistance row dropped -> no MIN>MAX issue, stays high
    assert not any(r.get("symbol") == "RthJA" for r in spec["data"]), \
        "thermal row not filtered"
    assert spec["confidence"] == "high", spec["reason"]


def test_ti_word_geometry_override():
    """TI layout routes to the word-geometry override: subscript-wrapped symbols
    rejoin, values bin correctly, and en-dash negatives parse."""
    if not _have_deps():
        print("  (skipped: pymupdf/pdfplumber not installed)"); return
    from s2p_tool.analysis import analyze
    d = tempfile.mkdtemp(); pdf = os.path.join(d, "tps.pdf")
    _make_ti_ec_pdf(pdf)
    res = analyze(pdf)
    assert res["vendor"]["key"] == "ti", res["vendor"]
    spec = res["sections"]["specs"]
    assert spec["confidence"] != "none", spec["reason"]
    rows = spec["data"]
    # value binning: the VIN row has min/typ/max in the right slots
    vin = next((r for r in rows if "VIN" in r["parameter"]), None)
    assert vin, [r["parameter"] for r in rows]
    assert (vin["min"], vin["typ"], vin["max"]) == ("2.7", "3.3", "5.5"), vin
    # subscript rejoin worked ('V' + 'IN' -> 'VIN', not 'V IN')
    assert "V IN" not in vin["parameter"], vin["parameter"]
    # negative recovered into MIN
    jt = next((r for r in rows if "Junction" in r["parameter"]), None)
    assert jt and jt["min"] == "-40", jt
    # dash normalization (en-dash / minus-sign -> value) is font-independent:
    from s2p_tool.analysis.sections.specs import _num
    assert _num("–40") == -40.0 and _num("−2") == -2.0, "dash normalize"
    # section header captured
    assert any(r.get("section") == "SUPPLY" for r in rows), \
        [r.get("section") for r in rows]


def test_pinout_two_row_header():
    """A merged two-row Pin Functions header folds into correct column roles;
    pins parse with name/number/io/description and multi-pin numbers survive."""
    if not _have_deps():
        print("  (skipped: pymupdf/pdfplumber not installed)"); return
    from s2p_tool.analysis import analyze
    d = tempfile.mkdtemp(); pdf = os.path.join(d, "pins.pdf")
    _make_pinout_pdf(pdf)
    res = analyze(pdf)
    pin = res["sections"]["pinout"]
    assert pin["confidence"] == "high", pin["reason"]
    by = {p["name"]: p for p in pin["data"]}
    assert by["VIN"]["number"] == "1" and by["VIN"]["io"] == "PWR", by.get("VIN")
    assert by["VIN"]["description"] == "supply input", by["VIN"]
    assert by["SW"]["number"] == "4, 5", by.get("SW")   # multi-pin preserved
    joined = " ".join(pin["interpretation"])
    assert "VIN" in joined and "GND" in joined, pin["interpretation"]


def test_curves_design_layout_sections():
    """Component detection + the migrated Curves/Design/Layout sections work
    end-to-end through analyze(): regulator detected, all three report high."""
    if not _have_deps():
        print("  (skipped: pymupdf/pdfplumber not installed)"); return
    from s2p_tool.analysis import analyze
    d = tempfile.mkdtemp(); pdf = os.path.join(d, "reg_doc.pdf")
    _make_regulator_doc_pdf(pdf)
    res = analyze(pdf)
    assert res["component"]["key"] == "regulator", res["component"]
    sec = res["sections"]
    # Design: requirements + at least one procedure step.
    dsn = sec["design"]
    assert dsn["confidence"] in ("high", "med"), dsn["reason"]
    assert dsn["data"]["requirements"], dsn
    # Layout: guideline checklist.
    assert sec["layout"]["confidence"] == "high", sec["layout"]["reason"]
    # Curves: the Vref plot digitized at high confidence + interpreted.
    cur = sec["curves"]
    assert "vref_vs_temp" in (cur["data"] or {}), cur["reason"]
    assert cur["confidence"] == "high", cur["reason"]
    assert any("Vref" in s or "kararl" in s for s in cur["interpretation"]), \
        cur["interpretation"]


def test_no_text_layer_is_rejected():
    """An outlined/scanned PDF is reported none with a stated reason — never
    mis-parsed into fake specs."""
    if not _have_deps():
        print("  (skipped: pymupdf/pdfplumber not installed)"); return
    from s2p_tool.analysis import analyze
    d = tempfile.mkdtemp(); pdf = os.path.join(d, "scan.pdf")
    _make_no_text_pdf(pdf)
    res = analyze(pdf)
    assert res["is_text_pdf"] is False, res["is_text_pdf"]
    spec = res["sections"]["specs"]
    assert spec["confidence"] == "none", spec
    assert "no-text-layer" in spec["issues"], spec["issues"]


def test_section_failure_is_isolated():
    """A section that raises comes back none+issue without sinking the run."""
    from s2p_tool.analysis.sections.base import Section

    class Boom(Section):
        key, label = "boom", "Patlar"

        def extract(self, ctx, res):
            raise ValueError("deliberate")

    r = Boom().run(ctx=None)          # ctx unused before the raise
    assert r.confidence == "none", r.confidence
    assert r.issues and "deliberate" in r.reason, (r.reason, r.issues)


if __name__ == "__main__":
    test_vendor_detection_by_part_and_marker()
    test_generic_bordered_specs()
    test_ti_word_geometry_override()
    test_pinout_two_row_header()
    test_curves_design_layout_sections()
    test_no_text_layer_is_rejected()
    test_section_failure_is_isolated()
    print("OK - all analysis-section backbone tests passed")
