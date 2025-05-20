import psycopg2
import os

try:
    conn = psycopg2.connect(
        dbname=os.getenv("SUPABASE_DB"),
        user=os.getenv("SUPABASE_USER"),
        password=os.getenv("SUPABASE_PASSWORD"),
        host=os.getenv("SUPABASE_HOST"),
        port=os.getenv("SUPABASE_PORT"),
        sslmode='require'
    )
    print("Connection successful!")
    conn.close()
except Exception as e:
    print("Connection failed:", e)
