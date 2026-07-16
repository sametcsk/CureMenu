
import hashlib
import hmac
import os
import re
from typing import Any
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

from src.logger import get_logger, log_failure
from src.config import settings
from src.privacy.redaction import dumps_redacted_json, redact_text
from src.quality.retrieval_filter import filter_retrieval_results

logger = get_logger(__name__)


_vector_db = None
_klinik_db = None
_official_klinik_db = None
_embeddings = None

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
CHROMA_DIR = settings.CHROMA_PERSIST_DIR
MEMORY_NAMESPACE_VERSION = "v1"
MEMORY_NAMESPACE_RE = re.compile(r"^memory_v1_[0-9a-f]{64}$")


def build_memory_namespace(account_id: str, subject_id: str) -> str:
    """Return an opaque, account-scoped namespace for persisted user memory."""
    account = (account_id or "").strip()
    subject = (subject_id or "").strip()
    if not account or not subject:
        raise ValueError("account_id and subject_id are required")

    payload = f"{MEMORY_NAMESPACE_VERSION}|account:{account}|subject:{subject}".encode("utf-8")
    digest = hmac.new(
        settings.jwt_secret_key.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return f"memory_{MEMORY_NAMESPACE_VERSION}_{digest}"


def _is_memory_namespace(value: str) -> bool:
    return bool(MEMORY_NAMESPACE_RE.fullmatch(value or ""))


def _get_embeddings() -> HuggingFaceEmbeddings:
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(
            model_name=MODEL_NAME,
            model_kwargs={"local_files_only": settings.EMBEDDINGS_LOCAL_ONLY},
        )
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

def geri_bildirim_ekle(kullanici_id: str, mesaj: str, metadata: dict[str, Any] | None = None):
    if not _is_memory_namespace(kullanici_id):
        raise ValueError("opaque memory namespace is required")
    try:
        vector_db = _get_vector_db()
        safe_metadata = {"kullanici_id": kullanici_id}
        if metadata:
            safe_metadata["context_json"] = dumps_redacted_json(metadata)
        vector_db.add_texts(
            texts=[redact_text(mesaj or "")],
            metadatas=[safe_metadata],
        )
        logger.info("Hafızaya eklendi")
    except RuntimeError as e:
        log_failure(logger, "memory_write", e, component="memory")

def hafizadakini_getir(kullanici_id: str, mesaj: str, k_adet: int = 3) -> list[str]:
    if not _is_memory_namespace(kullanici_id):
        return []
    try:
        vector_db = _get_vector_db()
    except Exception as e:
        log_failure(logger, "memory_initialize", e, component="memory")
        return []

    try:
        sonuclar = vector_db.similarity_search(
            query=mesaj, 
            k=k_adet,
            filter={"kullanici_id": kullanici_id}
        )
    except Exception as e:
        log_failure(logger, "memory_search", e, component="memory")
        return []
        
    return [doc.page_content for doc in sonuclar]

class ClinicalEvidence(str):
    def __new__(cls, content):
        obj = super().__new__(cls, content)
        obj.citations = []
        obj.evidence_policy = "official_scoped_only"
        obj.review_required = True
        obj.clinical_review_status = "not_established"
        return obj

def klinik_bilgi_getir(sorgu: str, k_adet: int = 3) -> str:
    global _klinik_db, _official_klinik_db
    try:
        if _klinik_db is None:
            _klinik_db = Chroma(
                collection_name=settings.CLINICAL_RAG_COLLECTION,
                embedding_function=_get_embeddings(),
                persist_directory=CHROMA_DIR,
            )
        if _official_klinik_db is None:
            _official_klinik_db = Chroma(
                collection_name=settings.CLINICAL_OFFICIAL_RAG_COLLECTION,
                embedding_function=_get_embeddings(),
                persist_directory=CHROMA_DIR,
            )
        
        candidate_count = max(k_adet * 10, 40)
        ham_sonuclar = _klinik_db.similarity_search_with_score(query=sorgu, k=candidate_count)
        if _official_klinik_db._collection.count() > 0:
            ham_sonuclar.extend(
                _official_klinik_db.similarity_search_with_score(query=sorgu, k=candidate_count)
            )
        sonuclar = filter_retrieval_results(
            sorgu,
            ham_sonuclar,
            limit=k_adet,
            evidence_context="health_claim",
        )
        if not sonuclar:
            return ClinicalEvidence("")
            
        birlestirilmis_metin = "\n\n--- KLİNİK KAYNAK ---\n"
        citations = []
        for result in sonuclar:
            doc = result.document
            score = result.distance
            kaynak = doc.metadata.get("source", "Bilinmeyen Kaynak")
            kaynak_adi = os.path.basename(kaynak)
            page = doc.metadata.get("page_label") or doc.metadata.get("page")
            page_label = f", sayfa {page}" if page is not None else ""
            birlestirilmis_metin += f"[{kaynak_adi}{page_label}]:\n{doc.page_content}\n\n"
            citations.append({
                "source_id": f"{kaynak_adi}{page_label}",
                "title": kaynak_adi,
                "page": page,
                "similarity_score": score,
                "lexical_score": result.lexical_score,
                "matched_terms": list(result.matched_terms),
                "evidence_span": doc.page_content[:200],
                "authority": doc.metadata.get("authority"),
                "authority_tier": doc.metadata.get("authority_tier", 3),
                "source_role": doc.metadata.get("source_role"),
                "source_url": doc.metadata.get("source_url"),
                "scope_version": doc.metadata.get("scope_version"),
                "file_sha256": doc.metadata.get("file_sha256"),
                "registry_source_id": doc.metadata.get("registry_source_id"),
                "verification_status": "source_verified",
                "clinical_review_status": "pending",
                "review_required": True,
            })
            
        result = ClinicalEvidence(birlestirilmis_metin)
        result.citations = citations
        result.clinical_review_status = "pending"
        return result
    except Exception as e:
        log_failure(logger, "clinical_evidence_search", e, component="memory")
        return ClinicalEvidence("")
