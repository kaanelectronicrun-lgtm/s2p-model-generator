# SRP6540_4R7_4u7H_power — Simulation Model Report

**Component class:** Inductor  
**Reference impedance:** 50 Ω  
**Source level:** ★ Physics Estimate

## 1. Component Summary

- Inductance: **4700.000 nH** (4.7 µH)
- DCR: 28.60 mΩ
- Parasitic Cp: 1.276 pF
- Core-loss Rp: 2.2 kΩ
- Core material: Ferrite (shielded power)
- Irms / Isat: 6.5 A / 9.0 A
- SRF (datasheet): 65.00 MHz
- SRF (model): 64.57 MHz

## 2. Equivalent Circuit

```
port1 ──[ DCR ]──[ L ]── port2
  └────────[ Cp ]────────┘
  └────────[ Rp ]────────┘   (core loss)
```

## 3. Model Validation

| Check | Result | Detail |
|-------|--------|--------|
| Passivity | ✅ PASS | max(|S11|^2+|S21|^2) = 0.999428 (<=1 required) |
| Causality (finite, rational) | ✅ PASS | all S-parameters finite — rational/minimum-phase by construction |
| Stability / Re(Z)>=0 | ✅ PASS | min Re(Z) = 2.8639e-02 Ohm |
| SRF consistency | ✅ PASS | model 64.57 MHz vs datasheet 65.00 MHz (0.7% error) |

## 4. Accuracy Report

- **Data source:** ★ Physics Estimate
- **Confidence:** 25–50%
- **Estimated branches:** 2

## 5. Data Provenance — kept separate

**ESTIMATED DATA** (physics / SRF back-solve — *not measured*):
- Cp estimated from SRF: 1.276 pF (SRF=65.0 MHz) [PHYSICS ESTIMATE]
- Rp (core loss) from Q=30 @ 2.5 MHz: 2.2 kOhm [DATASHEET FIT]

**MEASURED DATA:** none supplied.
**VENDOR DATA:** none supplied.

## 6. Engineering Review (Senior SI/PI)

**Assumptions:** lumped, linear, time-invariant; single dominant resonance; series-through 2-port at 50 Ω; no DC-bias / temperature derating applied to the nominal value.

**High-frequency risk:** single-pole Cp captures the first SRF only; secondary resonances and frequency-dependent core loss are not modelled. Above ~SRF the behaviour is approximate.

**Saturation:** Isat/Irms derating is not in the linear model — large-signal behaviour will differ.

**Limitations:** 2 parameter(s) were back-solved from physics. Confidence degrades accordingly; validate against measured S-parameters before sign-off on controlled-impedance or PI decoupling work.

---
> ⚠️ This is a **behavioral / estimated** model. Do not present the generated S-parameters as manufacturer-measured data.