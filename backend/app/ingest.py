import os
import json
import time
from typing import List, Dict, Any
from dotenv import load_dotenv
from supabase import create_client, Client
from langchain_huggingface import HuggingFaceEmbeddings

load_dotenv()

# 1. Inisialisasi Klien Supabase
supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

# 2. Inisialisasi Embedding Lokal (HuggingFace - Gratis & Tanpa Batas API / 384 Dimensi)
print("-> [Init] Memuat model embedding lokal (HuggingFace)...")
embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)

def ingest_from_json(json_path: str, batch_size: int = 40):
    print(f"-> [Ingest] Membaca corpus terstruktur dari: {json_path}")
    with open(json_path, "r", encoding="utf-8") as f:
        docs: List[Dict[str, Any]] = json.load(f)
        
    print(f"-> [Ingest] Total dokumen chunk yang akan diunggah: {len(docs)}")
    
    # Bersihkan data lama di tabel Supabase agar bersih dan tidak duplikat
    try:
        supabase.table("fact_documents").delete().neq("id", 0).execute()
        print("-> [Ingest] Menghapus data lama di database agar rapi...")
    except Exception as e:
        print(f"-> [Warning] Gagal membersihkan data lama: {e}")

    # Proses Batching 
    for i in range(0, len(docs), batch_size):
        batch = docs[i : i + batch_size]
        print(f"-> [Ingest] Memproses batch {i // batch_size + 1} dari total {(len(docs) + batch_size - 1) // batch_size} ({len(batch)} dokumen)...")
        
        # 1. Ekstrak teks konten untuk di-embedding secara lokal di laptop
        texts = [item["content"] for item in batch]
        
        # 2. Generate Vektor Angka via HuggingFace (Lokal)
        vectors = embeddings.embed_documents(texts)
        
        # 3. Siapkan payload untuk Supabase
        records = []
        for j, item in enumerate(batch):
            records.append({
                "title": item["title"],
                "content": item["content"],
                "url": item.get("url", ""),
                "embedding": vectors[j]
            })
            
        # 4. Upload batch ke Supabase
        try:
            supabase.table("fact_documents").insert(records).execute()
        except Exception as e:
            print(f"-> [Error] Gagal mengunggah batch ke Supabase: {e}")
            
        # Jeda sebentar (opsional karena sudah lokal, tapi bagus untuk kestabilan)
        time.sleep(0.5)

    print("-> [Ingest] SELESAI! Semua dokumen JSON berhasil tertanam di Supabase pgvector!")

if __name__ == "__main__":
    json_file = "data/processed/knowledge_base.json"
    ingest_from_json(json_file, batch_size=40)