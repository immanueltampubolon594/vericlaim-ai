import os
import json
import time
import pandas as pd
from typing import List, Dict, Any
from dotenv import load_dotenv
from supabase import create_client, Client
from langchain_cohere import CohereEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
COHERE_API_KEY = os.getenv("COHERE_API_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
embeddings = CohereEmbeddings(
    cohere_api_key=COHERE_API_KEY,
    model="embed-multilingual-v3.0"
)

# Konfigurasi: Membaca SEMUA data tanpa batasan limit (None)
DATA_SOURCES = [
    {"source": "TurnBackHoax", "path": "data/raw/tbh_cleaned_v3.csv"},
    {"source": "Kompas",       "path": "data/raw/kompas_cleaned_v3.csv"},
    {"source": "AntaraNews",   "path": "data/raw/antaranews_cleaned_v3.csv"},
    {"source": "Detik",        "path": "data/raw/detik_cleaned_v3.csv"},
]

CHECKPOINT_FILE = "data/processed/full_ingest_checkpoint.json"

def load_checkpoint() -> int:
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, "r") as f:
            data = json.load(f)
            return data.get("last_index", 0)
    return 0

def save_checkpoint(index: int):
    os.makedirs(os.path.dirname(CHECKPOINT_FILE), exist_ok=True)
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump({"last_index": index}, f)

def run_full_enterprise_ingestion():
    print("-> [Full Scale Ingest] Memulai pemrosesan SELURUH dataset mentah...")
    
    all_dfs = []
    for src in DATA_SOURCES:
        if os.path.exists(src["path"]):
            print(f"-> Membaca {src['path']}...")
            df = pd.read_csv(src["path"])
            
            title_col = 'judul' if 'judul' in df.columns else 'title'
            content_col = 'clean_text' if 'clean_text' in df.columns else 'content'
            url_col = 'url' if 'url' in df.columns else 'link'
            
            temp_df = df[[title_col, content_col, url_col]].copy()
            temp_df.columns = ['title', 'content', 'url']
            temp_df['source'] = src["source"]
            all_dfs.append(temp_df)
            
    if not all_dfs:
        print("-> [Error] Tidak ada file CSV yang ditemukan di data/raw/!")
        return

    master_df = pd.concat(all_dfs, ignore_index=True)
    master_df = master_df.dropna(subset=['title', 'content']).drop_duplicates(subset=['content'])
    
    total_rows = len(master_df)
    print(f"-> Total bersih SELURUH artikel unik yang akan di-ingest: {total_rows} artikel.")

    splitter = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=100)
    
    start_idx = load_checkpoint()
    print(f"-> Melanjutkan progres dari indeks artikel ke-{start_idx} dari {total_rows}...")

    batch_size = 40  # Batch size aman untuk API Cohere
    batch_records = []

    for idx in range(start_idx, total_rows):
        row = master_df.iloc[idx]
        title = str(row['title']).strip()
        content = str(row['content']).strip()
        url = str(row['url']).strip()
        source = str(row['source']).strip()

        if len(content) < 40:
            continue

        chunks = splitter.split_text(content)
        for c_idx, chunk_text in enumerate(chunks):
            batch_records.append({
                "title": f"[{source}] {title}",
                "content": chunk_text,
                "url": url
            })

        if len(batch_records) >= batch_size or idx == total_rows - 1:
            if not batch_records:
                continue
                
            try:
                print(f"-> Mengunggah batch (Artikel ke-{idx}/{total_rows}), total {len(batch_records)} chunks...")
                texts = [r["content"] for r in batch_records]
                
                vectors = embeddings.embed_documents(texts)
                
                payload = []
                for b_i, rec in enumerate(batch_records):
                    payload.append({
                        "title": rec["title"],
                        "content": rec["content"],
                        "url": rec["url"],
                        "embedding": vectors[b_i]
                    })
                    
                # Masukkan ke tabel vericlaim_documents di Supabase
                supabase.table("vericlaim_documents").insert(payload).execute()
                
                save_checkpoint(idx + 1)
                batch_records = []
                
                time.sleep(1.0) # Jeda agar aman dari limit Cohere
                
            except Exception as e:
                print(f"-> [Warning/Error pada indeks {idx}]: {e}")
                print("-> Menunggu 15 detik sebelum mencoba kembali...")
                time.sleep(15)

    print("-> [Full Scale Ingest] SELESAI! Database Vektor kamu kini berisi puluhan ribu pengetahuan penuh!")

if __name__ == "__main__":
    run_full_enterprise_ingestion()