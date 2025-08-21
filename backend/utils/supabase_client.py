from supabase import create_client
import os

# Add these imports to load .env file
try:
    from dotenv import load_dotenv
    # Load environment variables from .env file
    load_dotenv()
    print("Environment variables loaded from .env file")
except ImportError:
    print("python-dotenv package not found, trying to use existing environment variables")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("⚠️ Required environment variables not found!")
    print("SUPABASE_URL:", "✓ Found" if SUPABASE_URL else "❌ Not found")
    print("SUPABASE_KEY:", "✓ Found" if SUPABASE_KEY else "❌ Not found")
    raise ValueError("Set SUPABASE_URL and SUPABASE_KEY as environment variables.")

print(f"Connecting to Supabase at {SUPABASE_URL[:20]}...")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)