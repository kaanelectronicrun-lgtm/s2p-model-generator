# 1239AS-H-100M — Simulation Model Report

**Component class:** Inductor  
**Reference impedance:** 50 Ω  
**Source level:** ★★★★★ Measured

## 1. Component Summary

- Inductance: **10063.239 nH** (10.06 µH)
- DCR: 404.00 mΩ
- Parasitic Cp: 8.603 pF
- Core-loss Rp: 6.0 kΩ
- Core material: n/a
- Irms / Isat: n/a A / n/a A
- SRF (datasheet): 17.10 MHz
- SRF (model): 17.10 MHz

## 2. Equivalent Circuit

```
port1 ──[ DCR ]──[ L ]── port2
  └────────[ Cp ]────────┘
  └────────[ Rp ]────────┘   (core loss)
```

## 2b. Curve Fit (Vector Fitting)

- Method: **vector fitting** (Gustavsen pole-residue), 15 poles
- Fitted to digitized graph(s): 1239AS-H-100M_series.s2p
- Graph SRF: 17.10 MHz
- Relative RMS fit error: **0.44%**
- Stability: all poles in left half-plane — stable & causal
- **SPICE**: scikit-rf vector-fit S-parameter subcircuit, 15 poles, passive=False (passivity-tested). Null-accurate (no Foster positivity constraint).

## 3. Model Validation

| Check | Result | Detail |
|-------|--------|--------|
| Passivity | ✅ PASS | max(|S11|^2+|S21|^2) = 0.992099 (<=1 required) |
| Causality (finite, rational) | ✅ PASS | all S-parameters finite — rational/minimum-phase by construction |
| Stability / Re(Z)>=0 | ✅ PASS | min Re(Z) = 3.9990e-01 Ohm |
| SRF consistency | ✅ PASS | model 17.10 MHz vs datasheet 17.10 MHz (0.0% error) |

## 4. Accuracy Report

- **Data source:** ★★★★★ Measured
- **Confidence:** 95–99%
- **Estimated branches:** 0

## 5. Data Provenance — kept separate

**MEASURED DATA** (vendor Touchstone — authoritative): `1239AS-H-100M_series.s2p`. Parameters below are extracted from it.
- Parameters extracted from MEASURED Touchstone (111 pts, 102411-1.710e+07 Hz).
- SPICE = scikit-rf vector fit, 15 poles, passive=False (null-accurate).

**ESTIMATED DATA:** none — model derived from measurement.
**VENDOR DATA:** measured S-parameters (level ★★★★★).

## 6. Engineering Review (Senior SI/PI)

**Assumptions:** linear, time-invariant; series-through 2-port at 50 Ω. Model reflects the measured bias/temperature condition of the vendor file — re-import other DC-bias/temperature curves for those operating points.

**High-frequency risk:** single-pole Cp captures the first SRF only; secondary resonances and frequency-dependent core loss are not modelled. Above ~SRF the behaviour is approximate.

**Saturation:** Isat/Irms derating is not in the linear model — large-signal behaviour will differ.

**Limitations:** model is only as broadband as the measured file (check its frequency span) and fixed to its bias/temperature point; mounting inductance on your board adds to the measured ESL.

---
> ✅ Parameters and the `.s2p` are derived from **manufacturer-measured** S-parameters (vendor Touchstone). The synthesized `.cir` is a vector-fit of that measurement. Valid at the measured bias/temperature condition only.