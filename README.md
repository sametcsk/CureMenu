# CureMenu 🍽️

## Ürün Fikri ve Açıklaması

CureMenu, Türkiye'de milyonlarca insanın mücadele ettiği diyabet, çölyak, hipertansiyon gibi kronik hastalıklara özel olarak geliştirilmiş **Kişiselleştirilmiş Beslenme ve Karar Motorudur**. Türk mutfağının yapısını analiz eder ve kullanıcının (veya tüm ailenin) sağlık profiline uygun menüler sunar. Evde her gün yaşanan "Ne pişirsem?" ve "Bana uygun mu?" stresini ortadan kaldırmayı hedefler.

## Ürün Özellikleri

- **Kişiselleştirilmiş Sağlık Profili:** Hastalıklar, alerjiler ve demografik bilgilere göre detaylı profil oluşturma.
- **Aile Modu:** Farklı bireylerin sağlık durumlarını aynı anda analiz ederek **herkesin ortak yiyebileceği** yemekleri bulan kesişim algoritması.
- **CureBot AI:** LangGraph tabanlı çoklu ajan sistemi — öneri üretir, tıbbi guardrail ile denetler, tarif ve alışveriş listesi sunar.
- **Haftalık Plan:** 7 günlük kişiselleştirilmiş beslenme programı.
- **Menü Tarayıcı:** Restoran menüsünü URL veya QR kod ile okuyup profiline göre filtreler.
- **Ekonomist Ajan:** Haftalık plana göre güncel market fiyatlarıyla bütçe hesabı.

## Hedef Kitle

- Kendisinde veya ailesinde kronik sağlık sorunları olan bireyler.
- "Aileme sağlıklı ve uygun ne pişirebilirim?" diye düşünen ev hanımları ve çalışan ebeveynler.
- Dışarıda yemek yerken menüde kaybolan, hastalığına uygun güvenilir yemek arayan herkes.

---

## Kurucu & Geliştirici

- **Samet** (Founder & AI Developer)

---

## Teknolojik Altyapı

| Katman | Teknoloji |
|--------|-----------|
| **Web Arayüzü** | HTML / Tailwind CSS / JavaScript (`frontend/`) |
| **Backend API** | FastAPI (`api.py`) |
| **AI Motoru** | LangGraph + Google Gemini |
| **Hafıza** | ChromaDB (kullanıcı geri bildirimleri) |
| **Veritabanı** | SQLite (`healmenu.db`) |
| **Güvenlik** | Tıbbi guardrail döngüsü, rate limiting, SSRF koruması |

### Mimari

```
Kullanıcı (Tarayıcı)
    ↓
FastAPI (api.py) ──→ SQLite (profiller, loglar)
    ↓
LangGraph Pipeline
    ├── Yönlendirici (niyet analizi)
    ├── Beslenme Uzmanı (yemek önerisi)
    ├── Denetmen (tıbbi guardrail)
    └── Şef (tarif + Tavily arama)
    ↓
ChromaDB (geçmiş geri bildirimler)
```

> **Not:** `app.py` ve `pages/` altındaki Streamlit arayüzü erken prototip içindir. Üretim ve demo giriş noktası **FastAPI + web arayüzüdür**.

---

## Kurulum ve Çalıştırma

### Gereksinimler

- **Python 3.11 veya 3.12** (3.14 desteklenmez — `pyproject.toml` bakın)
- Google Gemini API anahtarı
- Tavily API anahtarı (tarif arama ve ekonomist ajan için)

### Adımlar

```bash
git clone <repo-linkiniz>
cd healmenu

python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

pip install -r requirements.txt

# Ortam değişkenlerini ayarla
copy .env.example .env          # Windows
# cp .env.example .env        # macOS / Linux
# .env dosyasına API anahtarlarını yaz

# Uygulamayı başlat (tek giriş noktası)
python run.py
```

Tarayıcıda aç: **http://localhost:8000**

- Giriş: `/`
- Dashboard: `/dashboard`

Alternatif başlatma:

```bash
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

### Ortam Değişkenleri (`.env`)

| Değişken | Açıklama |
|----------|----------|
| `GOOGLE_API_KEY` | Google Gemini API anahtarı |
| `TAVILY_API_KEY` | Tavily web arama API anahtarı |

---

## Testler

```bash
pytest tests/ -v
```

Test kapsamı:
- Profil kayıt / okuma (SQLite)
- Guardrail karar mantığı (LangGraph)
- API smoke testleri (login, profil, chat mock)

CI: GitHub Actions üzerinde Python 3.11 ve 3.12 ile otomatik çalışır (`.github/workflows/ci.yml`).

---

## Veritabanı Migration Notu

Bu projede mevcut SQLite şeması uzun süre `src/database.py` içindeki raw SQL `CREATE TABLE` akışıyla yönetildi. Alembic altyapısı bu mevcut şemayı manuel baseline olarak tanıtmak için eklendi; autogenerate kullanılmamalıdır.

Temel komutlar:

```bash
alembic upgrade head
alembic current
alembic revision -m "kisa_aciklama"
```

Notlar:
- İlk migration manuel baseline'dır ve destructive işlem içermez.
- Runtime uyumluluğu için `src/database.py` içindeki startup tablo oluşturma akışı bu fazda korunur.
- Bundan sonraki production şema değişiklikleri Alembic migration dosyalarıyla yapılmalıdır.

---

## Governance Event Schema

Yeni audit event metadata alanları geriye uyumlu şekilde `schema_version=governance_event.v1` ile normalize edilir.

- `event_name`: Event'in kanonik adı.
- `category`: Event sınıfı (`routing`, `policy`, `rule`, `medication_safety`, `grocery`, `retrieval`, `generation`, `privacy`, `system`).
- `severity`: Operasyonel önem seviyesi (`info`, `low`, `medium`, `high`, `critical`).
- `decision_effect`: Karara etkisi (`none`, `allow`, `caution`, `block`, `review_required`).
- `blocking` / `review_required`: KPI ve audit timeline için boolean karar bayrakları.
- `source_component`: Event'i üreten bileşen.

Eski metadata alanları silinmez; yeni alanlar yalnızca yorumlamayı standartlaştırmak için eklenir.

---

## Geliştirme Yol Haritası (Roadmap)

- **Multi-Agent Yapay Zeka Mimarisi** ✅ (MVP tamamlandı)
- **Geçmiş Hafıza ve Geri Bildirim Sistemi** ✅ (ChromaDB aktif)
- **Kamera ile Menü Tarama (OCR)** ✅ (Gemini Vision)
- **Sağlık & Bütçe Optimizasyon Ajanı** ✅ (Ekonomist Ajan)
- **Lokasyon Bazlı Restoran Önerisi (Top 10)** — planlanıyor
- **Giyilebilir Teknoloji (Wearable) Entegrasyonu** — planlanıyor
- **Doktor / Diyetisyen Raporlama Modülü (PDF)** — planlanıyor

---

## Veri Gizliliği

- Kullanıcı profilleri ve etkileşim logları **yerel SQLite** veritabanında tutulur.
- Geri bildirim vektörleri **yerel ChromaDB** klasöründe saklanır.
- `.env` dosyası ve veritabanı dosyaları `.gitignore` ile korunur; commit edilmemelidir.
- MVP'de sağlık ve audit kayıtları izlenebilirlik için tutulur.
- Audit/log kayıtlarına yazılan serbest metin ve metadata alanlarında e-posta, telefon, TC kimlik benzeri numara, IBAN ve token/API anahtarı gibi doğrudan tanımlayıcılar redaction'dan geçirilir.
- Production öncesinde veri saklama süresi, kullanıcı silme talebi, veri export süreci ve redaction kapsamı resmi politika olarak netleştirilmelidir.

---

## Lisans

TÜBİTAK BIGG kapsamında geliştirilmektedir.
