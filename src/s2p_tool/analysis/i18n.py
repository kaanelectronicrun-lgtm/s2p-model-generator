"""Report/plot localization — Turkish (default) and English.

Two layers:
 * ``STRINGS`` — structural UI text (section headings, notes, column headers)
   keyed by a stable id, per language.
 * ``LABELS`` — a canonical-Turkish -> English map for the fixed data labels the
   extractors emit (spec highlights, design requirements, procedure steps, curve
   descriptions/units, topology). Extractors keep producing one canonical form;
   the renderer localizes at display time via :func:`label`.

Datasheet-sourced prose (pin descriptions, features, layout guidelines) is NOT
here — that is handled by the machine-translation layer (``translate``) or left
in the source language.
"""
from __future__ import annotations

from typing import Dict

STRINGS: Dict[str, Dict[str, str]] = {
    "tr": {
        "title": "Datasheet Analizi",
        "type": "Tür",
        "subtype": "Alt tür",
        "vendor": "Üretici",
        "vendor_score": "tespit skoru",
        "source": "Kaynak",
        "sec_summary": "Bölüm Güven Özeti",
        "col_section": "Bölüm", "col_conf": "Güven", "col_reason": "Gerekçe",
        "description": "Açıklama",
        "pinout_h": "Pinout (Pin Fonksiyonları)",
        "col_pin": "Pin", "col_no": "No", "col_io": "I/O", "col_desc": "Açıklama",
        "pinout_img_cap": "Pinout (görsel tablo):",
        "pinout_img_note": ("{n} pinin işlev ve yön (I/O) özeti: besleme, toprak "
                            "ve kontrol pinleri tek bakışta."),
        "specs_h": "Elektriksel Özellikler — Öne Çıkanlar",
        "col_param": "Parametre", "col_value": "Değer",
        "specs_none": "Metinden yapısal spec çıkarılamadı.",
        "spectable_h": ("Elektriksel Özellikler — Tam Tablo "
                        "({n} satır, güven: {conf})"),
        "spectable_cols": ("Bölüm | Parametre | Sembol | Koşullar | Min | Typ | "
                           "Max | Birim"),
        "spec_ranges_cap": "MIN–TYP–MAX aralık grafiği (parametre başına normalize):",
        "spec_ranges_note": ("Her parametrenin kendi MIN–MAX aralığı 0–1'e "
                             "normalize; ● tipik (TYP) değeri işaretler. Dar bar "
                             "= sıkı tolerans."),
        "features_h": "Özellikler (Features)",
        "schematic_h": "Şematik / Uygulama Devresi (datasheet figürleri)",
        "page_abbr": "s.",
        "curves_h": "Çıkarılan Karakteristik Eğriler",
        "curves_cols": "Eğri | Güven | İz | Nokta | X | Y | CSV",
        "curves_replot_cap": ("Yeniden çizilen eğriler (dijitalize noktalardan) "
                              "+ kısa yorum:"),
        "curves_warn": ("> ⚠️ 'düşük' güvenli eğriler kalibrasyon/çoklu-iz "
                        "nedeniyle güvenilmez; doğrulanmadan kullanmayın."),
        "curves_none_h": "Karakteristik Eğriler",
        "curves_none": "Vektör grafikten güvenilir eğri çıkarılamadı.",
        "interp_h": "Grafik Yorumu",
        "req_h": "Tasarım Gereksinimleri (datasheet örnek tasarımı)",
        "proc_h": "Tasarım Hesapları (Detailed Design Procedure)",
        "proc_note": ("> Denklemlerin birebir glyph'i PDF metninden güvenilir "
                      "çıkmaz; her adımın amacı + değişken/sabit sözlüğü aşağıda."),
        "layout_h": "Layout Önerileri (datasheet §Layout Guidelines)",
        "layout_note": ("> Not: Gerçek şematik/PCB *üretimi* bu aracın kapsamı "
                        "dışı — `kicad`/`eda-agent` skill'leri ile yapılır."),
        "layout_img_h": "Layout Görselleri (datasheet figürleri)",
        "pinout_title": "Pinout — {part} ({n} pin)",
        "spec_ranges_title": "Spec MIN–TYP(●)–MAX (parametre başına normalize)",
        "fig_block": ("IC'nin iç blok yapısı: güç zinciri, kontrol/geri-besleme "
                      "ve koruma blokları ile aralarındaki bağlantılar."),
        "fig_layout": ("Önerilen PCB yerleşimi: bileşen konumları, toprak/güç "
                       "bakırı ve kritik yolların referans düzeni."),
        "fig_schematic": ("Tipik uygulama devresi: harici bileşen değerleri ve "
                          "bağlantılar — referans tasarım olarak kullanılabilir."),
        "fig_generic": "Datasheet'ten çıkarılan figür.",
        "badge_high": "✅ yüksek", "badge_med": "🟡 orta",
        "badge_low": "⚠️ düşük", "badge_none": "— yok",
        "curve_low_suffix": " (düşük güven)",
        "curve_low_watermark": "DÜŞÜK GÜVEN",
    },
    "en": {
        "title": "Datasheet Analysis",
        "type": "Type",
        "subtype": "Sub-type",
        "vendor": "Manufacturer",
        "vendor_score": "detection score",
        "source": "Source",
        "sec_summary": "Section Confidence Summary",
        "col_section": "Section", "col_conf": "Confidence", "col_reason": "Reason",
        "description": "Description",
        "pinout_h": "Pinout (Pin Functions)",
        "col_pin": "Pin", "col_no": "No", "col_io": "I/O", "col_desc": "Description",
        "pinout_img_cap": "Pinout (visual table):",
        "pinout_img_note": ("{n}-pin function and direction (I/O) summary: supply, "
                            "ground and control pins at a glance."),
        "specs_h": "Electrical Specs — Highlights",
        "col_param": "Parameter", "col_value": "Value",
        "specs_none": "No structured specs could be extracted from the text.",
        "spectable_h": ("Electrical Specs — Full Table "
                        "({n} rows, confidence: {conf})"),
        "spectable_cols": ("Section | Parameter | Symbol | Conditions | Min | Typ "
                           "| Max | Unit"),
        "spec_ranges_cap": "MIN–TYP–MAX range chart (normalized per parameter):",
        "spec_ranges_note": ("Each parameter's own MIN–MAX range is normalized to "
                             "0–1; ● marks the typical (TYP) value. Narrow bar = "
                             "tight tolerance."),
        "features_h": "Features",
        "schematic_h": "Schematic / Application Circuit (datasheet figures)",
        "page_abbr": "p.",
        "curves_h": "Extracted Characteristic Curves",
        "curves_cols": "Curve | Conf. | Traces | Points | X | Y | CSV",
        "curves_replot_cap": ("Re-plotted curves (from digitized points) + short "
                              "notes:"),
        "curves_warn": ("> ⚠️ 'low'-confidence curves are unreliable due to "
                        "calibration/multi-trace issues; verify before use."),
        "curves_none_h": "Characteristic Curves",
        "curves_none": "No reliable curve could be extracted from vector graphics.",
        "interp_h": "Graph Interpretation",
        "req_h": "Design Requirements (datasheet example design)",
        "proc_h": "Design Calculations (Detailed Design Procedure)",
        "proc_note": ("> Exact equation glyphs don't survive PDF text extraction "
                      "reliably; each step's intent + variable/constant glossary "
                      "is below."),
        "layout_h": "Layout Recommendations (datasheet §Layout Guidelines)",
        "layout_note": ("> Note: actual schematic/PCB *generation* is out of scope "
                        "for this tool — use the `kicad`/`eda-agent` skills."),
        "layout_img_h": "Layout Images (datasheet figures)",
        "pinout_title": "Pinout — {part} ({n} pins)",
        "spec_ranges_title": "Spec MIN–TYP(●)–MAX (normalized per parameter)",
        "fig_block": ("Internal block structure of the IC: power chain, "
                      "control/feedback and protection blocks and their links."),
        "fig_layout": ("Recommended PCB layout: component placement, ground/power "
                       "copper and reference routing of critical traces."),
        "fig_schematic": ("Typical application circuit: external component values "
                          "and connections — usable as a reference design."),
        "fig_generic": "Figure extracted from the datasheet.",
        "badge_high": "✅ high", "badge_med": "🟡 med",
        "badge_low": "⚠️ low", "badge_none": "— none",
        "curve_low_suffix": " (low confidence)",
        "curve_low_watermark": "LOW CONFIDENCE",
    },
}

# Canonical Turkish label -> English. Extractors emit the Turkish form; the
# renderer localizes for display.
LABELS: Dict[str, str] = {
    # spec highlights
    "Giriş gerilimi (VIN)": "Input voltage (VIN)",
    "Çıkış gerilimi (VOUT)": "Output voltage (VOUT)",
    "Anahtar akım kapasitesi": "Switch current capability",
    "Anahtarlama frekansı": "Switching frequency",
    "Tepe verim": "Peak efficiency",
    "Kapalı-durum akımı (shutdown)": "Shutdown current",
    "Aşırı gerilim koruma (OVP)": "Overvoltage protection (OVP)",
    "Anahtar direnci RDS(on)": "Switch resistance RDS(on)",
    "Paket": "Package",
    "Topoloji": "Topology",
    # topology values
    "Senkron boost": "Synchronous boost",
    "Senkron buck": "Synchronous buck",
    "Buck-boost": "Buck-boost",
    "Constant off-time peak-current kontrol": "Constant off-time peak-current control",
    "LDO (lineer)": "LDO (linear)",
    # design requirements
    "Giriş gerilimi aralığı": "Input voltage range",
    "Çıkış gerilimi": "Output voltage",
    "Çıkış ripple": "Output ripple",
    "Çıkış akımı": "Output current",
    "Çalışma frekansı": "Operating frequency",
    "Hafif-yük modu": "Light-load mode",
    # design-procedure step labels
    "Anahtarlama frekansı ayarı (RFSW)": "Switching frequency setting (RFSW)",
    "Tepe akım limiti ayarı (RILIM)": "Peak current limit setting (RILIM)",
    "İndüktör seçimi": "Inductor selection",
    "Çıkış kapasitörü seçimi": "Output capacitor selection",
    "Giriş kapasitörü seçimi": "Input capacitor selection",
    "Soft-start ayarı": "Soft-start setting",
    "Geri-besleme / çıkış gerilimi ayarı": "Feedback / output voltage setting",
    # curve descriptions
    "Verim eğrisi": "Efficiency curve",
    "Akım limiti vs ayar direnci": "Current limit vs setting resistance",
    "Anahtarlama frekansı vs ayar direnci": "Switching frequency vs setting resistance",
    "Referans gerilimi vs sıcaklık": "Reference voltage vs temperature",
    "Sükunet akımı vs sıcaklık": "Quiescent current vs temperature",
    "Kapalı-durum akımı vs sıcaklık": "Shutdown current vs temperature",
    # curve units
    "Sıcaklık (°C)": "Temperature (°C)",
    "Açık-çevrim kazanç/faz vs frekans": "Open-loop gain/phase vs frequency",
    "Çıkış gerilim salınımı vs çıkış akımı": "Output voltage swing vs output current",
    "Giriş bias akımı vs sıcaklık": "Input bias current vs temperature",
    "Çıkış akımı (mA)": "Output current (mA)",
    "Frekans (Hz)": "Frequency (Hz)",
    "Kazanç (dB)": "Gain (dB)",
    "Gürültü (nV/√Hz)": "Noise (nV/√Hz)",
    "Besleme (V)": "Supply (V)",
    # component type labels
    "Regülatör / DC-DC": "Regulator / DC-DC",
    "Op-Amp / Operasyonel Yükselteç": "Op-Amp / Operational Amplifier",
    "Diyot": "Diode",
    "Direnç (pasif)": "Resistor (passive)",
    # op-amp sub-types
    "Genel amaçlı": "General-purpose",
    "Sıfır-sürüklenme (zero-drift / chopper)": "Zero-drift (chopper)",
    "JFET / FET-girişli": "JFET / FET-input",
    "Yüksek hızlı (high-speed)": "High-speed",
    "Rail-to-rail (CMOS)": "Rail-to-rail (CMOS)",
    "Hassas (precision)": "Precision",
    "Düşük güç / mikrogüç": "Low-power / micropower",
    # diode sub-types
    "TVS / geçici gerilim bastırıcı": "TVS / transient voltage suppressor",
    "Zener (gerilim referans/regülasyon)": "Zener (voltage reference/regulation)",
    "Schottky (düşük VF / hızlı)": "Schottky (low VF / fast)",
    "LED / ışık yayan": "LED / light-emitting",
    "Hızlı/ultra-hızlı doğrultucu": "Fast/ultrafast rectifier",
    "Doğrultucu (standart)": "Rectifier (standard)",
    "Küçük-sinyal / anahtarlama": "Small-signal / switching",
    "Genel amaçlı diyot": "General-purpose diode",
    # resistor sub-types
    "Akım-algılama / shunt": "Current-sense / shunt",
    "İnce film (thin-film)": "Thin-film",
    "Kalın film (thick-film)": "Thick-film",
    "Tel sarımlı (wirewound)": "Wirewound",
    "Genel amaçlı direnç": "General-purpose resistor",
    # op-amp spec highlights
    "Besleme gerilimi aralığı": "Supply voltage range",
    "Kazanç-bant genişliği (GBW)": "Gain-bandwidth (GBW)",
    "Yükselme hızı (slew rate)": "Slew rate",
    "Giriş ofset gerilimi": "Input offset voltage",
    "Sükunet akımı (kanal başına)": "Quiescent current (per channel)",
    "Giriş bias akımı": "Input bias current",
    "Giriş gerilim gürültüsü": "Input voltage noise",
    "Kanal sayısı": "Channel count",
    # op-amp curve descriptions
    "Açık-çevrim kazanç vs frekans": "Open-loop gain vs frequency",
    "CMRR vs frekans": "CMRR vs frequency",
    "PSRR vs frekans": "PSRR vs frequency",
    "Giriş ofset gerilimi vs sıcaklık": "Input offset voltage vs temperature",
    "Giriş gerilim gürültüsü vs frekans": "Input voltage noise vs frequency",
    "Sükunet akımı vs besleme": "Quiescent current vs supply",
}


def norm(lang: str) -> str:
    """Normalize a language code to 'tr' or 'en' (default 'tr')."""
    l = (lang or "tr").lower()
    return "en" if l.startswith("en") else "tr"


def t(lang: str, key: str, **kw) -> str:
    """Structural string for ``key`` in ``lang`` (falls back to Turkish/key)."""
    d = STRINGS.get(norm(lang), STRINGS["tr"])
    s = d.get(key) or STRINGS["tr"].get(key) or key
    return s.format(**kw) if kw else s


def label(lang: str, s: str) -> str:
    """Localize a canonical (Turkish) data label; passthrough when English has no
    mapping or the language is Turkish."""
    if norm(lang) == "en" and s in LABELS:
        return LABELS[s]
    return s


def badge(lang: str, conf: str) -> str:
    return t(lang, f"badge_{conf}") if conf in ("high", "med", "low", "none") else conf
