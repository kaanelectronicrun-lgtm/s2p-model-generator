"""End-to-end pipeline: load JSON -> resolve parasitics -> Z(f) -> S -> export.

Outputs per part: <part>.s2p, <part>.cir, <part>_report.md, <part>_Zf.csv
"""
from __future__ import annotations

import json
import os
from dataclasses import replace
from typing import Optional, Tuple

import numpy as np

from . import graphs as graphmod
from . import derate, impedance, importer, report, skrf_backend, sparams, spice, validation
from .models import Capacitor, Inductor, SourceLevel
from .parasitics import resolve_capacitor, resolve_inductor
from .synth import fit_and_synthesize, synth_spice


def load_component(path: str):
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    kind = data.pop("kind", None) or data.pop("type", None)
    if "source" in data and isinstance(data["source"], (int, str)):
        data["source"] = SourceLevel(int(data["source"]))
    # Derating curves may be given as a CSV path (relative to the JSON) instead
    # of an inline [[x, dC_%], ...] list -> load them (Murata SimSurfing CSV).
    _base = os.path.dirname(os.path.abspath(path))
    for _key in ("dc_bias_curve", "tcc_curve"):
        _v = data.get(_key)
        if isinstance(_v, str):
            _p = _v if os.path.isabs(_v) else os.path.join(_base, _v)
            data[_key] = derate.load_curve_csv(_p)
    if kind == "capacitor":
        return Capacitor(**data)
    if kind == "inductor":
        return Inductor(**data)
    raise ValueError(f"Unsupported or missing 'kind' in {path}: {kind!r}. "
                     "Only 'capacitor' or 'inductor' are supported.")


def _apply_conditions(cap: Capacitor):
    """Derate effective capacitance for DC bias / temperature / AC drive.

    Returns (updated_cap, log_lines). If any behavioral (non-curve) estimate is
    applied, the model source level is downgraded to PHYSICS_ESTIMATE so the
    report stays honest. No-op when no operating conditions are set.
    """
    if not (cap.dc_bias_v or cap.temp_c is not None or cap.ac_vrms):
        return cap, []
    factor, log, used_estimate = derate.compute_factor(
        cap.dielectric, cap.voltage_rating_v,
        dc_bias_v=cap.dc_bias_v, temp_c=cap.temp_c, ac_vrms=cap.ac_vrms,
        dc_bias_curve=cap.dc_bias_curve, tcc_curve=cap.tcc_curve)
    if factor == 1.0 or not log:
        return cap, log
    c_eff = cap.capacitance_f * factor
    src = SourceLevel.PHYSICS_ESTIMATE if used_estimate else cap.source
    updated = replace(cap, nominal_capacitance_f=cap.capacitance_f,
                      capacitance_f=c_eff, source=src)
    tag = "behavioral ESTIMATE" if used_estimate else "vendor curve"
    log.append(f"Effective C under operating conditions: {c_eff*1e9:.3f} nF "
               f"(nominal {cap.capacitance_f*1e9:.1f} nF, "
               f"{(factor-1)*100:+.1f}%) [{tag}]")
    return updated, log


def _graph_fit(comp, json_path: str, f_start: float, f_stop: float):
    """Graph-fit path: reconstruct Z from digitized curves and vector-fit it.

    Returns (freq, z, vf_info) where vf_info feeds the report. Falls back to the
    lumped model (vf_info=None) only if no graphs are attached.
    """
    base = os.path.dirname(os.path.abspath(json_path))
    gpaths = {k: (v if os.path.isabs(v) else os.path.join(base, v))
              for k, v in comp.graphs.items()}
    gf = graphmod.reconstruct(gpaths, comp.kind, comp.srf_hz)
    eff_c = (importer.effective_capacitance(gf.freq, gf.z)
             if comp.kind == "capacitor" else None)
    # Adaptive order: most accurate VF that still synthesizes to a passive RLC ladder.
    vf, synth, meta = fit_and_synthesize(gf.freq, gf.z, max_pairs=8)
    # Stay within the digitized range — VF extrapolation outside data is unsafe.
    lo, hi = max(f_start, float(gf.freq.min())), min(f_stop, float(gf.freq.max()))
    f = impedance.build_sweep(lo, hi, srf_hz=gf.srf_hz)
    z = vf.eval(2j * np.pi * f)
    # Passivity enforcement: a series Z is passive iff Re(Z) >= 0. Vector fitting
    # is unconstrained, so floor Re(Z) at the measured ESR minimum (perturbation).
    floor = max(1e-3, float(np.min(gf.z.real)))
    perturbed = int(np.count_nonzero(z.real < floor))
    z = np.maximum(z.real, floor) + 1j * z.imag
    vf_info = {"rms_rel": vf.rms_rel, "n_poles": len(vf.poles),
               "graph_srf": gf.srf_hz, "graphs": gf.source_graphs,
               "passivity_floor": floor, "perturbed_points": perturbed,
               "synth_branches": len(synth.branches),
               "synth_passive": meta["passive_synth"],
               "synth_warnings": meta["n_warnings"],
               "effective_c": eff_c}
    return f, z, vf_info, synth


def process(path: str, out_dir: str, z0: float = 50.0,
            f_start: float = 1e4, f_stop: float = 1e10,
            topology: str = "series",
            dc_bias_v: Optional[float] = None,
            temp_c: Optional[float] = None,
            ac_vrms: Optional[float] = None,
            dc_bias_curve=None,
            tcc_curve=None) -> Tuple[str, str, str]:
    comp = load_component(path)
    os.makedirs(out_dir, exist_ok=True)
    is_cap = comp.kind == "capacitor"
    graph_mode = bool(comp.graphs)

    # CLI/GUI operating-condition overrides take precedence over JSON values.
    if is_cap:
        ov = {}
        if dc_bias_v is not None:
            ov["dc_bias_v"] = dc_bias_v
        if temp_c is not None:
            ov["temp_c"] = temp_c
        if ac_vrms is not None:
            ov["ac_vrms"] = ac_vrms
        if dc_bias_curve is not None:
            ov["dc_bias_curve"] = dc_bias_curve
        if tcc_curve is not None:
            ov["tcc_curve"] = tcc_curve
        if ov:
            comp = replace(comp, **ov)

    return _run(comp, out_dir, z0, f_start, f_stop, topology, graph_path=path)


def _run(comp, out_dir: str, z0: float, f_start: float, f_stop: float,
         topology: str, graph_path: Optional[str] = None,
         extra_log: Optional[list] = None) -> Tuple[str, str, str]:
    """Core: resolve -> (derate) -> Z(f) -> S -> write .s2p/.cir/report/.csv."""
    os.makedirs(out_dir, exist_ok=True)
    is_cap = comp.kind == "capacitor"
    graph_mode = bool(comp.graphs)

    if is_cap:
        comp, est_log = resolve_capacitor(comp)
        if not graph_mode:
            comp, dlog = _apply_conditions(comp)
            est_log += dlog
        spice_text = spice.capacitor_spice(comp)
    else:
        comp, est_log = resolve_inductor(comp)
        spice_text = spice.inductor_spice(comp)
    if extra_log:
        est_log = list(extra_log) + est_log

    vf_info: Optional[dict] = None
    if graph_mode:
        f, z, vf_info, synth = _graph_fit(comp, graph_path, f_start, f_stop)
        comp.source = SourceLevel.GRAPH_FIT  # measured-curve fit outranks physics
        # Effective (low-signal) capacitance from the impedance curve replaces
        # nominal for the model; nominal is retained only for the delta report.
        if is_cap and vf_info.get("effective_c"):
            comp = replace(comp, nominal_capacitance_f=comp.capacitance_f,
                           capacitance_f=vf_info["effective_c"])
            est_log.append(
                f"Effective C from impedance curve: {vf_info['effective_c']*1e9:.3f} nF "
                f"(nominal {comp.nominal_capacitance_f*1e9:.1f} nF) "
                "[freq-domain derived, preferred over nominal]")
        spice_text = synth_spice(synth, comp.part_number)  # RLC-ladder, not lumped
        est_log.append(
            f"Z(f) vector-fit to digitized graph(s): {vf_info['n_poles']} poles, "
            f"rel. RMS error {vf_info['rms_rel']*100:.2f}% [GRAPH FIT ***]")
        est_log.append(
            f"SPICE = synthesized RLC ladder ({vf_info['synth_branches']} branches, "
            f"{'passive' if vf_info['synth_passive'] else 'perturbed'})")
    else:
        f = impedance.build_sweep(f_start, f_stop, srf_hz=comp.srf_hz)
        z = (impedance.capacitor_impedance(comp, f) if is_cap
             else impedance.inductor_impedance(comp, f))

    s = sparams.z_to_s(z, z0, topology)
    model_srf = impedance.srf_check(z, f, comp.kind)
    checks = validation.run_all(s, z, model_srf, comp.srf_hz)

    topo = (topology or "series").lower()
    base = os.path.join(out_dir, _safe(comp.part_number) + f"_{topo}")
    s2p_path = base + ".s2p"
    cir_path = base + ".cir"
    rep_path = base + "_report.md"
    csv_path = base + "_Zf.csv"

    sparams.write_touchstone(s2p_path, f, s, z0, comp.part_number,
                             comment="\n".join(est_log), topology=topo)
    with open(cir_path, "w", encoding="utf-8") as fh:
        fh.write(spice_text)
    with open(rep_path, "w", encoding="utf-8") as fh:
        fh.write(report.build_report(comp, est_log, checks, model_srf, z0,
                                     vf_info, topology=topo))
    _write_zf_csv(csv_path, f, z)
    return s2p_path, cir_path, rep_path


def process_pdf(pdf_path: str, kind: str, out_dir: str, z0: float = 50.0,
                f_start: float = 1e3, f_stop: float = 1e10,
                topology: str = "series",
                dc_bias_v: Optional[float] = None,
                temp_c: Optional[float] = None,
                ac_vrms: Optional[float] = None,
                extract_curves: bool = True) -> Tuple[str, str, str]:
    """One-click: datasheet PDF -> .s2p/.cir/report, no intermediate JSON.

    Pulls scalar params from the PDF text AND (for capacitors) attempts to
    digitize the DC-bias / temperature derating curves straight from the PDF's
    vector plots. Extracted curves give exact derating; where a curve is not
    found the behavioral estimate is used. Default sweep is 1 kHz - 10 GHz.
    """
    from . import pdfcurves, pdfreader
    text = pdfreader.extract_text(pdf_path)
    stem = os.path.splitext(os.path.basename(pdf_path))[0]
    part = pdfreader._part_number(text, _safe(stem))
    log = [f"Model auto-built from datasheet PDF '{os.path.basename(pdf_path)}' "
           "(text + vector graphs, no intermediate JSON)."]
    cr = {}
    if extract_curves and pdfcurves.available():
        cr = pdfcurves.extract_curves(pdf_path)
        log += [f"curve: {ln}" for ln in cr.get("log", [])]
    elif extract_curves:
        log.append("curve: PyMuPDF yok — grafik çıkarımı atlandı")

    if kind == "capacitor":
        p = pdfreader.extract_capacitor(text)
        if not p.get("capacitance_f"):
            raise ValueError("Datasheet metninden kapasitans okunamadı — PDF metni "
                             "seçilebilir değil ya da format tanınmadı.")
        comp = Capacitor(
            part_number=part, capacitance_f=p["capacitance_f"],
            voltage_rating_v=p.get("voltage_rating_v"),
            dielectric=p.get("dielectric"), case=p.get("case"),
            dc_bias_v=dc_bias_v, temp_c=temp_c, ac_vrms=ac_vrms,
            dc_bias_curve=cr.get("dc_bias_curve"), tcc_curve=cr.get("tcc_curve"),
            source=SourceLevel.DATASHEET_TABLE,
            notes=f"Auto from datasheet PDF '{os.path.basename(pdf_path)}'.")
        # Highest fidelity: if the |Z|-vs-f curve was digitized, vector-fit it
        # (every point) instead of the lumped model.
        zc = cr.get("impedance_curve")
        if zc and len(zc) >= 5:
            gdir = _write_graph_csvs(out_dir, part, zc, cr.get("esr_curve"))
            comp = replace(comp, graphs=gdir)
            fmin = min(pt[0] for pt in zc); fmax = max(pt[0] for pt in zc)
            log.append(f"HIGH-FIDELITY: |Z|(f) curve vector-fit from datasheet "
                       f"({len(zc)} pts, {fmin:.3g}-{fmax:.3g} Hz)"
                       + (" + ESR curve" if cr.get("esr_curve") else "")
                       + ". Derating not layered on a measured curve.")
    else:
        p = pdfreader.extract_inductor(text)
        if not p.get("inductance_h"):
            raise ValueError("Datasheet metninden endüktans okunamadı.")
        comp = Inductor(
            part_number=part, inductance_h=p["inductance_h"],
            irms_a=p.get("irms_a"), isat_a=p.get("isat_a"),
            source=SourceLevel.DATASHEET_TABLE,
            notes=f"Auto from datasheet PDF '{os.path.basename(pdf_path)}'.")

    return _run(comp, out_dir, z0, f_start, f_stop, topology,
                graph_path=out_dir, extra_log=log)


def _write_graph_csvs(out_dir: str, part: str, zc, esr) -> dict:
    """Write digitized |Z|(f) [and ESR(f)] to CSVs; return a graphs dict."""
    os.makedirs(out_dir, exist_ok=True)
    zpath = os.path.join(out_dir, _safe(part) + "_Zf_from_pdf.csv")
    with open(zpath, "w", encoding="ascii") as fh:
        fh.write("freq_Hz,abs_Z_Ohm\n")
        for f, v in zc:
            fh.write(f"{f:.6e},{v:.6e}\n")
    graphs = {"impedance": zpath}
    if esr and len(esr) >= 5:
        epath = os.path.join(out_dir, _safe(part) + "_ESRf_from_pdf.csv")
        with open(epath, "w", encoding="ascii") as fh:
            fh.write("freq_Hz,ESR_Ohm\n")
            for f, v in esr:
                fh.write(f"{f:.6e},{v:.6e}\n")
        graphs["esr"] = epath
    return graphs


def process_import(s2p_path: str, kind: str, out_dir: str,
                   z0: float = 50.0, topology: str = "series") -> Tuple[str, str, str]:
    """Import a measured vendor Touchstone -> MEASURED-level model + report.

    Extracts real parameters from the measurement, vector-fits the measured Z and
    synthesizes an RLC ladder. The .s2p is re-exported from the measured data.
    """
    m = importer.load_touchstone(s2p_path)
    os.makedirs(out_dir, exist_ok=True)
    is_cap = (kind == "capacitor")

    if is_cap:
        p = importer.extract_capacitor(m)
        comp = Capacitor(part_number=m.part_number, capacitance_f=p["capacitance_f"],
                         esr_ohm=p["esr_ohm"], esl_h=p["esl_h"], srf_hz=p["srf_hz"],
                         source=SourceLevel.MEASURED_SPARAM)
    else:
        p = importer.extract_inductor(m)
        comp = Inductor(part_number=m.part_number, inductance_h=p["inductance_h"],
                        dcr_ohm=p["dcr_ohm"], cp_f=p["cp_f"], rp_ohm=p["rp_ohm"],
                        q_factor=p["q_tank"], q_ref_hz=p["srf_hz"],
                        srf_hz=p["srf_hz"], source=SourceLevel.MEASURED_SPARAM)

    topo = (topology or "series").lower()
    s = sparams.z_to_s(m.z, m.z0, topo)
    model_srf = p["srf_hz"]
    checks = validation.run_all(s, m.z, model_srf, comp.srf_hz)
    base = os.path.join(out_dir, _safe(comp.part_number) + f"_{topo}")
    s2p_out, cir_out, rep_out = base + ".s2p", base + ".cir", base + "_report.md"

    # .cir engine: prefer scikit-rf (passivity-enforced VF -> null-accurate AND
    # passive SPICE); fall back to the numpy Foster synthesis if skrf is absent.
    if skrf_backend.available():
        sk = skrf_backend.fit_passive_spice(m.freq, m.z, m.z0, cir_out)
        zmod = sk["z_model"]
        rms = float(np.sqrt(np.mean(np.abs(zmod - m.z) ** 2)) /
                    (np.sqrt(np.mean(np.abs(m.z) ** 2)) + 1e-30))
        spice_text = None
        engine_line = (f"SPICE = scikit-rf vector fit, {sk['n_poles']} poles, "
                       f"passive={sk['passive_after']} (null-accurate).")
        vf_info = {"rms_rel": rms, "n_poles": sk["n_poles"], "engine": "scikit-rf",
                   "synth_branches": sk["n_poles"], "synth_passive": sk["passive_after"],
                   "synth_warnings": 0}
    else:
        vf, synth, meta = fit_and_synthesize(m.freq, m.z, max_pairs=10)
        spice_text = synth_spice(synth, comp.part_number)
        engine_line = (f"SPICE = numpy Foster RLC ladder ({len(synth.branches)} "
                       f"branches), passive={meta['passive_synth']}.")
        vf_info = {"rms_rel": vf.rms_rel, "n_poles": len(vf.poles), "engine": "numpy",
                   "synth_branches": len(synth.branches),
                   "synth_passive": meta["passive_synth"],
                   "synth_warnings": meta["n_warnings"]}
    vf_info.update({"graph_srf": model_srf, "graphs": (os.path.basename(s2p_path),),
                    "passivity_floor": max(1e-3, float(np.min(m.z.real))),
                    "perturbed_points": 0})

    meas_log = [
        f"Parameters extracted from MEASURED Touchstone ({len(m.freq)} pts, "
        f"{m.freq.min():.0f}-{m.freq.max():.3e} Hz).",
        engine_line,
    ]

    sparams.write_touchstone(s2p_out, m.freq, s, m.z0, comp.part_number,
                             comment="MEASURED vendor data (re-exported).",
                             topology=topo)
    if spice_text is not None:
        with open(cir_out, "w", encoding="utf-8") as fh:
            fh.write(spice_text)
    with open(rep_out, "w", encoding="utf-8") as fh:
        fh.write(report.build_report(comp, meas_log, checks, model_srf, z0, vf_info,
                                     measured_src=os.path.basename(s2p_path),
                                     topology=topo))
    _write_zf_csv(base + "_Zf.csv", m.freq, m.z)
    return s2p_out, cir_out, rep_out


def validate_spice_roundtrip(s2p_path: str, kind: str = "capacitor") -> str:
    """Independent SPICE round-trip on a measured .s2p.

    Synthesizes the numpy Foster .cir, re-simulates it with the independent nodal
    solver (separate code path), and checks (1) the netlist realises the model Z,
    (2) how the simulated netlist compares to the measurement.
    """
    import tempfile
    from . import ngspice, skrf_backend, spicesim
    m = importer.load_touchstone(s2p_path)

    # Build the SAME .cir the import path ships (skrf when available, else numpy).
    if skrf_backend.available():
        tmp = tempfile.NamedTemporaryFile(suffix=".sp", delete=False)
        tmp.close()
        skrf_backend.fit_passive_spice(m.freq, m.z, m.z0, tmp.name)
        with open(tmp.name) as fh:
            cir = fh.read()
        os.unlink(tmp.name)
        engine = "scikit-rf S-parameter subckt"
    else:
        vf, synth, meta = fit_and_synthesize(m.freq, m.z, max_pairs=10)
        cir = synth_spice(synth, "DUT")
        engine = f"numpy Foster ladder ({len(synth.branches)} branches)"

    # Simulate the shipped netlist; prefer real ngspice, else the nodal solver
    # (nodal solver only handles R/L/C, i.e. the numpy ladder).
    if ngspice.available():
        f_sim, z_sim = ngspice.simulate_z(cir, float(m.freq.min()), float(m.freq.max()))
        sim_name = f"REAL ngspice ({os.path.basename(ngspice.find_ngspice())})"
    elif not skrf_backend.available():
        f_sim = m.freq
        z_sim = spicesim.impedance(cir, f_sim)
        sim_name = "independent numpy nodal solver"
    else:
        return (f"SPICE round-trip — {m.part_number}\n"
                f"  .cir engine: {engine}\n"
                "  (skrf S-param subckt needs real ngspice; install it or set "
                "S2P_NGSPICE to run the round-trip)")

    z_meas = _loginterp_c(f_sim, m.freq, m.z)
    rms = float(np.sqrt(np.mean(np.abs(z_sim - z_meas) ** 2)) /
                (np.sqrt(np.mean(np.abs(z_meas) ** 2)) + 1e-30))
    # SRF figure of merit: capacitor dips to ESR (min |Z|), inductor peaks at
    # parallel resonance (max |Z|).
    if kind == "inductor":
        i = int(np.argmax(np.abs(z_meas)))
        fom = "SRF peak"
    else:
        i = int(np.argmin(np.abs(z_meas)))
        fom = "SRF dip"
    err = abs(abs(z_sim[i]) - abs(z_meas[i])) / abs(z_meas[i]) * 100
    return "\n".join([
        f"SPICE round-trip — {m.part_number}",
        f"  .cir engine: {engine}",
        f"  simulator  : {sim_name}",
        f"  simulated netlist vs MEASURED : signal-RMS {rms*100:.3f}%",
        f"  simulated netlist at {fom} ({f_sim[i]/1e6:.1f} MHz) : {err:.2f}% error",
    ])


def _loginterp_c(fn: np.ndarray, f: np.ndarray, z: np.ndarray) -> np.ndarray:
    mag = 10 ** np.interp(np.log10(fn), np.log10(f), np.log10(np.abs(z)))
    ph = np.interp(np.log10(fn), np.log10(f), np.unwrap(np.angle(z)))
    return mag * np.exp(1j * ph)


def _write_zf_csv(path: str, f: np.ndarray, z: np.ndarray) -> None:
    with open(path, "w", encoding="ascii") as fh:
        fh.write("freq_Hz,Re_Z_ohm,Im_Z_ohm,mag_Z_ohm,phase_deg\n")
        mag = np.abs(z)
        ph = np.angle(z, deg=True)
        for i in range(len(f)):
            fh.write(f"{f[i]:.6e},{z[i].real:.6e},{z[i].imag:.6e},"
                     f"{mag[i]:.6e},{ph[i]:.4f}\n")


def _safe(s: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in s) or "part"
