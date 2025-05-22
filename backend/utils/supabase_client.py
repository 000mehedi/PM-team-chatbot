from supabase import create_client
import os

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Set SUPABASE_URL and SUPABASE_KEY as environment variables.")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
