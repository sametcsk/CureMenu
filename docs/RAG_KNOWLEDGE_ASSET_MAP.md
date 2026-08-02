# CureMenu RAG Bilgi Varlıkları Haritası

Bu belge, CureMenu için toplanan kaynakların projede hangi amaçla kullanılabileceğini ve hangi amaçla kullanılamayacağını açıklar. Kaynak sayısının yüksek olması tek başına klinik güven anlamına gelmez. Bu nedenle kütüphane, görevleri ve kanıt sınırları birbirinden ayrılmış katmanlar halinde yönetilir.

## Genel görünüm

| Katman | Kaynak | Bugünkü kullanım | Klinik iddia sınırı |
|---|---:|---|---|
| Resmî scoped kanıt | 8 belge, 29 seçilmiş sayfa | İlaç-besin ve belirli güvenlik kurallarının kaynak izlenebilirliği | Kaynak ve sayfa doğrulanmıştır; klinik uzman onayı hâlâ gereklidir |
| Klinik arka plan | 26 PDF, 1.976 parça | Literatür taraması, açıklama ve araştırma bağlamı | Hasta düzeyinde kesin öneriyi tek başına taşıyamaz |
| Ürün ve yapay zekâ araştırması | 11 PDF | Ürün tasarımı, çoklu ajan, RAG, davranış değişikliği ve guardrail gerekçeleri | Runtime klinik kanıt olarak kullanılmaz |
| Teknik referans | 4 PDF | FHIR, ICD-11, ePI ve mevzuat yol haritası | Klinik veya hukuki uygunluk kanıtı değildir |
| Karantina | 2 PDF | İnceleme bekleyen yerel varlık | OCR veya belge ayrıştırması tamamlanmadan indekslenmez |

Masaüstü kütüphanesindeki 43 PDF'nin tümü `data/rag_knowledge_catalog.json` içinde hash, konu, belge türü, kullanım alanı ve sınırlama bilgileriyle kayıtlıdır. Resmî kanıt koleksiyonu ise ayrıca `data/clinical_evidence_registry.json` tarafından yönetilir.

## Kaynaklar projeyi nasıl etkiledi?

### 1. Kullanıcı sorununu yalnızca “öneri üretme” olarak görmemek

Sağlık sohbet botları ve kronik hastalık öz yönetimi üzerine çalışmalar, kullanıcıların tek seferlik bir cevaptan çok süreklilik, anlaşılır açıklama, kişisel bağlam ve gerektiğinde insan desteğine ihtiyaç duyduğunu gösteren araştırma çerçevesi sağladı. Bu nedenle CureMenu yalnızca sohbet ekranı olarak değil; profil, haftalık plan, menü, buzdolabı ve alışveriş akışlarının birlikte çalıştığı bir karar destek ürünü olarak tasarlandı.

İlgili araştırma varlıkları:

- `ai_chatbots_health_behavior_change.pdf`
- `ai_chronic_disease_self_management.pdf`
- `s44325-025-00101-6.pdf`
- `20260623-168580-9qoc3l.pdf`

### 2. Yapay zekâyı tek karar verici yapmamak

Kişiselleştirilmiş beslenme, sağlık yapay zekâsı ve guardrail çalışmalarında ortaklaşan temel sorunlar; halüsinasyon, yanlış güven, yetersiz doğrulama, gizlilik ve yüksek boyutlu kullanıcı bağlamıdır. Bu bulgular CureMenu'da deterministik kuralların modelden önce çalışması, belirsizliğin açıkça işaretlenmesi ve riskli durumda profesyonel değerlendirmeye yönlendirme kararlarını destekledi.

İlgili araştırma varlıkları:

- `enhancing_guardrails_safe_healthcare_ai.pdf`
- `nutrients-18-00938-v2.pdf`
- `applsci-15-09283-v2.pdf`
- `journal.pdig.0000758.pdf`

### 3. Çoklu hastalık ve uzun dönem bağlamını parçalayarak işlemek

Uzun dönem sağlık kayıtları ve çoklu ajan mimarileri üzerine çalışmalar, bütün profilin tek bir modele tek seferde verilmesinin bağlam yükü ve dikkat dağılması yaratabileceğini gösteren teknik yaklaşımlar sundu. CureMenu'nun yönlendirici, diyetisyen ve ekonomist gibi ayrışmış sorumlulukları; profil, plan ve maliyet bağlamlarının kontrollü taşınması bu araştırma hattıyla uyumludur. Bu uyum klinik doğrulama iddiası değil, mimari tercihlerin literatürle gerekçelendirilmesidir.

İlgili araştırma varlıkları:

- `ehr_rag_bridging_long_horizon_records.pdf`
- `nutriorion_multi_agent_personalized_nutrition.pdf`
- `rag_type_2_diabetes_mellitus_care.pdf`

### 4. Kaynak kullanımını katmanlara ayırmak

RAG araştırmaları daha fazla belge getirmenin tek başına yeterli olmadığını gösterir. CureMenu bu nedenle genel klinik kütüphane ile hash ve sayfa kapsamı tanımlı resmî kanıt koleksiyonunu ayırır. Hasta düzeyindeki sağlık iddiasında yalnızca resmî registry kapsamındaki belge parçaları kanıt olarak kabul edilir. Genel makaleler benzerlik skorları yüksek olsa bile resmî kanıt yerine geçemez.

### 5. Birlikte çalışabilirlik ve mevzuatı bugünün özelliği değil, yol haritası olarak görmek

FHIR, ICD-11, ePI ve AB yapay zekâ düzenlemeleriyle ilgili kaynaklar mevcut prototipin mevzuata uygun veya tıbbi cihaz olduğunu göstermez. Bu belgeler; gelecekte standart veri modelleri, izlenebilirlik, insan gözetimi ve kurumsal entegrasyon gereksinimlerinin erkenden görülmesini sağlar.

İlgili teknik referanslar:

- `hl7-fhir-guide-to-esource-epro-interoperability.pdf`
- `presentation-fhir-and-eu-common-standard-epi-g-rodriguez_en.pdf`
- `icd11factsheet_en.pdf`
- `eu-ai-act-high-risk-compliance-pharma-medical-devices.pdf`

## Klinik arka plan kütüphanesi

Genel koleksiyondaki 26 kaynak şu konu kümelerini destekler:

- Diyabet ve kronik hastalıklar: TEMD 2025 rehberi, karbonhidrat ve kronik hastalık çalışmaları.
- Böbrek hastalığı: kronik böbrek yetmezliğinde beslenme ve ilgili derlemeler.
- Çölyak ve gastrointestinal alan: çölyak, IBS ve gastrointestinal beslenme araştırmaları.
- Hipertansiyon ve kardiyovasküler sağlık: hipertansiyon ve kalp-damar beslenme kaynakları.
- Tiroid ve Hashimoto: beslenme yönetimi derlemeleri.
- İlaç-besin etkileşimleri: farklı derleme ve kanıt sentezleri.
- Genel beslenme: Türkiye Beslenme Rehberi 2022 ve temel beslenme eğitim içerikleri.
- Hassas beslenme: kişiselleştirme, metabolik bağlam ve dijital beslenme araştırmaları.

Bu kaynaklar ürün araştırmasını zenginleştirir; ancak belirli ilaç, hastalık veya porsiyon kararında resmî scoped kanıt ve uzman değerlendirmesi gerekliliğini ortadan kaldırmaz.

## Karantinadaki iki belge

- `14.pdf`: Prof. Dr. Gönül Şahin ve Ecz. Gözde Girgin tarafından hazırlanan ilaç-besin, ilaç-alkol ve bitkisel ürün etkileşimleri yazısıdır. Dosyada metin katmanı bulunmadığı için OCR, bibliyografik kimlik ve sayfa kontrolü tamamlanmadan indekslenmez.
- `kepan_2025.pdf`: Birden çok belgeyi tek PDF içinde birleştiren 1.265 sayfalık yerel derlemedir. Alt belgeler güvenilir biçimde ayrıştırılmadan tek eser gibi atıf verilemez.

## Güvenli kullanım kuralları

1. Araştırma makalesi, ürün mimarisini gerekçelendirebilir; tek başına hasta önerisini doğrulayamaz.
2. Genel klinik kaynaklar arka plan sağlar; hasta düzeyindeki kesin sağlık iddiası resmî scoped kanıt gerektirir.
3. Resmî belgenin yalnızca registry'de izin verilen ve hash ile doğrulanan sayfaları kullanılır.
4. Registry kaydı kaynak bütünlüğünü kanıtlar, klinik uzman onayını kanıtlamaz.
5. Kanıt bulunamadığında sistem kesin konuşmaz; dikkat veya profesyonel değerlendirme üretir.
6. Teknik ve mevzuat belgeleri roadmap girdisidir; uyumluluk veya sertifikasyon iddiası değildir.

## Bir sonraki kanıt çalışması

- Türkiye'de kullanılan ilaçlar için güncel ve sürdürülebilir KÜB/KT kaynak kanalı oluşturmak.
- Çölyak ve gut için güncel birincil rehberleri resmî scoped koleksiyona eklemek.
- `14.pdf` için OCR ve kaynak kimliği doğrulaması yapmak.
- `kepan_2025.pdf` içindeki alt belgeleri ayrı bibliyografik kayıtlara bölmek.
- Diyetisyen, eczacı ve hekim tarafından imzalanmış örnek senaryo seti oluşturmak.
- Kaynak türü, kural sonucu ve uzman görüşü arasındaki uyumu ölçen bir değerlendirme matrisi kurmak.
