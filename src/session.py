# Session Yönetimi 

import streamlit as st
from src.models import KullaniciProfili, AileUyesi

def init_session():
    """Uygulama açıldığında boş bir profil oluşturur."""
    if "profil" not in st.session_state:
        st.session_state.profil = KullaniciProfili()

def get_profil() -> KullaniciProfili:
    """Mevcut profili getirir."""
    init_session()
    return st.session_state.profil

def set_ana_kullanici(uye: AileUyesi):
    """Kullanıcının kendi bilgilerini kaydeder."""
    init_session()
    st.session_state.profil.ana_kullanici = uye

def aile_uyesi_ekle(uye: AileUyesi):
    """Aileye yeni bir kişi ekler."""
    init_session()
    st.session_state.profil.aile_uyeleri.append(uye)

def aile_uyesi_sil(uye_id: str):
    """Aile üyesini ID'sine göre siler."""
    init_session()
    st.session_state.profil.aile_uyeleri = [
        u for u in st.session_state.profil.aile_uyeleri
        if u.id != uye_id
    ]

def profil_var_mi() -> bool:
    """Kullanıcı kendi profilini doldurmuş mu kontrol eder."""
    init_session()
    return st.session_state.profil.ana_kullanici is not None

    
        
