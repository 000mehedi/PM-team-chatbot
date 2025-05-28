from datetime import datetime
import pandas as pd
from io import BytesIO
import base64
from typing import Optional, List, Dict
from .supabase_client import supabase

# ======================= User =======================

def add_user(username: str, password: str, name: str) -> None:
    # WARNING: Storing passwords in plaintext is insecure.
    # Use Supabase Auth for user management instead.
    supabase.table("users").insert({
        "username": username,
        "password": password,
        "name": name
    }).execute()

def get_user_by_username(username: str) -> Optional[Dict]:
    res = supabase.table("users").select("*").eq("username", username).execute()
    data = res.data
    if data and len(data) == 1:
        return data[0]
    return None

# ======================= Uploaded File =======================

def save_uploaded_file(session_id: str, filename: str, bytes_data: bytes, user_id: str) -> None:
    encoded_content = base64.b64encode(bytes_data).decode("utf-8")
    supabase.table("uploaded_files").upsert({
        "session_id": session_id,
        "filename": filename,
        "content": encoded_content,  # store as base64 string
        "user_id": user_id
    }).execute()


def load_uploaded_file(session_id: str, user_id: str) -> Optional[pd.DataFrame]:
    if not session_id:
        return None

    res = supabase.table("uploaded_files") \
        .select("filename, content") \
        .eq("session_id", session_id) \
        .eq("user_id", user_id) \
        .order("id", desc=True) \
        .limit(1) \
        .execute()

    if not res.data:
        return None

    row = res.data[0]
    filename, encoded_content = row["filename"], row["content"]
    file_bytes = base64.b64decode(encoded_content)

    if filename.endswith(('.xlsx', '.xls')):
        return pd.read_excel(BytesIO(file_bytes))
    elif filename.endswith('.csv'):
        return pd.read_csv(BytesIO(file_bytes))
    else:
        return None
# ======================= Chat Sessions =======================

def create_new_session(user_id: str, session_name: str) -> str:
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_name = f"{session_name} ({created_at})"
    res = supabase.table("chats").insert({
        "user_id": user_id,           # <-- pass user_id here!
        "session_name": full_name,
        "created_at": created_at
    }).execute()
    return res.data[0]["id"]

    return res.data[0]["id"]

def get_all_sessions(user_id: str) -> list:
    res = supabase.table("chats") \
        .select("*") \
        .eq("user_id", user_id) \
        .order("created_at", desc=True) \
        .execute()
    chats = res.data or []
    return [{
        "id": chat["id"],
        "display_name": f"{chat['session_name']} ({chat['created_at']})",
        "session_name": chat["session_name"],
        "created_at": chat["created_at"]
    } for chat in chats]

def update_session_name(session_id: int, new_name: str) -> None:
    supabase.table("chats").update({"session_name": new_name}).eq("id", session_id).execute()

def rename_session(session_id: int, base_name: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    update_session_name(session_id, f"{base_name} ({timestamp})")

def delete_session(session_id: int, user_id: str) -> None:
    if not user_owns_session(user_id, session_id):
        raise PermissionError("You don't own this session")
    supabase.table("messages").delete().eq("session_id", session_id).execute()
    supabase.table("uploaded_files").delete().eq("session_id", session_id).execute()
    supabase.table("chats").delete().eq("id", session_id).execute()

# ======================= Messages =======================

def save_message(session_id: int, role: str, content: str, message_type: str = "text") -> None:
    supabase.table("messages").insert({
        "session_id": session_id,
        "role": role,
        "content": content,
        "message_type": message_type,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }).execute()

def load_messages_by_session(session_id: int) -> List[Dict]:
    if not session_id:
        return []
    res = supabase.table("messages") \
        .select("*") \
        .eq("session_id", session_id) \
        .order("timestamp", desc=False) \
        .execute()
    return res.data or []

def get_last_messages(session_id: int, n: int = 10) -> List[Dict]:
    res = supabase.table("messages") \
        .select("role, content") \
        .eq("session_id", session_id) \
        .order("timestamp", desc=True) \
        .limit(n) \
        .execute()
    rows = res.data or []
    rows.reverse()  # to get oldest first
    return [{"role": row["role"], "content": row["content"]} for row in rows]

def add_message_to_session(user_id: str, session_id: int, content: str, role: str = "user") -> None:
    if not user_owns_session(user_id, session_id):
        raise PermissionError("You don't own this session")
    save_message(session_id, role, content)

def get_messages_for_session(user_id: str, session_id: int) -> List[Dict]:
    if not user_owns_session(user_id, session_id):
        raise PermissionError("You don't own this session")
    return load_messages_by_session(session_id)

# ======================= FAQ =======================

def load_faqs() -> pd.DataFrame:
    res = supabase.table("faqs").select("*").execute()
    data = res.data
    return pd.DataFrame(data) if data else pd.DataFrame(columns=["category", "question", "answer"])

def add_faq(category: str, question: str, answer: str) -> None:
    supabase.table("faqs").insert({
        "category": category,
        "question": question,
        "answer": answer
    }).execute()

def delete_faq(faq_id: str) -> None:
    supabase.table("faqs").delete().eq("id", faq_id).execute()

# ======================= Security =======================

def user_owns_session(user_id: str, session_id: int) -> bool:
    res = supabase.table("chats").select("*") \
        .eq("id", session_id) \
        .eq("user_id", user_id) \
        .single() \
        .execute()
    return res.data is not None



def get_user_memory(user_id):
    res = supabase.table("user_memory").select("memory").eq("user_id", user_id).limit(1).execute()
    if res.data:
        return res.data[0]["memory"]
    return ""  # fallback if no memory yet
def update_user_memory(user_id, new_memory):
    existing = supabase.table("user_memory").select("user_id").eq("user_id", user_id).execute()
    if existing.data:
        supabase.table("user_memory").update({"memory": new_memory}).eq("user_id", user_id).execute()
    else:
        supabase.table("user_memory").insert({"user_id": user_id, "memory": new_memory}).execute()