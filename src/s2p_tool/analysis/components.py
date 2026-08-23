"""Component-family profiles — the type-specific config for curve targets,
design-procedure headings and curve interpretation.

Parallel to ``vendors`` (which captures *manufacturer* layout quirks), a
``ComponentProfile`` captures what a *component family* means: which
characteristic curves to look for, how to read them, and which design-procedure
sections exist. The clean sections (Curves/Design) stay generic and pull their
type-specific behaviour from the detected profile. First family: regulator/DC-DC.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from . import text_extract
from . import i18n


def _unit_of(label: Optional[str], default: str = "") -> str:
    """The unit token inside an axis label like 'Iq (µA)' → 'µA'. Falls back to
    ``default`` so a curve whose unit was relabeled off the datasheet axis is
    narrated in that real unit instead of a hardcoded guess."""
    m = re.search(r"\(([^()]*)\)", label or "")
    return m.group(1).strip() if m else default


class ComponentProfile:
    key: str = "component"
    label: str = "Komponent"
    keywords: Tuple[str, ...] = ()
    # (key, caption_regex, unit_x, unit_y, desc)
    curve_targets: Tuple[Tuple[str, str, str, str, str], ...] = ()
    proc_heads: Tuple[Tuple[str, str], ...] = text_extract.PROC_HEADS
    # Figure captions to pull out as images (schematic + layout example).
    schematic_captions: Tuple[str, ...] = (
        r"typical application", r"simplified schematic", r"application schematic",
        r"application circuit", r"functional block diagram", r"output converter",
        r"reference design")
    layout_captions: Tuple[str, ...] = (
        r"layout example", r"board layout", r"example layout",
        r"recommended layout", r"pcb layout", r"component placement",
        r"\blayout\b", r"top layer", r"bottom layer", r"copper layer")

    def matches(self, text: str) -> float:
        low = text.lower()
        return float(sum(low.count(k) for k in self.keywords))

    def _iter_high(self, curves: Dict):
        """Yield (key, curve) for each high-confidence curve only."""
        for key, c in curves.items():
            if key == "_log" or not isinstance(c, dict):
                continue
            if c.get("confidence") != "high":
                continue
            yield key, c

    def _curve_sentence(self, key: str, c: Dict, lang: str = "tr") -> Optional[str]:
        """One plain-language finding for a single high-confidence curve, or
        None. Base: a generic y/x-range summary; families override for
        domain-specific phrasing."""
        pts = c.get("curve") or []
        if not pts:
            return None
        ys = [p[1] for p in pts]
        xs = [p[0] for p in pts]
        desc = i18n.label(lang, c.get("desc", key))
        ux = i18n.label(lang, c.get("unit_x", ""))
        uy = i18n.label(lang, c.get("unit_y", ""))
        return (f"{desc}: {min(ys):.3g}…{max(ys):.3g} {uy} "
                f"({min(xs):.3g}…{max(xs):.3g} {ux}).")

    def interpret_curves(self, curves: Dict, lang: str = "tr") -> List[str]:
        """Plain-language findings from high-confidence curves (report section)."""
        out: List[str] = []
        for key, c in self._iter_high(curves):
            s = self._curve_sentence(key, c, lang)
            if s:
                out.append(s)
        return out

    def curve_captions(self, curves: Dict, lang: str = "tr") -> Dict[str, str]:
        """Short per-curve explanation keyed by curve key, for placing directly
        next to the rendered graph."""
        caps: Dict[str, str] = {}
        for key, c in self._iter_high(curves):
            s = self._curve_sentence(key, c, lang)
            if s:
                caps[key] = s
        return caps


class RegulatorProfile(ComponentProfile):
    key = "regulator"
    label = "Regülatör / DC-DC"
    keywords = (
        "boost converter", "buck converter", "buck-boost", "step-up",
        "step-down", "switching converter", "dc-dc", "dc/dc", "regulator",
        "ldo", "low-dropout", "pmic", "synchronous", "converter",
        "voltage regulator", "current limit", "switching frequency",
    )
    curve_targets = (
        ("efficiency", r"efficiency", "Output Current (A)",
         "Efficiency (%)", "Verim eğrisi"),
        # Require the resistor context: this curve is current-limit *vs setting
        # resistance*. A bare "Current Limit Threshold" plot (e.g. LM317, x-axis
        # is not a resistor) must not match, or it is digitized and narrated as
        # "vs setting resistor" with a nonsense kΩ x-axis.
        ("current_limit_vs_r", r"current limit.*resist", "R_SET (kΩ)",
         "Current Limit (A)", "Akım limiti vs ayar direnci"),
        ("fsw_vs_r", r"switching frequency|frequency vs", "R_SET (kΩ)",
         "fSW (kHz)", "Anahtarlama frekansı vs ayar direnci"),
        ("vref_vs_temp", r"reference voltage|voltage reference", "Sıcaklık (°C)",
         "Vref (V)", "Referans gerilimi vs sıcaklık"),
        ("iq_vs_temp", r"quiescent current", "Sıcaklık (°C)",
         "Iq (µA)", "Sükunet akımı vs sıcaklık"),
        ("ishutdown_vs_temp", r"shutdown current", "Sıcaklık (°C)",
         "I_SD (µA)", "Kapalı-durum akımı vs sıcaklık"),
    )

    @staticmethod
    def _interp(x, xs, ys):
        for i in range(1, len(xs)):
            if xs[i - 1] <= x <= xs[i] or xs[i] <= x <= xs[i - 1]:
                x0, x1, y0, y1 = xs[i - 1], xs[i], ys[i - 1], ys[i]
                if x1 == x0:
                    return y0
                return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
        return None

    def _curve_sentence(self, key: str, c: Dict, lang: str = "tr") -> Optional[str]:
        en = i18n.norm(lang) == "en"
        desc = i18n.label(lang, c.get("desc", key))
        # Axis labels are "Quantity (unit)"; the sentence already names the
        # quantity via ``desc``, so carry only the unit token to avoid "…581 Iq
        # (µA)" duplication. Bare-unit labels (no parens) pass through unchanged.
        _uy = i18n.label(lang, c.get("unit_y", ""))
        _ux = i18n.label(lang, c.get("unit_x", ""))
        uy = _unit_of(_uy, _uy)
        ux = _unit_of(_ux, _ux)
        traces = c.get("traces")
        if traces:
            segs = []
            for tr in traces:
                tys = [p[1] for p in tr["curve"]]
                segs.append(f"{tr['label']}: {min(tys):.3g}…{max(tys):.3g}")
            if en:
                return (f"{desc}: {len(traces)} traces separated by colour "
                        f"({uy}) — " + "; ".join(segs)
                        + ". Each trace in its own CSV column.")
            return (f"{desc}: {len(traces)} iz renk bazlı ayrıştırıldı "
                    f"({uy}) — " + "; ".join(segs)
                    + ". Her iz ayrı CSV sütununda.")
        pts = c.get("curve") or []
        if not pts:
            return None
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        lo, hi = min(xs), max(xs)
        ylo, yhi = min(ys), max(ys)
        mid = sorted(ys)[len(ys) // 2]
        if key == "vref_vs_temp":
            drift = (yhi - ylo) * 1000.0
            if en:
                return (f"Vref ≈ {mid:.3f} V; total drift ~{drift:.1f} mV over "
                        f"{lo:.0f}…{hi:.0f} °C → very stable reference.")
            return (f"Vref ≈ {mid:.3f} V; {lo:.0f}…{hi:.0f} °C aralığında toplam "
                    f"sapma ~{drift:.1f} mV → referans çok kararlı.")
        if key == "iq_vs_temp":
            if en:
                trend = "rises" if ys[-1] > ys[0] else "falls"
                return (f"Quiescent current Iq {ylo:.0f}…{yhi:.0f} µA; {trend} "
                        f"with temperature ({lo:.0f}→{hi:.0f} °C).")
            trend = "artıyor" if ys[-1] > ys[0] else "azalıyor"
            return (f"Sükunet akımı Iq {ylo:.0f}…{yhi:.0f} µA; sıcaklıkla {trend} "
                    f"({lo:.0f}→{hi:.0f} °C).")
        if key == "ishutdown_vs_temp":
            if en:
                return f"Shutdown current in the {ylo:.2g}…{yhi:.2g} µA range."
            return f"Kapalı-durum akımı {ylo:.2g}…{yhi:.2g} µA aralığında."
        if key == "current_limit_vs_r":
            paired = sorted(zip(xs, ys))
            sx = [p[0] for p in paired]; sy = [p[1] for p in paired]
            samples = []
            for rq in (100, 250, 360):
                iv = self._interp(rq, sx, sy)
                if iv is not None:
                    samples.append(f"R={rq}kΩ→{iv:.1f}A")
            if en:
                trend = "falls" if sy[-1] < sy[0] else "rises"
                s = (f"Current limit {trend} with the setting resistor "
                     f"({sx[0]:.0f}→{sx[-1]:.0f} kΩ, {sy[0]:.1f}→{sy[-1]:.1f} A).")
                if samples:
                    s += " From the curve: " + ", ".join(samples) + "."
                return s
            trend = "azalıyor" if sy[-1] < sy[0] else "artıyor"
            s = (f"Akım limiti ayar direnciyle {trend} "
                 f"({sx[0]:.0f}→{sx[-1]:.0f} kΩ, {sy[0]:.1f}→{sy[-1]:.1f} A).")
            if samples:
                s += " Eğriden: " + ", ".join(samples) + "."
            return s
        if key == "fsw_vs_r":
            if en:
                return (f"Switching frequency varies with the setting resistor "
                        f"({lo:.0f}→{hi:.0f} kΩ, {ylo:.0f}→{yhi:.0f}).")
            return (f"Anahtarlama frekansı ayar direnciyle değişiyor "
                    f"({lo:.0f}→{hi:.0f} kΩ, {ylo:.0f}→{yhi:.0f}).")
        return (f"{desc}: {ylo:.3g}…{yhi:.3g} {uy} "
                f"({lo:.3g}…{hi:.3g} {ux}).")


class OpAmpProfile(ComponentProfile):
    key = "opamp"
    label = "Op-Amp / Operasyonel Yükselteç"
    keywords = (
        "operational amplifier", "op amp", "op-amp", "opamp",
        "slew rate", "gain bandwidth", "gain-bandwidth", "unity-gain",
        "unity gain", "input offset voltage", "common-mode rejection",
        "cmrr", "psrr", "rail-to-rail", "input bias current",
        "quiescent current per amplifier", "gbw",
    )
    # Op-amp sub-families, most-specific first (first hit wins). The input stage
    # / trim technique defines the sub-type an engineer cares about; keywords are
    # the phrases datasheets use in their headline features. Anything that hits
    # none is a plain general-purpose part (LM324/LM358).
    subtypes = (
        ("zero_drift", "Sıfır-sürüklenme (zero-drift / chopper)",
         (r"zero[- ]?drift", r"auto[- ]?zero", r"auto[- ]?calibrat",
          r"chopper[- ]stabili", r"\bchopper\b")),
        ("jfet", "JFET / FET-girişli",
         (r"\bj-?fet\b", r"fet[- ]?input", r"bi-?fet")),
        ("high_speed", "Yüksek hızlı (high-speed)",
         (r"high[- ]speed", r"wideband", r"video amplifier",
          r"[3-9]\d{2}\s*mhz|\d+\s*ghz")),
        ("rail_to_rail", "Rail-to-rail (CMOS)",
         (r"rail[- ]to[- ]rail", r"\brrio\b", r"\brro\b")),
        # "precision" only on a strong signal: the word itself, or a µV-class
        # offset. A mV-class "low offset" feature is just a decent general-
        # purpose part (LM324/LM358), not a precision op-amp.
        ("precision", "Hassas (precision)",
         (r"\bprecision\b", r"ultra-?low\s+offset",
          r"offset voltage[^.\n]{0,30}\b\d+\s*[µuμ]v")),
        ("low_power", "Düşük güç / mikrogüç",
         (r"micropower", r"nanopower", r"low[- ]?power", r"micro[- ]power")),
    )

    def detect_subtype(self, text: str):
        """(key, label) of the op-amp sub-family from headline datasheet wording,
        or ('general', …) when nothing specific matches. Confined to the first
        pages by the caller so body mentions don't sway it."""
        low = (text or "").lower()
        for key, label, pats in self.subtypes:
            if any(re.search(p, low) for p in pats):
                return key, label
        return "general", "Genel amaçlı"
    curve_targets = (
        ("aol_phase", r"open.?loop gain", "Frekans (Hz)", "Kazanç (dB)",
         "Açık-çevrim kazanç/faz vs frekans"),
        ("cmrr", r"\bCMRR\b|common.?mode rejection", "Frekans (Hz)",
         "CMRR (dB)", "CMRR vs frekans"),
        ("psrr", r"\bPSRR\b|power.?supply rejection", "Frekans (Hz)",
         "PSRR (dB)", "PSRR vs frekans"),
        ("vos_temp", r"offset voltage vs temperature", "Sıcaklık (°C)",
         "Vos (µV)", "Giriş ofset gerilimi vs sıcaklık"),
        ("vnoise", r"voltage noise", "Frekans (Hz)", "Gürültü (nV/√Hz)",
         "Giriş gerilim gürültüsü vs frekans"),
        ("iq_temp", r"quiescent current vs temperature", "Sıcaklık (°C)",
         "Iq (mA)", "Sükunet akımı vs sıcaklık"),
        ("iq_supply", r"quiescent current vs supply", "Besleme (V)", "Iq (mA)",
         "Sükunet akımı vs besleme"),
        ("vout_iout", r"output voltage swing vs output current",
         "Çıkış akımı (mA)", "Vout (V)", "Çıkış gerilim salınımı vs çıkış akımı"),
        ("ib_temp", r"input bias current vs temperature", "Sıcaklık (°C)",
         "Ib (nA)", "Giriş bias akımı vs sıcaklık"),
    )

    def _curve_sentence(self, key: str, c: Dict, lang: str = "tr") -> Optional[str]:
        if c.get("traces"):
            return super()._curve_sentence(key, c, lang)
        en = i18n.norm(lang) == "en"
        pts = c.get("curve") or []
        if not pts:
            return None
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        lo, hi = min(xs), max(xs)
        ylo, yhi = min(ys), max(ys)
        if key == "aol_phase":
            return (f"Open-loop gain ~{yhi:.0f} dB at DC, rolling off with "
                    f"frequency toward ~{ylo:.0f} dB." if en else
                    f"Açık-çevrim kazanç DC'de ~{yhi:.0f} dB; frekansla düşerek "
                    f"~{ylo:.0f} dB'ye iniyor.")
        if key in ("cmrr", "psrr"):
            nm = key.upper()
            return (f"{nm} highest at low frequency (~{yhi:.0f} dB), falling to "
                    f"~{ylo:.0f} dB at high frequency." if en else
                    f"{nm} düşük frekansta en yüksek (~{yhi:.0f} dB), yüksek "
                    f"frekansa doğru ~{ylo:.0f} dB'ye düşüyor.")
        if key == "vnoise":
            return (f"Input voltage-noise floor ~{ylo:.1f} nV/√Hz; rises at low "
                    f"frequency (1/f) up to ~{yhi:.0f}." if en else
                    f"Giriş gerilim-gürültüsü tabanı ~{ylo:.1f} nV/√Hz; düşük "
                    f"frekansta 1/f ile ~{yhi:.0f}'e çıkıyor.")
        if key == "vos_temp":
            return (f"Input offset voltage drifts ~{(yhi - ylo):.1f} µV over "
                    f"{lo:.0f}…{hi:.0f} °C." if en else
                    f"Giriş ofset gerilimi {lo:.0f}…{hi:.0f} °C'de "
                    f"~{(yhi - ylo):.1f} µV kayıyor.")
        if key in ("iq_temp", "iq_supply"):
            uy = _unit_of(c.get("unit_y"), "mA")
            over = (("temperature" if key == "iq_temp" else "supply") if en
                    else ("sıcaklık" if key == "iq_temp" else "besleme"))
            return (f"Quiescent current {ylo:.3g}…{yhi:.3g} {uy} across {over}."
                    if en else
                    f"Sükunet akımı {over} boyunca {ylo:.3g}…{yhi:.3g} {uy}.")
        if key == "ib_temp":
            return (f"Input bias current {ylo:.3g}…{yhi:.3g} over "
                    f"{lo:.0f}…{hi:.0f} °C." if en else
                    f"Giriş bias akımı {lo:.0f}…{hi:.0f} °C'de "
                    f"{ylo:.3g}…{yhi:.3g}.")
        if key == "vout_iout":
            return (f"Output swing narrows with load current; ~{yhi:.2g} V at "
                    f"light load." if en else
                    f"Çıkış salınımı yük akımıyla daralır; hafif yükte "
                    f"~{yhi:.2g} V.")
        return super()._curve_sentence(key, c, lang)


class DiodeProfile(ComponentProfile):
    key = "diode"
    label = "Diyot"
    # Type-detection keywords. matches() does substring COUNT (not regex), so
    # every entry is a plain lowercase phrase. Grounded in real TI/onsemi diode
    # sheets: TI's discrete "diodes" are mostly ESD/TVS protection parts (tvs,
    # esd protection, clamping, IEC 61000, surge, breakdown) rather than classic
    # rectifiers — both vocabularies are covered. Multi-word phrases are used so
    # a generic "esd"/"diode" mention in an op-amp abs-max table doesn't score.
    keywords = (
        # rectifier / signal-diode vocabulary
        "schottky", "rectifier", "zener", "forward voltage", "reverse voltage",
        "reverse recovery", "forward current", "reverse current", "vrrm",
        "if(av)", "junction capacitance", "switching diode", "avalanche",
        "reverse leakage", "diode",
        # ESD / TVS protection vocabulary (TI/ADI discrete diode reality)
        "tvs", "esd protection", "clamping voltage", "clamping", "iec 61000",
        "surge", "breakdown voltage", "working voltage", "stand-off",
        "peak pulse current", "protection diode",
    )
    # Sub-families, most-specific first (first hit wins).
    subtypes = (
        ("tvs", "TVS / geçici gerilim bastırıcı",
         (r"transient voltage suppressor", r"\btvs\b", r"esd protection",
          r"clamping voltage")),
        ("zener", "Zener (gerilim referans/regülasyon)",
         (r"\bzener\b", r"voltage regulator diode")),
        ("schottky", "Schottky (düşük VF / hızlı)",
         (r"schottky",)),
        ("led", "LED / ışık yayan",
         (r"light[- ]emitting", r"luminous", r"\bled\b")),
        ("rectifier_fast", "Hızlı/ultra-hızlı doğrultucu",
         (r"ultra-?fast", r"fast recovery", r"soft recovery")),
        ("rectifier", "Doğrultucu (standart)",
         (r"rectifier", r"bridge rectifier")),
        ("small_signal", "Küçük-sinyal / anahtarlama",
         (r"small[- ]signal", r"switching diode", r"high[- ]speed switching")),
    )

    def detect_subtype(self, text: str):
        low = (text or "").lower()
        for key, label, pats in self.subtypes:
            if any(re.search(p, low) for p in pats):
                return key, label
        return "general", "Genel amaçlı diyot"

    curve_targets = (
        ("if_vf", r"forward current.*forward voltage|forward voltage char"
                  r"|instantaneous forward",
         "VF (V)", "IF (A)", "İleri akım vs ileri gerilim"),
        # Cj vs VR — TVS/ESD sheets title this "(Pin) Capacitance Across V"/
        # "vs Reverse Voltage"; rectifiers say "junction capacitance".
        ("cj_vr", r"junction capacitance|pin capacitance|capacitance across"
                  r"|capacitance vs.*(reverse|voltage)",
         "VR (V)", "Cj (pF)", "Jonksiyon kapasitansı vs ters gerilim"),
        ("ir_vr", r"reverse current|reverse leakage|leakage.*reverse",
         "VR (V)", "IR (µA)", "Ters kaçak akım vs ters gerilim"),
        # TVS clamp characteristic (I vs V) — the ESD-diode equivalent of if_vf.
        ("iv_clamp", r"\biv curve\b|i-v curve|clamp(?:ing)? voltage vs",
         "V (V)", "I (A)", "Kenetleme I–V karakteristiği"),
    )


class ResistorProfile(ComponentProfile):
    key = "resistor"
    label = "Direnç (pasif)"
    # Resistor-specific vocabulary; "resistance" alone is too common, so the
    # discriminating terms (TCR, ppm/°C, thick/thin film, wirewound…) carry it.
    keywords = (
        "temperature coefficient", "tcr", "ppm/°c", "ppm/k", "thick film",
        "thin film", "wirewound", "current sensing", "current sense", "shunt",
        "rated power", "resistance value", "resistance tolerance", "resistor",
        "ohmic", "derating", "e24", "e96", "e192",
    )
    subtypes = (
        ("current_sense", "Akım-algılama / shunt",
         (r"current[- ]sens", r"\bshunt\b", r"current sense resistor")),
        ("thin_film", "İnce film (thin-film)",
         (r"thin[- ]film",)),
        ("thick_film", "Kalın film (thick-film)",
         (r"thick[- ]film",)),
        ("wirewound", "Tel sarımlı (wirewound)",
         (r"wire[- ]?wound",)),
        ("precision", "Hassas (precision)",
         (r"\bprecision\b", r"high[- ]precision", r"\b0\.0[0-9]\s*%",
          r"[1-9]\s*ppm")),
    )

    def detect_subtype(self, text: str):
        low = (text or "").lower()
        for key, label, pats in self.subtypes:
            if any(re.search(p, low) for p in pats):
                return key, label
        return "general", "Genel amaçlı direnç"

    curve_targets = (
        ("derating", r"derating|power.*temperature|rated power vs",
         "Sıcaklık (°C)", "Güç (%)", "Güç derating eğrisi"),
    )


_PROFILES: List[ComponentProfile] = [
    RegulatorProfile(), OpAmpProfile(), DiodeProfile(), ResistorProfile(),
]
_GENERIC = ComponentProfile()


def detect_component(text: str) -> Tuple[ComponentProfile, Dict[str, float]]:
    """Score each family against the text; return (best_profile, scores)."""
    scores = {p.key: p.matches(text) for p in _PROFILES}
    best = max(_PROFILES, key=lambda p: scores.get(p.key, 0.0), default=_GENERIC)
    if not scores or scores.get(best.key, 0.0) <= 0:
        return _GENERIC, scores
    return best, scores


def get_component(key: str) -> Optional[ComponentProfile]:
    if key in ("component", "generic", ""):
        return _GENERIC
    return next((p for p in _PROFILES if p.key == key), None)
