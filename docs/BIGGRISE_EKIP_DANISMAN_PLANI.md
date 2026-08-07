# CureMenu - Ekip ve Danışman Planı

Bu doküman BİGGRISE/2026-2 hızlandırma sürecinde ekip yapısı, eksik yetkinlikler ve danışman ihtiyacını net anlatmak için hazırlanmıştır.

## 1. Mevcut Durum

CureMenu, ilaç kullanımı, alerji, kronik hastalık, tahlil sonuçları ve aile ihtiyaçları gibi faktörleri dikkate alarak günlük yemek kararlarını destekleyen yapay zeka destekli bir beslenme karar destek sistemi olarak geliştirilmektedir.

Projenin ilk çalışan MVP'si tek kurucu tarafından geliştirilmiştir. Mevcut ürün; sağlık profili oluşturma, CureBot ile soru-cevap, haftalık plan, tahlil PDF yükleme, menü/buzdolabı analizi, alışveriş listesi ve güvenlik kontrol katmanlarını içermektedir.

Bu aşamada ürün teknik olarak çalışan bir prototip seviyesine gelmiştir. Bundan sonraki temel ihtiyaç, klinik doğrulama, pazar doğrulama, ekip yapısı ve pilot kullanım planının güçlendirilmesidir.

## 2. Mevcut Kurucu Rolü

**Samet Coşkun - Kurucu / Teknik Ürün Geliştirme**

- Ürün fikri, kullanıcı problemi ve ilk MVP geliştirme sürecinden sorumludur.
- Python, yapay zeka, veri işleme, backend/frontend geliştirme ve ürün tasarımı tarafında çalışmaktadır.
- CureMenu'nun mevcut mimarisi, demo akışı, güvenlik kontrolleri ve test altyapısı üzerinde aktif olarak çalışmaktadır.
- Hızlandırma sürecinde iş planı, ürün yol haritası, ekip kurma ve pilot doğrulama çalışmalarını yürütecektir.

## 3. Eksik Yetkinlikler

Değerlendirme geri bildirimleri doğrultusunda özellikle şu alanların güçlendirilmesi gerekmektedir:

- Klinik beslenme ve diyetetik doğrulama
- İlaç-besin etkileşimleri konusunda uzman görüşü
- Dijital sağlıkta KVKK, sağlık verisi ve regülasyon uyumu
- Pazar segmentasyonu ve müşteri görüşmeleri
- B2B satış, klinik/diyetisyen kanalı ve iş geliştirme
- Ürün güvenilirliği için pilot çalışma tasarımı

## 4. Aranan Ekip ve Danışman Profilleri

### Beslenme ve Diyetetik Uzmanı

Beklenen katkı:

- Beslenme önerilerinin klinik açıdan sınırlarını değerlendirmek
- Alerji, kronik hastalık ve ilaç kullanımı gibi durumlarda kullanıcıya gösterilecek uyarı dilini gözden geçirmek
- Pilot kullanıcı senaryoları ve değerlendirme kriterleri oluşturmak
- CureMenu'nun doktor/diyetisyen yerine geçmeyen karar destek sistemi olarak doğru konumlanmasına katkı sağlamak

### Sağlık Teknolojileri / Regülasyon Danışmanı

Beklenen katkı:

- KVKK, açık rıza, aydınlatma metni ve sağlık verisi işleme süreçlerini değerlendirmek
- Ürünün tıbbi cihaz veya klinik iddia riski doğurabilecek noktalarını analiz etmek
- Kapalı beta ve pilot çalışma için asgari uyum gerekliliklerini belirlemek

### Yazılım / Yapay Zeka / Veri Bilimi Destek Kişisi

Beklenen katkı:

- AI tabanlı öneri sisteminin test edilmesi ve iyileştirilmesi
- Veri işleme, kaynak yönetimi, değerlendirme metrikleri ve otomasyon tarafında destek sağlamak
- Ürünün ölçeklenebilir teknik mimarisine katkı vermek

### İş Geliştirme / Pazar Araştırması Destek Kişisi

Beklenen katkı:

- İlk hedef müşteri segmentlerini netleştirmek
- Diyetisyenler, kronik hastalık dernekleri, klinikler ve potansiyel kullanıcılarla görüşmeler yürütmek
- Rakip analizi, fiyatlandırma ve pazara giriş stratejisini somutlaştırmak

## 5. İlk 1 Aylık Hedef

Hızlandırma programı süresince ilk ay için hedefler:

- En az bir diyetisyen veya klinik beslenme uzmanından düzenli geri bildirim almak
- En az 10 potansiyel kullanıcı veya uzman görüşmesi yapmak
- Hedef müşteri segmentini daraltmak ve ilk kullanım senaryosunu netleştirmek
- AGY-112 iş planında ekip, pazar, rekabet ve ticarileşme bölümlerini somut verilerle güçlendirmek
- Panel sunumunda CureMenu'yu "klinik doğrulaması tamamlanmış ürün" değil, "uzman doğrulaması ve pilot çalışması planlanan karar destek MVP'si" olarak konumlandırmak

## 6. Eğitimde Sorulacak Ana Sorular

1. Tek kurucu olarak başlayan projede, ekip üyelerinin resmi ortak olması mı beklenir, yoksa proje ekibi/danışman olarak tanımlanması yeterli olabilir mi?
2. Diyetisyen veya sağlık uzmanı proje ekibinde hangi rolde gösterilmelidir: kurucu ortak, danışman, proje personeli veya hizmet alımı?
3. Klinik doğrulama tamamlanmadan, ürünün karar destek sistemi olarak doğru ve güvenli şekilde konumlandırılması için iş planında hangi sınırlar açık yazılmalıdır?
4. Kapalı beta veya pilot çalışma için kullanıcı görüşmeleri, anketler ve uzman değerlendirmeleri nasıl kanıt olarak sunulmalıdır?
5. Sağlık verisi kullanan ancak tanı/tedavi sunmayan bir MVP için KVKK ve regülasyon açısından asgari beklentiler nelerdir?

## 7. Kısa Tanıtım Metni

CureMenu, ilaç, alerji, kronik hastalık, tahlil sonuçları ve aile ihtiyaçlarını dikkate alarak günlük yemek kararlarını daha güvenli hale getirmeyi amaçlayan yapay zeka destekli bir beslenme karar destek sistemidir. Ürün doktor veya diyetisyen yerine geçmez; kullanıcının sağlık profiliyle çakışabilecek durumları belirleyerek güvenli alternatifler, açıklayıcı uyarılar ve gerektiğinde uzman yönlendirmesi sunar.

## 8. Görüşülecek Kişiler İçin Kısa Çağrı

CureMenu projesi BİGGRISE/2026-2 hızlandırma programına kabul edildi. Bu süreçte klinik beslenme, dijital sağlık, yapay zeka, veri bilimi ve iş geliştirme alanlarında katkı sağlayabilecek ekip arkadaşları veya danışmanlarla görüşmek istiyorum. Çalışan bir MVP mevcut; hedefimiz ürünü pilot doğrulama, iş planı ve panel sürecine daha güçlü hazırlamak.
