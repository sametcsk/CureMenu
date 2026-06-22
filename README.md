# CureMenu 🍽️

## Ürün Fikri ve Açıklaması

CureMenu, Türkiye'de milyonlarca insanın mücadele ettiği diyabet, çölyak, hipertansiyon gibi kronik hastalıklara özel olarak geliştirilmiş **Kişiselleştirilmiş Beslenme ve Karar Motorudur**. Türk mutfağının yapısını analiz eder ve kullanıcının (veya tüm ailenin) sağlık profiline uygun menüler sunar. Evde her gün yaşanan "Ne pişirsem?" ve "Bana uygun mu?" stresini ortadan kaldırmayı hedefler.

## Ürün Özellikleri

- **Kişiselleştirilmiş Sağlık Profili:** Hastalıklar (Diyabet, Çölyak, Hipertansiyon, Kolesterol), alerjiler ve demografik bilgilere göre detaylı profil oluşturma. _(Not: Şuanlık temel kronik hastalıklar mevcuttur, ilerleyen aşamalarda çok daha fazla alternatif hastalık ve kısıt kuralı eklenecektir)._
- **Aile Modu:** Evdeki farklı bireylerin (örn: babada diyabet, çocukta çölyak) sağlık durumlarını aynı anda analiz ederek **herkesin ortak ve güvenle yiyebileceği** yemekleri bulan kesişim algoritması.
- **Akıllı Sınıflandırma Sistemi:** Yemekleri "Rahatça Tüketilebilir", "Porsiyon Kontrollü" ve "Uzak Durulmalı" olarak 3 farklı kategoride, bilimsel uyarı nedenleriyle listeleme.
- **Zengin Veritabanı:** Şu an için 50'den fazla popüler Türk yemeği ve detaylı besin değerlerini (Kalori, Karbonhidrat, Protein vb.) barındırır. İlerleyen süreçte bu veriler statik kalmayacak; yapay zeka ajanları ile anlık veriler çekilerek binlerce yemeği kapsayan dev ve dinamik bir veritabanına dönüşecektir.

## Hedef Kitle

- Kendisinde veya ailesinde kronik sağlık sorunları (Diyabet, Çölyak vb.) olan, diyetine dikkat etmek zorunda olan bireyler.
- "Aileme sağlıklı ve uygun ne pişirebilirim?" diye düşünen ev hanımları ve çalışan ebeveynler.
- Dışarıda yemek yerken restoran menülerinde kaybolan, hastalığına uygun güvenilir bir yemek bulmakta zorlanan ve kişisel bir dijital asistana ihtiyaç duyan herkes.

---

## Proje Yönetimi (Bootcamp Süreci)

### Takım Bilgileri

- **Takım İsmi:** Solo Innovators
- **Takım Üyeleri ve Rolleri:**
  - **Samet** (Product Owner, Scrum Master, Developer)

### Sprint 1 Özeti ve Notları

**Sprint Hedefi:** Fikrin olgunlaştırılması, uygulamanın teknik mimarisinin (veri modelleri, veritabanı, kural motoru) kurulması ve Minimum Viable Product (MVP) arayüzünün ayağa kaldırılması.

**Sprint İçinde Yapılanlar (Product Increment):**

- Proje dizin yapısı oluşturuldu. Pydantic ile veri modelleri (`models.py`) kodlandı.
- 50 adet Türk yemeği detaylı besin analizleriyle JSON formatında sisteme entegre edildi.
- Hastalıklara özel kısıtlamaları hesaplayan kural tabanlı öneri motoru (`recommendation.py`) yazıldı. _(Bu kurallar ileriki aşamalarda Yapay Zeka ajanlarının sağlığa zararlı tavsiyeler vermesini engelleyecek "Güvenlik Sınırları - Guardrails" olarak kullanılacaktır)._
- Streamlit kullanılarak özel CSS tasarımlı "Profil", "Aile" ve "Öneriler" sayfaları geliştirildi.
- Aile modu (Kesişim Algoritması) başarıyla çalışır hale getirildi.

**Sprint Retrospective (Değerlendirme):**

- _İyi Gidenler:_ Python ve Streamlit entegrasyonunu başarılı bir şekilde kurdum. Aile Modu mantığı (kesişim algoritması) beklediğimden çok daha performanslı çalışıyor ve UI tasarımım oldukça profesyonel görünüyor.
- _Geliştirilmesi Gerekenler:_ Projeyi tek başıma yürüttüğüm için her rolde kendim yoğun bir efor sarf etmek zorunda kaldım ve dokümantasyonu sprintin sonuna sıkıştırdım. Bir sonraki sprintte günlük (daily) takibi daha düzenli yapmalıyım. Ayrıca site tasarımı (UI/UX) daha da iyileştirilmeli, kullanıcı deneyimini artıracak yeni tasarım ögeleri eklenmelidir.
- _Sonraki Sprint (Sprint 2) Odakları:_
  - **Multi-Agent Yapay Zeka Mimarisi:** Sistemin kural tabanlı yapıdan çıkıp, LLM tabanlı "Beslenme Uzmanı" ajanlarına devredilmesi. Sprint 1'de yazılan kurallar, bu ajanlar için katı güvenlik sınırları olarak çalışacaktır. Bu sayede hem yapay zekanın esnekliğini kullanırken hem de sağlık verilerinin güvenliğini garanti altına alacağız.
  - **Geçmiş Hafıza ve Geri Bildirim Sistemi (Memory):** Uygulamanın kullanıcının yediği yemekleri hafızasında tutması ve "Bu yemek bana iyi geldi" veya "Bunu yiyince rahatsız oldum" gibi geri bildirimler alarak gelecekteki menü önerilerini sürekli olarak optimize etmesi. Bu sayede uygulama, her kullanıcı için zamanla daha akıllı ve kişisel hale gelecektir.
  - **Lokasyon Bazlı Restoran Önerisi (Top 10):** Google Maps entegrasyonu eklenerek kullanıcının bulunduğu konuma yakın, hastalığına uygun restoranların gösterilmesi. Sadece menü uygunluğuna değil, mekanın **Google Yıldız Puanlarına (örn: 4.5 ve üzeri)** bakılarak en kaliteli ve en güvenilir Top 10 restoranın filtrelenmesi.
  - **Sağlık & Bütçe Optimizasyon Ajanı:** "Sağlıklı beslenmek pahalıdır" algısını kırmak için, kullanıcının günlük alması gereken besinleri internetteki güncel fiyatlarla tarayıp, bütçesine en uygun ve en sağlıklı alternatifleri önüne çıkaran ekonomik AI asistanı.

### Gelecek Vizyonu (Sprint 3 ve Sonrası)

Projenin tamamen olgunlaştığında ulaşacağı vizyoner hedefler:

- **Giyilebilir Teknoloji (Wearable) Entegrasyonu:** Akıllı saatlerden veya Sürekli Glikoz Ölçüm (CGM) cihazlarından anlık sağlık verisi alarak proaktif yemek tavsiyeleri sunma ("Şu an şekerin düşüş eğiliminde, hemen şu sağlıklı atıştırmalığı tüketmelisin").
- **Doktor / Diyetisyen Raporlama Modülü:** Hafızada tutulan yemek geçmişinin ve "Nasıl hissettirdi?" geri bildirimlerinin haftalık/aylık olarak analiz edilip, kullanıcının doktoruna veya diyetisyenine detaylı bir tıbbi ilerleme raporu (PDF) olarak sunulması.
- **Kamera ile Menü Tarama (OCR):** Dışarıdaki bir restoranda menünün fotoğrafı çekildiğinde, Gemini Vision modeli ile menüyü yapay zekaya okutarak, profil kısıtlamalarına göre o restoranda "Ne yemeliyim?" sorusuna anında yanıt veren özelliğin kodlanması.

---

## Kurulum ve Çalıştırma

Projeyi yerel bilgisayarınızda çalıştırmak için:

```bash
git clone <sizin-repo-linkiniz>
cd healmenu
python -m venv .venv
.venv\Scripts\activate  # Windows için
pip install -r requirements.txt
streamlit run app.py
```
