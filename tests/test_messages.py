from src.messages import kullanici_hatasi, ZAMAN_ASIMI, AI_YAPILANDIRMA_HATASI, GENEL_HATA


def test_timeout_turkceye_cevrilir():
    assert kullanici_hatasi(Exception("Connection timeout")) == ZAMAN_ASIMI


def test_api_key_hatasi_turkce():
    assert kullanici_hatasi(Exception("Invalid API key provided")) == AI_YAPILANDIRMA_HATASI


def test_bilinmeyen_hata_genel_mesaj():
    assert kullanici_hatasi(Exception("some random internal error xyz")) == GENEL_HATA
