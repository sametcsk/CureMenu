<div align="center">
  <h1>🍽️ CureMenu</h1>
  <p><strong>Kronik Hastalıklara Özel Kişiselleştirilmiş Beslenme ve Karar Motoru</strong></p>
  <p>
    <i>🚀 <b>Proje Durumu:</b> Bu proje, <strong>TÜBİTAK BİGG (Bireysel Genç Girişim)</strong> programı kapsamında Ar-Ge niteliğiyle geliştirilmektedir.</i>
  </p>
</div>

---

## 💡 Ürün Fikri ve Açıklaması

**CureMenu**, Türkiye'de milyonlarca insanın mücadele ettiği diyabet, çölyak, hipertansiyon gibi kronik hastalıklara özel olarak geliştirilmiş yapay zeka destekli bir platformdur. Türk mutfağının yapısını analiz eder ve kullanıcının (veya tüm ailenin) sağlık profiline uygun güvenli menüler sunar. Evde her gün yaşanan *"Ne pişirsem?"* ve *"Bana uygun mu?"* stresini tamamen ortadan kaldırmayı hedefler.

## ✨ Öne Çıkan Özellikler

- 🛡️ **Kişiselleştirilmiş Sağlık Profili:** Hastalıklar, alerjiler ve demografik bilgilere göre detaylı profil yönetimi.
- 👨‍👩‍👧‍👦 **Aile Modu:** Farklı bireylerin sağlık durumlarını aynı anda analiz ederek **herkesin ortak yiyebileceği** yemekleri bulan akıllı kesişim algoritması.
- 🤖 **CureBot AI (LangGraph):** Çoklu ajan sistemi (Multi-Agent). Öneri üretir, tıbbi güvenlik bariyeri (Guardrail) ile denetler, tarif ve alışveriş listesi sunar.
- 📅 **Haftalık Plan:** Profil sınırlarına %100 uyumlu, 7 günlük kişiselleştirilmiş beslenme programı.
- 📱 **Menü Tarayıcı:** Restoran menüsünü URL veya QR kod ile okuyup tıbbi profilinize göre anında filtreler.
- 💰 **Akıllı Bütçe (Ekonomist Ajan):** Haftalık plana göre tahmini fiyat bantları üzerinden market bütçesini çıkarır.

---

## 🎯 Hedef Kitle

- Kendisinde veya ailesinde kronik sağlık sorunları olan bireyler.
- "Aileme sağlıklı ve uygun ne pişirebilirim?" diye düşünen çalışan ebeveynler.
- Dışarıda yemek yerken menüde kaybolan, hastalığına uygun güvenilir yemek arayan herkes.

---

## 🛠️ Teknolojik Altyapı

| Katman | Teknoloji |
|--------|-----------|
| **Web Arayüzü** | Vanilla JS, HTML, Tailwind CSS (`frontend/`) |
| **Backend API** | FastAPI, Python 3.12 (`api.py`) |
| **AI Motoru** | LangGraph, Google Gemini, Tavily |
| **Hafıza & RAG** | ChromaDB (Geri bildirimler ve tahlil hafızası) |
| **Veritabanı** | SQLite (Profiller, loglar) + Alembic Migration |
| **Güvenlik** | Tıbbi Guardrail, Rate Limiting, Pydantic Structured Outputs |

<details>
<summary><b>Mimarinin Çalışma Şeması (Tıklayıp Açabilirsiniz)</b></summary>

```text
Kullanıcı (Tarayıcı / Arayüz)
    │
    ▼
FastAPI ──→ SQLite (Profiller, Karar/Audit Logları)
    │
    ▼
LangGraph Pipeline (Multi-Agent)
    ├── 1. Yönlendirici (Niyet analizi)
    ├── 2. Beslenme Uzmanı (Öneri üretimi)
    ├── 3. Denetmen (Tıbbi Guardrail / Governance)
    └── 4. Şef (Tarif & Web Arama)
    │
    ▼
ChromaDB (Kişisel tercihler ve geri bildirimler)
```
</details>

---

## 🚀 Kurulum ve Çalıştırma

### Gereksinimler
- **Python 3.11 veya 3.12** (Not: 3.14 henüz desteklenmez)
- Google Gemini API Anahtarı
- Tavily API Anahtarı (Tarif aramaları için)

### Başlangıç Adımları

```bash
# 1. Repoyu klonlayın
git clone https://github.com/sametcsk/CureMenu.git
cd CureMenu

# 2. Sanal ortamı kurun ve aktif edin
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

# 3. Bağımlılıkları yükleyin
pip install -r requirements.txt

# 4. Çevre değişkenlerini ayarlayın
copy .env.example .env        # Windows
# cp .env.example .env        # macOS / Linux
# .env dosyasını açıp API anahtarlarınızı girin.

# 5. Uygulamayı başlatın
python run.py
```

Tarayıcınızda açın: **http://localhost:8000**
- Ana Sayfa / Giriş: `/`
- Uygulama Arayüzü: `/dashboard`

---

## 🧪 Testler ve CI/CD

Proje geniş kapsamlı bir test altyapısına sahiptir:
```bash
pytest tests/ -v
```
**Kapsanan Senaryolar:** Profil kayıt/okuma, Guardrail karar mantığı, API smoke testleri (login, profil, chat mock), Tahlil (PDF) validasyonları ve Data Privacy Redaction testleri.  
*Testler GitHub Actions üzerinden CI/CD pipeline'ı ile her commit'te otomatik çalıştırılır.*

---

## 🔐 Veri Gizliliği ve İzlenebilirlik (Governance)

CureMenu, klinik standartlarda bir yapı hedeflenerek tasarlanmıştır:
- Kullanıcı profilleri, loglar (**SQLite**) ve vektör geri bildirimler (**ChromaDB**) tamamen yerel tutulur.
- Kritik numaralar, IBAN veya özel API anahtarları `Data Redaction` katmanından geçer.
- Sistem tarafından alınan her tıbbi karar, sistemde bir **Event** (örn: `InputGuardrailBlocked`) olarak loglanır. Bunlar Dashboard üzerindeki *İzlenebilirlik (Governance)* ekranından şeffaf bir şekilde incelenebilir.

---

## 🗺️ Yol Haritası (Roadmap)

- [x] Multi-Agent Yapay Zeka Mimarisi
- [x] Geçmiş Hafıza ve Geri Bildirim Sistemi
- [x] Kamera ile Menü Tarama (OCR)
- [x] Ekonomi & Bütçe Ajanı Entegrasyonu
- [x] Klinik Guardrail ve Operasyonel Güvenlik Eventleri
- [ ] Yapısal Akıllı Sepet (Structured Smart Grocery) Modülü *(Devam Ediyor)*
- [ ] Lokasyon Bazlı Restoran Önerisi (Top 10)
- [ ] Giyilebilir Teknoloji (Wearable) Entegrasyonu
