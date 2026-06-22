# Öneriler Sayfası 

import streamlit as st
from src.session import get_profil, profil_var_mi
from src.food_db import yemekleri_yukle, kategori_goster, tum_kategoriler
from src.recommendation import toplu_degerlendir
from src.models import UygunlukDurumu
from src.ui import inject_custom_css, render_metric

# CSS Enjeksiyonu
inject_custom_css()

st.markdown("<h1 class='hero-title'>🍽️ Kişiselleştirilmiş Yemek Önerileri</h1>", unsafe_allow_html=True)

# Kullanıcı profili yoksa uyar ve durdur
if not profil_var_mi():
    st.warning("⚠️ Henüz bir sağlık profili oluşturmadınız. Lütfen önce sol menüden 'Profil' sayfasına giderek profilinizi tamamlayın.")
    st.stop()

profil = get_profil()
ana_kullanici = profil.ana_kullanici

st.markdown(f"Merhaba **{ana_kullanici.ad}**, aşağıdaki öneriler senin sağlık profiline ("
            f"*{', '.join([h.value.title() for h in ana_kullanici.hastaliklar]) or 'Bilinen hastalık yok'}*) "
            f"özel olarak hazırlanmıştır.")

# Kategoriler için filtre
tum_kat = tum_kategoriler()
secilen_kategori = st.selectbox(
    "Kategori Filtresi", 
    options=["Tümü"] + tum_kat,
    format_func=lambda x: "Tüm Yemekler" if x == "Tümü" else kategori_goster(x)
)

# Yemekleri veritabanından çek ve (varsa) filtrele
yemekler = yemekleri_yukle()
if secilen_kategori != "Tümü":
    yemekler = [y for y in yemekler if y["kategori"] == secilen_kategori]

# Toplu değerlendirme motorunu çalıştır
sonuclar = toplu_degerlendir(yemekler, ana_kullanici)

st.markdown("<br>", unsafe_allow_html=True)

# Üst kısımda Metrik Kartları (Dashboard görünümü)
m1, m2, m3 = st.columns(3)
with m1:
    render_metric("Rahatça Yenebilir", len(sonuclar['uygun']), "text-green")
with m2:
    render_metric("Porsiyon Kontrolü", len(sonuclar['dikkatli']), "text-yellow")
with m3:
    render_metric("Uzak Durulmalı", len(sonuclar['onerilmez']), "text-red")

st.markdown("<hr style='margin: 2rem 0; opacity: 0.5;'>", unsafe_allow_html=True)

# --- UYGUN YEMEKLER ---
st.markdown("<h3 style='color: #10b981;'>✅ Rahatça Tüketebilecekleriniz</h3>", unsafe_allow_html=True)
if sonuclar["uygun"]:
    for y in sonuclar["uygun"]:
        with st.expander(f"🟢 {y.yemek_adi}"):
            st.markdown(f"<div style='opacity: 0.9;'><b>Neden Uygun?</b> {y.aciklama}</div>", unsafe_allow_html=True)
else:
    st.info("Bu kategoride profilinize tam uygun bir yemek bulunamadı.")

# --- DİKKATLİ YEMEKLER ---
st.markdown("<h3 style='color: #f59e0b; margin-top: 2rem;'>⚠️ Porsiyon Kontrolüyle Tüketilebilecekler</h3>", unsafe_allow_html=True)
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
    st.info("Bu kategoride dikkatli tüketmeniz gereken bir yemek bulunamadı.")

# --- ÖNERİLMEYEN YEMEKLER ---
st.markdown("<h3 style='color: #ef4444; margin-top: 2rem;'>❌ Uzak Durmanız Gerekenler</h3>", unsafe_allow_html=True)
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
    st.info("Harika! Bu kategoride size yasaklı olan bir yemek yok.")
