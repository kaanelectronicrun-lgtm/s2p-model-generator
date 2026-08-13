# GRM188R71C104KA01 — Simulation Model Report

**Component class:** Capacitor  
**Reference impedance:** 50 Ω  
**Source level:** ★ Physics Estimate

## 1. Component Summary

- Capacitance (nominal — no freq-domain data): **100.000 nF** (0.1 µF)
- Dielectric: X7R
- Voltage rating: 16.0 V
- ESR: 10.00 mΩ
- ESL: 0.700 nH
- SRF (datasheet): 19.02 MHz
- SRF (model): 19.28 MHz

## 2. Equivalent Circuit

```
port1 ──[ ESL ]──[ ESR ]──[ C ]── port2
```

## 3. Model Validation

| Check | Result | Detail |
|-------|--------|--------|
| Passivity | ✅ PASS | max(|S11|^2+|S21|^2) = 0.999943 (<=1 required) |
| Causality (finite, rational) | ✅ PASS | all S-parameters finite — rational/minimum-phase by construction |
| Stability / Re(Z)>=0 | ✅ PASS | min Re(Z) = 1.0000e-02 Ohm |
| SRF consistency | ✅ PASS | model 19.28 MHz vs datasheet 19.02 MHz (1.3% error) |

## 4. Accuracy Report

- **Data source:** ★ Physics Estimate
- **Confidence:** 25–50%
- **Estimated branches:** 2

## 5. Data Provenance — kept separate

**ESTIMATED DATA** (physics / SRF back-solve — *not measured*):
- ESL computed from case 0603: 0.700 nH; SRF computed = 19.02 MHz [GEOMETRY ESTIMATE]
- ESR unknown -> default 10 mOhm [PHYSICS ESTIMATE, low confidence]

**MEASURED DATA:** none supplied.
**VENDOR DATA:** none supplied.

## 6. Engineering Review (Senior SI/PI)

**Assumptions:** lumped, linear, time-invariant; single dominant resonance; series-through 2-port at 50 Ω; no DC-bias / temperature derating applied to the nominal value.

**High-frequency risk:** above SRF the part is inductive; mounting inductance dominates and is layout-dependent — the ESL here is a single lumped value, real boards vary ±50%.

**DC-bias / temperature:** Class-II dielectric (X7R) loses significant capacitance under DC bias and temperature — model uses nominal C only.

**Limitations:** 2 parameter(s) were back-solved from physics. Confidence degrades accordingly; validate against measured S-parameters before sign-off on controlled-impedance or PI work.

---
> ⚠️ This is a **behavioral / estimated** model. Do not present the generated S-parameters as manufacturer-measured data.