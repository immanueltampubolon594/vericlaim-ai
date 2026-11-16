import { createClient } from '@supabase/supabase-js'

// Ambil URL dan Anon/Public Key dari project Supabase kamu
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || "https://rojzefukixfxlktfyszf.supabase.co"
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "eyJhbGciOi..." // Ganti dengan anon/publishable key dari Supabase kamu

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY)