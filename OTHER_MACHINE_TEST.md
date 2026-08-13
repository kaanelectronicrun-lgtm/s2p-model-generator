# Başka Makinede Exe Testi — Kontrol Listesi

`s2p-1.0.0-win64.exe` Python KURULMAMIŞ bir Windows makinesinde test etmek için.

## Kopyalanacaklar
1. `releases/s2p-1.0.0-win64.exe`  (zorunlu, ~116 MB)
2. Bir örnek girdi (model üretimi testi için):
   - `components/example_cap.json`  (ve istenirse diğer örnekler)
3. (Opsiyonel) bir ölçülmüş `.s2p` (ör. SimSurfing'den).
4. (Opsiyonel, gerçek round-trip için) ngspice console binary.

## Adımlar ve beklenen sonuç

### 1) Self-test — Python'suz çalışıyor mu
```cmd
s2p-1.0.0-win64.exe components\example_cap.json -o out
```
**Beklenen:** `[OK]` + `out\` içinde 4 dosya (`.s2p .cir _report.md _Zf.csv`).
Hiçbir Python/DLL hatası olmamalı. → exe self-contained.

### 2) Ölçüm import — scikit-rf gömülü mü
```cmd
s2p-1.0.0-win64.exe --import "yol\...series.s2p" --kind capacitor -o out
```
**Beklenen:** `[OK] (measured)`; raporda "scikit-rf vector-fit S-parameter
subcircuit ... passive=True". → bundled skrf çalışıyor.

### 3) SPICE round-trip — ngspice davranışı
```cmd
s2p-1.0.0-win64.exe --validate-spice "yol\...series.s2p" --kind capacitor
```
- **ngspice VARSA** (Downloads'ta / PATH'te / `S2P_NGSPICE` ortam değişkeninde):
  `simulator: REAL ngspice` + `vs MEASURED: signal-RMS ~0.000%`.
- **ngspice YOKSA:** çökmez — şu mesajı verir:
  *"skrf S-param subckt needs real ngspice; install it or set S2P_NGSPICE"*.
  (Model üretimi yine de tam çalışır; yalnız bu doğrulama adımı ngspice ister.)

ngspice'ı tanıtmak için (kuruluysa):
```cmd
set S2P_NGSPICE=C:\yol\ngspice\bin\ngspice_con.exe
```

## Olası takılmalar (ve çözüm)
- **"Windows SmartScreen / Defender" uyarısı:** imzasız exe; "Yine de çalıştır".
- **Antivirüs karantinası:** PyInstaller exe'leri bazen yanlış pozitif; istisna ekle.
- **VC++ runtime hatası (nadiren):** Microsoft VC++ Redistributable 2015-2022 kur.
- **Çok eski Windows:** Win10/11 x64 hedeflenir; Win7/32-bit denenmedi.

## Sonuç
1 ve 2 geçiyorsa exe başka makinede tam çalışıyor demektir. 3 yalnız ngspice
varlığına bağlı — opsiyonel doğrulama adımı, çekirdek işlev değil.
