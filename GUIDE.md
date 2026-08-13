# s2p — Hızlı Kullanım Kılavuzu  (v1.0.0)

Kapasitör / indüktör datasheet'ini **simülasyona hazır modele** çevirir:
SPICE (`.cir`), Touchstone (`.s2p`), empedans tablosu (`.csv`) ve mühendislik raporu (`.md`).

> Kapsam: **yalnız kapasitör ve indüktör.** Ferrit bead, CMC, TVS, konnektör,
> kristal, filtre, MOSFET, IC, IBIS, iletim hattı → reddedilir.
> Üretilen S-parametreleri **davranışsal/tahmini** modeldir; ölçülmüş veri değildir.

---

## 1. Kurulum (tek sefer)

```bash
cd "s2p"
python -m pip install -r requirements.txt   # numpy (çekirdek)
```

**Opsiyonel güçlendirmeler** (kuruluysa otomatik devreye girer, yoksa tool numpy ile çalışır):
- **scikit-rf** (`pip install scikit-rf`) → ölçüm import'unda passivity-test edilmiş,
  **dip-doğru** `.cir` (S-param alt-devre). Yoksa numpy Foster RLC merdiveni kullanılır.
- **ngspice** (binary; [ngspice.sourceforge.io](https://ngspice.sourceforge.io)) → `--validate-spice`
  ile gerçek simülatör round-trip'i. `.exe`'yi `S2P_NGSPICE` ortam değişkenine veya
  İndirilenler'e koy; tool otomatik bulur. Yoksa saf-numpy nodal çözücüye düşer.

## 2. Çalıştırma

```bash
python run.py components/example_cap.json            # tek parça
python run.py "components/*.json" -o outputs          # toplu
python tests/test_vectorfit.py                        # öz-testler
```

**Python'suz (tek dosya .exe):** `releases/s2p-1.0.0-win64.exe` — Python kurulu
olmayan makinede `python run.py` yerine doğrudan çalışır (scikit-rf gömülü;
ngspice'ı İndirilenler'den otomatik bulur):
```bash
s2p-1.0.0-win64.exe components/example_cap.json -o outputs
s2p-1.0.0-win64.exe --import "...DC0V...series.s2p" --kind capacitor
s2p-1.0.0-win64.exe --validate-spice "...series.s2p" --kind inductor
```
Yeniden derleme:
`python -m PyInstaller --onefile --name s2p --paths src --collect-submodules s2p_tool _entry.py`

Her parça `outputs/` içine 4 dosya üretir:

| Dosya | İçerik |
|-------|--------|
| `<parça>.s2p` | Touchstone, `# Hz S RI R 50` — S11/S21/S12/S22 |
| `<parça>.cir` | SPICE alt-devre (LTspice / SIwave / HFSS / ADS) |
| `<parça>_report.md` | Özet · eşdeğer devre · doğrulama · doğruluk · mühendislik incelemesi |
| `<parça>_Zf.csv` | Z(f): reel, sanal, genlik, faz |

---

## 3. İki model yolu

### A) Lumped (manuel parametre) — varsayılan
Datasheet'ten okuduğun değerleri JSON'a yaz. Eksik parazitikler **SRF'den
geri-çözülür** (her biri rapora "tahmin" olarak işlenir). Tek rezonansta kesin.

**Datasheet PDF'ten otomatik ön-doldurma** (`--pdf`, pypdf gerekir):
```bash
s2p --pdf "yol\datasheet.pdf" --kind capacitor -o outputs
```
PDF metninden C/L · gerilim · dielektrik · kasa çıkarıp `<parça>_from_pdf.json`
yazar. SRF/ESR/ESL datasheet metninde yoktur — **kasa** kalırsa geometriden
ESL/SRF hesaplanır (§3 A). Üretilen JSON'u **gözden geçir**, sonra modele çevir:
`s2p outputs\<parça>_from_pdf.json -o outputs`. (Heuristik; her zaman doğrula.)

### B) Grafik-fit (vector fitting + RLC sentezi)
JSON'a `graphs` bloğu ekle → digitize edilmiş `|Z|`/`ESR` eğrilerini okur,
kompleks `Z(f)`'i **vector fitting** ile fit eder, kararlılık + pasiflik zorlar,
`.s2p`'yi fit'ten üretir. `.cir` ise **sentezlenmiş RLC merdiveni** (Foster-I):
mertebe, pasif bir ağa sentezlenen en doğru fit olacak şekilde otomatik seçilir.
Çok-rezonanslı / frekansa bağlı kayıp davranışını yakalar.

Eğri digitize: [WebPlotDigitizer](https://automeris.io) → CSV (`freq_Hz,value`)
→ `components/graphs/`. Örnek: `example_cap_graph.json`.

### C) Ölçülmüş Touchstone içe-aktarma (★★★★★ — en yüksek kaynak)
Üretici ölçülmüş `.s2p`'si varsa (ör. Murata **SimSurfing** → "S-parameter / series"),
doğrudan içe aktar. Araç S→Z çevirir, gerçek C/ESR/ESL/SRF'i **ölçümden çıkarır**,
vector-fit + RLC sentezi yapar, raporu ★★★★★ ile damgalar:

```bash
python run.py --import "C:\...\GRM188R71C104KA01_DC0V_25degC_series.s2p" --kind capacitor
```

Bu yol tahmin yapmaz — parametreler ölçümden gelir. Rapor "MEASURED DATA" olarak
işaretlenir ve altbilgi ölçülmüş veri olduğunu açıkça belirtir.

---

## 3.1 SPICE round-trip doğrulama (`--validate-spice`)

Üretilen `.cir`'i **bağımsız bir simülatöre** yükleyip Z(f)'i geri ölçerek ölçümle
kıyaslar — "netlist gerçekten çalışıyor ve gerçeği üretiyor mu?" sorusunu yanıtlar.

```bash
python run.py --validate-spice "C:\...\GRM188R71C104KA01_DC0V_25degC_series.s2p" --kind capacitor
```

Örnek çıktı (skrf `.cir` + gerçek ngspice):
```
.cir engine: scikit-rf S-parameter subckt
simulator  : REAL ngspice (ngspice_con.exe)
simulated netlist vs MEASURED : signal-RMS 0.000%
simulated netlist at SRF dip  : 1.14% error
```

- **ngspice kuruluysa:** gerçek simülatör round-trip'i (en güçlü doğrulama). Netlist
  tipini otomatik algılar — skrf S-param alt-devresi için VNA harness'i (S21→Z),
  numpy RLC merdiveni için 1A enjeksiyon harness'i.
- **ngspice yoksa:** saf-numpy bağımsız nodal çözücü (yalnız R/L/C merdiveni; skrf
  S-param `.cir`'i gerçek ngspice ister).
- **scikit-rf yoksa:** numpy Foster `.cir` doğrulanır.

Bu adım, "matematiksel doğru"yu "endüstri simülatöründe gerçekten çalışıyor"a yükseltir.

---

## 4. Parça nasıl eklenir

Bir parça = bir JSON dosyası. **SI temel birimleri** (F, H, Ω, Hz).

**Kapasitör** (zorunlu: `kind`, `part_number`, `capacitance_f`):
```json
{
  "kind": "capacitor",
  "part_number": "GRM188R71C104_100nF",
  "capacitance_f": 1.0e-7,
  "esr_ohm": 0.05, "srf_hz": 1.6e7,
  "dielectric": "X7R", "voltage_rating_v": 16,
  "source": 5
}
```
Opsiyonel: `esl_h`, `dissipation_factor`, `esr_ref_hz`, `graphs`.

**İndüktör** (zorunlu: `kind`, `part_number`, `inductance_h`):
```json
{
  "kind": "inductor",
  "part_number": "LQW18AN10NJ_10nH",
  "inductance_h": 1.0e-8,
  "dcr_ohm": 0.18, "srf_hz": 3.6e9,
  "q_factor": 38, "q_ref_hz": 5.0e8,
  "core_material": "Ferrite", "source": 5
}
```
Opsiyonel: `cp_f`, `rp_ohm`, `irms_a`, `isat_a`, `graphs`.

### `source` (model kaynak hiyerarşisi → rapordaki güven yüzdesini belirler)
`1` Ölçülmüş S-param ★★★★★ · `2` Üretici Touchstone ★★★★ · `3` Üretici SPICE ★★★★ ·
`4` Grafik fit ★★★ · `5` Datasheet tablo ★★ · `6` Fizik tahmini ★

---

## 5. Doğrulanmış deneme sonuçları

Aşağıdakiler bu repodaki örneklerle gerçekten üretildi:

| Parça | Yol | Geri-çözülen | Model SRF vs datasheet | Pasiflik | Güven |
|-------|-----|--------------|------------------------|----------|-------|
| 100 nF X7R (`example_cap`) | Lumped | ESL 0.99 nH | 16.22 / 16.0 MHz → **%1.4** | ✅ 0.9997 | ★ 30–55% |
| 10 nF RF (`example_ind`) | Lumped | Cp, Rp | 3557 / 3600 MHz → **%1.2** | ✅ | ★ |
| 10 pF C0G (`trial_cap_cog`) | Lumped | ESL 0.44 nH | 2427 / 2400 MHz → **%1.1** | ✅ 1.0000 | ★ |
| 4.7 µH güç (`trial_ind_power`) | Lumped | Cp 1.28 pF, Rp 2.2 kΩ | 64.6 / 65.0 MHz → **%0.7** | ✅ | ★ |
| 100 nF grafik (`example_cap_graph`) | Grafik-fit | — | VF %0.59 RMS | ✅ 0.9998 | ★★★ |

**Grafik-fit sentez doğrulaması:** 100 nF eğrisinden sentezlenen `.cir` fiziksel
değerleri geri kazandı — `Lser=0.907 nH` (gerçek 0.9 nH), `Cp=100.99 nF` (≈100 nF),
`Rser=21.5 mΩ` (ESR). Netlist empedansı fit ile `<1e-9` eşleşir, tüm elemanlar pozitif.

**Kapsam-dışı testi:** `trial_out_of_scope.json` (ferrit bead) →
`[FAIL] ... Only 'capacitor' or 'inductor' are supported.` ✅

---

## 6. Raporu nasıl okumalı

- **§3 Doğrulama** — Pasiflik (`|S11|²+|S21|²≤1`), nedensellik, kararlılık
  (`Re(Z)≥0`), SRF tutarlılığı (<%15). Hepsi geçmeli.
- **§4 Doğruluk** — kaynak yıldızı + güven bandı. Çok parazitik tahmin edildiyse
  güven düşer (her tahmin −%5).
- **§5 Veri kökeni** — ÖLÇÜLEN / ÜRETİCİ / TAHMİN **ayrı** listelenir. Tahmini
  parazitikler asla "ölçülmüş" gibi sunulmaz.
- **§6 Mühendislik incelemesi** — varsayımlar, HF riskleri (örn. SRF üstü davranış,
  X7R DC-bias kaybı, indüktör doygunluğu).

---

## 7. Sık ipuçları

- En yüksek doğruluk için: `srf_hz` mutlaka gir — tüm parazitik geri-çözümü buna dayanır.
- ESR yoksa `dissipation_factor` + `esr_ref_hz` ver → ESR = DF/(2πfC) ile hesaplanır.
- İndüktörde `q_factor` + `q_ref_hz` ver → çekirdek kayıp Rp = Q·ωL ile hesaplanır.
- Grafik-fit yalnız `impedance` eğrisiyle de çalışır; `esr` eğrisi varsa Re(Z) daha doğru.
- Tarama bandı: `--fstart`/`--fstop` (varsayılan 10 kHz – 10 GHz), `--z0` (varsayılan 50 Ω).
