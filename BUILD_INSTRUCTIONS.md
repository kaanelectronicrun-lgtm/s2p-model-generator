# S2P Tool - EXE Derleme Yönergeleri

## Hızlı Başlangıç (Windows)

### Seçenek 1: Otomatik Derleme (Önerilen)

1. **Gerekli Yazılım:**
   - Python 3.8+ ([python.org](https://www.python.org/downloads/) adresinden indirin)
   - Git (isteğe bağlı)

2. **Adım 1: Dizine Gidin**
   ```bash
   cd "C:\Users\Excalibur\Desktop\OBS_KAAN\Kaan AKCAN\Uygulamalar\s2p"
   ```

3. **Adım 2: Bağımlılıkları Yükleyin**
   ```bash
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```
   
   > **Not:** İlk kez yükleniyorsa 10-15 dakika alabilir.

4. **Adım 3: GUI'yi Test Edin**
   ```bash
   python gui_main.py
   ```
   
   GUI açılırsa, bağımlılıklar düzgün yüklüdür.

5. **Adım 4: EXE Oluşturun**
   ```bash
   python build_exe.py
   ```
   
   > **Bekleme Süresi:** 2-5 dakika (ilk kez daha uzun olabilir)
   > **Çıktı:** `releases/s2p-1.0.0-win64.exe`

---

## Seçenek 2: Komut Satırı ile Doğrudan PyInstaller

Eğer `build_exe.py` çalışmazsa:

```bash
pyinstaller --onefile --windowed ^
  --name s2p-1.0.0-win64 ^
  --distpath releases ^
  --add-data "src/s2p_tool:s2p_tool" ^
  --hidden-import=numpy ^
  --hidden-import=PyQt5 ^
  --hidden-import=PyQt5.QtCore ^
  --hidden-import=PyQt5.QtGui ^
  --hidden-import=PyQt5.QtWidgets ^
  gui_main.py
```

---

## Sorun Giderme

### Hata: "ModuleNotFoundError: No module named 'PyQt5'"

**Çözüm:**
```bash
python -m pip install PyQt5 --upgrade
```

### Hata: "PyInstaller not found"

**Çözüm:**
```bash
python -m pip install pyinstaller --upgrade
```

### Hata: "No module named 's2p_tool'"

**Çözüm:** Dosyaların düzgün olduğundan emin olun:
- `src/s2p_tool/` klasörü var mı?
- `src/s2p_tool/__init__.py` dosyası var mı?
- `gui_main.py` kök dizinde var mı?

### EXE çok büyük (>200MB)

Bu normal! PyQt5, numpy ve diğer bağımlılıklar ağır yazılımlardır.
Optimize etmek için:

```bash
pyinstaller ... --exclude-module matplotlib
```

---

## Derleme Sonrasında

### ✓ Başarılı Derleme

```
✓ SUCCESS: s2p-1.0.0-win64.exe (185.3 MB)

You can now run:
  releases/s2p-1.0.0-win64.exe
```

### EXE'yi Çalıştırın

1. **Windows Explorer'dan:**
   - `releases/s2p-1.0.0-win64.exe` dosyasına çift tıklatın

2. **Komut satırından:**
   ```bash
   releases\s2p-1.0.0-win64.exe
   ```

3. **Batch launcher'dan (isteğe bağlı):**
   - `releases/s2p-gui.bat` dosyasını çalıştırın

---

## Ek Seçenekler

### Özel İcon Eklemek

```bash
pyinstaller ... --icon=icon.ico gui_main.py
```

### İcon Oluşturmak

[ico-convert.com](https://icoconvert.com/) adresinde PNG → ICO dönüştürün.

### Konsol Penceresini Göstermek (Hata Ayıklama)

```bash
pyinstaller --onefile --name s2p-1.0.0-win64 ... gui_main.py
# (--windowed'ı kaldırın)
```

---

## Versiyon Güncellemesi

EXE'yi yeniden derlemek için versiyonu güncelleyin:

**`src/s2p_tool/__init__.py`:**
```python
__version__ = "1.0.1"  # Eski: "1.0.0"
```

Sonra:
```bash
python build_exe.py
```

Yeni EXE otomatik olarak `releases/s2p-1.0.1-win64.exe` adıyla oluşturulacak.

---

## Kaynak Kodlar

**Ana Dosyalar:**
- `gui_main.py` - GUI giriş noktası
- `src/s2p_tool/gui.py` - PyQt5 arayüzü
- `src/s2p_tool/cli.py` - Komut satırı arayüzü
- `src/s2p_tool/pipeline.py` - İşleme mantığı

**Derleme Araçları:**
- `build_exe.py` - PyInstaller otomasyonu
- `make_release.py` - Kaynak ZIP paketi oluşturucu

---

## Sistem Gereksinimleri

| Gereklilik | Min | Önerilen |
|-----------|-----|----------|
| **Windows** | Windows 7 | Windows 10+ |
| **Python** | 3.8 | 3.10+ |
| **Disk** | 500 MB | 1 GB+ |
| **RAM** | 2 GB | 4 GB+ |
| **İnternet** | (kurulum sırasında) | |

---

## Notlar

- EXE **Python yüklü olmadan** çalıştırılabilir
- Tüm bağımlılıklar EXE'ye gömülüdür
- Birden fazla dişli işlem desteklenir
- S2P, SPICE ve PDF özellikleri kullanılabilir

---

## İletişim / Destek

- **GitHub Issues:** [link burada]
- **Email:** [email burada]

---

**Başarılar! 🚀**
