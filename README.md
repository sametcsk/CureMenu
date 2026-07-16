<div align="center">
  <h1>🍽️ CureMenu</h1>
  <p><strong>Kronik Hastalıklara Özel Kişiselleştirilmiş Beslenme ve Karar Motoru</strong></p>
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
| **Backend API** | FastAPI, Python 3.12 |
| **Yapay Zeka Mimarisi** | LangGraph (StateGraph tabanlı Multi-Agent Workflow), Google Gemini, Tavily |
| **Hafıza & RAG** | ChromaDB (Yerel vektör veritabanı, HuggingFace embeddings) |
| **İlişkisel Veritabanı** | SQLite (Profiller, loglar) + Alembic Migration |
| **Kalite ve Güvenlik** | Deterministik kontrol kuralları, kaynak izlenebilirliği, Pydantic Structured Outputs |

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
