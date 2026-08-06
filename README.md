# CureMenu

Profil ve güvenlik bağlamını bir araya getiren beslenme karar destek prototipi.

[![CI](https://github.com/sametcsk/CureMenu/actions/workflows/ci.yml/badge.svg)](https://github.com/sametcsk/CureMenu/actions/workflows/ci.yml)

## Ürün özeti

CureMenu; kronik hastalığı, alerjisi, ilaç kullanımı veya özel beslenme hedefi olan kişilerin günlük yemek kararlarını daha bilinçli değerlendirmesine yardımcı olur. Sağlık profili, aile profili, haftalık plan, menü analizi, tahlil ve buzdolabı akışlarını tek bir uygulamada birleştirir.

Bu proje bir **beslenme karar destek prototipidir**. Doktorun, diyetisyenin veya başka bir sağlık profesyonelinin yerini almaz; tanı koymaz ve tedavi düzenlemez.

## Problem

“Bugün ne yiyebilirim?” sorusu; kronik hastalık, alerji, ilaç kullanımı ve farklı aile bireylerinin kısıtları bir araya geldiğinde zorlaşır. Evdeki malzemeler, restoran menüleri, tahlil sonuçları ve alışveriş bütçesi çoğu zaman ayrı ayrı değerlendirilir. CureMenu, bu kararları daha anlaşılır ve izlenebilir bir akışta toplamayı hedefler.

## Çözüm

- Profil bilgilerini ve bilinen kısıtları öneri bağlamına taşır.
- Aile modu ile farklı profillerin ortak güvenli seçeneklerini değerlendirir.
- Menü fotoğrafı veya manuel link üzerinden seçenekleri sınıflandırır.
- Metin katmanı bulunan tahlil PDF’lerinden beslenme bağlamı çıkarır.
- Haftalık plan, tarif ve öğün alternatifleri oluşturur.
- Plan alışverişini ve Türkiye geneli tahmini bütçeyi birlikte gösterir.
- Güvenlik kararlarını ve etkileşimleri izlenebilir kayıtlarla destekler.

## Öne çıkan özellikler

- **CureBot:** Profil bağlamında doğal dil ile beslenme sorularını yanıtlar.
- **Sağlık profili:** Hastalık, alerji, ilaç ve hedef bilgilerini yönetir.
- **Aile profili:** Kendim, aile üyesi veya tüm aile kapsamında değerlendirme yapar.
- **Haftalık plan:** Günlük öğünler, tarifler ve güvenlik notları sunar.
- **Menü analizi:** Fotoğraf veya linkten restoran menüsü analizi yapar.
- **Tahlil PDF analizi:** Metin içeren laboratuvar PDF’lerini geçmişe kaydeder.
- **Buzdolabı analizi:** Fotoğraftaki malzemelerden profil uyumlu fikirler üretir.
- **Plan alışverişi ve bütçesi:** Alışveriş listesini yaklaşık bütçeyle birleştirir.
- **Governance ve izlenebilirlik:** Karar kayıtları, kural kontrolleri ve güvenlik durumlarını saklar.

## Mimari

| Katman | Teknoloji / yaklaşım |
|---|---|
| Frontend | Vanilla JavaScript, HTML ve CSS; `frontend/` altında modüler yapı |
| Backend | Python 3.11/3.12, FastAPI, Uvicorn |
| AI/LLM | LangGraph tabanlı akışlar ve Google Gemini |
| RAG/Hafıza | ChromaDB, HuggingFace embeddings ve sınırlı bağlamsal hafıza |
| Veritabanı | SQLite; profil, etkileşim ve karar kayıtları |
| Güvenlik/kalite | Deterministik safety kuralları, Pydantic çıktıları, rate limiting, redaction ve izlenebilirlik |

## Kurulum

Gereksinimler: Python 3.11 veya 3.12.

```powershell
git clone https://github.com/sametcsk/CureMenu.git
cd CureMenu

python -m venv .venv
.venv\Scripts\Activate.ps1

pip install -c constraints.txt -r requirements.txt
copy .env.example .env

# .env içindeki gerekli API anahtarlarını ve ortam ayarlarını düzenleyin.
python run.py
```

macOS/Linux için sanal ortamı `source .venv/bin/activate` ile etkinleştirebilirsiniz.

Uygulama varsayılan olarak [http://localhost:8000](http://localhost:8000) adresinde açılır. Sağlık kontrol uçları `/live` ve `/ready` yollarındadır.

## Testler

```powershell
# Python kaynaklarının derlenebilirlik kontrolü
.\.venv\Scripts\python.exe -m compileall src

# Backend ve API testleri
.\.venv\Scripts\python.exe -m pytest -q tests --ignore=tests/e2e

# Playwright uçtan uca testleri
.\.venv\Scripts\python.exe -m pytest -q tests/e2e

# Vendor hariç frontend JavaScript dosyaları için syntax kontrolü
Get-ChildItem frontend -Recurse -Filter *.js |
  Where-Object { $_.FullName -notmatch '\\vendor\\' } |
  ForEach-Object { node --check $_.FullName }
```

Testler yazılım regresyonlarını ve güvenlik kontrollerini ölçer; klinik etkinlik veya tıbbi doğrulama anlamına gelmez.

## Gizlilik ve güvenlik

CureMenu sağlık verisi işleyebildiği için hassas veri varsayımıyla tasarlanmıştır.

- Profil, etkileşim ve karar kayıtları yerel SQLite/Chroma katmanlarında tutulabilir.
- Yanıt üretimi için gerekli sınırlı bağlam Google Gemini gibi harici model sağlayıcılarına gönderilebilir.
- Telefon, e-posta, kimlik numarası ve token benzeri tanımlayıcılar için redaction ve veri minimizasyonu kontrolleri bulunur.
- Kimlik doğrulama, rate limiting, dosya boyutu/format kontrolleri ve URL güvenlik kontrolleri uygulanır.
- KVKK, sağlık mevzuatı ve kurumsal veri yönetişimi için ayrıca hukuki, teknik ve operasyonel çalışma gerekir.

Bu repository production-ready klinik yazılım olarak sunulmamaktadır.

## Demo durumu

CureMenu kontrollü demo ve eğitim senaryolarında kullanılabilir. Ana demo akışı olarak manuel menü linki veya menü fotoğrafı önerilir. QR/kamera akışı cihaz, HTTPS ve tarayıcı izinlerine bağlı olduğu için yardımcı/fallback akışı olarak değerlendirilmelidir.

## Yol haritası

- Kontrollü beta ve geri bildirim döngüsü
- Beslenme uzmanlarıyla pilot çalışma
- Tanımlı klinik validasyon ve güvenlik değerlendirmeleri
- Lisanslı, doğrulanabilir veri kaynaklarının genişletilmesi
- Deployment, gözlemlenebilirlik ve veri saklama hardening’i
- Restoran, konum ve menü entegrasyonlarının güçlendirilmesi

## Sorumluluk reddi

CureMenu tanı koymaz, tedavi düzenlemez ve sağlık profesyonelinin yerini almaz. Öneriler eğitim ve karar desteği amaçlıdır; kişisel sağlık durumları, ilaçlar ve tahliller için doktor veya diyetisyen değerlendirmesi gerekir. Acil bir durumda uygulamaya değil, doğrudan uygun sağlık kuruluşuna başvurulmalıdır.
