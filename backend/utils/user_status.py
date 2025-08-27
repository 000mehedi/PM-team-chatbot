from backend.utils.supabase_client import supabase

# Table: user_status (user_id: uuid, status: text)

def add_user_status(user_id: str, email: str, status: str = "pending"):
    supabase.table("user_status").upsert({"user_id": user_id, "email": email, "status": status}).execute()

def get_user_status(user_id: str) -> str:
    res = supabase.table("user_status").select("status").eq("user_id", user_id).execute()
    if res.data and len(res.data) > 0:
        return res.data[0]["status"]
    return None

def get_pending_users():
    res = supabase.table("user_status").select("user_id, email, status").eq("status", "pending").execute()
    return res.data or []

def approve_user(user_id: str):
    supabase.table("user_status").update({"status": "approved"}).eq("user_id", user_id).execute()

def block_user(user_id: str):
    supabase.table("user_status").update({"status": "blocked"}).eq("user_id", user_id).execute()
