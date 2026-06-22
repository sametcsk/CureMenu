import streamlit as st
import uuid
from src.session import get_profil, set_ana_kullanici
from src.models import AileUyesi, Hastalik, Cinsiyet
from src.ui import inject_custom_css

# CSS Enjeksiyonu
inject_custom_css()

st.title("👤 Kendi Sağlık Profiliniz")
st.markdown("Önce kendi profilinizi oluşturalım. Yemek önerileri bu bilgilere göre yapılacaktır.")

# Mevcut profili al
profil = get_profil()
mevcut_uye = profil.ana_kullanici

# Formu oluştur
with st.form("profil_formu", clear_on_submit=False):
    col_kisisel1, col_kisisel2, col_kisisel3 = st.columns(3)
    with col_kisisel1:
        ad = st.text_input("Adınız", value=mevcut_uye.ad if mevcut_uye else "")
    with col_kisisel2:
        yas = st.number_input("Yaşınız", min_value=1, max_value=120, value=mevcut_uye.yas if mevcut_uye else 30)
    with col_kisisel3:
        cinsiyet_str = st.selectbox(
            "Cinsiyetiniz", 
            ["Erkek", "Kadın"], 
            index=0 if (mevcut_uye and mevcut_uye.cinsiyet == Cinsiyet.ERKEK) else 1
        )
    
    st.markdown("<hr style='margin: 1.5rem 0; opacity: 0.5;'>", unsafe_allow_html=True)
    
    st.subheader("🏥 Sağlık Durumunuz")
    st.caption("Size uygun yemeklerin seçilmesi için lütfen rahatsızlıklarınızı işaretleyin.")
    
    # Checkboxları yan yana dizelim
    col_h1, col_h2 = st.columns(2)
    with col_h1:
        diyabet_var = st.checkbox("Diyabet (Şeker Hastalığı)", value=Hastalik.DIYABET in mevcut_uye.hastaliklar if mevcut_uye else False)
        colyak_var = st.checkbox("Çölyak", value=Hastalik.COLYAK in mevcut_uye.hastaliklar if mevcut_uye else False)
    with col_h2:
        hipertansiyon_var = st.checkbox("Hipertansiyon (Yüksek Tansiyon)", value=Hastalik.HIPERTANSIYON in mevcut_uye.hastaliklar if mevcut_uye else False)
        kolesterol_var = st.checkbox("Yüksek Kolesterol", value=Hastalik.KOLESTEROL in mevcut_uye.hastaliklar if mevcut_uye else False)
    
    st.markdown("<hr style='margin: 1.5rem 0; opacity: 0.5;'>", unsafe_allow_html=True)
    
    st.subheader("⚠️ Alerjileriniz")
    alerji_metni = st.text_input(
        "Alerjilerinizi virgülle ayırarak yazın (Örn: süt, yumurta, yer fıstığı)",
        value=", ".join(mevcut_uye.alerjiler) if mevcut_uye and mevcut_uye.alerjiler else "",
        help="Alerjiniz olan yiyecekleri yazmanız, ilerdeki filtrelemelerde işinize yarayacaktır."
    )
    
    st.markdown("<br>", unsafe_allow_html=True)

    # Form gönderilince çalışacak buton
    submit = st.form_submit_button("💾 Profilimi Kaydet", use_container_width=True)

# Butona basılırsa ne olacak?
if submit:
    if not ad:
        st.error("Lütfen adınızı girin!")
    else:
        # Seçilen hastalıkları listeye ekle
        secilen_hastaliklar = []
        if diyabet_var: secilen_hastaliklar.append(Hastalik.DIYABET)
        if colyak_var: secilen_hastaliklar.append(Hastalik.COLYAK)
        if hipertansiyon_var: secilen_hastaliklar.append(Hastalik.HIPERTANSIYON)
        if kolesterol_var: secilen_hastaliklar.append(Hastalik.KOLESTEROL)
        
        # Alerjileri temizle ve listeye çevir
        alerjiler_listesi = [a.strip().lower() for a in alerji_metni.split(",") if a.strip()]
        
        # Yeni AileUyesi nesnesi oluştur
        yeni_uye = AileUyesi(
            id=mevcut_uye.id if mevcut_uye else str(uuid.uuid4())[:8],
            ad=ad,
            yas=yas,
            cinsiyet=Cinsiyet.ERKEK if cinsiyet_str == "Erkek" else Cinsiyet.KADIN,
            hastaliklar=secilen_hastaliklar,
            alerjiler=alerjiler_listesi
        )
        
        # Sessiona kaydet
        set_ana_kullanici(yeni_uye)
        st.success(f"✅ Profiliniz başarıyla kaydedildi, {ad}! Artık size uygun yemekleri görebilirsiniz.")
