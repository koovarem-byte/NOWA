from supabase import create_client

SUPABASE_URL = "ВСТАВЬ_СЮДА_СВОЙ_URL"

SUPABASE_KEY = "ВСТАВЬ_СЮДА_СВОЙ_ANON_KEY"

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)