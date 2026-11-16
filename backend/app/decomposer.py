import os
from typing import List
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()

# 1. Skema Pydantic dengan instruksi yang lebih tegas untuk LLM
class SubClaim(BaseModel):
    id: int = Field(description="Nomor urut sub-klaim")
    claim: str = Field(description="Sub-klaim spesifik yang bisa diverifikasi fakta kebenarannya")

class ClaimDecompositionResult(BaseModel):
    original_claim: str = Field(description="Wajib isi ulang klaim berita asli yang dimasukkan pengguna")
    sub_claims: List[SubClaim] = Field(description="Daftar potongan sub-klaim atomik")

# 2. Inisialisasi LLM
llm = ChatGroq(
    model="openai/gpt-oss-20b",
    temperature=0,
    max_tokens=4096   
)

# 3. Prompt Instruksi Pemecah Berita yang dipertegas
prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "Kamu adalah asisten fact-checker bahasa Indonesia level pakar.\n"
        "Tugasmu adalah menganalisis klaim berita kompleks dan memecahnya menjadi sub-klaim atomik.\n"
        "PENTING: Kamu wajib menyertakan kembali teks berita asli ke dalam properti 'original_claim'."
    ),
    ("human", "Analisis dan pecah klaim berita berikut:\n\n{claim}")
])

decomposer_chain = prompt | llm.with_structured_output(ClaimDecompositionResult)

def decompose_news(claim_text: str) -> ClaimDecompositionResult:
    result = decomposer_chain.invoke({"claim": claim_text})
    
    # Safety fallback: Jika LLM tetap lupa mengisi original_claim, kita isi secara otomatis
    if not result.original_claim:
        result.original_claim = claim_text
        
    return result

if __name__ == "__main__":
    contoh_berita = (
        "Presiden meresmikan jalan tol baru di Jawa dan mulai besok "
        "seluruh jalan tol tersebut gratis selamanya tanpa bayar e-toll."
    )
    hasil = decompose_news(contoh_berita)
    print("Berita Asli:", hasil.original_claim)
    print("Sub-Klaim:", hasil.sub_claims)