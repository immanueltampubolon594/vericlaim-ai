import os
import urllib.parse
from typing import List, Literal
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_huggingface import HuggingFaceEmbeddings
from sentence_transformers import CrossEncoder
from supabase import create_client, Client
from ddgs import DDGS

from app.decomposer import decompose_news

load_dotenv()

# 1. Inisialisasi LLM Groq OpenAI OSS 20B (Lega Token TPM & Max Tokens 4096)
llm = ChatGroq(
    model="openai/gpt-oss-20b",
    temperature=0,
    max_tokens=4096   
)

# 2. Inisialisasi Embedding Lokal HuggingFace (Tahap 1: Bi-Encoder Retrieval)
embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)

# 3. Inisialisasi Model Cross-Encoder (Tahap 2: Cross-Encoder Reranker)
print("-> [Init] Memuat Model Cross-Encoder Re-Ranker...")
reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

# 4. Skema Output Laporan (Diperkaya Modus Hoaks & Tips Literasi Digital)
class VerifiedSubClaim(BaseModel):
    id: int
    claim: str
    status: Literal["BENAR", "SALAH", "TIDAK_DAPAT_DIPASTIKAN"]
    confidence_score: float = Field(description="Skor keyakinan (0.0 - 1.0 atau 0 - 100)")
    explanation: str
    evidence_source: str = Field(description="WAJIB berupa URL tautan web (diawali https://) dari bukti rujukan. Jika tidak ada bukti, isi dengan 'Tidak Ada'")

class FactCheckReport(BaseModel):
    original_news: str
    final_verdict: Literal["BENAR", "MENYESATKAN", "HOAX"]
    summary: str
    sub_claims_result: List[VerifiedSubClaim]
    # --- FITUR TAMBAHAN: LITERASI EDUKASI PUBLIK ---
    manipulation_tactics: List[str] = Field(description="Daftar taktik psikologis / modus hoaks yang digunakan (contoh: 'False Urgency', 'Impersonasi Tokoh', 'Fear Mongering')")
    educational_tips: List[str] = Field(description="Daftar 2-3 tips praktis literasi digital agar pembaca tidak tertipu pola hoaks serupa")

# 5. Fungsi Two-Stage Re-Ranking
def rerank_candidate_docs(query: str, raw_documents: list, top_k: int = 3) -> list:
    if not raw_documents:
        return []
    
    pairs = [[query, doc.get("content", "")] for doc in raw_documents]
    scores = reranker.predict(pairs)
    
    for idx, doc in enumerate(raw_documents):
        doc["rerank_score"] = float(scores[idx])
        
    ranked_docs = sorted(raw_documents, key=lambda x: x["rerank_score"], reverse=True)
    return ranked_docs[:top_k]

# 6. PENCARIAN SUMBER 1: Supabase Vector Search dengan Two-Stage Re-Ranking
def search_supabase_facts(query: str, count: int = 8) -> str:
    try:
        query_vector = embeddings.embed_query(query)
        
        # Tahap 1: Tarik 8 kandidat dokumen mentah dari Supabase
        res = None
        try:
            res = supabase.rpc("match_fact_documents", {
                "query_embedding": query_vector,
                "match_count": count
            }).execute()
        except Exception:
            res = supabase.rpc("match_vericlaim_documents", {
                "query_embedding": query_vector,
                "match_count": count
            }).execute()
        
        candidates = res.data if res else []
        if not candidates:
            return ""
        
        # Tahap 2: Re-Ranking menggunakan Cross-Encoder (Ambil Top-3 paling presisi)
        top_matches = rerank_candidate_docs(query, candidates, top_k=3)
        
        snippets = []
        for m in top_matches:
            raw_url = m.get('url', '')
            raw_title = m.get('title', '')
            rerank_score = m.get('rerank_score', 0)

            # Google Search Fallback agar tautan selalu aktif
            if "turnbackhoax.id" in raw_url:
                clean_query = raw_title.replace("[SALAH]", "").replace("[PENIPUAN]", "").replace("Tidak Benar,", "").strip()
                safe_url = f"https://www.google.com/search?q={urllib.parse.quote_plus(clean_query + ' turnbackhoax fakta')}"
            else:
                safe_url = raw_url

            snippets.append(
                f"[Arsip TurnBackHoax (Re-Rank Score: {rerank_score:.2f})]\n"
                f"Judul: {raw_title}\n"
                f"Fakta: {m.get('content')}\n"
                f"Link: {safe_url}"
            )
        return "\n\n".join(snippets)
    except Exception as e:
        print(f"[Supabase Error]: {e}")
        return ""

# 7. PENCARIAN SUMBER 2: Live Web Search
def search_web_evidence(query: str, max_results: int = 2) -> str:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query + " hoax turnbackhoax fakta", region="id-id", max_results=max_results))
            if not results:
                return ""
            snippets = []
            for r in results:
                snippets.append(f"[Berita Web Live]\nJudul: {r.get('title')}\nCuplikan: {r.get('body')}\nLink: {r.get('href')}")
            return "\n\n".join(snippets)
    except Exception:
        return ""

# 8. Gabungkan Multi-Source RAG
def retrieve_multi_source_evidence(claim: str) -> str:
    local_evidence = search_supabase_facts(claim)
    web_evidence = search_web_evidence(claim)
    
    combined = []
    if local_evidence:
        combined.append(local_evidence)
    if web_evidence:
        combined.append(web_evidence)
        
    if not combined:
        return "Tidak ditemukan bukti pendukung maupun bantahan yang valid."
    return "\n\n".join(combined)

# 9. Prompt Hakim Verifikator & Edukator Literasi Digital
verifier_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "Kamu adalah pakar verifikator fakta (Fact-Checker) dan edukator literasi digital Indonesia dengan standar jurnalisme tinggi.\n\n"
        "TUGAS UTAMA:\n"
        "1. Analisis klaim murni berdasarkan teks BUKTI yang dilampirkan.\n"
        "2. Di kolom 'manipulation_tactics', sebutkan trik psikologis atau modus hoaks yang digunakan dalam pesan ini (contoh: 'False Urgency', 'Impersonasi Pejabat', 'Fear Mongering').\n"
        "3. Di kolom 'educational_tips', berikan 2-3 tips literasi digital praktis agar masyarakat terlindung dari modus serupa.\n\n"
        "ATURAN MUTLAK:\n"
        "- Di kolom 'evidence_source', WAJIB menuliskan tautan URL murni (diawali https://) dari BUKTI yang dilampirkan. Jika tidak ada, isi 'Tidak Ada'."
    ),
    (
        "human",
        "BERITA ASLI:\n{original_news}\n\n"
        "BUKTI-BUKTI MULTI-SOURCE:\n{claims_with_evidence}\n\n"
        "Keluarkan laporan cek fakta lengkap beserta modul edukasi literasi dalam format terstruktur sesuai skema."
    )
])

verifier_chain = verifier_prompt | llm.with_structured_output(FactCheckReport)

# 10. Fungsi Utama
def verify_claim(news_text: str) -> FactCheckReport:
    decomposition = decompose_news(news_text)
    
    claims_evidence_text = ""
    for item in decomposition.sub_claims:
        evidence = retrieve_multi_source_evidence(item.claim)
        claims_evidence_text += f"\n[Sub-Klaim {item.id}]: {item.claim}\nBUKTI:\n{evidence}\n"
    
    report = verifier_chain.invoke({
        "original_news": news_text,
        "claims_with_evidence": claims_evidence_text
    })
    return report