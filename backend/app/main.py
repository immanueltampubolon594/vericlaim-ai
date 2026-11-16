import os
import io
import traceback
from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from supabase import create_client, Client
from dotenv import load_dotenv
import easyocr
import pypdf

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from app.verifier import verify_claim, FactCheckReport

load_dotenv()

app = FastAPI(
    title="VeriClaim API",
    description="Enterprise Multi-Source RAG Fact-Checker with Multimodal Vision, PDF Parsing & Two-Stage Reranking",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

# Inisialisasi OCR Reader
print("-> [Init] Memuat Model OCR Lokal (EasyOCR)...")
ocr_reader = easyocr.Reader(['id', 'en'], gpu=False)

class NewsCheckRequest(BaseModel):
    text: str = Field(..., description="Pesan berita atau teks klaim")

class AuthRequest(BaseModel):
    email: str
    password: str

# 1. Endpoint Register
@app.post("/api/register")
async def register_user(payload: AuthRequest):
    try:
        existing = supabase.table("app_users").select("*").eq("email", payload.email).execute()
        if existing.data:
            raise HTTPException(status_code=400, detail="Email sudah terdaftar.")
        
        supabase.table("app_users").insert({
            "email": payload.email,
            "password": payload.password
        }).execute()
        
        return {"status": "success", "message": "Registrasi berhasil!"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# 2. Endpoint Login
@app.post("/api/login")
async def login_user(payload: AuthRequest):
    try:
        res = supabase.table("app_users").select("*").eq("email", payload.email).eq("password", payload.password).execute()
        if not res.data:
            raise HTTPException(status_code=401, detail="Email atau password salah.")
        
        return {"status": "success", "message": "Login berhasil!", "user": {"email": payload.email}}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# 3. Endpoint Multimodal Ingestion (Mendukung Gambar PNG/JPG & Dokumen PDF)
@app.post("/api/ocr-extract")
async def extract_text_from_media(file: UploadFile = File(...)):
    try:
        file_bytes = await file.read()
        filename = (file.filename or "").lower()
        content_type = (file.content_type or "").lower()
        extracted_text = ""

        # JIKA YANG DIUNGGAH ADALAH FILE PDF (Surat Edaran / Siaran Pers)
        if filename.endswith(".pdf") or "pdf" in content_type:
            pdf_stream = io.BytesIO(file_bytes)
            pdf_reader = pypdf.PdfReader(pdf_stream)
            pages_text = []
            for page in pdf_reader.pages:
                text = page.extract_text()
                if text:
                    pages_text.append(text)
            extracted_text = " ".join(pages_text).strip()
            print(f"-> [PDF Ingestion Sukses]: Berhasil mengekstrak {len(pdf_reader.pages)} halaman.")

        # JIKA YANG DIUNGGAH ADALAH GAMBAR (Screenshot WA, Foto Pamflet)
        else:
            results = ocr_reader.readtext(file_bytes, detail=0)
            extracted_text = " ".join(results).strip()
            print(f"-> [OCR Sukses]: {extracted_text[:100]}...")

        if not extracted_text:
            raise HTTPException(status_code=400, detail="Tidak ada teks yang dapat dikenali dalam berkas tersebut.")

        return {"status": "success", "extracted_text": extracted_text}
    except Exception as e:
        print("\n[Media Ingestion Error]:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Gagal memproses berkas: {str(e)}")

# 4. Endpoint Verifikasi Utama
@app.post("/api/verify", response_model=FactCheckReport)
async def check_news_endpoint(payload: NewsCheckRequest):
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Teks berita tidak boleh kosong.")
    try:
        report = verify_claim(payload.text)
        return report
    except Exception as e:
        print("\n================ DETEKSI ERROR BACKEND ================")
        traceback.print_exc()
        print("=======================================================\n")
        raise HTTPException(status_code=500, detail=f"Gagal memproses verifikasi: {str(e)}")

# 5. Endpoint Export PDF Laporan Investigasi Resmi
@app.post("/api/export-pdf")
async def export_pdf_report(report: FactCheckReport):
    try:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
        elements = []
        
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=18, textColor=colors.HexColor('#0F172A'), spaceAfter=8)
        meta_style = ParagraphStyle('Meta', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#64748B'), spaceAfter=14)
        verdict_style = ParagraphStyle('Verdict', parent=styles['Heading2'], fontSize=14, textColor=colors.HexColor('#DC2626') if report.final_verdict == "HOAX" else colors.HexColor('#16A34A'), spaceAfter=10)
        body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#334155'), leading=14, spaceAfter=8)

        elements.append(Paragraph("VERICLAIM AI • FACT-CHECK INTELLIGENCE REPORT", title_style))
        elements.append(Paragraph("Dokumen Audit Cek Fakta Resmi Berbasis Two-Stage RAG & Multi-Source Verification", meta_style))
        elements.append(Spacer(1, 10))

        elements.append(Paragraph(f"FINAL VERDICT: {report.final_verdict}", verdict_style))
        elements.append(Paragraph(f"<b>Ringkasan Eksekutif:</b> {report.summary}", body_style))
        elements.append(Spacer(1, 12))

        table_data = [["No", "Sub-Klaim", "Status", "Keyakinan", "Analisis & Sumber"]]
        for item in report.sub_claims_result:
            sub_text = f"<b>{item.claim}</b><br/><font size='8' color='#64748B'>Sumber: {item.evidence_source}</font>"
            table_data.append([
                str(item.id),
                Paragraph(sub_text, body_style),
                item.status,
                f"{item.confidence_score}%",
                Paragraph(item.explanation, body_style)
            ])

        t = Table(table_data, colWidths=[25, 170, 75, 60, 210])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E293B')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 9),
            ('BOTTOMPADDING', (0,0), (-1,0), 6),
            ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#F8FAFC')),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ]))
        elements.append(t)

        doc.build(elements)
        buffer.seek(0)
        return StreamingResponse(
            buffer, 
            media_type="application/pdf", 
            headers={"Content-Disposition": "attachment; filename=VeriClaim_FactCheck_Report.pdf"}
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Gagal generate PDF: {str(e)}")

@app.get("/")
def read_root():
    return {"status": "online", "service": "VeriClaim AI Enterprise Engine"}