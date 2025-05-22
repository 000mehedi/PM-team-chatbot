from datetime import datetime
import pandas as pd
from io import BytesIO
from supabase import Client
from .supabase_client import supabase

# ======================= User =======================

def add_user(username: str, password: str, name: str):
    supabase.table("users").insert({
        "username": username,
        "password": password,
        "name": name
    }).execute()


def get_user_by_username(username: str):
    res = supabase.table("users").select("*").eq("username", username).execute()
    data = res.data
    if data and len(data) == 1:
        return data[0]
    else:
        return None



def rename_session(session_id: int, new_name: str):
    supabase.table("chats").update({"session_name": new_name}).eq("id", session_id).execute()


# ======================= Uploaded File =======================

import base64

def save_uploaded_file(session_id, filename, bytes_data):
    # Encode bytes to base64 string
    encoded_content = base64.b64encode(bytes_data).decode('utf-8')

    # Upsert (insert or update) the file into Supabase
    res = supabase.table("uploaded_files").upsert({
        "session_id": session_id,
        "filename": filename,
        "content": encoded_content  # store base64 string, not raw bytes
    }).execute()

    return res

def load_uploaded_file(session_id):
    if not session_id:
        return None  # No session selected, so no file to load

    res = supabase.table("uploaded_files") \
        .select("filename, content") \
        .eq("session_id", session_id) \
        .execute()

    if not res.data or len(res.data) == 0:
        # No file uploaded for this session yet
        return None

    # There should be only one row due to PRIMARY KEY constraint
    row = res.data[0]
    filename, encoded_content = row["filename"], row["content"]

    # Decode base64 string to bytes
    file_bytes = base64.b64decode(encoded_content)

    if filename.endswith('.xlsx') or filename.endswith('.xls'):
        return pd.read_excel(BytesIO(file_bytes))
    elif filename.endswith('.csv'):
        return pd.read_csv(BytesIO(file_bytes))
    else:
        return None



# ======================= Chat Sessions =======================

def create_new_session(username: str, session_name: str):
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_name = f"{session_name} ({created_at})"
    res = supabase.table("chats").insert({
        "username": username,
        "session_name": full_name,
        "created_at": created_at
    }).execute()
    return res.data[0]["id"]


def get_all_sessions(username: str):
    res = supabase.table("chats") \
    .select("*") \
    .eq("username", username) \
    .order("created_at", desc=True) \
    .execute()

    chats = res.data
    return [
        {
            "id": chat["id"],
            "display_name": f"{chat['session_name']} ({chat['created_at']})",
            "session_name": chat["session_name"],
            "created_at": chat["created_at"]
        }
        for chat in chats
    ]

def load_faqs():
    res = supabase.table("faqs").select("*").execute()
    data = res.data
    return pd.DataFrame(data) if data else pd.DataFrame(columns=["question", "answer"])

def add_faq(category, question, answer):
    # Example with Supabase insert
    supabase.table("faqs").insert({
        "category": category,
        "question": question,
        "answer": answer
    }).execute()



def get_last_messages(session_id, n=10):
    res = supabase.table("messages").select("role, content") \
        .eq("session_id", session_id) \
        .order("timestamp", desc=True) \
        .limit(n).execute()
    rows = res.data
    rows.reverse()
    return [{"role": row["role"], "content": row["content"]} for row in rows]


def update_session_name(session_id, new_name):
    supabase.table("chats").update({"session_name": new_name}).eq("id", session_id).execute()


def rename_session_with_timestamp(session_id, base_name):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_name = f"{base_name} ({timestamp})"
    update_session_name(session_id, new_name)


# ======================= Messages =======================

def save_message(session_id: int, role: str, content: str, message_type: str = "text"):
    supabase.table("messages").insert({
        "session_id": session_id,
        "role": role,
        "content": content,
        "message_type": message_type,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }).execute()


def load_messages_by_session(session_id):
    if not session_id:
        return []

    res = supabase.table("messages") \
        .select("*") \
        .eq("session_id", session_id) \
        .order("timestamp", desc=False) \
        .execute()

    return res.data if res.data else []

def delete_faq(faq_id: str):
    supabase.table("faqs").delete().eq("id", faq_id).execute()




def add_message_to_session(username: str, session_id: int, content: str, role: str = "user"):
    if not user_owns_session(username, session_id):
        raise PermissionError("You don't own this session")
    save_message(session_id, role, content)


def get_messages_for_session(username: str, session_id: int):
    if not user_owns_session(username, session_id):
        raise PermissionError("You don't own this session")
    return load_messages_by_session(session_id)


def delete_session(session_id: int, username: str):
    if not user_owns_session(username, session_id):
        raise PermissionError("You don't own this session")

    supabase.table("messages").delete().eq("session_id", session_id).execute()
    supabase.table("uploaded_files").delete().eq("session_id", session_id).execute()
    supabase.table("chats").delete().eq("id", session_id).execute()


# ======================= Security Check =======================

def user_owns_session(username: str, session_id: int):
    res = supabase.table("chats").select("*") \
        .eq("id", session_id).eq("username", username).single().execute()
    return res.data is not None
