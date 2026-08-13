# s2p — Yapılacaklar

Sıradaki turlar. Her madde bağımsız; sıra zorunlu değil.

> ⏰ **HATIRLATMA (yarın · Perşembe 2026-08-05):** datasheet-analizi yönünü (bölüm e)
> gözden geçir ve prototip hedefini seç. *(Not: araç gerçek bildirim gönderemez —
> bu satır dosyada duruyor; yarın burada göreceksin.)*

## a) DC-bias derating gösterimi (X7R)
- [ ] SimSurfing'den `GRM188R71C104KA01_DC6V3_25degC_series.s2p` (veya DC10V) indir.
- [ ] `python run.py --compare "...DC0V..." "...DC6V3..." --kind capacitor` çalıştır.
- [ ] Çıktıdan kapasitans düşüşünü (etkin C, bias ile) raporla.
- **Durum:** komut hazır (`compare.py`), yalnız bias'lı dosya bekleniyor.

## b) İndüktör yolunu gerçek veriyle doğrula ✅ TAMAMLANDI
- [x] Murata `1239AS-H-100M_series.s2p` (10 µH güç indüktörü) ile test edildi.
- [x] Çıkarım: L=10.06 µH (nominal 10 ✓), DCR=404 mΩ, Cp=8.6 pF, SRF=17.1 MHz.
- [x] ngspice round-trip: **signal-RMS %0.767, SRF tepe (17.1 MHz) %0.24** ✓.
- **Bulgular / düzeltmeler:**
  - skrf `passivity_enforce` indüktörde başarısız olup modeli %11.5'e bozuyordu →
    backend artık doğal-pasif aday yoksa **en doğru doğal fit'i** tutuyor (enforce'la
    bozmuyor), pasifliği dürüstçe `passive=False` raporluyor.
  - İndüktör SRF metriği **tepe** (max |Z|), dip değil — `validate_spice_roundtrip`
    kind-farkında yapıldı; CLI `--kind`'i artık geçiriyor.
  - Kapasitör regresyonu korundu (pasif=True, dip %0.00).
- [x] **Rp ölçümden Q ile çıkarıldı:** rezonans tepesinden `Rp = 1/(1/Z_peak −
  g_series)`, tank Q = Rp/(ωL). 1239AS: Rp=6.0 kΩ, Q=5.56. Lumped model tepesi
  artık ölçümle %0.0 (eski 1e6 ile %12283 hataydı). `extract_inductor` + report.
- **Kalan opsiyonel:** SimSurfing indüktör eğrisiyle (farklı parça) tekrar denenebilir.

## c) `releases/` paketleme ✅ TAMAMLANDI
- [x] Sürüm **1.0.0** (`src/s2p_tool/__init__.py` tek kaynak).
- [x] `CHANGELOG.md` + README/GUIDE sürüm damgası (v1.0.0).
- [x] `make_release.py` → `releases/s2p-1.0.0.zip` (40 dosya, 54 KB; outputs/
      __pycache__/*.pyc hariç). Tekrarlanabilir, sürümü init'ten okur.
- [x] Smoke test: arşiv açılıp standalone çalışıyor (5 test yeşil, örnek koşuyor).
- **Sonraki sürüm:** `python make_release.py` (önce __init__.py sürümünü artır).

## d) Arayüz (GUI) — "datasheet yükle → dosya üret"  ✅ TAMAMLANDI (2026-08-04)
Kullanıcının komut satırı bilmeden çalışabileceği bir arayüz.

- [x] **Akış:** PyQt5 GUI — PDF/JSON/.s2p yükle → gözden geçir/düzelt → "Üret" →
      `.s2p` + `.cir` + rapor + Z(f). 6 sekme (Model Üret · S2P İçeri Aktar ·
      PDF'ten Model · Datasheet → S2P · Ayarlar · Yardım).
- [x] Ölçülmüş `.s2p` import yolu aynı arayüzde (S2P İçeri Aktar sekmesi).
- [x] Masaüstü seçeneği uygulandı: PyQt5 + PyInstaller onefile exe (~84 MB).
- **Bugün eklenen (2026-08-04):** Series/Shunt topolojisi · DC-bias/sıcaklık/AC
      derating (davranışsal + vendor CSV eğrisi) · **Datasheet → S2P** tek-tık
      sekmesi (PyMuPDF ile PDF metin+grafik → doğrudan s2p, 1kHz–10GHz) ·
      vektörel |Z|(f)/ESR eğrisi okuma → her noktadan graph-fit yüksek-doğruluk.
- **Kalan opsiyonel:** sonuç ekranında canlı empedans eğrisi çizimi (plot).
- **Durum:** ✅ ana akış tamam; gerçek datasheet'lerle çıkarım isabeti kalibre edilecek.

## e) Datasheet komponent analizi  ⏳ DEVAM EDİYOR (v1.1.0: regülatör tamam)
"Datasheet inceleme" tek problem değil; ayrı komponent aileleri + ayrı teknikler.
**Mimari kuruldu** (`component_analysis.py` registry + "Komponent Analizi" GUI
sekmesi + grid-farkında `pdfcurves`), ilk aile regülatör TPS61088 ile doğrulandı.

- [x] **Regülatör / DC-DC (e-1)** — uçtan uca 5 aşama, TPS61088 doğrulandı:
      **pinout** (Table 5-1), **spec** (VIN/VOUT/fSW/Iq/OVP/RDS/paket/topoloji),
      **grafik yorumu** (Vref/Iq/ILIM yüksek-güvenli eğrilerden düz-dil bulgu),
      **tasarım hesapları** (§8.2.1 gereksinimler + §8.2.2 adım + değişken/sabit
      sözlüğü), **layout önerileri** (§10.1 checklist). Grid segmentasyonu + robust
      tick fit + curve despike + güven kapısı. GUI alt-sekmesi + JSON/CSV/rapor.
- [ ] **Şematik/PCB üretimi (e-1 devamı):** typical-application netlist + gerçek
      şematik/layout → `kicad`/`eda-agent` skill'i (bu araçta üretilmez, delege).
- [x] **Eğri sağlamlığı — çerçeve/tick eşlemesi (regülatör) ✅ (2026-08-07):**
      `_frame_above_caption` iç eksen-kutusunu kilitliyor (gridline'ları x-uzanıma
      göre grupla, kutu yüksekliğini dikey kenarlardan türet → komşu/istifli grafiği
      yutmuyor); caption-merkezli pencere (sayfa-yarısı yerine, ortadaki grafiği de
      yakalar); `_axis_ticks` birleşik etiketi ("0.1 0.2") ayırıp yayıyor ve y-bandını
      kesin çerçeve-solunda tutuyor (x-ekseni satırı artık y-tick sanılmıyor).
      **TPS61088: 3→5 yüksek eğri** (fsw_vs_r + ishutdown kurtarıldı); tps62743'e de
      genelledi (efficiency/fsw/iq çıkıyor). Kalibre olmayanlar artık hangi eksende
      tick bulunamadığını dürüstçe raporluyor (efficiency y-ekseni vektör → metin yok).
- [x] **Eğri sağlamlığı — çoklu-iz ayrıştırma (regülatör) ✅ (2026-08-07):**
      tek çerçevede N eğri **stroke rengine göre** ayrıştırılıyor (`_color_segments`
      + `_separate_traces`): overall spread ≥0.2 olunca renk grupları digitize edilip
      temiz (spread<0.2, x-kapsamı ≥%30) izler ayrı ayrı tutuluyor; `meta['traces']`
      → analyzer `curves[k]['traces']` (+`ntraces`). Uçtan uca plumbing: yorum satırı,
      uzun-format CSV (`trace,x,y`), rapor tablosu İz sütunu, Excel `Egriler` iz başına
      satır, GUI listesi. **Doğrulandı:** tps62743 fsw Fig9-13 → 2 iz (high); tps61088
      tek-iz eğriler değişmedi; sentetik grid testi yeşil. Fills/gridline/parça-iz
      spread & kapsam kapılarıyla eleniyor.
- [ ] **e-2 OpAmp analyzer:** GBW/slew/Vos/CMRR/PSRR/supply + açık-çevrim kazanç/
      faz eğrisi. `RegulatorAnalyzer` deseninde yeni plugin — **doğrulamak için
      bir opamp datasheet PDF'i gerekiyor.**
- [ ] **e-3 tablo-yoğun (MCU/SoC/ADC/DAC):** vektör DEĞİL; fitz `find_tables()` ile
      güç rayları (VDD/VDDA/VDDIO V+I), pin fonksiyonu, mutlak maks, decoupling.
- [x] **e-4a Excel'e topla** — çok-parçalı proje analizini tek `.xlsx`'te biriktir
      (`excel_export.py`; Özet/Speclar/Pinout/Egriler/GrafikYorumu/Hesaplar/Layout,
      parça-no upsert). GUI'de "Excel'e topla" kutusu.
- [ ] **e-4b birleştirme (ileri):** biriken analizlerden güç ağacı + decoupling
      netlist'i (SPICE/KiCad). Gerçek şema/PCB → `kicad`/`eda-agent`.

**Not:** İlgili hazır araçlar — `datasheets` skill (pinout/elektriksel/topoloji),
`kicad`/`eda-agent` skill'leri (şema üretimi/analizi). s2p'yi şişirmeden parçayı
doğru araca oturt.
- **Durum:** registry + regülatör canlı; sıradaki aile için örnek PDF bekleniyor.

## Dağıtım / kurulum (2026-08-07 notları)
- [x] **Tek dosya installer** — `build_installer.py` (yeni): sürümü `__init__.py`'den
      okur, `releases/s2p-<ver>-win64.exe`'yi Inno Setup 6 ile tek bir
      `releases/s2p-setup-<ver>.exe`'ye sarar. Kullanıcı-bazlı kurulum (admin yok,
      `{autopf}\s2p`), Başlat menüsü + isteğe bağlı masaüstü kısayolu, kaldırıcı.
      **Üretildi + doğrulandı:** `s2p-setup-1.1.0.exe` (82.1 MB); sessiz kurulum →
      s2p.exe hash eşleşti (bozulmadı) → sessiz kaldırma temiz.
      Yeniden derleme: `py -3.12 build_exe.py` → `py -3.12 build_installer.py`.
      Gereksinim: Inno Setup (`winget install --id JRSoftware.InnoSetup -e`) — kurulu.
- **exe referans (v1.1.0):** boyut `84.875.102` bayt, SHA256
      `6ffe21cb187323273fddc775e2c7db6c98b2e4f44937b06a66bc503168a59196`.
- [ ] **"Başka makinede çalışmıyor" teşhisi (AÇIK):** hedef **Win10/11 x64** (mimari/
      sürüm değil). Olasılık sırası: (1) bozuk/yarım kopya → hedefte
      `Get-FileHash ... SHA256` yukarıdaki ile karşılaştır, tutmazsa zip'le yeniden
      gönder; (2) AV karantinası / "Engellemeyi kaldır"; (3) eksik VC++ x64 redist
      (`aka.ms/vs/17/release/vc_redist.x64.exe`) — onefile DLL'leri gömdüğü için
      genelde gerekmez. Kullanıcı hash sonucuyla dönecek.
- [ ] **exe boyutu ~80 MB** — sebep: onefile içinde komple Python 3.12 + PyQt5
      (~40–55 MB, en büyük) + PyMuPDF + numpy. Küçültme (opsiyonel): kullanılmayan
      Qt modül/eklenti hariç, `--collect-all=pymupdf` yerine hedefli import, UPX.
      Hedef ~50–55 MB. `s2p_tool` kendi kodu birkaç yüz KB.
- [ ] **exe'yi bugünkü eğri iyileştirmeleriyle yeniden derle** → sürümü 1.2.0'a çek,
      yeni setup üret. (Kaynak güncel; exe hâlâ 1.1.0.)

## Bilinen sınırlar (açık, kapatılması opsiyonel)
- [ ] skrf `.cir` dip-doğru ama 2-port S-param subckt; numpy nodal çözücü onu
      simüle edemez (yalnız gerçek ngspice). Belgelenmiş; aksiyon gerekmez.
- [ ] Doğrulama kapsamı tek gerçek parça (Murata 100nF) — istatistiksel güven için
      daha çok ölçülmüş parça gerekir.
- [ ] HF-ESR fizik olarak datasheet'ten hesaplanamaz (yapı-bağımlı); ölçüm/sınıf
      tahmini ile sınırlı.

## Tamamlananlar (referans)
- [x] Üç giriş yolu: manuel/datasheet · grafik-fit · ölçüm-import
- [x] Vector fitting (Gustavsen) + ağırlıklı fit opsiyonu
- [x] RLC sentezi (Foster-I) + adaptif pasif mertebe
- [x] scikit-rf opsiyonel backend (passivity-test, dip-doğru `.cir`)
- [x] ngspice round-trip (`--validate-spice`), her iki `.cir` motoru için
- [x] Etkin vs nominal C kuralı (frekans-domeni → etkin C)
- [x] Hata-eğrisi analizi + PNG (`plot_error.py`)
- [x] Datasheet PDF girdi (`--pdf`, pypdf) → JSON şablonu ön-doldurma
- [x] Tek dosya Windows exe (PyInstaller, skrf+pypdf gömülü, çift-tıkla-dostu pause)
- [x] Mini-guide (argümansız açılışta) + v1.0.0 paketleme (zip + exe + dokümanlar)
