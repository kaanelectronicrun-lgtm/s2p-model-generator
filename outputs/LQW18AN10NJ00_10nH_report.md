# LQW18AN10NJ00_10nH — Simulation Model Report

**Component class:** Inductor  
**Reference impedance:** 50 Ω  
**Source level:** ★ Physics Estimate

## 1. Component Summary

- Inductance: **10.000 nH** (0.01 µH)
- DCR: 180.00 mΩ
- Parasitic Cp: 0.195 pF
- Core-loss Rp: 1.2 kΩ
- Core material: Ferrite (wire-wound)
- Irms / Isat: 0.7 A / 1.0 A
- SRF (datasheet): 3600.00 MHz
- SRF (model): 3557.29 MHz

## 2. Equivalent Circuit

```
port1 ──[ DCR ]──[ L ]── port2
  └────────[ Cp ]────────┘
  └────────[ Rp ]────────┘   (core loss)
```

## 3. Model Validation

| Check | Result | Detail |
|-------|--------|--------|
| Passivity | ✅ PASS | max(|S11|^2+|S21|^2) = 0.996413 (<=1 required) |
| Causality (finite, rational) | ✅ PASS | all S-parameters finite — rational/minimum-phase by construction |
| Stability / Re(Z)>=0 | ✅ PASS | min Re(Z) = 1.7997e-01 Ohm |
| SRF consistency | ✅ PASS | model 3557.29 MHz vs datasheet 3600.00 MHz (1.2% error) |

## 4. Accuracy Report

- **Data source:** ★ Physics Estimate
- **Confidence:** 25–50%
- **Estimated branches:** 2

## 5. Data Provenance — kept separate

**ESTIMATED DATA** (physics / SRF back-solve — *not measured*):
- Cp estimated from SRF: 0.195 pF (SRF=3600.0 MHz) [PHYSICS ESTIMATE]
- Rp (core loss) from Q=38 @ 500.0 MHz: 1.2 kOhm [DATASHEET FIT]

**MEASURED DATA:** none supplied.
**VENDOR DATA:** none supplied.

## 6. Engineering Review (Senior SI/PI)

**Assumptions:** lumped, linear, time-invariant; single dominant resonance; series-through 2-port at 50 Ω; no DC-bias / temperature derating applied to the nominal value.

**High-frequency risk:** single-pole Cp captures the first SRF only; secondary resonances and frequency-dependent core loss are not modelled. Above ~SRF the behaviour is approximate.

**Saturation:** Isat/Irms derating is not in the linear model — large-signal behaviour will differ.

**Limitations:** 2 parameter(s) were back-solved from physics. Confidence degrades accordingly; validate against measured S-parameters before sign-off on controlled-impedance or PI work.

---
> ⚠️ This is a **behavioral / estimated** model. Do not present the generated S-parameters as manufacturer-measured data.