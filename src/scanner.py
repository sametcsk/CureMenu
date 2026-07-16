import base64
import binascii
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
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_PIXELS = 16_000_000
MAX_IMAGE_DIMENSION = 8192
MAX_URL_RESPONSE_BYTES = 5 * 1024 * 1024
MAX_REDIRECTS = 3
ALLOWED_URL_PORTS = {"http": {80}, "https": {443}}
ALLOWED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}


class ImageValidationError(ValueError):
    pass


def _is_private_host(hostname: str) -> bool:
    if not hostname:
        return True
    host = hostname.strip("[]").lower()
    if host in {"localhost", "0.0.0.0"} or host.endswith(".local"):
        return True

    try:
        return not ipaddress.ip_address(host).is_global
    except ValueError:
        pass

    try:
        addresses = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError("Menü adresi çözümlenemedi.") from exc

    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            return True
    return False


def _validate_public_url(url: str) -> str:
    raw = (url or "").strip()
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Geçerli bir http/https menü linki girin.")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("Kullanıcı bilgisi içeren menü linklerine izin verilmez.")
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError as exc:
        raise ValueError("Menü linkindeki port geçersiz.") from exc
    if port not in ALLOWED_URL_PORTS[parsed.scheme]:
        raise ValueError("Menü linkinde yalnızca standart web portlarına izin verilir.")
    if _is_private_host(parsed.hostname):
        raise ValueError("Güvenlik ihlali: iç ağ adreslerine erişim yasaktır.")
    return raw


def _image_dimensions(data: bytes, mime_type: str) -> tuple[int, int]:
    if mime_type == "image/png":
        if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError("Geçersiz PNG görüntüsü.")
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")

    if mime_type == "image/webp":
        if len(data) < 30 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
            raise ValueError("Geçersiz WebP görüntüsü.")
        chunk_type = data[12:16]
        if chunk_type == b"VP8X":
            return int.from_bytes(data[24:27], "little") + 1, int.from_bytes(data[27:30], "little") + 1
        if chunk_type == b"VP8L" and len(data) >= 25 and data[20] == 0x2F:
            b0, b1, b2, b3 = data[21:25]
            width = 1 + b0 + ((b1 & 0x3F) << 8)
            height = 1 + ((b1 & 0xC0) >> 6) + (b2 << 2) + ((b3 & 0x0F) << 10)
            return width, height
        if chunk_type == b"VP8 " and len(data) >= 30 and data[23:26] == b"\x9d\x01\x2a":
            return int.from_bytes(data[26:28], "little") & 0x3FFF, int.from_bytes(data[28:30], "little") & 0x3FFF
        raise ValueError("Geçersiz WebP görüntüsü.")

    if len(data) < 4 or data[:3] != b"\xff\xd8\xff":
        raise ValueError("Geçersiz JPEG görüntüsü.")
    position = 2
    start_of_frame_markers = {
        0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
        0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF,
    }
    while position + 3 < len(data):
        if data[position] != 0xFF:
            position += 1
            continue
        while position < len(data) and data[position] == 0xFF:
            position += 1
        if position >= len(data):
            break
        marker = data[position]
        position += 1
        if marker in {0xD8, 0xD9}:
            continue
        if position + 2 > len(data):
            break
        segment_length = int.from_bytes(data[position:position + 2], "big")
        if segment_length < 2 or position + segment_length > len(data):
            break
        if marker in start_of_frame_markers and segment_length >= 7:
            height = int.from_bytes(data[position + 3:position + 5], "big")
            width = int.from_bytes(data[position + 5:position + 7], "big")
            return width, height
        position += segment_length
    raise ValueError("JPEG boyut bilgisi okunamadı.")


def _detect_image_mime(data: bytes) -> str:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    raise ValueError("Yalnızca JPEG, PNG veya WebP görüntüleri desteklenir.")


def _validate_base64_image_impl(image_base64: str) -> tuple[str, str]:
    """Base64 görüntüyü decode eder, gerçek biçimini ve güvenli boyutlarını doğrular."""
    raw = (image_base64 or "").strip()
    declared_mime = None
    if raw.lower().startswith("data:"):
        if "," not in raw:
            raise ValueError("Geçersiz görüntü veri adresi.")
        header, raw = raw.split(",", 1)
        header_parts = header[5:].split(";")
        declared_mime = header_parts[0].lower()
        if "base64" not in {part.lower() for part in header_parts[1:]}:
            raise ValueError("Görüntü base64 formatında olmalıdır.")
        if declared_mime not in ALLOWED_IMAGE_MIME_TYPES:
            raise ValueError("Yalnızca JPEG, PNG veya WebP görüntüleri desteklenir.")

    payload = "".join(raw.split())
    if not payload or len(payload) > MAX_IMAGE_BASE64_LEN:
        raise ValueError("Görüntü çok büyük veya boş. Lütfen daha küçük bir fotoğraf yükleyin.")
    try:
        decoded = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Görüntü verisi geçerli base64 formatında değil.") from exc
    if not decoded or len(decoded) > MAX_IMAGE_BYTES:
        raise ValueError("Görüntü çok büyük. Lütfen daha küçük bir fotoğraf yükleyin.")

    actual_mime = _detect_image_mime(decoded)
    if declared_mime and declared_mime != actual_mime:
        raise ValueError("Görüntünün bildirilen türü gerçek dosya biçimiyle eşleşmiyor.")
    width, height = _image_dimensions(decoded, actual_mime)
    if (
        width <= 0
        or height <= 0
        or width > MAX_IMAGE_DIMENSION
        or height > MAX_IMAGE_DIMENSION
        or width * height > MAX_IMAGE_PIXELS
    ):
        raise ValueError("Görüntü piksel boyutu çok büyük.")

    image = cv2.imdecode(np.frombuffer(decoded, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise ValueError("Görüntü dosyası bozuk veya okunamıyor.")
    return base64.b64encode(decoded).decode("ascii"), actual_mime


def _validate_base64_image(image_base64: str) -> tuple[str, str]:
    try:
        return _validate_base64_image_impl(image_base64)
    except ImageValidationError:
        raise
    except ValueError as exc:
        raise ImageValidationError(str(exc)) from exc


def _validate_response_peer(response) -> None:
    """Bağlantı soketi erişilebiliyorsa DNS rebinding ile özel ağa geçişi reddeder."""
    raw = getattr(response, "raw", None)
    connection = getattr(raw, "_connection", None) or getattr(raw, "connection", None)
    sock = getattr(connection, "sock", None)
    if sock is None:
        return
    try:
        peer_ip = ipaddress.ip_address(sock.getpeername()[0])
    except (OSError, ValueError, TypeError):
        return
    if not peer_ip.is_global:
        raise ValueError("Güvenlik ihlali: bağlantı iç ağ adresine yönlendi.")


def _read_limited_response(response) -> bytes:
    content_length = response.headers.get("Content-Length")
    if content_length:
        try:
            declared_size = int(content_length)
        except (TypeError, ValueError):
            declared_size = None
        if declared_size is not None and declared_size > MAX_URL_RESPONSE_BYTES:
            raise ValueError("Hedef sayfa boyutu çok büyük (Maksimum 5 MB).")

    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_content(chunk_size=64 * 1024):
        if not chunk:
            continue
        total += len(chunk)
        if total > MAX_URL_RESPONSE_BYTES:
            raise ValueError("Hedef sayfa boyutu çok büyük (Maksimum 5 MB).")
        chunks.append(chunk)
    return b"".join(chunks)


def scrape_menu_from_url(url: str) -> str:
    """
    Verilen URL'deki sayfayı indirir ve içindeki metinleri çıkarır.
    SSRF, Timeout ve OOM (Boyut) korumaları içerir.
    """
    try:
        # Bypass basic anti-bot mechanisms using browser User-Agent / Anti-bot korumalarını aşmak için User-Agent kullanımı
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        url = _validate_public_url(url)
        response = None
        for _ in range(MAX_REDIRECTS + 1):
            response = requests.get(
                url,
                headers=headers,
                timeout=(3.05, 5),
                allow_redirects=False,
                stream=True,
            )
            try:
                _validate_response_peer(response)
            except Exception:
                response.close()
                raise
            if response.is_redirect:
                location = response.headers.get("Location")
                response.close()
                if not location:
                    break
                url = _validate_public_url(urljoin(url, location))
                continue
            break
        if response is None:
            raise ValueError("Menü linki okunamadı.")
        if response.is_redirect:
            raise ValueError("Menü linkinde çok fazla yönlendirme var.")
        try:
            response.raise_for_status()
            response_bytes = _read_limited_response(response)
        finally:
            response.close()
            
        # Parse HTML content / HTML içeriğini ayrıştır
        encoding = response.encoding or "utf-8"
        soup = BeautifulSoup(response_bytes.decode(encoding, errors="replace"), "html.parser")
        
        # Remove non-content tags before text extraction / Metin çıkarımı öncesi gereksiz etiketleri temizle
        for element in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            element.extract()
            
        # Extract raw text content / Ham metin içeriğini çıkar
        text = soup.get_text(separator="\n")
        
        # Normalize whitespace to optimize token usage / Token optimizasyonu için boşlukları düzenle
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text_clean = "\n".join(chunk for chunk in chunks if chunk)
        
        # Truncate content to 5000 characters to stay within context limits / Context sınırını korumak için 5000 karaktere kırp
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
        payload, mime_type = _validate_base64_image(image_base64)
        message = HumanMessage(
            content=[
                {"type": "text", "text": "Bu bir restoran menüsünün fotoğrafı. Lütfen içindeki tüm yemek adlarını, içeriklerini ve varsa fiyatlarını çıkar. Sadece menüdeki yazıları düz metin formatında (alt alta) yaz, ekstra yorum ekleme."},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{payload}"},
                },
            ]
        )
        response = invoke_with_model_fallback(
            [message],
            preferred_model=settings.GEMINI_VISION_MODEL,
            temperature=0.2,
        )
        return parse_llm_response(response)
    except ImageValidationError:
        raise
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
        payload, mime_type = _validate_base64_image(image_base64)
        message = HumanMessage(
            content=[
                {
                    "type": "text", 
                    "text": "This is a photo of a refrigerator or kitchen counter. Please identify all edible ingredients (vegetables, fruits, meat, dairy, jars, sauces, etc.). List ONLY the names of the ingredients separated by commas IN TURKISH (e.g., Domates, Yumurta, Süt, Tavuk). If there is an unbranded jar, sauce, bottle, or closed container where you cannot determine the exact contents, add it to the list EXACTLY as '(Bilinmeyen Kap/Sos - Lütfen kullanmak isterseniz ne olduğunu tarifte belirtin)'. Do not add any other explanations or comments."
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{payload}"},
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
    except ImageValidationError:
        raise
    except Exception as e:
        raise Exception(f"Fotoğraftaki malzemeler okunamadı: {str(e)}")
    

    
