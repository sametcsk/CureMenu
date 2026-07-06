import os
import sys
from tqdm import tqdm
from langchain_community.document_loaders import PyMuPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma

# Ensure project root is in python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.memory import _get_embeddings, CHROMA_DIR
from src.logger import get_logger

logger = get_logger(__name__)

RAG_FOLDER = os.getenv("RAG_FOLDER", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "rag_dosyalari"))

def main():
    if not os.path.exists(RAG_FOLDER):
        logger.error("RAG klasörü bulunamadı: %s", RAG_FOLDER)
        return

    logger.info("RAG Belgeleri taranıyor...")
    
    documents = []
    files_to_process = [f for f in os.listdir(RAG_FOLDER) if f.endswith('.pdf') or f.endswith('.txt')]
    
    if not files_to_process:
        logger.warning("RAG klasöründe işlenecek PDF veya TXT dosyası bulunamadı.")
        return
        
    for filename in tqdm(files_to_process, desc="Dosyalar Yükleniyor"):
        filepath = os.path.join(RAG_FOLDER, filename)
        try:
            if filename.endswith('.pdf'):
                loader = PyMuPDFLoader(filepath)
                documents.extend(loader.load())
            elif filename.endswith('.txt'):
                loader = TextLoader(filepath, encoding='utf-8')
                documents.extend(loader.load())
        except Exception as e:
            logger.error("Dosya okunamadı %s: %s", filename, e)

    logger.info("Toplam %d sayfa/bölüm yüklendi. Parçalanıyor...", len(documents))

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", " ", ""]
    )
    
    chunks = text_splitter.split_documents(documents)
    logger.info("Toplam %d adet chunk (parça) oluşturuldu. Vektör DB'ye kaydediliyor...", len(chunks))

    embedding_function = _get_embeddings()

    # Vektör veritabanını oluştur ve kaydet
    try:
        vector_db = Chroma.from_documents(
            documents=chunks,
            embedding=embedding_function,
            collection_name="klinik_kutuphane",
            persist_directory=CHROMA_DIR
        )
        logger.info("Başarıyla ChromaDB'ye kaydedildi! RAG modeli artık bu dosyaları hafızasında tutuyor.")
    except Exception as e:
        logger.error("ChromaDB kaydı sırasında hata oluştu: %s", e)

if __name__ == "__main__":
    main()
