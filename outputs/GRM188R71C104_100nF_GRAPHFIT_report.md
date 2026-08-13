# GRM188R71C104_100nF_GRAPHFIT — Simulation Model Report

**Component class:** Capacitor  
**Reference impedance:** 50 Ω  
**Source level:** ★★★ Graph Fit

## 1. Component Summary

- Capacitance (**effective**, freq-domain derived): **101.129 nF** (nominal 100.0 nF, +1.1%)
- Dielectric: X7R
- Voltage rating: 16 V
- ESR: 10.00 mΩ
- ESL: 0.500 nH
- SRF (datasheet): n/a
- SRF (model): 16.79 MHz

## 2. Equivalent Circuit

```
port1 ──[ ESL ]──[ ESR ]──[ C ]── port2
```

## 2b. Curve Fit (Vector Fitting)

- Method: **vector fitting** (Gustavsen pole-residue), 2 poles
- Fitted to digitized graph(s): cap100nF_Z.csv, cap100nF_ESR.csv
- Graph SRF: 16.62 MHz
- Relative RMS fit error: **0.75%**
- Stability: all poles in left half-plane — stable & causal
- Passivity: Re(Z) floored at 14.6 mΩ (ESR min); 0 point(s) perturbed
- **SPICE**: synthesized RLC ladder, 1 Foster branches — all elements positive (passive). Netlist impedance equals the fit by construction.

## 3. Model Validation

| Check | Result | Detail |
|-------|--------|--------|
| Passivity | ✅ PASS | max(|S11|^2+|S21|^2) = 0.999803 (<=1 required) |
| Causality (finite, rational) | ✅ PASS | all S-parameters finite — rational/minimum-phase by construction |
| Stability / Re(Z)>=0 | ✅ PASS | min Re(Z) = 2.1465e-02 Ohm |
| SRF consistency | ✅ PASS | no datasheet SRF to compare |

## 4. Accuracy Report

- **Data source:** ★★★ Graph Fit
- **Confidence:** 52–70%
- **Estimated branches:** 5

## 5. Data Provenance — kept separate

**ESTIMATED DATA** (physics / SRF back-solve — *not measured*):
- ESL not derivable (no SRF, no case) -> default 0.5 nH [PHYSICS ESTIMATE, low confidence]
- ESR unknown -> default 10 mOhm [PHYSICS ESTIMATE, low confidence]
- Effective C from impedance curve: 101.129 nF (nominal 100.0 nF) [freq-domain derived, preferred over nominal]
- Z(f) vector-fit to digitized graph(s): 2 poles, rel. RMS error 0.75% [GRAPH FIT ***]
- SPICE = synthesized RLC ladder (1 branches, passive)

**MEASURED DATA:** none supplied.
**VENDOR DATA:** none supplied.

## 6. Engineering Review (Senior SI/PI)

**Assumptions:** lumped, linear, time-invariant; single dominant resonance; series-through 2-port at 50 Ω; no DC-bias / temperature derating applied to the nominal value.

**High-frequency risk:** above SRF the part is inductive; mounting inductance dominates and is layout-dependent — the ESL here is a single lumped value, real boards vary ±50%.

**DC-bias / temperature:** Class-II dielectric (X7R) loses significant capacitance under DC bias and temperature — model uses nominal C only.

**Limitations:** 5 parameter(s) were back-solved from physics. Confidence degrades accordingly; validate against measured S-parameters before sign-off on controlled-impedance or PI work.

---
> ⚠️ This is a **behavioral / estimated** model. Do not present the generated S-parameters as manufacturer-measured data.