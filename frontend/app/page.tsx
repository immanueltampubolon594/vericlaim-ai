"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { 
  ShieldAlert, 
  CheckCircle2, 
  XCircle, 
  AlertTriangle, 
  ExternalLink, 
  Sparkles, 
  Send, 
  LogOut, 
  User, 
  Upload,
  FileDown,
  BookOpen,
  Lightbulb
} from "lucide-react";

interface SubClaimResult {
  id: number;
  claim: string;
  status: "BENAR" | "SALAH" | "TIDAK_DAPAT_DIPASTIKAN";
  confidence_score: number;
  explanation: string;
  evidence_source: string;
}

interface ReportData {
  original_news: string;
  final_verdict: "BENAR" | "MENYESATKAN" | "HOAX";
  summary: string;
  sub_claims_result: SubClaimResult[];
  manipulation_tactics: string[];
  educational_tips: string[];
}

export default function Home() {
  const [userEmail, setUserEmail] = useState<string>("");
  const [inputNews, setInputNews] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const [ocrLoading, setOcrLoading] = useState<boolean>(false);
  const [pdfLoading, setPdfLoading] = useState<boolean>(false);
  const [report, setReport] = useState<ReportData | null>(null);
  const [error, setError] = useState<string>("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();

  useEffect(() => {
    const email = localStorage.getItem("user_email");
    if (email) {
      setUserEmail(email);
    }
  }, []);

  const handleLogout = () => {
    localStorage.removeItem("user_email");
    router.push("/login");
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setOcrLoading(true);
    setError("");

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch("http://127.0.0.1:8000/api/ocr-extract", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) throw new Error("Gagal mengekstrak teks dari berkas.");
      const data = await response.json();
      
      if (data.extracted_text) {
        setInputNews(data.extracted_text);
        handleCheck(data.extracted_text);
      } else {
        setError("Tidak ada teks yang dapat dibaca dari berkas tersebut.");
      }
    } catch (err: any) {
      setError(err.message || "Gagal memproses berkas.");
    } finally {
      setOcrLoading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleCheck = async (textToCheck: string = inputNews) => {
    if (!textToCheck.trim()) return;
    setLoading(true);
    setError("");
    setReport(null);

    try {
      const response = await fetch("http://127.0.0.1:8000/api/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: textToCheck }),
      });

      if (!response.ok) throw new Error("Gagal terhubung ke AI Backend FastAPI.");
      const data: ReportData = await response.json();
      setReport(data);
    } catch (err: any) {
      setError(err.message || "Terjadi kesalahan pada server. Pastikan uvicorn menyala.");
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadPDF = async () => {
    if (!report) return;
    setPdfLoading(true);

    try {
      const response = await fetch("http://127.0.0.1:8000/api/export-pdf", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(report),
      });

      if (!response.ok) throw new Error("Gagal mengunduh dokumen PDF.");

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `VeriClaim_Report_${Date.now()}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err: any) {
      alert("Gagal mengunduh PDF: " + err.message);
    } finally {
      setPdfLoading(false);
    }
  };

  return (
    <main 
      style={{ backgroundImage: "url('/bg-cyber.png')" }}
      className="min-h-screen bg-slate-950 bg-cover bg-center bg-fixed text-[#F8FAFC] flex flex-col font-sans selection:bg-[#06B6D4] selection:text-[#030712] overflow-x-hidden relative"
    >
      <div className="absolute inset-0 bg-slate-950/40 pointer-events-none z-0"></div>

      <div className="relative z-10 flex flex-col min-h-screen">

        {/* Navbar */}
        <header className="border-b border-[#2B374E] bg-[#090D16]/90 backdrop-blur-xl sticky top-0 z-50 px-6 py-4 flex items-center justify-between w-full">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-[#3B82F6] to-[#06B6D4] flex items-center justify-center shadow-lg shadow-[#06B6D4]/20 shrink-0">
              <ShieldAlert className="h-6 w-6 text-[#030712]" />
            </div>
            <div>
              <h1 className="font-bold text-lg tracking-tight text-[#F8FAFC]">VeriClaim AI</h1>
              <p className="text-xs text-[#94A3B8]">Multimodal & Two-Stage RAG Fact-Checker</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="hidden sm:flex items-center gap-2 text-xs bg-[#131C2E] border border-[#2B374E] px-3.5 py-1.5 rounded-full text-[#F8FAFC]">
              <User className="h-3.5 w-3.5 text-[#06B6D4]" />
              <span className="font-medium text-slate-300 truncate max-w-[180px]">{userEmail || "AI Engineer"}</span>
            </div>

            <button
              onClick={handleLogout}
              className="flex items-center gap-1.5 text-xs bg-[#EF4444]/10 hover:bg-[#EF4444]/20 border border-[#EF4444]/30 px-3.5 py-1.5 rounded-xl text-[#EF4444] font-medium transition-all cursor-pointer shrink-0"
            >
              <LogOut className="h-3.5 w-3.5" /> Keluar
            </button>
          </div>
        </header>

      {/* Main Content */}
        <div className="flex-1 max-w-4xl w-full mx-auto px-4 md:px-6 py-6 flex flex-col gap-6 overflow-x-hidden">
          
          {/* Hero Banner */}
          <div className="text-center py-3 flex flex-col items-center gap-2.5">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#06B6D4]/10 border border-[#06B6D4]/20 text-[#22D3EE] text-xs font-medium">
              <Sparkles className="h-3.5 w-3.5" /> Real-Time Multimodal News Intelligence & Media Literacy
            </div>
            <h2 className="text-3xl md:text-5xl font-extrabold tracking-tight max-w-2xl text-[#F8FAFC]">
              Deteksi Hoax dan Berita Menyesatkan Seketika.
            </h2>
            <p className="text-[#94A3B8] text-sm md:text-base max-w-xl">
              Dilengkapi analisis modus psikologis hoaks dan panduan edukasi literasi digital publik.
            </p>
          </div>

          {/* Quick Test Chips */}
          <div className="flex flex-wrap items-center justify-center gap-2">
            <span className="text-xs text-[#64748B]">Contoh Uji Coba:</span>
            {[
              "Presiden meresmikan jalan tol baru di Jawa dan gratis selamanya",
              "Bagi-bagi subsidi uang tunai 50 juta rupiah untuk semua warga"
            ].map((example, i) => (
              <button
                key={i}
                onClick={() => { setInputNews(example); handleCheck(example); }}
                className="text-xs bg-[#131C2E]/90 hover:bg-[#1A253A] border border-[#2B374E] px-3 py-1.5 rounded-lg text-[#94A3B8] hover:text-[#F8FAFC] transition-all text-left truncate max-w-xs cursor-pointer shadow-md"
              >
                "{example}"
              </button>
            ))}
          </div>

          {/* Analysis Box */}
          <div className="bg-[#131C2E]/90 border border-[#2B374E] rounded-2xl p-4 shadow-2xl flex flex-col gap-4 backdrop-blur-xl max-w-full overflow-hidden">
            
            <div className="flex flex-col gap-2.5">
              <textarea
                rows={3}
                value={inputNews}
                onChange={(e) => setInputNews(e.target.value)}
                placeholder="Tempel teks berita, broadcast WhatsApp, atau unggah tangkapan layar / dokumen PDF hoaks..."
                className="w-full bg-[#090D16] border border-[#2B374E] rounded-xl p-3.5 text-sm text-[#F8FAFC] placeholder:text-[#64748B] focus:outline-none focus:border-[#06B6D4] transition-all resize-none shadow-inner"
              />
              
              <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
                <input 
                  type="file" 
                  ref={fileInputRef} 
                  onChange={handleFileUpload} 
                  accept="image/*,.pdf,application/pdf" 
                  className="hidden" 
                />

                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={ocrLoading || loading}
                  className="flex items-center gap-2 text-xs bg-[#1E293B] hover:bg-[#334155] border border-slate-700 px-4 py-2.5 rounded-xl text-slate-300 font-medium transition-all cursor-pointer disabled:opacity-50"
                >
                  {ocrLoading ? (
                    <>
                      <div className="h-3.5 w-3.5 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
                      Mengekstrak Berkas...
                    </>
                  ) : (
                    <>
                      <Upload className="h-4 w-4 text-[#06B6D4]" /> Unggah Gambar / PDF
                    </>
                  )}
                </button>

                <button
                  onClick={() => handleCheck(inputNews)}
                  disabled={loading || ocrLoading || !inputNews.trim()}
                  style={{ backgroundColor: '#06B6D4', color: '#030712' }}
                  className="hover:bg-[#22D3EE] disabled:opacity-50 font-bold px-6 py-2.5 rounded-xl text-sm flex items-center gap-2 shadow-lg shadow-[#06B6D4]/25 transition-all cursor-pointer disabled:cursor-not-allowed ml-auto"
                >
                  {loading ? (
                    <>
                      <div className="h-4 w-4 border-2 border-[#030712] border-t-transparent rounded-full animate-spin" />
                      Menganalisis...
                    </>
                  ) : (
                    <>
                      <Send className="h-4 w-4" /> Periksa Fakta
                    </>
                  )}
                </button>
              </div>
            </div>

            {error && (
              <div className="p-3 bg-[#EF4444]/10 border border-[#EF4444]/20 rounded-xl text-[#EF4444] text-xs flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {/* REPORT RESULTS */}
            {report && (
              <div className="flex flex-col gap-6 pt-4 border-t border-[#2B374E] animate-in fade-in duration-500 max-w-full overflow-hidden">
                
                {/* Header Action: Download PDF Resmi */}
                <div className="flex items-center justify-between pb-1">
                  <span className="text-xs font-semibold text-slate-400">Hasil Cek Fakta Inteligensi:</span>
                  <button
                    onClick={handleDownloadPDF}
                    disabled={pdfLoading}
                    className="flex items-center gap-2 text-xs bg-[#0284C7]/20 hover:bg-[#0284C7]/30 border border-[#0284C7]/40 text-sky-400 px-3.5 py-1.5 rounded-xl font-medium transition-all cursor-pointer shadow-md disabled:opacity-50"
                  >
                    {pdfLoading ? (
                      <>
                        <div className="h-3 w-3 border-2 border-sky-400 border-t-transparent rounded-full animate-spin" />
                        Membuat PDF...
                      </>
                    ) : (
                      <>
                        <FileDown className="h-3.5 w-3.5" /> Unduh Laporan PDF
                      </>
                    )}
                  </button>
                </div>

                {/* Verdict Header Badge */}
                <div className={`p-5 rounded-2xl border flex flex-col md:flex-row items-start md:items-center justify-between gap-4 max-w-full overflow-hidden ${
                  report.final_verdict === "HOAX" 
                    ? "bg-[#EF4444]/10 border-[#EF4444]/30 text-[#EF4444]" 
                    : report.final_verdict === "MENYESATKAN"
                    ? "bg-[#F59E0B]/10 border-[#F59E0B]/30 text-[#F59E0B]"
                    : "bg-[#10B981]/10 border-[#10B981]/30 text-[#10B981]"
                }`}>
                  <div className="flex items-center gap-4">
                    <div className="p-3 rounded-xl bg-[#090D16]/80 border border-white/5 shrink-0">
                      {report.final_verdict === "HOAX" && <XCircle className="h-8 w-8 text-[#EF4444]" />}
                      {report.final_verdict === "MENYESATKAN" && <AlertTriangle className="h-8 w-8 text-[#F59E0B]" />}
                      {report.final_verdict === "BENAR" && <CheckCircle2 className="h-8 w-8 text-[#10B981]" />}
                    </div>
                    <div>
                      <span className="text-xs uppercase tracking-wider font-semibold opacity-80">Verdict Akhir AI</span>
                      <h3 className="text-2xl font-black tracking-tight">{report.final_verdict}</h3>
                    </div>
                  </div>
                  <p className="text-xs md:text-sm text-[#94A3B8] w-full md:max-w-md bg-[#090D16]/80 p-3.5 rounded-xl border border-white/5 leading-relaxed break-words">
                    {report.summary}
                  </p>
                </div>

                {/* --- FITUR BARU: KARTU AKADEMI LITERASI DIGITAL --- */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Modus / Taktik Hoaks */}
                  <div className="bg-[#090D16]/90 border border-purple-500/30 rounded-2xl p-5 flex flex-col gap-3 shadow-lg">
                    <div className="flex items-center gap-2 text-purple-400 font-bold text-xs uppercase tracking-wider">
                      <BookOpen className="h-4 w-4" /> Modus & Taktik Psikologis Hoaks
                    </div>
                    <div className="flex flex-wrap gap-1.5 pt-1">
                      {report.manipulation_tactics?.map((tactic, idx) => (
                        <span key={idx} className="text-xs bg-purple-500/10 border border-purple-500/30 text-purple-300 px-3 py-1 rounded-full font-medium">
                          {tactic}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Tips Literasi Digital */}
                  <div className="bg-[#090D16]/90 border border-cyan-500/30 rounded-2xl p-5 flex flex-col gap-3 shadow-lg">
                    <div className="flex items-center gap-2 text-cyan-400 font-bold text-xs uppercase tracking-wider">
                      <Lightbulb className="h-4 w-4" /> Tips Literasi Digital Mandiri
                    </div>
                    <ul className="flex flex-col gap-1.5 text-xs text-slate-300 list-disc list-inside">
                      {report.educational_tips?.map((tip, idx) => (
                        <li key={idx} className="leading-relaxed">{tip}</li>
                      ))}
                    </ul>
                  </div>
                </div>

                {/* Sub-Claims Breakdown */}
                <div className="flex flex-col gap-3 max-w-full overflow-hidden">
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-[#64748B]">
                    Dekomposisi Sub-Klaim & Bukti Verifikasi (Two-Stage Reranked)
                  </h4>
                  
                  <div className="grid gap-3 max-w-full">
                    {report.sub_claims_result.map((sub, idx) => (
                      <div key={idx} className="bg-[#090D16]/85 border border-[#2B374E] rounded-2xl p-5 flex flex-col gap-3 shadow-inner max-w-full overflow-hidden">
                        
                        <div className="flex flex-col gap-3 w-full max-w-full overflow-hidden">
                          <div className="flex items-start gap-3 w-full max-w-full">
                            <span className="flex items-center justify-center h-6 w-6 rounded-lg bg-[#1E293B] text-[#F8FAFC] text-xs font-bold shrink-0 border border-slate-700">
                              {sub.id}
                            </span>
                            <p className="text-sm font-semibold text-[#F8FAFC] break-words whitespace-normal flex-1 max-w-full">"{sub.claim}"</p>
                          </div>
                          
                          <div className="flex flex-wrap items-center gap-2 pl-9">
                            <span className={`text-xs px-2.5 py-1 rounded-full font-bold ${
                              sub.status === "SALAH" ? "bg-[#EF4444]/20 text-[#EF4444] border border-[#EF4444]/30" :
                              sub.status === "BENAR" ? "bg-[#10B981]/20 text-[#10B981] border border-[#10B981]/30" :
                              "bg-[#F59E0B]/20 text-[#F59E0B] border border-[#F59E0B]/30"
                            }`}>
                              {sub.status}
                            </span>
                            <span className="text-xs bg-[#111827] border border-[#2B374E] px-2.5 py-1 rounded-full text-[#94A3B8] font-mono">
                              {sub.confidence_score}% Keyakinan
                            </span>
                          </div>
                        </div>

                        <p className="text-xs text-[#94A3B8] pl-0 md:pl-9 leading-relaxed break-words whitespace-normal max-w-full">
                          <strong className="text-[#F8FAFC]">Analisis:</strong> {sub.explanation}
                        </p>

                        <div className="pl-0 md:pl-9 pt-2.5 border-t border-[#1E293B] flex items-center gap-2 text-xs text-[#06B6D4] max-w-full overflow-hidden">
                          <ExternalLink className="h-3.5 w-3.5 shrink-0" />
                          {sub.evidence_source && sub.evidence_source.startsWith("http") ? (
                            <a 
                              href={sub.evidence_source} 
                              target="_blank" 
                              rel="noopener noreferrer" 
                              className="truncate hover:underline hover:text-[#22D3EE] cursor-pointer max-w-full font-medium"
                            >
                              Rujukan: {sub.evidence_source}
                            </a>
                          ) : (
                            <span className="truncate text-slate-500 max-w-full">
                              Rujukan: {sub.evidence_source || "Tidak ada bukti tautan"}
                            </span>
                          )}
                        </div>

                      </div>
                    ))}
                  </div>
                </div>

              </div>
            )}

          </div>

        </div>

        {/* Footer */}
        <footer className="border-t border-[#2B374E]/60 py-6 text-center text-xs text-[#64748B] bg-slate-950/60 backdrop-blur-md">
          VeriClaim AI Enterprise Engine • Built with FastAPI, Two-Stage Reranked RAG & Supabase pgvector.
        </footer>

      </div>
    </main>
  );
}