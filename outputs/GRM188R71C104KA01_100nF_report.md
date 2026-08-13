# GRM188R71C104KA01_100nF — Simulation Model Report

**Component class:** Capacitor  
**Reference impedance:** 50 Ω  
**Source level:** ★ Physics Estimate

## 1. Component Summary

- Capacitance (nominal — no freq-domain data): **100.000 nF** (0.1 µF)
- Dielectric: X7R
- Voltage rating: 16 V
- ESR: 50.00 mΩ
- ESL: 0.989 nH
- SRF (datasheet): 16.00 MHz
- SRF (model): 16.22 MHz

## 2. Equivalent Circuit

```
port1 ──[ ESL ]──[ ESR ]──[ C ]── port2
```

## 3. Model Validation

| Check | Result | Detail |
|-------|--------|--------|
| Passivity | ✅ PASS | max(|S11|^2+|S21|^2) = 0.999717 (<=1 required) |
| Causality (finite, rational) | ✅ PASS | all S-parameters finite — rational/minimum-phase by construction |
| Stability / Re(Z)>=0 | ✅ PASS | min Re(Z) = 5.0000e-02 Ohm |
| SRF consistency | ✅ PASS | model 16.22 MHz vs datasheet 16.00 MHz (1.4% error) |

## 4. Accuracy Report

- **Data source:** ★ Physics Estimate
- **Confidence:** 30–55%
- **Estimated branches:** 1

## 5. Data Provenance — kept separate

**ESTIMATED DATA** (physics / SRF back-solve — *not measured*):
- ESL estimated from SRF: 0.989 nH (SRF=16.0 MHz) [PHYSICS ESTIMATE]

**MEASURED DATA:** none supplied.
**VENDOR DATA:** none supplied.

## 6. Engineering Review (Senior SI/PI)

**Assumptions:** lumped, linear, time-invariant; single dominant resonance; series-through 2-port at 50 Ω; no DC-bias / temperature derating applied to the nominal value.

**High-frequency risk:** above SRF the part is inductive; mounting inductance dominates and is layout-dependent — the ESL here is a single lumped value, real boards vary ±50%.

**DC-bias / temperature:** Class-II dielectric (X7R) loses significant capacitance under DC bias and temperature — model uses nominal C only.

**Limitations:** 1 parameter(s) were back-solved from physics. Confidence degrades accordingly; validate against measured S-parameters before sign-off on controlled-impedance or PI work.

---
> ⚠️ This is a **behavioral / estimated** model. Do not present the generated S-parameters as manufacturer-measured data.