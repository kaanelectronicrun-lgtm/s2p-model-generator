# Datasheet Analizi — TPS61088

**Tür:** Regülatör / DC-DC  
**Kaynak:** tps61088.pdf

## Açıklama

The TPS61088 is a high-power density, fully- integrated synchronous boost converter with a 11-mΩ power switch and a 13-mΩ rectifier switch to provide a high efficiency and small size solution in portable systems. The TPS61088 has a wide input voltage range from 2.7 V to 12 V to support applications with single-cell or two-cell Lithium batteries. The device has 10-A switch current capability and is capable of providing an output voltage up to 12.6 V. The TPS61088 uses adaptive constant off-time peak current control topology to regulate the output voltage. In moderate to heavy load condition, th

## Pinout (Pin Fonksiyonları)

| Pin | No | I/O | Açıklama |
|---|---|---|---|
| VCC | 1 | O | Output of the internal regulator. A ceramic capacitor of more than 1.0 µF is required between this pin and ground. |
| EN | 2 | I | Enable logic input. Logic high level enables the device. Logic low level disables the device and turns it into shutdown mode. |
| FSW | 3 | I | The switching frequency is programmed by a resistor between this pin and the SW pin. |
| SW | 4, 5, 6, 7 | I | The switching node pin of the converter. It is connected to the drain of the internal low-side power MOSFET and the source of the internal high-side power MOSFET. |
| BOOT | 8 | O | Power supply for high-side MOSFET gate driver. A ceramic capacitor of 0.1 µF must be connected between this pin and the SW pin. |
| VIN | 9 | I | IC power supply input |
| SS | 10 | O | Soft-start programming pin. An external capacitor sets the ramp rate of the reference voltage of the internal error amplifier during soft start. |
| NC | 11, 12 | — | No connection inside the device. Connect these two pins to the ground plane on the PCB for good thermal dissipation. |
| MODE | 13 | I | Operation mode selection pin for the device in light load condition. When this pin is connected to ground, the device works in PWM mode. When this pin is left floating, the device works in PFM mode. |
| VOUT | 14, 15, 16 | O | Boost converter output |
| FB | 17 | I | Voltage feedback. Connect to the center tape of a resistor divider to program the output voltage. |
| COMP | 18 | O | Output of the internal error amplifier, the loop compensation network must be connected between this pin and the AGND pin. |
| ILIM | 19 | O | Adjustable switch peak current limit. An external resistor must be connected between this pin and the AGND pin. |
| AGND | 20 | — | Signal ground of the IC |
| PGND | 21 | — | Power ground of the IC. It is connected to the source of the low-side MOSFET. |

## Elektriksel Özellikler

| Parametre | Değer |
|---|---|
| Giriş gerilimi (VIN) | 2.7 V – 12 V |
| Çıkış gerilimi (VOUT) | 4.5 V – 12.6 V |
| Anahtar akım kapasitesi | 10 A |
| Anahtarlama frekansı | 200 kHz – 2.2 MHz |
| Tepe verim | %91 |
| Kapalı-durum akımı (shutdown) | 1.0 µA |
| Aşırı gerilim koruma (OVP) | 13.2 V |
| Anahtar direnci RDS(on) | 11 mΩ (HS) / 13 mΩ (rectifier) |
| Paket | 4.50-mm × 3.50-mm 20-pin VQFN |
| Topoloji | Senkron boost |

## Özellikler (Features)

- 2.7-V to 12-V input voltage range
- 4.5-V to 12.6-V output voltage range
- 10-A switch current
- Up to 91% efficiency at VIN = 3.3 V, VOUT = 9 V, and IOUT = 3 A
- Mode selection between PFM mode and forced PWM mode at light load
- 1.0-µA current into the VIN pin during shutdown
- Resistor-programmable switch peak current limit
- Adjustable switching frequency: 200 kHz to 2.2 MHz
- Programmable soft start
- Output overvoltage protection at 13.2 V
- Cycle-by-cycle overcurrent protection
- Thermal shutdown
- 4.50-mm × 3.50-mm 20-pin VQFN package
- Create a custom design using the TPS61088 with the WEBENCH Power Designer

## Çıkarılan Karakteristik Eğriler

| Eğri | Güven | İz | Nokta | X | Y | CSV |
|---|---|---|---|---|---|---|
| Akım limiti vs ayar direnci | ✅ yüksek | 1 | 25 | R_SET (kΩ) | Current Limit (A) | TPS61088_current_limit_vs_r.csv |
| Anahtarlama frekansı vs ayar direnci | ✅ yüksek | 1 | 6 | R_SET (kΩ) | fSW (kHz) | TPS61088_fsw_vs_r.csv |
| Referans gerilimi vs sıcaklık | ✅ yüksek | 1 | 19 | Sıcaklık (°C) | Vref (V) | TPS61088_vref_vs_temp.csv |
| Sükunet akımı vs sıcaklık | ✅ yüksek | 1 | 35 | Sıcaklık (°C) | Iq (µA) | TPS61088_iq_vs_temp.csv |
| Kapalı-durum akımı vs sıcaklık | ✅ yüksek | 1 | 10 | Sıcaklık (°C) | I_SD (µA) | TPS61088_ishutdown_vs_temp.csv |

> ⚠️ 'düşük' güvenli eğriler kalibrasyon/çoklu-iz nedeniyle güvenilmez; doğrulanmadan kullanmayın.

## Grafik Yorumu

- Akım limiti ayar direnciyle azalıyor (90→349 kΩ, 13.1→3.3 A). Eğriden: R=100kΩ→11.9A, R=250kΩ→4.6A.
- Anahtarlama frekansı ayar direnciyle değişiyor (50→787 kΩ, 216→1916).
- Vref ≈ 1.204 V; -40…125 °C aralığında toplam sapma ~1.7 mV → referans çok kararlı.
- Sükunet akımı Iq 94…119 µA; sıcaklıkla artıyor (-40→84 °C).
- Kapalı-durum akımı 0.36…0.7 µA aralığında.

## Tasarım Gereksinimleri (datasheet örnek tasarımı)

| Parametre | Değer |
|---|---|
| Giriş gerilimi aralığı | 3.3 to 4.2 V |
| Çıkış gerilimi | 9 V |
| Çıkış ripple | 100 mV peak to peak |
| Çıkış akımı | 3 A |
| Çalışma frekansı | 600 kHz |
| Hafif-yük modu | PFM |

## Tasarım Hesapları (Detailed Design Procedure)

> Denklemlerin birebir glyph'i PDF metninden güvenilir çıkmaz; her adımın amacı + değişken/sabit sözlüğü aşağıda.

### Anahtarlama frekansı ayarı (RFSW)
The switching frequency is set by a resistor connected between the FSW pin and the SW pin of the TPS61088.
- RFREQ = the resistance connected between the FSW pin and the SW pin
- CFREQ = 23 pF
- ƒSW = the desired switching frequency
- tDELAY = 89 ns
- VIN = the input voltage
- VOUT = the output voltage

### Tepe akım limiti ayarı (RILIM)
The peak input current is set by selecting the correct external resistor value correlating to the required current limit.
- RILIM = the resistance connected between the ILIM pin and ground
- ILIM = the switching peak current limit

### İndüktör seçimi
Three most important specifications to the performance of the inductor are the inductor value, DC resistance, and saturation current.

### Çıkış kapasitörü seçimi
For small output voltage ripple, TI recommends a low-ESR output capacitor like a ceramic capacitor.
- Vripple_dis = output voltage ripple caused by charging and discharging of the output capacitor
- Vripple_ESR = output voltage ripple caused by ESR of the output capacitor
- VIN_MIN = the minimum input voltage of boost converter
- VOUT = the output voltage
- IOUT = the output current
- ILpeak = the peak current of the inductor
- ƒSW = the converter switching frequency
- RC_ESR = the ESR of the output capacitors

### Giriş kapasitörü seçimi
For good input voltage filtering, TI recommends low-ESR ceramic capacitors.

### Geri-besleme / çıkış gerilimi ayarı
The output voltage is set by an external resistor divider (R1, R2 in Figure 8-1).

## Layout Önerileri (datasheet §Layout Guidelines)

- If layout is not carefully done, the regulator could suffer from instability and noise problems.
- To maximize efficiency, switch rise and fall times are very fast.
- To prevent radiation of high- frequency noise (for example, EMI), proper layout of the high-frequency switching path is essential.
- Minimize the length and area of all traces connected to the SW pin, and always use a ground plane under the switching regulator to minimize interplane coupling.
- The input capacitor needs to be close to the VIN pin and GND pin in order to reduce the Iinput supply ripple.
- The layout should also be done with well consideration of the thermal as this is a high power density device.
- A thermal pad that improves the thermal capabilities of the package should be soldered to the large ground plate, using thermal vias underneath the thermal pad.

> Not: Gerçek şematik/PCB *üretimi* bu aracın kapsamı dışı — `kicad`/`eda-agent` skill'leri ile yapılır.
