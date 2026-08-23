"""Validate the new Section pipeline (vendor detect + SpecSection) on real
datasheets across vendors. Run: py -3.12 scripts/probe_sections.py"""
import sys
sys.path.insert(0, "src")

from s2p_tool.analysis import analyze

PDFS = {
    "TI TPS61088": r"C:\Users\Excalibur\Desktop\OBS_KAAN\Kaan AKCAN\Projeler\Wearable BLE fitness tracker system architecture\Altium Proje Dosyaları\Qi_RX_Engineering_Package_RevA_v0.3_LCSC_TUNE\tps61088.pdf",
    "TI TPS62743": r"C:\Users\Excalibur\Desktop\OBS_KAAN\Kaan AKCAN\Projeler\Wearable BLE fitness tracker system architecture\Component_Files\Datasheets\TPS62743YFPR.pdf",
    "onsemi NCP164": r"C:\Users\Excalibur\Desktop\OBS_KAAN\Kaan AKCAN\Projeler\Wearable BLE fitness tracker system architecture\Component_Files\Datasheets\NCP164PST33T2.pdf",
    "ADI LTC3780": r"C:\Users\Excalibur\Desktop\OBS_KAAN\Kaan AKCAN\Projeler\Wearable BLE fitness tracker system architecture\real_kicad_reference\LTC3780\LTC3780.pdf",
}

L = []
for name, path in PDFS.items():
    L.append("=" * 74)
    L.append(name)
    L.append("=" * 74)
    try:
        res = analyze(path)
    except Exception as e:
        L.append(f"  HATA: {type(e).__name__}: {e}")
        L.append("")
        continue
    v = res["vendor"]
    L.append(f"  part={res['part']}  vendor={v['key']} ({v['label']}) "
             f"score={v['score']} [{v['reason']}]  text_pdf={res['is_text_pdf']}")
    spec = res["sections"]["specs"]
    L.append(f"  SPEC: confidence={spec['confidence']} — {spec['reason']}")
    L.append(f"        evidence_pages={[e['page'] for e in spec['evidence']]}")
    if spec["issues"]:
        L.append(f"        issues({len(spec['issues'])}): {spec['issues'][:4]}")
    for f in spec["interpretation"]:
        L.append(f"        » {f}")
    rows = spec["data"] or []
    L.append(f"        --- ilk 10 satır / {len(rows)} ---")
    for r in rows[:10]:
        L.append("        {sec:<14} | {sym:<8} | {p:<28} | "
                 "{mn:>6} | {ty:>6} | {mx:>6} | {u}".format(
                     sec=(r.get("section") or "")[:14],
                     sym=(r.get("symbol") or "")[:8],
                     p=(r.get("parameter") or "")[:28],
                     mn=r.get("min") or "", ty=r.get("typ") or "",
                     mx=r.get("max") or "", u=r.get("unit") or ""))
    L.append("")

out = "\n".join(L)
with open("scripts/probe_sections_out.txt", "w", encoding="utf-8") as fh:
    fh.write(out)
print("wrote scripts/probe_sections_out.txt (%d lines)" % len(L))
