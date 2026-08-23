# Dil / Otomatik Çeviri — Ertelenen Karar (sonra bakılacak)

Durum: **ERTELENDİ.** Karar verildi, uygulama sonraya bırakıldı.

## Seçilen yön
- **Birincil: DeepL API** — en yüksek TR kalitesi + belge (PDF/DOCX) çevirisi.
  - **DeepL API Free: 500.000 karakter/ay ücretsiz**, kredi kartı yok, günlük limit yok.
  - Bu araçta yalnızca çıkarılan snippet'ler (pin açıklaması, features, figür başlıkları,
    layout kuralları) çevrileceği için birkaç KB/datasheet → ücretsiz kotaya rahat sığar.
  - Gereken: https://www.deepl.com/pro-api → ücretsiz key → env `DEEPL_API_KEY`.
- **Offline fallback (opsiyonel):** Argos Translate (MIT) veya OPUS-MT `opus-mt-tc-big-en-tr`
  (CC-BY, CTranslate2). Key yoksa devreye girer. (NLLB-200 KULLANMA — CC-BY-NC, ticari değil.)

## Uygulanacak mimari (mevcut plotting.py/figures.py deseniyle)
- `analysis/translate.py`: `available(backend)`, `translate(texts, target="tr", backend="auto")`.
  - auto: DeepL key varsa DeepL → yoksa offline model → yoksa glossary-only → yoksa orijinal.
  - `(hash, backend) → çeviri` JSON cache; tekrar çeviri maliyeti sıfır.
- **Terim sözlüğü (glossary) şart:** quiescent current→sükunet akımı, reference voltage→
  referans gerilimi, soft-start→yumuşak başlatma, feedback→geri besleme, ... MT'den önce/sonra
  uygulanır ki teknik terimler bozulmasın.
- `analyze_pdf(..., lang="tr")` parametresi; `_enrich_with_sections` / `_render_report`
  çevrilmiş snippet'leri kullanır. GUI'ye dil + backend seçici.

## Kapsam kararı (netleştirilecek)
- Şu an: bizim ürettiğimiz anlatım Türkçe (offline, deterministik); datasheet birebir metni
  İngilizce. Çeviri eklenince datasheet snippet'leri de hedef dile çevrilecek.
- Varsayılan dil (Türkçe / PDF'e göre otomatik / İngilizce) sonra seçilecek.

## Eğitim hedefi notu
"Gerçek kazanım" için LLM (yerel Ollama veya bulut) sadece çevirmez, öğrenci için açıklar da —
birebir metni Türkçeleştir + kısa öğretici not ekle. En çok değeri bu katar.
