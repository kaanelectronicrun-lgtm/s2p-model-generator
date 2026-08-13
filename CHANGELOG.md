# Değişiklik Günlüğü

## Yayınlanmamış — Regülatör eğri çıkarımı sağlamlığı (2026-08-07)

`pdfcurves` çerçeve/tick tespiti yeniden yazıldı; kalibre olamayan gerçek eğriler
kurtarıldı ve renk-tabanlı çoklu-iz ayrıştırma eklendi.

- **İç eksen-kutusu bulucu** (`_frame_above_caption`): gridline'ları x-uzanıma göre
  gruplayıp kutu yüksekliğini **dikey kenarlardan** türetir → komşu/istifli grafiği
  yutmaz; caption-merkezli pencere sayfa ortasındaki grafiği de yakalar.
- **Tick eşlemesi** (`_axis_ticks`): birleşik etiketi (`"0.1 0.2"`) ayırıp yayar;
  y-bandı kesin çerçeve-solunda → x-ekseni satırı artık y-tick sanılmaz. Kalibre
  olamayan grafik hangi eksende tick bulunamadığını dürüstçe raporlar.
- **Sonuç:** TPS61088 **3 → 5 yüksek-güvenli eğri** (fsw_vs_r + ishutdown kurtarıldı);
  tps62743'e genelledi (efficiency/fsw/iq çıkıyor).
- **Çoklu-iz ayrıştırma** (`_color_segments` + `_separate_traces`): tek çerçevede N
  eğri stroke rengine göre ayrılır; temiz izler (spread<0.2, x-kapsamı ≥%30) ayrı
  tutulur. Plumbing: `curves[k]['traces']`/`ntraces`, uzun-format CSV (`trace,x,y`),
  rapor **İz** sütunu, Excel `Egriler` iz başına satır, GUI listesi, yorum satırı.
  Doğrulandı: tps62743 fsw Fig9-13 → 2 iz (high). Sentetik grid testi yeşil.

## 1.1.0 — Komponent Analizi (datasheet → tam komponent incelemesi)

s2p model yolundan ayrı, yeni bir eksen: bir datasheet PDF'inden komponentin
**türünü tespit edip** uçtan uca yapısal analizini çıkaran motor + GUI sekmesi.
İlk komponent ailesi **regülatör/DC-DC**, TPS61088 (TI 10-A boost) ile
doğrulandı. Kapsanan aşamalar: **pinout → spec → grafik yorumu → tasarım
hesapları → layout önerileri**.

### 1) Analiz motoru — `component_analysis.py` (yeni)
- **Analyzer registry**: her komponent ailesi bir plugin (`RegulatorAnalyzer`).
  Yeni aile eklemek = tek sınıf; GUI ve CLI otomatik büyür.
- `detect_type()` anahtar-kelime skoruyla tür tespiti; `analyze_pdf()` uçtan uca.
- Ortak metin çıkarımı: parça no (metadata/başlık), Description, Features listesi,
  Figure başlıkları envanteri.
- **Regülatör spec çıkarımı**: VIN/VOUT aralığı, anahtar akımı, fSW aralığı,
  tepe verim, shutdown akımı, OVP, RDS(on) HS/rectifier, paket, topoloji.
- Çıktı: `<part>_analysis.json` + eğri başına `<part>_<curve>.csv` + `<part>_analysis.md` rapor.
- **Pinout** (`_pin_functions`): Table 5-1 Pin Functions → name/no/I-O/açıklama
  (`find_tables`).
- **Grafik yorumu** (`interpret_curves`): yüksek-güvenli eğrilerden düz-dil bulgu
  (Vref kararlılığı, Iq trendi, ILIM(R) tersi + eğriden R→A örnekleri).
- **Tasarım hesaplarının anlatılması** (`_design_requirements`/`_design_procedure`):
  §8.2.1 Design Requirements tablosu + §8.2.2 adımları (RFSW/RILIM/L/Cout/Cin/
  feedback) — her adımın amacı + "where" değişken/sabit sözlüğü. Denklem glyph'i
  PDF'ten güvenilir çıkmadığı için formül uydurulmaz, prosedür anlatılır.
- **Layout önerileri** (`_layout_guidelines`): §10.1 guideline'ları checklist'e.
  Gerçek şematik/PCB *üretimi* kapsam dışı → `kicad`/`eda-agent` skill'i.

### 2) Grid-farkında vektör eğri çıkarımı — `pdfcurves` genişletmesi
- `extract_labeled_curves()` — grafiği **caption'ından** (Figure N. …) bulur; TI
  tarzı 2×2/3×2 çoklu-grafik sayfasında her subplot'u kendi grid sütununda
  ayrı çerçeveler (`_frame_above_caption`).
- `_axis_ticks()` — tick etiketlerini frame kenarına değil **kümeleyerek** bulur
  (en alt yatay satır = X, en sol dikey sütun = Y); köşe/komşu karışmasını önler.
- `_calibrate` artık **robust fit** (`_robust_lin`, outlier tick atma) — birleşik/
  bozuk etiketleri (ör. "120130") eler; pasif yol etkilenmez (temiz tick → no-op).
- **Güven kapısı**: her eğriye `confidence` (high/low) — r²≥0.985, ≥3 tick, tek-iz
  (spread<0.25). Düşük güvenli/çoklu-izli eğri açıkça etiketlenir, doğru diye sunulmaz.

### 3) GUI — "Komponent Analizi" sekmesi
- Üst sekme + tür başına otomatik alt-sekme (Otomatik algıla · Regülatör / DC-DC).
  Registry'ye analyzer eklenince alt-sekme kendiliğinden gelir.
- `AnalysisWorker` (QThread) arka planda; sonuç panelinde spec tablosu + eğri
  güven listesi + yazılan dosyalar.
- **Excel'e topla** (`excel_export.py`, yeni): her analiz tek bir `.xlsx`
  çalışma kitabına parça-no ile **upsert** edilir (tekrar analiz → satır güncellenir,
  çift kayıt olmaz). Sayfalar: Özet (geniş) · Speclar · Pinout · Egriler ·
  GrafikYorumu · Hesaplar · Layout — hepsi uzun/şemasız, çok-parçalı projede
  birikir. Panelde "Excel'e topla" kutusu + yol; analiz sonrası otomatik ekler.
  Bağımlılık: openpyxl (exe'ye gömülü).

### Doğrulama (TPS61088, TI 10-A boost, 35 sayfa)
- Spec'ler birebir: VIN 2.7–12 V, VOUT 4.5–12.6 V, 10 A, fSW 200 kHz–2.2 MHz,
  %91 verim, shutdown 1.0 µA, OVP 13.2 V, RDS 11/13 mΩ, VQFN, senkron boost.
- Eğriler (HIGH, r²=1.000): current-limit vs R (33 nk), Vref vs T = 1.204 V (19 nk),
  Iq vs T 94–119 µA (35 nk). Çoklu-izli efficiency + kenar-durum fsw/ishutdown
  dürüstçe atlandı (yanlış veri üretilmedi).

### Testler
- `test_grid_curve_segmentation_and_confidence` (sentetik 2-grafik grid PDF:
  segmentasyon + kalibrasyon + güven, cross-talk yok) ve
  `test_component_specs_and_type_detect` (spec regex + tür tespiti) eklendi.
  Tüm paket geçiyor; pasif yol regresyonsuz.

### Dürüst sınırlar
- Çoklu-iz (birden çok eğri tek çerçevede) izleri henüz ayrıştırılmıyor → low
  flag. Raster grafik yine desteklenmez. Bazı kenar-yerleşimli subplot'lar
  çerçeve/tick eşleşmezse dürüstçe atlanır. Yeni türler (OpAmp vb.) örnek PDF ile
  doğrulanmayı bekliyor.

## 2026-08-04 — GUI, EXE ve datasheet-otomasyonu (geliştirme günlüğü)

Çekirdek motorun üstüne arayüz + üç büyük özellik ekseni. Tümü test edildi;
Windows exe her adımda yeniden derlenip çalışır halde doğrulandı.

### 1) PyQt5 GUI + tek-dosya EXE
- `src/s2p_tool/gui.py`, `gui_main.py` — 6 sekmeli arayüz (Model Üret · S2P İçeri
  Aktar · PDF'ten Model · **Datasheet → S2P** · Ayarlar · Yardım).
- `build_exe.py` — PyInstaller onefile; `releases/s2p-1.0.0-win64.exe` (~80 MB).
- Uzun işler için arka-plan `QThread` (ProcessWorker / AutoWorker) — arayüz donmaz.

### 2) Series / Shunt topolojisi
- `sparams.py` — `shunt_z_to_s` + `z_to_s(z, z0, topology)` dispatcher.
  Series: DC-blok (SRF'de geçirir); Shunt: bypass (SRF'de şaseye bloklar).
- `pipeline.process/process_import`, `report.py`, `cli.py --topology`, GUI seçici.
  Çıktı adına `_series` / `_shunt` eklenir (ikisi bir arada üretilebilir).

### 3) Koşula bağlı derating (DC bias · sıcaklık · AC Vrms)
- `derate.py` (yeni) — dielektrik sınıfı (C0G/NP0 = I, stabil; X7R vb. = II).
  DC-bias Hill fonksiyonu, sıcaklık parabolik droop, AC ikincil model.
- İki kademe: **vendor eğrisi** (tam, interpolasyon) > **davranışsal tahmin**
  (sınıf-tipik, "ESTIMATE" etiketli, kaynak PHYSICS_ESTIMATE'e düşer).
- Efektif C derate edilir → SRF fiziksel olarak yukarı kayar.
- `models.py` yeni alanlar; `cli.py --dc-bias/--temp/--ac-vrms`; GUI spinbox'ları.

### 4) Vendor derating eğrisi (CSV) çıkarımı
- `derate.load_curve_csv` — SimSurfing "Save as CSV" toleranslı okuyucu.
- JSON `dc_bias_curve`/`tcc_curve` = CSV yolu *veya* satır-içi liste.
- `cli.py --dc-bias-csv/--tcc-csv`; GUI'de eğri gözat alanları.

### 5) Datasheet → S2P (tek tık, ara işlemsiz)
- `pipeline.process_pdf` — PDF metni (part/C/V/dielektrik) + grafik → doğrudan
  `.s2p/.cir/rapor`, ara JSON yok. Varsayılan tarama 1 kHz – 10 GHz.
- `pdfcurves.py` (yeni, **PyMuPDF**) — datasheet grafiğinden **vektörel** eğri
  digitizasyonu: başlık/eksen bul → tick etiketlerinden (SI-ekli, **auto lin/log**)
  piksel→veri kalibrasyonu → çizili eğri.
- Çıkarılan hedefler: DC-bias, sıcaklık (TCC), **|Z|–frekans**, **ESR–frekans**.

### 6) Vektörel |Z|(f) → her noktadan yüksek-doğruluk s2p
- |Z|(f) eğrisi bulunursa `process_pdf` mevcut **graph-fit** motoruna yönlendirir
  (vector-fitting + RLC sentezi) → model eğriyi her noktada izler; yoksa lumped +
  derating. Uzunluk-bazlı gridline reddi SRF çentiğini korur.
- Doğrulama: sentetik log-log datasheet → model |Z| gerçeğe göre ~%0.7 (RMS fit
  %0.18); frozen exe'de 117-nokta graph-fit s2p üretimi kanıtlandı.

### Testler / bağımlılık
- `tests/test_vectorfit.py` — topoloji, derating, CSV, PDF-eğri ve empedans-graphfit
  öz-testleri eklendi (fitz/skrf yoksa temiz atlar). Tüm paket geçiyor.
- `requirements.txt` — **PyMuPDF** eklendi (exe'ye `--collect-all=pymupdf` ile gömülü).

### Dürüst sınırlar
- Graph-fit yalnız eğrinin **kapsadığı frekans aralığında** güvenilir; ötesine
  ekstrapolasyon yapılmaz. Tick-merkez kalibrasyonunda ~%0.7 sistematik offset.
- **Raster (taranmış)** grafikten vektör çıkmaz → o eğri atlanır, davranışsal/lumped'e düşülür.
- Davranışsal derating sınıf-tipiktir, parça-kesin değil (eğri sağlanınca tam olur).

## 1.0.0 — İlk doğrulanmış sürüm

Kapasitör/indüktör datasheet & ölçümünden simülasyona hazır model (SPICE `.cir`,
Touchstone `.s2p`, rapor, Z(f) CSV) üreten, uçtan uca gerçek ngspice ile
doğrulanmış ilk tam sürüm.

### Giriş yolları
- **Manuel / datasheet** — JSON parametre; eksik parazitikler SRF'den geri-çözülür.
- **Datasheet PDF** (`--pdf`, pypdf) — metinden C/L · gerilim · dielektrik · kasa
  çıkarıp JSON şablonu ön-doldurur (heuristik; gözden geçirilmeli).
- **Paket geometrisi** — kasa (ör. 0603) → ESL hesaplanır → SRF = 1/(2π√(LC)).
- **Grafik-fit** — digitize `|Z|`/`ESR` eğrileri → vector fitting + RLC sentezi.
- **Ölçüm import** (`--import`) — üretici `.s2p`'den S→Z, etkin parametre çıkarımı (★★★★★).

### Model motorları
- Gustavsen **vector fitting** (saf numpy) + opsiyonel bağıl ağırlık.
- **Foster-I RLC sentezi** — adaptif pasif mertebe.
- Opsiyonel **scikit-rf backend** — passivity-test edilmiş, dip-doğru `.cir`
  (kuruluysa otomatik; yoksa numpy Foster).

### Doğrulama
- Pasiflik / nedensellik / kararlılık / SRF tutarlılığı her modelde.
- **SPICE round-trip** (`--validate-spice`) — gerçek ngspice (varsa) ya da saf-numpy
  nodal çözücü; netlist tipini otomatik algılar (S-param VNA vs seri RLC harness'i).
- 5 öz-test (`tests/test_vectorfit.py`).

### Doğrulanmış sonuçlar (gerçek Murata veri)
- **GRM188R71C104** 100 nF: ngspice round-trip %0.000 RMS, dip %1.14; etkin C 91.3 nF.
- **1239AS-H-100M** 10 µH: ngspice round-trip %0.767 RMS, SRF tepe %0.24;
  Rp ölçümden 6.0 kΩ (Q=5.56).

### Dürüstlük kuralları
- Kaynak hiyerarşisi (★…★★★★★); tahmini asla ölçülmüş gibi sunmaz.
- MLCC **etkin (low-signal) C** frekans-domeni veriden türetilir; nominal yalnız fallback.
- İndüktör fit'i doğal pasif değilse `passive=False` dürüstçe raporlanır (sahte enforce yok).

### Dağıtım
- `releases/s2p-1.0.0.zip` — kaynak + dokümanlar + örnekler (Python ile).
- `releases/s2p-1.0.0-win64.exe` — tek dosya Windows exe (PyInstaller; scikit-rf
  gömülü, ngspice'ı İndirilenler'den otomatik bulur; Python gerekmez, ~116 MB).

### Bilinen sınırlar
- skrf `.cir` (2-port S-param subckt) gerçek ngspice ister; saf-numpy nodal çözücü
  yalnız R/L/C merdivenini simüle eder.
- HF-ESR datasheet'ten hesaplanamaz (yapı-bağımlı); ölçüm/sınıf tahmini ile sınırlı.
- Doğrulama kapsamı sınırlı sayıda gerçek parça.
