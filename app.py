# CureMenu Ana Sayfa 


import streamlit as st
from src.ui import inject_custom_css

# Sayfa ayarları 
st.set_page_config(
    page_title="CureMenu | Sağlıklı Karar Motoru",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS Enjeksiyonu (Premium görünüm)
inject_custom_css()

# Ana sayfa başlığı (Gradient efektli)
st.markdown("<h1 class='hero-title'>🍽️ CureMenu</h1>", unsafe_allow_html=True)
st.subheader("Your body is unique. Your plate should be too.")

st.write("") # Boşluk

# İki Sütunlu Modern Düzen
col1, col2 = st.columns([1.5, 1])

with col1:
    st.markdown("""
    <div class="custom-card">
        <h3>📌 CureMenu Nedir?</h3>
        <p style="opacity: 0.9; line-height: 1.6;">
        Türkiye'de milyonlarca kişi diyabet, çölyak veya hipertansiyon gibi kronik hastalıklarla mücadele ediyor. 
        Evde her gün <b>"Ne pişirsem?"</b> veya <b>"Bana uygun mu?"</b> sorusu büyük bir strese dönüşüyor.<br><br>
        CureMenu, Türk mutfağının karmaşık yapısını analiz eder ve sizin veya ailenizin sağlık profiline göre:
        </p>
        <ul style="opacity: 0.9; padding-left: 20px;">
            <li><span style="color: #10b981; font-weight:bold;">✅ Güvenle yiyebileceklerinizi</span></li>
            <li><span style="color: #f59e0b; font-weight:bold;">⚠️ Porsiyon kontrolü yapmanız gerekenleri</span></li>
            <li><span style="color: #ef4444; font-weight:bold;">❌ Uzak durmanız gerekenleri</span></li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div class="custom-card">
        <h3>🚀 Nasıl Kullanılır?</h3>
        <p style="opacity: 0.9;">👈 <b>Sol menüden</b> adımları takip edin:</p>
        <ol style="opacity: 0.9; padding-left: 20px; line-height: 1.8;">
            <li><b>👤 Profil:</b> Kendi sağlık bilgilerinizi girin.</li>
            <li><b>👨‍👩‍👧‍👦 Aile (Yakında):</b> Aile üyelerini ekleyin.</li>
            <li><b>🍽️ Öneriler:</b> Size özel filtrelenmiş menüyü keşfedin.</li>
        </ol>
    </div>
    """, unsafe_allow_html=True)

st.write("") # Boşluk

# Tıbbi uyarı
st.warning(
    "**Tıbbi Uyarı:** CureMenu bir tıbbi teşhis veya tedavi aracı değildir. "
    "Öneriler genel beslenme kurallarına dayanmaktadır. Lütfen diyetinizle ilgili köklü değişiklikler yapmadan önce "
    "doktorunuza veya diyetisyeninize danışın.",
    icon="⚕️"
)
