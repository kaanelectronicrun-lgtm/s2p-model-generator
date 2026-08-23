# Datasheet Parsing — Repo Scout (per-section, adopt-vs-build)

**Tarih:** 2026-08-21
**Bağlam:** s2p `component_analysis` motorunu monolitik `analyze()`'dan **her başlığın kendi
bağımsız değerlendirme birimi** olduğu bir `Section` sözleşmesine (extract→validate→score→
interpret→cite) taşıma kararı. Bu scout, zor bölümler (TI-dışı spec tabloları + denklem
çıkarımı + pinout) için dış repo adopt-vs-build kararını netleştirir.

**İki sert kapı:**
1. **Lisans** — s2p KAPALI `.exe` olarak dağıtılıyor → AGPL/GPL viral = link EDİLEMEZ.
2. **Bundle ağırlığı (torch)** — exe zaten ~85MB ve Kaan küçültmek istiyor. torch/ViT tabanlı
   araçlar (docling models, TATR, pix2tex) exe'yi 500MB+'a şişirir → **bundle edilemez**,
   sadece opsiyonel dış-pipeline (kullanıcı ayrıca kurar) olabilir.

---

## 1. Aday Havuzu

| Araç | Kapsam | Teknik | Lisans | Bakım | Ağırlık |
|---|---|---|---|---|---|
| **pdfplumber** | tablo + char/word geometri | pdfminer.six char-pozisyon | **MIT ✅** | aktif (2026 default öneri) | hafif (saf-python) |
| **camelot** | bordürlü tablo | lattice/stream + Ghostscript | **MIT ✅** | aktif | orta (Ghostscript şart) |
| **docling** (IBM/LF) | tam-doküman: layout+tablo+okuma-sırası | TableFormer v2 DL + opsiyonel VLM | **MIT ✅** (VLM Apache-2.0) | çok aktif (37k★, 100+ release) | **AĞIR (torch/DL model)** |
| **table-transformer (TATR)** | görsel tablo yapısı | DETR object-detection | **MIT ✅** | 2025-05 güncel | **AĞIR (torch)** |
| **pix2tex / LaTeX-OCR** | denklem görseli → LaTeX | ViT | **MIT ✅** | aktif | **AĞIR (torch)** |
| **DatasheetExtractor** (PySpice-org) | komponent datasheet | tabula-py(Java)+PyMuPDF+OpenCV | **AGPL-3.0 ❌** | 74 commit | orta+Java |
| **uConfig** (Robotips) | pinout → KiCad | Poppler + "magic rules" | **GPL-3.0 ❌** | 2024-12, Qt5 GUI | orta+Qt |
| **datasheet-cli** (Rust) | pinout/spec/footprint→JSON | Rust parser | belirsiz (fetch olmadı) | — | subprocess-only |
| **sheetsdata-mcp** | pinout+spec MCP | cloud MCP | belirsiz | — | local değil |

## 2. Stabilite Kapısı (4 kapı + bayrak)

- **pdfplumber 🟢** — bakım aktif; bağımsız kanıt: 2026 karşılaştırmalarında MIN/TYP/MAX kolon
  hizası için "char-pozisyonu kullandığı için en iyi" (tahmin değil gerçek pozisyon); MIT;
  headless kütüphane. **s2p'nin bespoke `_parametric_tables`'ı zaten aynı tekniğin el-yapımı hâli.**
- **camelot 🟡** — MIT + aktif ama Ghostscript sistem-bağımlılığı (exe'ye ek yük) + bordürsüz
  datasheet tablolarında zayıf. TI spec tabloları çoğu bordürsüz → uygun değil.
- **docling 🟡** — teknik olarak SOTA + MIT (temiz), ama torch/DL model → bundle kapısına takılır.
  Bağımsız kanıt güçlü (arXiv teknik rapor, TableFormer). Adopt DEĞİL ama opsiyonel dış-mod adayı.
- **TATR 🟡** — MIT, görsel-tablo için güçlü; torch. Yalnız pinout/spec RASTER (taranmış) datasheet'te
  gerekli — bizim vaka çoğunlukla vektör → düşük öncelik.
- **pix2tex 🟡** — MIT, denklem için tek temiz seçenek; torch. Bundle edilemez → opsiyonel.
- **DatasheetExtractor 🔴** — AGPL viral, kapalı exe'ye giremez. Ayrıca tabula-py Java gerektirir.
- **uConfig 🔴** — GPL viral + Qt GUI. Kod link edilemez; sadece "magic rules" pinout YÖNTEMİ ders.

## 3. Best-of Sentezi (araç → tek güçlü yan → s2p'de eşleme)

| Araç | Çalınacak tek güçlü yan | s2p'de eşleme |
|---|---|---|
| pdfplumber | char-pozisyon tabanlı kolon hizalama (vendor-agnostik) | **Specs Section** — `_parametric_tables`'ı değiştir/güçlendir |
| uConfig | pin no ↔ etiket eşleme "magic rules" (blok sıralama) | **Pinout Section** — `_pin_functions` genişletme YÖNTEMİ |
| docling | TableFormer okuma-sırası + karmaşık tablo | opsiyonel "derin mod" (dış venv), default değil |
| pix2tex | denklem görseli → LaTeX | opsiyonel denklem eki; default narration korunur |
| datasheet-cli | pinout/spec → temiz JSON şema | çıktı JSON şema tasarımına referans |

## 4. Adopt-vs-Build Kararı

- **Specs (Elektriksel) → ADOPT pdfplumber** (MIT, hafif, saf-python). char-pozisyon binning'i
  vendor-agnostik; bespoke kodu tek battle-tested bağımlılıkla değiştirir → Infineon/ST/MPS/ADI
  genellemesi burada gelir. torch yok, exe şişmez. *Alternatif: mevcut `_parametric_tables`'ı bitir
  (BUILD) — ama pdfplumber aynı işi daha dayanıklı yapar, yeniden-icat etme.*
- **Pinout → BUILD** (`_pin_functions` genişlet), uConfig magic-rules + pdfplumber tablo YÖNTEMİ
  referans. uConfig kodu GPL → link yok.
- **Eğriler → BUILD** (pdfcurves korunur; torch-free, zaten güçlü). Adopt YOK.
- **Eğri yorumu → BUILD** (kural-tabanlı; Section'a `interpret()` olarak taşı). Opsiyonel LLM sonra.
- **Tasarım hesapları/denklem → REFERENCE / opsiyonel** — pix2tex MIT ama torch → bundle edilemez.
  Default: mevcut dürüst narration. İsteğe bağlı: kullanıcı `pip install pix2tex` yaparsa devreye giren
  opsiyonel eklenti (exe-dışı).
- **docling → REFERENCE / opsiyonel derin-mod** — MIT + SOTA ama torch. Bundle default DEĞİL;
  power-user için dış-pipeline kancası bırakılabilir.

## 5. Section Sözleşmesi Bağlama Planı

Her bölüm `Section` (RAF-node benzeri) olur: `extract(ctx)→validate→score(high/med/low+sebep)→
interpret→cite(page,bbox)`. `ctx` = paylaşılan parse bağlamı (doc + metin + **pdfplumber tablo
cache** + sayfa görselleri). Rapor/GUI/Excel tek sözleşmeden büyür.

- `IdentitySection` (BUILD, regex) · `PinoutSection` (BUILD+pdfplumber tablo) ·
  `SpecSection` (ADOPT pdfplumber) · `CurveSection` (BUILD pdfcurves + yorum) ·
  `DesignProcedureSection` (BUILD narration + opsiyonel pix2tex) · `LayoutSection` (BUILD metin).
- Her Section'a golden V&V: TI TPS61088/TPS62743 = regresyon tabanı; Infineon/ST/MPS/ADI = genelleme.
  "çalışıyor ≠ doğru" — SpecSection için sanity: VIN.min<VIN.max, birim tutarlılığı, TYP∈[MIN,MAX].

## ✅ Empirik Doğrulama (2026-08-21, `scripts/probe_pdfplumber.py`)

pdfplumber 0.11.10, `lines` stratejisi, 4 gerçek datasheet — SpecSection adopt kararının kanıtı:

| Datasheet | Vendor | Sonuç |
|---|---|---|
| TPS61088 | TI | ✅ MIN/TYP/MAX ayrı hücre; ⚠️ param-adı/sembol satır-sarması (VIN_UVLO alt-simge alt satıra kayıyor) → rejoin gerek |
| TPS62743 | TI | ✅ değer kolonları ayrı |
| **NCP164** | **onsemi (TI-dışı)** | ✅✅ MIN/TYP/MAX **temiz ayrıldı** (VADJ: 1.078/1.1/1.122; VDO: —/170/295). Out-of-the-box genelleme kanıtı |
| LTC3780 | ADI | ❌ **kapsam dışı**: PDF 1 sayfa, 0 metin, 10554 vektör-çizim = fontlar outline'a çevrilmiş, metin katmanı YOK. Hiçbir metin aracı (pymupdf dahil) okuyamaz → yalnız OCR |

**Karar doğrulandı:** pdfplumber `lines` MIN/TYP/MAX'i regex'in yapamadığı şekilde ayırıyor VE
TI-dışı onsemi'de sıfır ayar ile çalışıyor. İki takip işi:
1. **Param-adı satır-sarması rejoin** (TI alt-simgeleri alt satıra kayıyor) — post-process heuristic.
2. **MIN/MAX-only tablolar** (TYP yok, ör. Recommended Operating Conditions) — zarif ele al.
3. **Outline/raster PDF** (LTC3780) — dürüst kapsam-dışı; opsiyonel OCR fallback (Tesseract zaten kurulu,
   global file-io skill) — bundle-dışı ayrı yol.

## ⚠️ Lisans Uyarısı
- **AGPL/GPL (DatasheetExtractor, uConfig) → kapalı exe'ye LINK EDİLEMEZ.** Yalnız yöntem-referansı
  (temiz-oda yeniden yazım). Kod kopyalanmaz.
- **İkinci kapı = torch bundle ağırlığı.** docling/TATR/pix2tex MIT (lisans temiz) ama torch → default
  exe'ye giremez; opsiyonel dış-pipeline.

## Kaynaklar
- https://github.com/docling-project/docling · https://arxiv.org/html/2408.09869v5
- https://github.com/jsvine/pdfplumber · https://github.com/camelot-dev/camelot
- https://github.com/microsoft/table-transformer
- https://github.com/lukas-blecher/LaTeX-OCR (MIT)
- https://github.com/PySpice-org/DatasheetExtractor (AGPL-3.0)
- https://github.com/Robotips/uConfig (GPL-3.0)
- https://crates.io/crates/datasheet-cli · https://github.com/octoco-ltd/sheetsdata-mcp
- https://dev.to/martin_pdfexcel/tabula-vs-camelot-vs-pdfplumber-in-2026-which-python-library-actually-wins-22kn
