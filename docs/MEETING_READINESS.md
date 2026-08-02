# CureMenu Meeting Readiness

## Kisa Karar

Kod freeze onerilir.

Bu noktadan sonra kod yalnizca su durumlarda degismeli:

- Dogrulanmis guvenlik acigi
- Veri kaybi veya veri sizintisi riski
- Demo akisini bozan kritik hata
- Testle tekrar uretilebilen yuksek oncelikli regresyon

Yeni ozellik, genel refactor, UI polish ve klinik kapsam genisletme gorusme sonrasina birakilmalidir.

## Mevcut Teknik Durum

Son bilinen durum:

- Backend ve E2E disi testler: 278 passed, 1 warning
- Hedefli backend chat regresyonlari: passed
- Hedefli CureBot fetch error E2E: passed
- Python compile: temiz
- Frontend node parse check: temiz
- git diff --check: temiz
- Package/source safety: SOURCE_SAFE
- Profil snapshot izolasyonu: testlerle dogrulandi
- Tahlil ve buzdolabi history/F5 akisi: onceki demo blocker turunda duzeltildi ve test kapsamina alindi
- Raw "Failed to fetch" kullaniciya basilmiyor; sade hata mesaji gosteriliyor

Not: Tam Playwright E2E suite, test ortaminda cok sayida register istegi attigi icin /api/register rate limitine takilabiliyor. Bu production davranisi degil, test fixture izolasyonu konusudur.

## Demo Yapilabilir Akis

1. Login yap.
2. Profil ekraninda ana profil ve varsa aile uyesi bilgilerini goster.
3. CureBot'ta hedef kisi secimini goster.
4. Guvenli alternatif sorusu sor.
5. Alerjen iceren soruda sistemin blokladigini goster.
6. Haftalik plan olustur.
7. Bir ogunde "Tarifi Al" calistir.
8. "Yiyemedim" ile alternatif uret.
9. "Atistirmalik Oner" ile gunluk plana uygun ara ogun goster.
10. Tahlil PDF yukleme akisini goster.
11. Buzdolabi veya menu analizi goster.
12. Smart Grocery / butce ekranini kisa goster.
13. Gecmis ve izlenebilirlik ekranini teknik detay olarak sadece gerekirse ac.

## 5 Dakikalik Urun Akisi

1. Problem: Ozel beslenme ihtiyaci olan kisi yemek kararinda hastalik, alerji, ilac ve gunluk kosullari birlikte dusunmek zorunda kaliyor.
2. Profil: CureMenu once aktif kisi profilini cozumler; ana profil, aile uyesi veya tum aile hedefi ayrilir.
3. CureBot: Soruya dogrudan cevap vermeden once profil ve guvenlik kurallariyla kontrol yapar.
4. Ornek risk: Süt/yumurta/yer fistigi iceren kahvalti sorusunda alerjenleri yakalar.
5. Ornek alternatif: Yumurtasiz, sutsuz, glutensiz pratik kahvalti onerir.
6. Plan: Haftalik plan, tarif, alternatif ve atistirmalik akislari ayni profil baglamiyla calisir.
7. Kayit: Tahlil, buzdolabi ve gecmis kayitlari hedef kisi metadata'si ile tutulur.
8. Sinir: Sistem doktor/diyetisyen yerine gecmez; riskli veya belirsiz durumda uzmana yonlendirir.

## Hocaya Sorulacak 5 Ana Soru

1. Bu urunun klinik pilot oncesi hangi risk senaryolariyla test edilmesi gerekir?
2. Diyetisyen veya hekim panelinde hangi karar kayitlari gorunmeli, hangileri kullaniciya gosterilmemeli?
3. Ilac-besin etkilesimi ve alerji kontrollerinde hangi kaynak hiyerarsisi daha dogru olur?
4. Kapali beta icin en dogru hedef grup kim olmali: bireysel kullanici, diyetisyen danisani, klinik veya kurumsal pilot?
5. Bu proje BİGG/Ar-Ge dilinde nasil konumlanmali: teknik belirsizlik, klinik dogrulama ve ticarilesme acisindan hangi vurgu daha guclu olur?

## Dürüst Teknik Sinirlar

- CureMenu tanı koymaz, tedavi duzenlemez, doktor veya diyetisyen yerine gecmez.
- Test sonuclari yazilim regresyon kanitidir; klinik dogrulama kaniti degildir.
- RAG karar verici degildir; kaynak/aciklama ve izlenebilirlik katmanidir.
- Deterministic rule engine ve ingredient catalog guvenlik katmanidir; nihai klinik veri tabani olarak sunulmamalidir.
- LLM ciktilari guardrail ve rule engine ile sinirlandirilir, ancak uzman pilotu olmadan klinik etkinlik iddiasi kurulmaz.
- Kapali beta oncesi HTTPS staging, gercek cihaz/kamera testi, dependency audit surekliligi ve uzman onayi gerekir.

## Gorusme Sonrasi Ar-Ge Basliklari

- Uzmanlarla risk senaryolari listesi ve kabul kriterleri
- Klinik kaynak registry'sinin uzman onay sureci
- Ilac-besin etkilesimi kapsam genisletme
- Ingredient catalog kapsam buyutme ve structured meal extraction
- Kapali beta logging/privacy denetimi
- Hosted staging deployment runbook
- E2E test fixture rate-limit izolasyonu
- Kullanici geri bildirim dongusu ve hata siniflandirma paneli

## Demo Sirasinda Kacinilacak Ifadeler

- "Klinik olarak dogrulandi"
- "Tam guvenli"
- "Sifir risk"
- "Doktor/diyetisyen yerine gecer"
- "Tum hastaliklar ve tum ilac etkilesimleri kapsaniyor"
- "Yapay zeka tek basina karar veriyor"
- "Bu oneriyi uygulayabilirsiniz" gibi kesin tedavi dili

## Kullanilacak Guvenli Dil

- "Karar destek MVP'si"
- "Uzman dogrulamasi gereken Ar-Ge urunu"
- "Guvenlik katmanlari test edilmis prototip"
- "Riskli veya belirsiz durumda uzmana yonlendirir"
- "RAG kaynak/aciklama katmani olarak kullaniliyor"
- "Rule engine ve ingredient catalog ilk guvenlik kontrol katmanidir"

## Canli Demo Aksarsa Yedek Plan

1. Calisan ekran goruntulerini veya kisa kayitli demo videosunu ac.
2. CureBot yerine hazir test senaryolarini goster.
3. Profil snapshot izolasyonunu teknik diagram veya dokumanla anlat.
4. Test sonucu ozetini goster: backend, E2E hedefli test, package safety.
5. Canli servis sorunu varsa bunu "yerel/demo ortam problemi" diye ayir; urun mantigini test kayitlariyla anlat.

## CureBot Demo Sorulari

| Soru | Beklenen iyi cevap | Kotu gorunurse anlami | Demo karari |
| --- | --- | --- | --- |
| Yumurtasiz, sutsuz ve glutensiz tok tutan kahvalti onerir misin? | Guvenli alternatif verir; colyak/alerji/diyabet/levotiroksin dilini sade tutar. | Sadece uyari verip onermezse fazla konservatif davranis var. | Kullanilir |
| Kas kazanmak icin sut, yumurta ve yer fistigi ezmeli kahvalti tuketebilir miyim? | Sut, yumurta, yer fistigi alerjisini yakalar; teknik skor gostermez. | Sakatat/bobrek/gut gibi ilgisiz uyari cikarsa profil sizintisi olabilir. | Kullanilir |
| Glutensiz makarna ve yogurtlu sos yiyebilir miyim? | Glutensiz makarnayi gluten ihlali saymaz; yogurtu sut alerjisiyle yakalar. | "Failed to fetch" veya gluten false positive cikarsa demo icin risklidir. | Kisa testten sonra kullanilir |
| Levotiroksini kahvaltiyla birlikte alabilir miyim? | Zamanlama icin doktor/eczaci onerisine uyulmasini soyler; tek uyarida kalir. | Kesin dakika/talimat verirse dil fazla klinik olur. | Kullanilir |
| Diyabet baslangicim var, tatli istegimi nasil daha dengeli yonetebilirim? | Lif/protein, porsiyon ve dusuk ilave seker odakli pratik onerir. | Yasaklayici veya tedavi dili kullanirsa riskli. | Kullanilir |
| IBS'im var, kahvaltida nelere dikkat etmeliyim? | Tolerans kisiden kisiye degisir der; pratik ve yumuşak oneriler verir. | Kesin yasak listesi veya tani dili cikarsa kullanma. | Dikkatli kullanilir |
| Evdeki malzemelerle alisveris listemi daha uygun butceyle nasil tamamlarim? | Smart Grocery/butce mantigini aciklar; maliyet ve uygunluk dengesi kurar. | Saglik profili yerine sadece fiyat onerirse eksik kalir. | Kullanilir |
| Bu oneriyi neden boyle verdin? | Profil, alerji/ilac/colyak kontrolu ve kaynak/guvenlik katmanini sade anlatir. | Governance, Decision ID, risk skoru gibi teknik dil gosterirse sorun. | Kullanilir |

## Net Freeze Karari

Kod freeze onerilir.

Gorusme oncesi odak kod degil; anlatim, demo sirası, yedek ekranlar, hocaya sorular ve projenin Ar-Ge sinirlarini dogru ifade etmek olmalidir.
