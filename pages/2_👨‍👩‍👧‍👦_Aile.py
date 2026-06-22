# Aile Modu Sayfası

import streamlit as st
from src.session import get_profil, aile_uyesi_ekle, aile_uyesi_sil, profil_var_mi
from src.models import AileUyesi, Hastalik, Cinsiyet
from src.ui import inject_custom_css, render_metric
from src.food_db import yemekleri_yukle, tum_kategoriler, kategori_goster
from src.recommendation import aile_ortak_degerlendir

inject_custom_css()

st.markdown("<h1 class='hero-title'>👨‍👩‍👧‍👦 Aile Modu (Kesişim)</h1>", unsafe_allow_html=True)

if not profil_var_mi():
    st.warning("⚠️ Önce kendi profilinizi oluşturmalısınız. Lütfen sol menüden 'Profil' sayfasına gidin.")
    st.stop()

profil = get_profil()

st.markdown("""
<div class="custom-card">
    <p style="opacity: 0.9; margin: 0;">
    Ailenizdeki diğer kişileri buraya ekleyebilirsiniz. CureMenu, tüm ailenin profillerini analiz ederek 
    <b>herkesin güvenle yiyebileceği ortak yemekleri</b> bulur. Kural basittir: Bir yemek evdeki tek bir kişi için bile riskliyse, ortak menüde uyarı verir.
    </p>
</div>
""", unsafe_allow_html=True)

# 1. BÖLÜM: Aile Üyeleri Listesi
st.subheader("📋 Aile Üyeleri")

# Ana kullanıcıyı her zaman göster
st.markdown(f"**👤 {profil.ana_kullanici.ad} (Sen)** - {', '.join([h.value.title() for h in profil.ana_kullanici.hastaliklar]) or 'Sağlıklı'}")

# Eklenen diğer üyeleri listele
if profil.aile_uyeleri:
    for uye in profil.aile_uyeleri:
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown(f"**🧑 {uye.ad}** ({uye.yas} yaş) - {', '.join([h.value.title() for h in uye.hastaliklar]) or 'Sağlıklı'}")
        with col2:
            if st.button("❌ Sil", key=f"sil_{uye.id}"):
                aile_uyesi_sil(uye.id)
                st.rerun()
else:
    st.info("Henüz aile üyesi eklemediniz. Aşağıdaki formdan ekleyebilirsiniz.")

st.markdown("<hr style='opacity: 0.2;'>", unsafe_allow_html=True)

# 2. BÖLÜM: Yeni Kişi Ekle Formu
with st.expander("➕ Yeni Aile Üyesi Ekle", expanded=False):
    with st.form("yeni_uye_formu"):
        ad = st.text_input("Adı")
        yas = st.number_input("Yaşı", min_value=1, max_value=120, value=30)
        cinsiyet = st.selectbox("Cinsiyeti", [Cinsiyet.KADIN.value, Cinsiyet.ERKEK.value])
        
        st.markdown("<div style='margin-top: 15px; margin-bottom: 10px;'><b>Sağlık Durumu</b></div>", unsafe_allow_html=True)
        hastaliklar = []
        c1, c2 = st.columns(2)
        with c1:
            if st.checkbox("Diyabet (Şeker Hastalığı)", key="uye_diyabet"): hastaliklar.append(Hastalik.DIYABET)
            if st.checkbox("Çölyak", key="uye_colyak"): hastaliklar.append(Hastalik.COLYAK)
        with c2:
            if st.checkbox("Hipertansiyon", key="uye_hipertansiyon"): hastaliklar.append(Hastalik.HIPERTANSIYON)
            if st.checkbox("Yüksek Kolesterol", key="uye_kolesterol"): hastaliklar.append(Hastalik.KOLESTEROL)
            
        kaydet = st.form_submit_button("Aileyi Güncelle")
        if kaydet:
            if ad.strip():
                yeni_uye = AileUyesi(
                    ad=ad,
                    yas=yas,
                    cinsiyet=Cinsiyet(cinsiyet),
                    hastaliklar=hastaliklar
                )
                aile_uyesi_ekle(yeni_uye)
                st.success(f"{ad} başarıyla eklendi!")
                st.rerun()
            else:
                st.error("Lütfen bir ad girin.")

st.markdown("<br><br>", unsafe_allow_html=True)

# 3. BÖLÜM: Kesişim Algoritması Sonuçları (Ortak Menü)
if len(profil.tum_uyeler()) > 1:
    st.markdown("<h2 style='text-align: center; color: #6366f1;'>🍽️ Aile İçin Ortak Menü</h2>", unsafe_allow_html=True)
    
    # Kategoriler için filtre
    tum_kat = tum_kategoriler()
    secilen_kategori = st.selectbox(
        "Kategori Filtresi", 
        options=["Tümü"] + tum_kat,
        format_func=lambda x: "Tüm Yemekler" if x == "Tümü" else kategori_goster(x),
        key="aile_kategori"
    )

    yemekler = yemekleri_yukle()
    if secilen_kategori != "Tümü":
        yemekler = [y for y in yemekler if y["kategori"] == secilen_kategori]
        
    # KESİŞİM ALGORİTMASINI ÇALIŞTIR
    sonuclar = aile_ortak_degerlendir(yemekler, profil.tum_uyeler())
    
    # Metrikler
    m1, m2, m3 = st.columns(3)
    with m1:
        render_metric("Herkes İçin Güvenli", len(sonuclar['uygun']), "text-green")
    with m2:
        render_metric("Porsiyon Kontrollü", len(sonuclar['dikkatli']), "text-yellow")
    with m3:
        render_metric("Uzak Durulmalı", len(sonuclar['onerilmez']), "text-red")

    st.markdown("<hr style='margin: 2rem 0; opacity: 0.5;'>", unsafe_allow_html=True)

    # UYGUN YEMEKLER
    st.markdown("<h3 style='color: #10b981;'>✅ Herkes İçin Güvenli Olanlar</h3>", unsafe_allow_html=True)
    if sonuclar["uygun"]:
        for y in sonuclar["uygun"]:
            with st.expander(f"🟢 {y.yemek_adi}"):
                st.markdown(f"<div style='opacity: 0.9;'>{y.aciklama}</div>", unsafe_allow_html=True)
    else:
        st.info("Ailenizdeki herkes için tam anlamıyla güvenli ortak bir yemek bulunamadı.")

    # DİKKATLİ YEMEKLER
    st.markdown("<h3 style='color: #f59e0b; margin-top: 2rem;'>⚠️ Bazıları İçin Porsiyon Kontrolü Gerekenler</h3>", unsafe_allow_html=True)
    if sonuclar["dikkatli"]:
        for y in sonuclar["dikkatli"]:
            with st.expander(f"🟡 {y.yemek_adi}"):
                st.markdown(f"<div style='color: #b45309;'><b>Uyarı:</b> {y.aciklama}</div>", unsafe_allow_html=True)
                if y.uyari_detaylari:
                    st.markdown("<ul>", unsafe_allow_html=True)
                    for detay in y.uyari_detaylari:
                        st.markdown(f"<li style='opacity: 0.8; font-size: 0.9em;'>{detay}</li>", unsafe_allow_html=True)
                    st.markdown("</ul>", unsafe_allow_html=True)
    else:
        st.info("Bu kategoride sonuç bulunamadı.")

    # ÖNERİLMEYEN YEMEKLER
    st.markdown("<h3 style='color: #ef4444; margin-top: 2rem;'>❌ Aileden Birileri İçin Yasaklı Olanlar</h3>", unsafe_allow_html=True)
    if sonuclar["onerilmez"]:
        for y in sonuclar["onerilmez"]:
            with st.expander(f"🔴 {y.yemek_adi}"):
                st.markdown(f"<div style='color: #991b1b;'><b>Neden Önerilmez?</b> {y.aciklama}</div>", unsafe_allow_html=True)
                if y.uyari_detaylari:
                    st.markdown("<ul>", unsafe_allow_html=True)
                    for detay in y.uyari_detaylari:
                        st.markdown(f"<li style='opacity: 0.8; font-size: 0.9em;'>{detay}</li>", unsafe_allow_html=True)
                    st.markdown("</ul>", unsafe_allow_html=True)
    else:
        st.info("Bu listede hiç yemek yok, harika!")
else:
    st.info("Ortak menüyü görebilmek için lütfen en az bir aile üyesi daha ekleyin.")
