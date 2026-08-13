# GJM1555C1H100_10pF_C0G — Simulation Model Report

**Component class:** Capacitor  
**Reference impedance:** 50 Ω  
**Source level:** ★ Physics Estimate

## 1. Component Summary

- Capacitance: **0.010 nF** (1e-05 µF)
- Dielectric: C0G/NP0
- Voltage rating: 50 V
- ESR: 70.00 mΩ
- ESL: 0.440 nH
- SRF (datasheet): 2400.00 MHz
- SRF (model): 2426.61 MHz

## 2. Equivalent Circuit

```
port1 ──[ ESL ]──[ ESR ]──[ C ]── port2
```

## 3. Model Validation

| Check | Result | Detail |
|-------|--------|--------|
| Passivity | ✅ PASS | max(|S11|^2+|S21|^2) = 1.000000 (<=1 required) |
| Causality (finite, rational) | ✅ PASS | all S-parameters finite — rational/minimum-phase by construction |
| Stability / Re(Z)>=0 | ✅ PASS | min Re(Z) = 7.0000e-02 Ohm |
| SRF consistency | ✅ PASS | model 2426.61 MHz vs datasheet 2400.00 MHz (1.1% error) |

## 4. Accuracy Report

- **Data source:** ★ Physics Estimate
- **Confidence:** 30–55%
- **Estimated branches:** 1

## 5. Data Provenance — kept separate

**ESTIMATED DATA** (physics / SRF back-solve — *not measured*):
- ESL estimated from SRF: 0.440 nH (SRF=2400.0 MHz) [PHYSICS ESTIMATE]

**MEASURED DATA:** none supplied.
**VENDOR DATA:** none supplied.

## 6. Engineering Review (Senior SI/PI)

**Assumptions:** lumped, linear, time-invariant; single dominant resonance; series-through 2-port at 50 Ω; no DC-bias / temperature derating applied to the nominal value.

**High-frequency risk:** above SRF the part is inductive; mounting inductance dominates and is layout-dependent — the ESL here is a single lumped value, real boards vary ±50%.

**Limitations:** 1 parameter(s) were back-solved from physics. Confidence degrades accordingly; validate against measured S-parameters before sign-off on controlled-impedance or PI decoupling work.

---
> ⚠️ This is a **behavioral / estimated** model. Do not present the generated S-parameters as manufacturer-measured data.