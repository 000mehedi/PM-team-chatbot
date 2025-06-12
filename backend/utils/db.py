from datetime import datetime
import pandas as pd
from io import BytesIO
import base64
from typing import Optional, List, Dict
from backend.utils.supabase_client import supabase
# ======================= User =======================

def add_user(username: str, password: str, name: str) -> None:
    # WARNING: Storing passwords in plaintext is insecure.
    # Use Supabase Auth for user management instead.
    supabase.table("users").insert({
        "username": username,
        "password": password,
        "name": name
    }).execute()

def get_pm_tasks(pm_code: str):
    # Query the dictionary table for matching PM code (or pm_name if you want to support that too)
    # Using ilike allows case-insensitive match and partial matching.
    query = supabase.table("dictionary") \
        .select("pm_code, pm_name, sequence, description") \
        .ilike("pm_code", f"%{pm_code}%") \
        .execute()
    if query.error:
        print("Error:", query.error)
        return None
    return query.data

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


def save_user_feedback(user_id, user_name, title, feedback, file_bytes=None, file_name=None):
    encoded_file = base64.b64encode(file_bytes).decode("utf-8") if file_bytes else None
    data = {
        "user_id": user_id,
        "user_name": user_name,  # <-- add this line
        "title": title,
        "feedback": feedback,
        "file_name": file_name,
        "file_bytes": encoded_file,
    }
    supabase.table("user_feedback").insert(data).execute()

def load_all_feedback():
    res = supabase.table("user_feedback").select("*").order("created_at", desc=True).execute()
    return res.data if hasattr(res, "data") else []

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

def get_all_sessions_analytics():
    sessions = supabase.table("chats").select("*").execute()
    analytics = []
    if hasattr(sessions, "data"):
        for session in sessions.data:
            session_id = session["id"]
            session_name = session.get("session_name", f"Session {session_id}")
            user_id = session.get("user_id", "Unknown")
            # Get user name
            user_profile = supabase.table("user_profiles").select("name").eq("user_id", user_id).execute()
            user_name = user_profile.data[0]["name"] if user_profile.data else "Unknown"
            # Get messages for this session
            msgs = supabase.table("messages").select("*").eq("session_id", session_id).order("timestamp", desc=False).execute()
            messages = msgs.data if hasattr(msgs, "data") else []
            num_messages = len(messages)
            user_messages = sum(1 for m in messages if m.get("role") == "user")
            bot_messages = sum(1 for m in messages if m.get("role") == "assistant")
            # Session duration
            if messages:
                start_time = messages[0].get("timestamp")
                end_time = messages[-1].get("timestamp")
                from datetime import datetime
                fmt = "%Y-%m-%d %H:%M:%S"
                try:
                    duration = (datetime.strptime(end_time, fmt) - datetime.strptime(start_time, fmt)).total_seconds() / 60
                    duration = round(duration, 2)
                except Exception:
                    duration = "N/A"
            else:
                duration = "N/A"
            # Average response time (user to bot)
            response_times = []
            last_user_time = None
            for m in messages:
                if m.get("role") == "user":
                    last_user_time = m.get("timestamp")
                elif m.get("role") == "assistant" and last_user_time:
                    try:
                        t1 = datetime.strptime(last_user_time, fmt)
                        t2 = datetime.strptime(m.get("timestamp"), fmt)
                        response_times.append((t2 - t1).total_seconds())
                    except Exception:
                        pass
                    last_user_time = None
            avg_response_time = round(sum(response_times)/len(response_times), 2) if response_times else "N/A"
            # Last activity
            last_activity = messages[-1].get("timestamp") if messages else session.get("created_at", "")
            # Top words
            from collections import Counter
            import re
            stopwords = {"the", "and", "to", "of", "a", "in", "for", "is", "on", "with", "as", "by", "at", "an", "be"}
            words = []
            for m in messages:
                words += [w.lower() for w in re.findall(r"\b\w+\b", m["content"]) if w.lower() not in stopwords]
            from itertools import islice
            top_words = [w for w, _ in islice(Counter(words).most_common(3), 3)]
            analytics.append({
                "session_id": session_id,
                "session_name": session_name,
                "user_id": user_id,
                "user_name": user_name,
                "num_messages": num_messages,
                "user_messages": user_messages,
                "bot_messages": bot_messages,
                "duration_min": duration,
                "avg_response_time_sec": avg_response_time,
                "last_activity": last_activity[:19] if last_activity else "N/A",
                "top_words": ", ".join(top_words) if top_words else "N/A"
            })
    return analytics

def get_prompt_completion_pairs():
    """
    Returns a list of {'prompt': user_message, 'completion': bot_reply}
    for all user/assistant message pairs in all sessions.
    """
    sessions = supabase.table("chats").select("id").execute()
    pairs = []
    if hasattr(sessions, "data"):
        for session in sessions.data:
            session_id = session["id"]
            msgs = supabase.table("messages").select("role, content, timestamp").eq("session_id", session_id).order("timestamp", desc=False).execute()
            messages = msgs.data if hasattr(msgs, "data") else []
            last_user_msg = None
            for m in messages:
                if m.get("role") == "user":
                    last_user_msg = m.get("content")
                elif m.get("role") == "assistant" and last_user_msg:
                    pairs.append({
                        "prompt": last_user_msg.strip(),
                        "completion": m.get("content", "").strip()
                    })
                    last_user_msg = None
    return pairs

def get_fine_tune_training_data(min_length=10):
    """
    Returns cleaned prompt-completion pairs from all sessions for fine-tuning.
    """
    pairs = get_prompt_completion_pairs()
    seen = set()
    clean_pairs = []
    for pair in pairs:
        prompt = pair["prompt"].strip()
        completion = pair["completion"].strip()
        if len(prompt) < min_length or len(completion) < min_length:
            continue
        if (prompt, completion) in seen:
            continue
        seen.add((prompt, completion))
        clean_pairs.append(pair)
    return clean_pairs

def build_dynamic_context(top_n=10):
    faqs = supabase.table("faqs").select("question, answer").execute()
    if not hasattr(faqs, "data"):
        return ""
    top_faqs = faqs.data[:top_n]
    context = "\n".join([f"Q: {f['question']}\nA: {f['answer']}" for f in top_faqs])
    return context