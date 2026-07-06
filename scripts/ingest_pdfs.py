import os
import glob
import time
import hashlib
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

DESKTOP_DIR = r"C:\Users\samet\Desktop\curemenu_rag_dosyaları"
CHROMA_PERSIST_DIR = "./chroma_db"
COLLECTION_NAME = "klinik_kutuphane"
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

def main():
    print(f"[{DESKTOP_DIR}] klasöründeki PDF'ler taranıyor...")
    
    # Tüm PDF dosyalarını bul
    pdf_files = glob.glob(os.path.join(DESKTOP_DIR, "*.pdf"))
    if not pdf_files:
        print("Klasörde hiç PDF dosyası bulunamadı!")
        return

    print(f"Toplam {len(pdf_files)} PDF dosyası bulundu.")
    
    docs = []
    # PDF'leri yükle
    for file_path in pdf_files:
        print(f"Yükleniyor: {os.path.basename(file_path)}")
        try:
            loader = PyMuPDFLoader(file_path)
            loaded_docs = loader.load()
            docs.extend(loaded_docs)
            print(f" -> {len(loaded_docs)} sayfa okundu.")
        except Exception as e:
            print(f"HATA: {os.path.basename(file_path)} okunamadı. Detay: {e}")

    if not docs:
        print("Okunabilir metin bulunamadı. Çıkılıyor.")
        return

    print(f"\nToplam {len(docs)} sayfalık devasa bir veri elde edildi. Parçalanıyor (Chunking)...")
    
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1500,
        chunk_overlap=300,
        separators=["\n\n", "\n", ".", " ", ""]
    )
    
    splits = text_splitter.split_documents(docs)
    print(f"INFO: Documents split into {len(splits)} chunks. Generating embeddings...")
    
    embeddings = HuggingFaceEmbeddings(model_name=MODEL_NAME)
    
    # ChromaDB'ye ekle
    vector_db = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=CHROMA_PERSIST_DIR
    )
    
    batch_size = 50
    for i in range(0, len(splits), batch_size):
        batch = splits[i:i + batch_size]
        
        batch_ids = [hashlib.md5(doc.page_content.encode("utf-8")).hexdigest() for doc in batch]
            
        try:
            vector_db.add_documents(documents=batch, ids=batch_ids)
            print(f"INFO: Ingested chunks {min(i + batch_size, len(splits))}/{len(splits)}")
        except Exception as e:
            print(f"ERROR: Ingestion failed at batch {i}: {e}")

    print("INFO: Ingestion complete.")

if __name__ == "__main__":
    main()
