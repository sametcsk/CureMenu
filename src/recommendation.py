# Kural Tabanlı Öneri Motoru 

from src.models import AileUyesi, Hastalik, YemekUygunluk, UygunlukDurumu

SKOR={
    UygunlukDurumu.UYGUN:2,
    UygunlukDurumu.DIKKATLI:1,
    UygunlukDurumu.ONERILMEZ:0,


}

def diyabet_degerlendirme(yemek):
    gi=yemek.get("glisemik_indeks","orta")
    karb=yemek["besin_degerleri"]["karbonhidrat"]

    if gi=="yuksek":
        return UygunlukDurumu.ONERILMEZ, "Bu yemek yüksek glisemik indeksli — kan şekerinizi hızla yükseltebilir. Diyabet hastaları için önerilmez, alternatif düşük GI'li yemeklere yönelin."

    elif gi=="orta":
        msg = "Bu yemek orta glisemik indeksli. Kan şekerinizi ani değil ama kademeli yükseltebilir, porsiyon kontrolü yapmanız önemli."
        if karb > 45:
            msg += f" Ayrıca karbonhidrat miktarı da yüksek ({karb}g) — küçük porsiyon tercih edin."
        return UygunlukDurumu.DIKKATLI, msg
    else:
        if karb > 45:
            return UygunlukDurumu.DIKKATLI, f"Glisemik indeksi düşük olsa da karbonhidrat miktarı yüksek ({karb}g). Küçük porsiyonlarla tüketmeniz tavsiye edilir."
        return UygunlukDurumu.UYGUN, "Bu yemek düşük glisemik indeksli ve dengeli karbonhidrat içeriyor — diyabet hastaları için güvenle tüketilebilir."
    
    

def colyak_degerlendirme(yemek):
    if yemek.get("gluten_icerir",False):
        return UygunlukDurumu.ONERILMEZ, "Bu yemek gluten içermektedir — çölyak hastaları için uygun değildir. Glutensiz alternatif tariflere göz atmanızı öneririz."
    return UygunlukDurumu.UYGUN, "Bu yemek glutensiz, çölyak hastaları için güvenle tüketilebilir."

def hipertansiyon_degerlendirme(yemek):
    sodyum = yemek["besin_degerleri"]["sodyum"]
    if sodyum > 600:
        return UygunlukDurumu.ONERILMEZ, f"Bu yemek {sodyum}mg sodyum içeriyor — bu oldukça yüksek ve tansiyonunuzu olumsuz etkileyebilir. Daha az tuzlu alternatifler tercih edin."
    elif sodyum >= 300:
        return UygunlukDurumu.DIKKATLI, f"Bu yemek {sodyum}mg sodyum içeriyor — orta düzeyde. Hazırlarken tuz miktarını azaltarak tansiyonunuzu koruyabilirsiniz."
    return UygunlukDurumu.UYGUN, f"Bu yemek yalnızca {sodyum}mg sodyum içeriyor — hipertansiyon hastaları için güvenli düzeyde."

def kolesterol_degerlendirme(yemek):
    dy = yemek["besin_degerleri"]["doymus_yag"]
    kol = yemek["besin_degerleri"]["kolesterol"]
    if dy > 5 or kol > 100:
        return UygunlukDurumu.ONERILMEZ, f"Bu yemek {dy}g doymuş yağ ve {kol}mg kolesterol içeriyor — bu değerler yüksek. Kalp sağlığınız için daha az yağlı alternatifler tercih edin."
    elif dy >= 2 or kol >= 50:
        return UygunlukDurumu.DIKKATLI, f"Bu yemek {dy}g doymuş yağ ve {kol}mg kolesterol içeriyor — orta düzeyde. Küçük porsiyonlarla ve sık olmayacak şekilde tüketebilirsiniz."
    return UygunlukDurumu.UYGUN, f"Bu yemek düşük yağ ({dy}g) ve düşük kolesterol ({kol}mg) içeriyor — kolesterol hastaları için güvenle tüketilebilir."

    

KURAL_HARITASI={
    Hastalik.DIYABET: diyabet_degerlendirme,
    Hastalik.COLYAK:colyak_degerlendirme,
    Hastalik.HIPERTANSIYON:hipertansiyon_degerlendirme,
    Hastalik.KOLESTEROL:kolesterol_degerlendirme,
}

def yemek_degerlendir(yemek,profil):
    if not profil.hastaliklar:
        return YemekUygunluk(
            yemek_id=yemek["id"],
            yemek_adi=yemek["ad"],
            uygunluk=UygunlukDurumu.UYGUN,
            aciklama="Bilinen bir sağlık kısıtlaması olmadığı için bu yemek uygundur.",
            uyari_detaylari=[],
            skor=2,
        )
    
    sonuclar=[]
    for hastalik in profil.hastaliklar:
        kural_fn=KURAL_HARITASI.get(hastalik)
        if kural_fn:
            durum,aciklama=kural_fn(yemek)
            sonuclar.append((durum,aciklama,hastalik.value))

    if not sonuclar:
        return YemekUygunluk(
            yemek_id=yemek["id"],
            yemek_adi=yemek["ad"],
            uygunluk=UygunlukDurumu.UYGUN,
            aciklama="Bilinen bir sağlık kısıtlaması olmadığı için bu yemek uygundur.",
            uyari_detaylari=[],
            skor=2,
        )

    en_kisitlayici=min(sonuclar,key=lambda s:SKOR[s[0]])
    sonuc=en_kisitlayici[0]
    uyari_detaylari=[]
    for durum,aciklama,hastalik in sonuclar:
        uyari_detaylari.append(f"[{hastalik.upper()}] {aciklama}")

    return YemekUygunluk(
        yemek_id=yemek["id"],
        yemek_adi=yemek["ad"],
        uygunluk=sonuc,
        aciklama=en_kisitlayici[1],
        uyari_detaylari=uyari_detaylari,
        skor=SKOR[sonuc],
    )


def toplu_degerlendir(yemekler,profil):
    """
    Tüm yemekleri değerlendirir ve 3 kategoriye ayırarak döndürür:
        -uygun: Rahatça yenilebilenler
        -dikkatli: Porsiyonuna veya hazırlanışına dikkat edilmesi gerekenler
        -onerilmez:Tüketilmemesi gerekenler
        """
    sonuclar={
        "uygun":[],
        "dikkatli":[],
        "onerilmez":[],
    }

    for yemek in yemekler:
        uygunluk_sonucu=yemek_degerlendir(yemek,profil)

        if uygunluk_sonucu.uygunluk== UygunlukDurumu.UYGUN:
            sonuclar["uygun"].append(uygunluk_sonucu)
        elif uygunluk_sonucu.uygunluk== UygunlukDurumu.DIKKATLI:
            sonuclar["dikkatli"].append(uygunluk_sonucu)
        else:
            sonuclar["onerilmez"].append(uygunluk_sonucu)   

    # Her kategori içindeki yemekleri ismine göre alfabetik sırala
    for grup in sonuclar.values():
        grup.sort(key=lambda x: x.yemek_adi)
    return sonuclar
        
def aile_ortak_degerlendir(yemekler, aile_uyeleri):
    """
    Birden fazla kişinin (ailenin) olduğu durumda kesişim algoritması.
    Bir yemek, ailedeki en kısıtlı kişiye göre değerlendirilir.
    """
    sonuclar = {
        "uygun": [],
        "dikkatli": [],
        "onerilmez": [],
    }

    if not aile_uyeleri:
        return sonuclar

    for yemek in yemekler:
        uyeler_sonuclari = []
        for uye in aile_uyeleri:
            # Her üye için yemeği ayrı ayrı değerlendir
            uye_sonucu = yemek_degerlendir(yemek, uye)
            uyeler_sonuclari.append((uye, uye_sonucu))
        
        # En kısıtlayıcı skoru bul
        en_kisitlayici_sonuc = min(uyeler_sonuclari, key=lambda x: x[1].skor)
        uye = en_kisitlayici_sonuc[0]
        sonuc = en_kisitlayici_sonuc[1]
        
        # Uyarı detaylarını birleştir ve kimden geldiğini belirt
        ortak_uyari_detaylari = []
        for u, s in uyeler_sonuclari:
            if s.uygunluk != UygunlukDurumu.UYGUN:
                for detay in s.uyari_detaylari:
                    ortak_uyari_detaylari.append(f"<b>{u.ad}:</b> {detay}")
        
        # Ortak sonucu oluştur
        ortak_yemek_uygunluk = YemekUygunluk(
            yemek_id=yemek["id"],
            yemek_adi=yemek["ad"],
            uygunluk=sonuc.uygunluk,
            aciklama=f"Bu yemek {uye.ad} için en fazla risk teşkil ediyor. Nedeni: {sonuc.aciklama}" if sonuc.uygunluk != UygunlukDurumu.UYGUN else "Bu yemek ailenizdeki herkes için güvenli.",
            uyari_detaylari=ortak_uyari_detaylari,
            skor=sonuc.skor
        )

        if ortak_yemek_uygunluk.uygunluk == UygunlukDurumu.UYGUN:
            sonuclar["uygun"].append(ortak_yemek_uygunluk)
        elif ortak_yemek_uygunluk.uygunluk == UygunlukDurumu.DIKKATLI:
            sonuclar["dikkatli"].append(ortak_yemek_uygunluk)
        else:
            sonuclar["onerilmez"].append(ortak_yemek_uygunluk)   

    for grup in sonuclar.values():
        grup.sort(key=lambda x: x.yemek_adi)
    
    return sonuclar