
import os
from langchain_chroma import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

from src.logger import get_logger
from src.config import settings

logger = get_logger(__name__)


_vector_db = None
_klinik_db = None
_embeddings = None

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
CHROMA_DIR = settings.CHROMA_PERSIST_DIR


def _get_embeddings() -> HuggingFaceEmbeddings:
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(model_name=MODEL_NAME)
    return _embeddings


def _get_vector_db() -> Chroma:
    global _vector_db
    if _vector_db is not None:
        return _vector_db

    _vector_db = Chroma(
        collection_name="kullanici_hafizasi",
        embedding_function=_get_embeddings(),
        persist_directory=CHROMA_DIR,
    )
    return _vector_db

def geri_bildirim_ekle(kullanici_id: str, mesaj: str):
    try:
        vector_db = _get_vector_db()
        vector_db.add_texts(
            texts=[mesaj],
            metadatas=[{"kullanici_id": kullanici_id}],
        )
        logger.info("Hafızaya eklendi (%s)", kullanici_id)
    except RuntimeError as e:
        logger.warning("Geri bildirim kaydedilemedi: %s", e)

def hafizadakini_getir(kullanici_id: str, mesaj: str, k_adet: int = 3) -> list[str]:
    try:
        vector_db = _get_vector_db()
    except Exception as e:
        logger.warning("Hafiza hazirlanamadi, bos geciliyor: %s", e)
        return []

    try:
        sonuclar = vector_db.similarity_search(
            query=mesaj, 
            k=k_adet,
            filter={"kullanici_id": kullanici_id}
        )
    except Exception as e:
        logger.warning("Geçmiş getirilirken hata yaşandı. Hata: %s", str(e))
        return []
        
    return [doc.page_content for doc in sonuclar]

class ClinicalEvidence(str):
    def __new__(cls, content):
        obj = super().__new__(cls, content)
        obj.citations = []
        return obj

def klinik_bilgi_getir(sorgu: str, k_adet: int = 3) -> str:
    global _klinik_db
    try:
        if _klinik_db is None:
            _klinik_db = Chroma(
                collection_name="klinik_kutuphane",
                embedding_function=_get_embeddings(),
                persist_directory=CHROMA_DIR,
            )
        
        # similarity_search_with_score returns (Document, score) tuples
        sonuclar = _klinik_db.similarity_search_with_score(query=sorgu, k=k_adet)
        if not sonuclar:
            return ClinicalEvidence("")
            
        birlestirilmis_metin = "\n\n--- KLİNİK KAYNAK ---\n"
        citations = []
        for i, (doc, score) in enumerate(sonuclar):
            kaynak = doc.metadata.get("source", "Bilinmeyen Kaynak")
            kaynak_adi = os.path.basename(kaynak)
            birlestirilmis_metin += f"[{kaynak_adi}]:\n{doc.page_content}\n\n"
            citations.append({
                "source_id": kaynak_adi,
                "similarity_score": score,
                "evidence_span": doc.page_content[:200]
            })
            
        result = ClinicalEvidence(birlestirilmis_metin)
        result.citations = citations
        return result
    except Exception as e:
        logger.warning("Klinik kütüphanede arama yapılırken hata oluştu: %s", e)
        return ClinicalEvidence("")
