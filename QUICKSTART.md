# S2P Tool GUI - Hızlı Başlangıç

## 🎯 Ne Yapıldı?

S2P Tool'unuz için profesyonel bir **PyQt5 tabanlı GUI arayüzü** ve **EXE oluşturucu** oluşturdum.

### Eklenen Dosyalar:

```
s2p/
├── src/s2p_tool/
│   └── gui.py                    ← PyQt5 arayüzü (tam özellik)
├── gui_main.py                   ← GUI giriş noktası
├── run_gui.bat                   ← GUI'yi kolayca çalıştırmak için
├── build_exe.py                  ← PyInstaller otomasyonu (Python)
├── build_exe.bat                 ← PyInstaller otomasyonu (Batch)
├── BUILD_INSTRUCTIONS.md         ← Detaylı derleme yönergeleri
├── QUICKSTART.md                 ← Bu dosya
└── requirements.txt              ← Güncellenmiş (PyQt5 + PyInstaller ekli)
```

---

## ⚡ Hızlı Başlangıç (30 saniye)

### Seçenek A: GUI'yi Test Etmek (Önerilen ilk adım)

1. **GUI'yi çalıştırın:**
   ```bash
   run_gui.bat
   ```
   veya:
   ```bash
   python gui_main.py
   ```

2. GUI arayüzü açılırsa, her şey yolunda!

### Seçenek B: EXE Oluşturmak

1. **Batch dosyasını çalıştırın:**
   ```bash
   build_exe.bat
   ```
   
   veya Python ile:
   ```bash
   python build_exe.py
   ```

2. **Bekleme:** 2-5 dakika (ilk kez daha uzun)

3. **Sonuç:** `releases/s2p-1.0.0-win64.exe`

---

## 🖥️ GUI Özellikleri

### 📋 "Model Üret" Sekmesi
- ✅ Tek/çok JSON dosyası seçimi
- ✅ Klasör içindeki tüm dosyaları toplu işleme
- ✅ Parametre ayarları (Z0, frekans aralığı)
- ✅ Gerçek zamanlı işlem günlüğü
- ✅ Çıktı klasörü seçimi

### 📥 "S2P İçeri Aktar" Sekmesi
- ✅ Vendor S2P dosyalarını içeri aktarma
- ✅ Bileşen türü seçimi (kapasitor/inductor)
- ✅ SPICE netlist ve rapor oluşturma

### ⚙️ "Ayarlar" Sekmesi
- ✅ Bilgi ve özellikler
- ✅ Çıktı dosyaları hakkında
- ✅ Desteklenen formatlar

### ❓ "Yardım" Sekmesi
- ✅ Detaylı kullanım kılavuzu
- ✅ JSON parametre örneği
- ✅ Açıklamalar ve notlar

---

## 📂 Proje Yapısı

```
Giriş (Input)
    ↓
┌─────────────────────────┐
│  GUI Arayüzü (PyQt5)    │
│  - Dosya seçimi         │
│  - Parametre ayarı      │
│  - Gerçek zamanlı log   │
└─────────────────────────┘
    ↓
┌─────────────────────────┐
│  İşleme Mantığı         │
│  - pipeline.py          │
│  - cli.py (backend)     │
└─────────────────────────┘
    ↓
Çıktı (Output)
    S2P, SPICE, Rapor
```

---

## 🔧 Sistem Gereksinimleri

| Gereklilik | Değer |
|-----------|-------|
| **Windows** | Windows 7+ |
| **Python** | 3.8+ |
| **Disk** | 500 MB (kaynaklar) + 500 MB (derlenmiş) |
| **RAM** | 2 GB+ |

---

## 📖 Yaygın Görevler

### 1️⃣ GUI'yi Çalıştırmak

```bash
# Seçenek A: Batch dosyası
run_gui.bat

# Seçenek B: Komut satırı
python gui_main.py

# Seçenek C: Kök dizindeki run.py (CLI)
python run.py components/example_cap.json -o outputs
```

### 2️⃣ EXE Oluşturmak

```bash
# Seçenek A: Batch dosyası (önerilen)
build_exe.bat

# Seçenek B: Python
python build_exe.py

# Seçenek C: Doğrudan PyInstaller
pyinstaller --onefile --windowed ^
  --name s2p-1.0.0-win64 ^
  --add-data "src/s2p_tool:s2p_tool" ^
  --hidden-import=numpy --hidden-import=PyQt5 ^
  gui_main.py
```

### 3️⃣ Bağımlılıkları Yüklemek

```bash
python -m pip install -r requirements.txt
```

### 4️⃣ CLI'yi Kullanmak (GUI Olmadan)

```bash
# Tek dosya
python run.py components/example_cap.json -o outputs

# Çoklu dosya
python run.py "components/*.json" -o outputs

# S2P dosyasını içeri aktar
python run.py --import "path/to/file.s2p" --kind capacitor -o outputs
```

---

## ❌ Sorun Giderme

| Hata | Çözüm |
|------|-------|
| `ModuleNotFoundError: No module named 'PyQt5'` | `pip install PyQt5` |
| `PyInstaller not found` | `pip install pyinstaller` |
| `No module named 's2p_tool'` | `src/s2p_tool/` klasörü kontrol et |
| GUI açılmıyor | `python run_gui.bat` ile komut satırında çalıştır |
| EXE çok büyük (>200MB) | Normal! PyQt5 ve numpy ağır |

**Detaylı sorun giderme:** `BUILD_INSTRUCTIONS.md` dosyasına bakın.

---

## 📝 Dosya Açıklamaları

### `gui.py` (PyQt5 Arayüzü)
- **ProcessWorker:** Arka planda işleme yapan thread
- **S2PGui:** Ana arayüz penceresi
- Sekmeler: Model Üret, S2P İçeri Aktar, Ayarlar, Yardım

### `gui_main.py` (Giriş Noktası)
- PyQt5 uygulamasını başlatır
- `sys.path` düzenlemesi
- `gui.py`'den `main()` fonksiyonunu çalıştırır

### `build_exe.py` (Python Builder)
- Versiyonu otomatik okur
- PyInstaller komutunu oluşturur
- Derleme sonrası temizlik yapar

### `run_gui.bat` / `build_exe.bat` (Windows Batch)
- Python kurulum kontrolü
- Bağımlılık kontrolü
- Kullanıcı dostu hata mesajları

---

## 🚀 EXE Dağıtımı

Derleme başarılı olursa:

```
releases/
├── s2p-1.0.0-win64.exe    ← ANA DOSYA (185 MB)
└── s2p-gui.bat            ← Launcher (isteğe bağlı)
```

### Dağıtım için:

1. **Tek dosya:** `s2p-1.0.0-win64.exe` yeterli
2. **Kurulum paketi:** [InnoSetup](https://jrsoftware.org/isinfo.php) ile MSI oluştur
3. **GitHub Releases:** Sürüm sayfasına yükle

---

## 📞 Teknik Detaylar

### PyQt5 Seçilme Nedeni:
- ✅ Modern, profesyonel görünüm
- ✅ Platform bağımsız (Windows, Linux, Mac)
- ✅ Geniş widget koleksiyonu
- ✅ Arka planda işleme desteği (QThread)
- ✅ NumPy entegrasyonu kolay

### PyInstaller Seçilme Nedeni:
- ✅ Tek `.exe` dosya oluşturur
- ✅ Python yüklü olmayan makinelerde çalışır
- ✅ Bağımlılıkları otomatik ekler
- ✅ Basit ve hızlı

---

## 📚 İleri Konular

### İcon Değiştirmek
```bash
# icon.ico dosyası hazırla
# build_exe.py'ye ekle:
# "--icon=icon.ico"
```

### Sürüm Güncelleme
`src/s2p_tool/__init__.py`:
```python
__version__ = "1.0.1"  # Değiştir
```

### Konsol Göstermek (Hata Ayıklama)
`build_exe.py`'de `--windowed` kaldır.

---

## ✅ Denetim Listesi

- [ ] Python 3.8+ yüklü?
- [ ] `python run_gui.bat` çalışıyor mu?
- [ ] `python build_exe.bat` tamamlandı mı?
- [ ] `releases/s2p-*-win64.exe` var mı?
- [ ] EXE çalıştırıldığında GUI açılıyor mu?

Tüm kutular işaretlendiğinde, hazırsınız! 🎉

---

## 📞 Destek

Sorular ve sorunlar için:
1. `BUILD_INSTRUCTIONS.md` dosyasını kontrol et
2. Komut satırında `python -V` ile Python sürümü doğrula
3. `pip list | findstr PyQt5` ile PyQt5'i kontrol et

---

**Başarılar! Umarım GUI'niz harika bir uygulamadır.** 🚀
