import streamlit as st

def inject_custom_css():
    """Uygulamaya modern, şık ve premium bir CSS tasarımı enjekte eder."""
    st.markdown("""
        <style>
        /* Google Fonts: Inter */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
        
        /* Genel Font Ayarları */
        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif !important;
        }

        /* Gradient Hero Başlık */
        .hero-title {
            background: linear-gradient(135deg, #2563eb, #14b8a6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 800;
            font-size: 3rem !important;
            padding-bottom: 0.5rem;
        }

        /* Modern Kart Tasarımı */
        .custom-card, [data-testid="stForm"] {
            background-color: var(--secondary-background-color);
            color: var(--text-color);
            border-radius: 16px;
            padding: 24px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2), 0 2px 4px -1px rgba(0, 0, 0, 0.1);
            border: 1px solid rgba(128,128,128,0.2);
            margin-bottom: 1rem;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        .custom-card:hover, [data-testid="stForm"]:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
        }

        /* Butonları Şıklaştırma */
        .stButton>button {
            background-color: #2563eb !important;
            color: white !important;
            border-radius: 8px !important;
            border: none !important;
            font-weight: 600 !important;
            padding: 0.5rem 1.5rem !important;
            transition: all 0.2s ease !important;
        }
        .stButton>button:hover {
            background-color: #1d4ed8 !important;
            box-shadow: 0 4px 12px rgba(37, 99, 235, 0.2) !important;
        }

        /* Uyarı (Warning) Kutusunu Güzelleştirme */
        .stAlert {
            border-radius: 12px !important;
            border: none !important;
        }
        
        /* Expander (Açılır Kapanır Kutular) */
        .streamlit-expanderHeader {
            font-weight: 600 !important;
            border-radius: 8px !important;
        }
        
        /* Metrik Kutuları (Öneriler sayfasındaki üst sayılar) */
        .metric-box {
            background-color: var(--secondary-background-color);
            color: var(--text-color);
            border-radius: 12px;
            padding: 16px;
            text-align: center;
            border: 1px solid rgba(128,128,128,0.2);
            box-shadow: 0 1px 3px rgba(0,0,0,0.2);
        }
        .metric-value {
            font-size: 2rem;
            font-weight: 800;
        }
        .metric-label {
            font-size: 0.875rem;
            opacity: 0.8;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        .text-green { color: #10b981; }
        .text-yellow { color: #f59e0b; }
        .text-red { color: #ef4444; }
        
        </style>
    """, unsafe_allow_html=True)

def render_metric(label, value, color_class):
    """HTML tabanlı şık metrik kartı çizer."""
    st.markdown(f"""
        <div class="metric-box">
            <div class="metric-value {color_class}">{value}</div>
            <div class="metric-label">{label}</div>
        </div>
    """, unsafe_allow_html=True)
