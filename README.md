<div align="center">
  <h1>🍽️ CureMenu</h1>
  <p><strong>Kronik Hastalıklara Özel Kişiselleştirilmiş Beslenme ve Karar Motoru</strong></p>
</div>

---

## Ürün Fikri ve Açıklaması

**CureMenu**, her türlü kronik hastalık, alerji, tıbbi hassasiyet veya spesifik beslenme hedefi olan bireyler ve aileleri için geliştirilmiş yapay zeka destekli, klinik standartları rehber edinen kapsamlı bir beslenme asistanıdır. Geleneksel "herkese uyan" diyet listeleri yerine, kullanıcının tahlil geçmişini, güncel rahatsızlıklarını, tüm alerjilerini ve ilaç kullanımlarını dikkate alan gelişmiş algoritmik bir altyapı sunar. Sadece hasta bireyleri değil, sağlıklı beslenmek isteyen herkesi kapsar.

Evde veya dışarıda yaşanan "Ne yiyebilirim?" sorununu çözmek amacıyla, çoklu ajan (Multi-Agent) mimarisinden güç alarak sadece yemek önerisi vermekle kalmaz; bu önerileri tıbbi güvenlik kurallarına tabi tutarak güvenilir bir karar destek mekanizması sunar.

## Öne Çıkan Özellikler

- **Gelişmiş Sağlık Profili & Tahlil (PDF) Entegrasyonu:** Hastalık, alerji ve kullanılan ilaç bilgilerinin yanı sıra sisteme yüklenen laboratuvar sonuçlarını okuyarak (OCR/PDF Parsing) risk analizi yapar.
- **Kesişim Odaklı Aile Modu:** Aynı evi paylaşan ancak farklı kronik rahatsızlıkları (örn. biri diyabet, diğeri çölyak) olan aile bireyleri için herkesin güvenle tüketebileceği "ortak payda" yemeklerini hesaplar.
- **Güvenlik Çemberi (Clinical Guardrails):** Üretken yapay zekanın halüsinasyon riskine karşı, her bir öneriyi arka planda denetmen ajanlar ve statik kurallar (örn. ilaç-besin etkileşim listesi) ile kontrol eder. Şüpheli durumları bloklar.
- **Dinamik Haftalık Plan & Atıştırmalık:** Kullanıcının makro dengesine ve sağlık profiline uygun 7 günlük plan oluşturur. Öğün alternatifleri ve anlık atıştırmalık taleplerini yönetir.
- **Akıllı Menü Tarayıcı:** Restorana gidildiğinde QR kod veya fotoğraf üzerinden menüyü okuyarak, menüdeki hangi yiyeceklerin sağlık profilinize uygun olduğunu saniyeler içinde analiz eder.
- **İzlenebilirlik ve Karar Kayıtları (Governance):** Yapay zekanın "neden" o yemeği önerdiğini, hangi kaynakları baz aldığını ve güvenlik skorunu şeffaf bir olay zinciri (event log) ile kullanıcıya sunar.
- **Bütçe Optimizasyonu:** Sunulan haftalık planın tahmini market maliyetini hesaplayarak aile bütçesine katkı sağlar.

---

## Hedef Kitle

- Kendisinde veya sevdiklerinde kronik sağlık sorunları olan ve günlük beslenme rutinini güvenle yönetmek isteyen bireyler.
- Birden fazla farklı diyeti (örn. glutensiz ve az tuzlu) aynı mutfakta yönetmeye çalışan ebeveynler.
- Sporcular, gebeler veya özel beslenme hedefleri olan, kan tahlillerine uygun menü arayanlar.
- Dışarıda, restoran menülerinde ne yiyeceği konusunda kafa karışıklığı ve korku yaşayan alerjik bireyler.

---

## Teknolojik Altyapı

| Katman | Teknoloji |
|--------|-----------|
| **Web Arayüzü** | Vanilla JS, HTML, CSS (`frontend/` modüler yapısı) |
| **Backend API** | FastAPI, Python 3.12 |
| **Yapay Zeka Mimarisi** | LangGraph (StateGraph tabanlı Multi-Agent Workflow), Google Gemini, Tavily |
| **Hafıza & RAG** | ChromaDB (Yerel vektör veritabanı, HuggingFace embeddings) |
| **İlişkisel Veritabanı** | SQLite (Profiller, loglar) + Alembic Migration |
| **Kalite ve Güvenlik** | NeMo benzeri tıbbi Guardrail, Pydantic Structured Outputs |

---

## Kurulum ve Çalıştırma

### Gereksinimler
- **Python 3.11 veya 3.12**
- Google Gemini API Anahtarı
- Tavily API Anahtarı

### Başlangıç Adımları

```bash
git clone https://github.com/sametcsk/CureMenu.git
cd CureMenu

# Sanal ortamı kurun ve aktif edin
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

# Bağımlılıkları yükleyin
pip install -r requirements.txt

# Çevre değişkenlerini ayarlayın
copy .env.example .env        # Windows
# cp .env.example .env        # macOS / Linux
# (Sonrasında .env dosyasını açıp API anahtarlarınızı girin)

# Uygulamayı başlatın
python run.py
```

Tarayıcınızda açın: **http://localhost:8000**
- Ana Sayfa: `/`
- Dashboard: `/dashboard`

---

## Veri Gizliliği ve Güvenlik Modeli

CureMenu, hassas sağlık verilerini işlediği için sıkı bir veri güvenliği protokolü izler:
- **Yerel Depolama:** Kullanıcı profilleri, kişisel bilgiler ve oluşturulan loglar (`SQLite`) ile bağlamsal geri bildirimler (`ChromaDB`) tamamen yerel sunucuda/disk üzerinde tutulur.
- **Veri Maskeleme (Data Redaction):** LLM'e gönderilen istemlerde ve veri tabanına yazılan kalıcı izlenebilirlik (audit) loglarında T.C. Kimlik, Telefon Numarası, IBAN ve API Token gibi kişisel tanımlayıcı veriler regex maskeleme mekanizmaları ile sansürlenir.
- **Sistem İzolasyonu:** API endpointleri Rate Limiting ve SSRF koruma önlemleri ile dış tehditlere karşı korunmuştur. Modellerin dış internet aramaları Tavily üzerinden güvenli sınırlara hapsedilmiştir.

---

## Testler ve CI/CD

Proje geniş kapsamlı bir test altyapısına sahiptir:
```bash
pytest tests/ -v
```
**Kapsam:** Profil CRUD işlemleri, Guardrail ve kural motoru kararları, API entegrasyonları, PDF analiz validasyonları ve PII (Kişisel Veri) Redaction testleri.  
*Tüm testler GitHub Actions üzerinden CI/CD pipeline'ı ile doğrulanmaktadır.*

---

## Yol Haritası (Roadmap)

- [x] Multi-Agent Yapay Zeka Mimarisi
- [x] Geçmiş Hafıza ve Geri Bildirim Sistemi
- [x] Kamera/QR ile Menü Tarama (OCR)
- [x] Ekonomi & Bütçe Ajanı Entegrasyonu
- [x] Klinik Guardrail ve İzlenebilirlik Kayıtları
- [x] Tahlil (PDF) Ayrıştırma ve Bio-Marker Takibi
- [ ] Yapısal Akıllı Sepet (Structured Smart Grocery) Modülü
- [ ] Lokasyon Bazlı Restoran Önerisi
- [ ] Giyilebilir Teknoloji (Wearable) Entegrasyonu

---

## Son Güncellemeler (Son Sprint)

- **Frontend Modülerizasyonu**: UI katmanındaki karmaşıklığı yönetmek adına, tüm API ağ istekleri, markdown işlemleri ve token (yetki) yönetimi `frontend/app.js` içerisinden çıkartılarak global, atomik bir `api-client.js` modülüne taşınmıştır.
- **Dinamik Plan Rejenerasyonu (Cache-Busting)**: Kullanıcı oluşturulan bir planı beğenmeyip "Yeniden Oluştur" dediğinde aynı yemeklerin üretilmesi engellendi. Dinamik "UUID Random Seed" kullanımı, spesifik `CRITICAL REGENERATION REQUEST` talimatı ve esnek temperature değerleriyle yapay zekanın tamamen yepyeni kombinasyonlar ve güvenli yemekler sunması garanti altına alındı.
- **İngilizce Prompt & Türkçe Çıktı Mimarisi**: Çekirdek ajanlar ve API uç noktalarındaki tüm talimat (prompt) metinleri İngilizceye çevrildi. LLM'lerin kendi anadilinde (İngilizce) daha isabetli sağlık muhakemesi (reasoning) yapması, ancak son çıktıyı kusursuz bir Türkçe formunda döndürmesi sağlandı. Böylece tıp terminolojisi denetimi (Guardrails) ve tutarlılık maksimuma çıkarıldı.
