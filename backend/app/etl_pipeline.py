import os
import json
import pandas as pd
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from langchain_text_splitters import RecursiveCharacterTextSplitter

# 1. Skema Dokumen Standar AI Engineer
class DocumentChunk(BaseModel):
    chunk_id: str
    source: str
    title: str
    content: str
    url: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

# 2. Pipeline ETL Multi-Source
class MultiSourceETLPipeline:
    def __init__(self, chunk_size: int = 600, chunk_overlap: int = 100):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""]
        )

    def _extract_chunks(self, df: pd.DataFrame, source_name: str, max_records: int) -> List[DocumentChunk]:
        # Deteksi nama kolom secara dinamis (mengantisipasi beda nama kolom di tiap media)
        title_col = 'judul' if 'judul' in df.columns else 'title'
        content_col = 'clean_text' if 'clean_text' in df.columns else ('konten' if 'konten' in df.columns else 'content')
        url_col = 'url' if 'url' in df.columns else 'link'

        sample_df = df.dropna(subset=[title_col, content_col]).head(max_records)
        chunks_result: List[DocumentChunk] = []

        for idx, row in sample_df.iterrows():
            title = str(row[title_col]).strip()
            content = str(row[content_col]).strip()
            url = str(row.get(url_col, '')) if url_col in df.columns else ''

            if len(content) < 50: # Abaikan artikel yang terlalu pendek/kosong
                continue

            chunks = self.text_splitter.split_text(content)
            for c_idx, chunk_text in enumerate(chunks):
                chunks_result.append(DocumentChunk(
                    chunk_id=f"{source_name.lower()}_{idx}_c{c_idx}",
                    source=source_name,
                    title=title,
                    content=chunk_text,
                    url=url,
                    metadata={"source": source_name, "chunk_idx": c_idx}
                ))

        return chunks_result

    def build_corpus(self, sources_config: Dict[str, Dict[str, Any]], output_path: str):
        all_chunks: List[DocumentChunk] = []

        for source_name, cfg in sources_config.items():
            path = cfg["path"]
            limit = cfg["limit"]
            if os.path.exists(path):
                print(f"-> [ETL] Memproses {limit} artikel dari {source_name} ({path})...")
                df = pd.read_csv(path)
                chunks = self._extract_chunks(df, source_name, limit)
                all_chunks.extend(chunks)
                print(f"   -> Selesai: {len(chunks)} chunks dihasilkan dari {source_name}.")
            else:
                print(f"-> [Warning] File {path} tidak ditemukan, dilewati.")

        print(f"\n-> [ETL] Menyimpan total {len(all_chunks)} chunks ke {output_path}...")
        json_data = [c.model_dump() for c in all_chunks]
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
            
        print(f"-> [ETL] SUKSES BESAR! Corpus {output_path} berhasil dibuat ({len(json_data)} dokumen)!\n")

if __name__ == "__main__":
    pipeline = MultiSourceETLPipeline(chunk_size=600, chunk_overlap=100)

    # Konfigurasi Multi-Source Dataset
    sources = {
        "TurnBackHoax": {"path": "data/raw/tbh_cleaned_v3.csv", "limit": 300},
        "Kompas":       {"path": "data/raw/kompas_cleaned_v3.csv", "limit": 200},
        "AntaraNews":   {"path": "data/raw/antaranews_cleaned_v3.csv", "limit": 200},
        "Detik":        {"path": "data/raw/detik_cleaned_v3.csv", "limit": 200},
    }

    output_file = "data/processed/knowledge_base.json"
    pipeline.build_corpus(sources, output_file)