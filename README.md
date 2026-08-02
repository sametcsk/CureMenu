<div align="center">
  <h1>🍽️ CureMenu</h1>
  <p><strong>Profil ve güvenlik kontrolleriyle beslenme karar desteği</strong></p>
  <p>
    <a href="https://github.com/sametcsk/CureMenu/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/sametcsk/CureMenu/actions/workflows/ci.yml/badge.svg"></a>
  </p>
</div>

---

## Ürün Fikri ve Açıklaması

**CureMenu**, ilaç kullanan, alerjisi veya kronik durumu bulunan kişilerin günlük yemek kararlarını profil bilgisi, sınırlı deterministik güvenlik kuralları ve kaynak destekli açıklamalarla destekleyen bir beslenme karar destek prototipidir. Tanı koymaz, tedavi düzenlemez ve sağlık profesyonelinin yerine geçmez.

Evde veya dışarıda yaşanan "Ne yiyebilirim?" sorusuna yardımcı olmak amacıyla önerileri profil, alerji ve bilinen ilaç-besin kurallarıyla kontrol eder. Kapsam dışı, riskli veya belirsiz durumda koşulsuz uygunluk iddiası yerine profesyonel değerlendirme uyarısı üretir.

## Öne Çıkan Özellikler

- **Sağlık Profili & Tahlil PDF Akışı:** Hastalık, alerji ve ilaç bilgileriyle birlikte metin katmanı bulunan laboratuvar PDF'lerinden beslenme bağlamı çıkarır; sonuçlar tanı amacıyla kullanılmaz.
- **Kesişim Odaklı Aile Modu:** Farklı kısıtları olan aile bireyleri için ortak seçenek taslağı üretir ve bilinen çatışmaları işaretler.
- **Güvenlik Kontrolleri:** Üretken yapay zeka çıktısını sınırlı deterministik kurallar ve denetim akışıyla kontrol eder; riskli sonucu engeller, belirsiz sonucu uzman incelemesine yönlendirir.
- **Dinamik Haftalık Plan & Atıştırmalık:** Sağlık profiline göre 7 günlük plan taslağı, öğün alternatifi ve atıştırmalık önerileri üretir.
- **Akıllı Menü Tarayıcı:** URL veya fotoğraftan çıkarılan menü metnini profil kısıtlarıyla karşılaştırır; okunamayan veya belirsiz içerikte uyarı verir.
- **İzlenebilirlik ve Karar Kayıtları (Governance):** Öneri akışındaki kaynak, kural ve tahmini risk kayıtlarını olay zinciriyle saklar; bu kayıtlar klinik doğruluk skoru değildir.
- **Bütçe Optimizasyonu:** Sunulan haftalık planın tahmini market maliyetini hesaplayarak aile bütçesine katkı sağlar.

---

## Hedef Kitle

- Kendisinde veya sevdiklerinde kronik sağlık sorunları olan ve günlük beslenme rutinini güvenle yönetmek isteyen bireyler.
- Birden fazla farklı diyeti (örn. glutensiz ve az tuzlu) aynı mutfakta yönetmeye çalışan ebeveynler.
- Özel beslenme hedefi olan ve plan taslağını sağlık profesyoneliyle birlikte değerlendirmek isteyen kullanıcılar. Çocuk, gebelik/emzirme ve böbrek hastalığı gibi yüksek değişkenlik taşıyan profiller uzman incelemesi gerektirir.
- Dışarıda, restoran menülerinde ne yiyeceği konusunda kafa karışıklığı ve korku yaşayan alerjik bireyler.

---

## Teknolojik Altyapı

| Katman | Teknoloji |
|--------|-----------|
| **Web Arayüzü** | Vanilla JS, HTML, CSS (`frontend/` modüler yapısı) |
| **Backend API** | FastAPI, Python 3.11 / 3.12 |
| **Yapay Zeka Mimarisi** | LangGraph (StateGraph tabanlı Multi-Agent Workflow), Google Gemini |
| **Hafıza & RAG** | ChromaDB (Yerel vektör veritabanı, HuggingFace embeddings) |
| **İlişkisel Veritabanı** | SQLite (Profiller, loglar) + Alembic Migration |
| **Kalite ve Güvenlik** | Deterministik kontrol kuralları, kaynak izlenebilirliği, Pydantic Structured Outputs |

---

## Kurulum ve Çalıştırma

### Gereksinimler
- **Python 3.11 veya 3.12**
- Google Gemini API Anahtarı

### Başlangıç Adımları

```bash
git clone https://github.com/sametcsk/CureMenu.git
cd CureMenu

# Sanal ortamı kurun ve aktif edin
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

# Tekrarlanabilir runtime bağımlılıklarını yükleyin
pip install -c constraints.txt -r requirements.txt

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
- Liveness: `/live`
- Readiness: `/ready`

### Kontrollü beta dağıtımı

Depoda Render için bir Blueprint (`render.yaml`) ve güvenli başlangıç scripti
bulunur. Mevcut SQLite + ChromaDB yapısı yalnızca düşük trafikli, tek instance
kapalı beta için kalıcı disk üzerinde çalıştırılmalıdır; çoklu instance veya
genel kullanıma açık production ölçeği için yönetilen ilişkisel ve vektör veri
katmanına geçiş gerekir.

Dağıtım öncesi ortam değişkenleri, migration, yedekleme, rollback ve smoke test
adımları [`docs/DEPLOYMENT_RUNBOOK.md`](docs/DEPLOYMENT_RUNBOOK.md) içinde
belgelenmiştir. Blueprint'in depoda bulunması, canlı ortamın klinik olarak
doğrulandığı veya production'a hazır olduğu anlamına gelmez.

### Sağlık kaynağı izlenebilirliği

Resmî kaynak URL'leri, PDF hash'leri, izin verilen sayfalar ve ilaç-besin kural bağlantıları `data/clinical_evidence_registry.json` dosyasında tek yerde tutulur.

```powershell
# Yerel PDF/hash/sayfa/kural kontrolü
.\.venv\Scripts\python.exe scripts\sync_clinical_evidence.py --check-only

# Kaynak bütünlüğü kontrolü geçerse resmî kapsamlı koleksiyonu yeniden kur
.\.venv\Scripts\python.exe scripts\sync_clinical_evidence.py --rebuild
```

Uzak kaynak değiştiğinde hash otomatik kabul edilmez; insan ve sağlık uzmanı incelemesi gerekir. Kaynak bütünlüğü kontrolü klinik performans kanıtı değildir.

---

## Veri Gizliliği ve Güvenlik Modeli

CureMenu, hassas sağlık verilerini işlediği için sıkı bir veri güvenliği protokolü izler:
- **Kalıcı Veri Katmanı:** Profil, işlem kaydı ve bağlamsal hafıza verileri yapılandırılmış sunucu diskinde SQLite ve ChromaDB ile saklanır. Kapalı beta ortamında bu disk erişimi ve yedekleri ayrıca sınırlandırılmalıdır.
- **Harici Model Sınırı:** Yanıt üretimi için gerekli sınırlı bağlam Google Gemini hizmetine gönderilebilir. Bu nedenle sistem tamamen çevrimdışı veya yalnızca yerel veri işleyen bir ürün olarak değerlendirilmemelidir.
- **Veri Maskeleme (Data Redaction):** Model, izlenebilirlik kaydı ve bağlamsal hafıza yollarında e-posta, telefon, kimlik numarası, IBAN ve token benzeri kişisel tanımlayıcılar maskelenir. Bu kontroller veri minimizasyonu ve açık kullanıcı bilgilendirmesi gereksinimini ortadan kaldırmaz.
- **Sistem İzolasyonu:** API endpointlerinde kimlik doğrulama, rate limiting, güvenlik başlıkları; URL ve dosya akışlarında SSRF, format, boyut ve işlem limitleri uygulanır.

---

## Testler ve CI/CD

```powershell
# Birim ve API testleri
python -m pytest -q tests --ignore=tests/e2e

# Gerçek tarayıcı E2E testleri
python -m pytest -q tests/e2e
```
**Kapsam:** Profil CRUD işlemleri, Guardrail ve kural motoru kararları, API entegrasyonları, PDF analiz validasyonları ve PII (Kişisel Veri) Redaction testleri.  
GitHub Actions, bağımlılık kurulumunu ve iki test paketini Python 3.11 ile 3.12 üzerinde ayrı ayrı doğrular. Otomatik test sonuçları yazılım regresyon kanıtıdır; klinik doğrulama kanıtı değildir.

---

## Yol Haritası (Roadmap)

- [x] Multi-Agent Yapay Zeka Mimarisi
- [x] Geçmiş Hafıza ve Geri Bildirim Sistemi
- [x] Kamera/QR ile Menü Tarama (OCR)
- [x] Ekonomi & Bütçe Ajanı Entegrasyonu
- [x] Klinik Guardrail ve İzlenebilirlik Kayıtları
- [x] Tahlil (PDF) Ayrıştırma ve Bio-Marker Takibi
- [x] Yapısal Akıllı Sepet (Structured Smart Grocery) Modülü
- [x] Kontrollü beta deployment Blueprint'i ve operasyon runbook'u
- [ ] Gerçek HTTPS ortamında deployment ve fiziksel cihaz smoke testi
- [ ] Uzman pilotu ve tanımlı klinik validasyon süreci
- [ ] Lokasyon Bazlı Restoran Önerisi
- [ ] Giyilebilir Teknoloji (Wearable) Entegrasyonu
