import requests
import cv2
import numpy as np
import ipaddress
import socket
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from langchain_core.messages import HumanMessage
from src.config import settings
from src.llm import invoke_with_model_fallback, parse_llm_response

MAX_IMAGE_BASE64_LEN = 8_000_000  # ~6 MB ham görüntü
MAX_REDIRECTS = 3


def _is_private_host(hostname: str) -> bool:
    if not hostname:
        return True
    host = hostname.strip("[]").lower()
    if host in {"localhost", "0.0.0.0"} or host.endswith(".local"):
        return True

    try:
        addresses = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError("Menü adresi çözümlenemedi.") from exc

    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return True
    return False


def _validate_public_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Geçerli bir http/https menü linki girin.")
    if _is_private_host(parsed.hostname):
        raise ValueError("Güvenlik ihlali: iç ağ adreslerine erişim yasaktır.")
    return raw


def _normalize_base64_image(image_base64: str) -> str:
    """data:image/jpeg;base64,... önekini temizler."""
    raw = (image_base64 or "").strip()
    if "," in raw and raw.lower().startswith("data:"):
        return raw.split(",", 1)[1]
    return raw


def scrape_menu_from_url(url: str) -> str:
    """
    Verilen URL'deki sayfayı indirir ve içindeki metinleri çıkarır.
    SSRF, Timeout ve OOM (Boyut) korumaları içerir.
    """
    try:
        # Anti-bot korumalarını aşmak için kendimizi sisteme gerçek bir tarayıcı (Chrome) gibi gösteriyoruz
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        url = _validate_public_url(url)
        response = None
        for _ in range(MAX_REDIRECTS + 1):
            response = requests.get(url, headers=headers, timeout=5, allow_redirects=False)
            if response.is_redirect:
                location = response.headers.get("Location")
                if not location:
                    break
                url = _validate_public_url(urljoin(url, location))
                continue
            break
        if response is None:
            raise ValueError("Menü linki okunamadı.")
        if response.is_redirect:
            raise ValueError("Menü linkinde çok fazla yönlendirme var.")
        response.raise_for_status()
        
        # Sunucumuzun RAM'ini (OOM) şişirmemeleri için indirilecek HTML dosyasına 5MB üst limit koyuyoruz
        if len(response.content) > 5 * 1024 * 1024:
            raise ValueError("Güvenlik İhlali: Hedef sayfa boyutu çok büyük (Maksimum 5MB).")
            
        # BeautifulSoup ile HTML'i parse et
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # LLM'e göndermeyeceğimiz script ve style gibi gereksiz DOM etiketlerini HTML'den ayıklıyoruz
        for element in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            element.extract()
            
        # Kalan saf HTML'in içinden sadece ham metinleri (text) çekiyoruz
        text = soup.get_text(separator="\n")
        
        # Token tasarrufu için boş satırları ve gereksiz boşlukları (whitespace) optimize ediyoruz
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text_clean = "\n".join(chunk for chunk in chunks if chunk)
        
        # Context sınırını (Token limiti) aşmamak için en alakalı ilk 5000 karakteri döndürüyoruz
        return text_clean[:5000]
        
    except requests.exceptions.Timeout:
        raise Exception("Menü sayfasına ulaşılamadı: Zaman aşımı (Timeout).")
    except Exception as e:
        raise Exception(f"Menü linki okunamadı: {str(e)}")

def extract_text_from_image_base64(image_base64: str) -> str:
    """
    Kullanıcının yüklediği menü fotoğrafını Gemini Vision modeline göndererek
    içindeki yemek isimlerini ve içerikleri metin olarak çıkarıyoruz (OCR işlemi).
    """
    try:
        payload = _normalize_base64_image(image_base64)
        if len(payload) > MAX_IMAGE_BASE64_LEN:
            raise ValueError("Görüntü çok büyük. Lütfen daha küçük bir fotoğraf yükleyin.")
        message = HumanMessage(
            content=[
                {"type": "text", "text": "Bu bir restoran menüsünün fotoğrafı. Lütfen içindeki tüm yemek adlarını, içeriklerini ve varsa fiyatlarını çıkar. Sadece menüdeki yazıları düz metin formatında (alt alta) yaz, ekstra yorum ekleme."},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{payload}"},
                },
            ]
        )
        response = invoke_with_model_fallback(
            [message],
            preferred_model=settings.GEMINI_VISION_MODEL,
            temperature=0.2,
        )
        return parse_llm_response(response)
    except Exception as e:
        raise Exception(f"Fotoğraftan menü okunamadı: {str(e)}")


def qr_kodu_oku(kamera_goruntusu) -> str:
    """Kullanıcının kamerasından gelen görüntüdeki QR kodunu okuyup URL'yi ayrıştırıyoruz."""
    try:
        file_bytes = np.asarray(bytearray(kamera_goruntusu.read()), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        if img is None:
            return "Görüntü okunamadı. Lütfen tekrar deneyin."

        detector = cv2.QRCodeDetector()
        data, _, _ = detector.detectAndDecode(img)
        if data and "http" in data.lower():
            return data.strip()
        return "QR kod bulunamadı. Kodu net şekilde gösterin veya linki manuel yapıştırın."
    except Exception as e:
        return f"QR okuma hatası: {str(e)}"


def menuyu_siteden_cek(url: str) -> str:
    """Streamlit QR Menü sayfası için uyumlu sarmalayıcı."""
    try:
        return scrape_menu_from_url(url)
    except Exception as e:
        return f"Hata: {str(e)}"

def extract_ingredients_from_image_base64(image_base64: str) -> str:
    """
    Kullanıcının yüklediği buzdolabı veya mutfak tezgahı fotoğrafını analiz ederek,
    içindeki yenilebilir tüm malzemeleri virgülle ayırarak döndürür.
    """
    try:
        payload = _normalize_base64_image(image_base64)
        if len(payload) > MAX_IMAGE_BASE64_LEN:
            raise ValueError("Görüntü çok büyük. Lütfen daha küçük bir fotoğraf yükleyin.")
        message = HumanMessage(
            content=[
                {
                    "type": "text", 
                    "text": "This is a photo of a refrigerator or kitchen counter. Please identify all edible ingredients (vegetables, fruits, meat, dairy, jars, sauces, etc.). List ONLY the names of the ingredients separated by commas IN TURKISH (e.g., Domates, Yumurta, Süt, Tavuk). If there is an unbranded jar, sauce, bottle, or closed container where you cannot determine the exact contents, add it to the list EXACTLY as '(Bilinmeyen Kap/Sos - Lütfen kullanmak isterseniz ne olduğunu tarifte belirtin)'. Do not add any other explanations or comments."
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{payload}"},
                },
            ]
        )
        response = invoke_with_model_fallback(
            [message],
            preferred_model=settings.GEMINI_VISION_MODEL,
            temperature=0.2,
        )
        raw_text = parse_llm_response(response)
        
        # Mükerrer olanları temizle (Özellikle Bilinmeyen Kap uyarısının 10 kez yazılmasını engellemek için)
        items = [item.strip() for item in raw_text.split(",")]
        unique_items = []
        for item in items:
            if item and item not in unique_items:
                unique_items.append(item)
                
        return ", ".join(unique_items)
    except Exception as e:
        raise Exception(f"Fotoğraftaki malzemeler okunamadı: {str(e)}")
    

    
