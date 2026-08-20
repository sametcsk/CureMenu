# İlaç–Besin Güvenlik Senaryoları (Uzman İnceleme Scaffold'u)

Bu yapı, **klinik içerik ÜRETMEZ**. Amaç, alan uzmanıyla (ör. Melih Hoca) birlikte
gözden geçirilebilecek **yapılandırılmış bir güvenlik senaryosu iskeletidir**.
Senaryolardaki `expected_system_behavior` alanı bir **klinik hüküm değil**, sistemin
göstermesi gereken **davranışı** (kaynaksız kesin konuşmama, profesyonele yönlendirme,
belirsizlikte clarification) tanımlar.

## Dosya
`docs/drug_food_scenarios.csv` — sütunlar:

| Sütun | Anlam |
|---|---|
| `scenario_id` | Benzersiz kimlik (DF-XXX) |
| `drug_or_active_ingredient` | İlaç / etken madde (inceleme konusu) |
| `food_or_food_group` | Gıda / gıda grubu |
| `risk_level` | Uzman belirleyene kadar `pending_review` |
| `expected_system_behavior` | Sistemin davranışı (klinik hüküm değil) |
| `source_required` | Kaynak zorunlu mu (true/false) |
| `professional_referral_required` | Profesyonele yönlendirme gerekli mi |
| `expert_status` | `pending_review` \| `approved` \| `revision_required` |
| `notes` | Serbest not |

## Governance kuralları (test ile zorlanır)
- Her satır geçerli bir `expert_status` taşır.
- **Uzman doğrulaması olmadan hiçbir satır `approved` olamaz.** Başlangıçta tüm
  satırlar `pending_review`.
- Bir satır `approved` yapılacaksa: `source_required=true` ise `notes` içinde bir
  kaynak referansı bulunmalı ve `revision_required` olmamalı.
- `risk_level`, uzman doldurana kadar `pending_review` kalır.

## Kullanım
1. Uzman satırları inceler; `risk_level`, `expected_system_behavior`, kaynak ve
   yönlendirme alanlarını doldurur.
2. Onaylanan satır `expert_status=approved` + `notes`'ta kaynak ile işaretlenir.
3. `tests/test_drug_food_scenarios.py` invariant'ları CI'da korur — onaylı içeriğin
   kaynaksız/incelemesiz girmesini engeller.

> Bu scaffold, ilaç-besin mantığını **kod içine gömmez**; yalnız uzmanla birlikte
> geliştirilebilecek denetlenebilir bir veri katmanı sağlar.
