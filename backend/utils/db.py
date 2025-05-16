import sqlite3
from datetime import datetime
import pandas as pd
from io import BytesIO

DB_PATH = "backend/data/app.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Enables dict-like access
    return conn


def create_tables():
    conn = get_db()
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            name TEXT NOT NULL
        );
    """)

    # Chats table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            session_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (username) REFERENCES users(username)
        );
    """)

    # Messages table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            message_type TEXT DEFAULT 'text',
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES chats(id)
        );
    """)

    # ✅ Add this new table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS uploaded_files (
            session_id INTEGER PRIMARY KEY,
            filename TEXT NOT NULL,
            content BLOB NOT NULL,
            FOREIGN KEY (session_id) REFERENCES chats(id)
        );
    """)

    conn.commit()
    conn.close()


# ======================= User =======================

def add_user(username: str, password: str, name: str):
    conn = get_db()
    conn.execute("INSERT INTO users (username, password, name) VALUES (?, ?, ?)", (username, password, name))
    conn.commit()
    conn.close()


def get_user_by_username(username: str):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return dict(user) if user else None


def rename_session(session_id: int, new_name: str):
    conn = get_db()
    conn.execute("UPDATE chats SET session_name = ? WHERE id = ?", (new_name, session_id))
    conn.commit()
    conn.close()


# ======================= Uploaded File =======================

def save_uploaded_file(session_id, filename, file_bytes):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO uploaded_files (session_id, filename, content)
        VALUES (?, ?, ?)
    """, (session_id, filename, file_bytes))
    conn.commit()
    conn.close()


def load_uploaded_file(session_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT filename, content FROM uploaded_files WHERE session_id = ?
    """, (session_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        filename, content = row
        if filename.endswith('.xlsx') or filename.endswith('.xls'):
            return pd.read_excel(BytesIO(content))
    return None


# ======================= Chat Sessions =======================

def create_new_session(username: str, session_name: str):
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_name = f"{session_name} ({created_at})"

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO chats (username, session_name, created_at) VALUES (?, ?, ?)", (username, full_name, created_at))
    conn.commit()
    session_id = cursor.lastrowid
    conn.close()
    return session_id


def get_last_messages(conn, session_id, n=10):
    query = """
    SELECT role, content FROM messages
    WHERE session_id = ?
    ORDER BY timestamp DESC
    LIMIT ?
    """
    cursor = conn.execute(query, (session_id, n))
    rows = cursor.fetchall()
    rows.reverse()
    return [{"role": row[0], "content": row[1]} for row in rows]


def update_session_name(conn, session_id, new_name):
    query = "UPDATE chats SET session_name = ? WHERE id = ?"
    conn.execute(query, (new_name, session_id))
    conn.commit()


def rename_session_with_timestamp(conn, session_id, base_name):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_name = f"{base_name} ({timestamp})"
    update_session_name(conn, session_id, new_name)


def get_all_sessions(username: str):
    conn = get_db()
    chats = conn.execute(
        "SELECT id, session_name, created_at FROM chats WHERE username = ? ORDER BY created_at DESC", 
        (username,)
    ).fetchall()
    conn.close()

    return [
        {
            "id": chat["id"],
            "display_name": f"{chat['session_name']} ({chat['created_at']})",
            "session_name": chat["session_name"],
            "created_at": chat["created_at"]
        }
        for chat in chats
    ]


# ======================= Messages =======================

def save_message(session_id: int, role: str, content: str, message_type: str = "text"):
    conn = get_db()
    conn.execute(
        "INSERT INTO messages (session_id, role, content, message_type) VALUES (?, ?, ?, ?)",
        (session_id, role, content, message_type)
    )
    conn.commit()
    conn.close()


def load_messages_by_session(session_id: int):
    conn = get_db()
    messages = conn.execute("""
        SELECT role, content, message_type, timestamp
        FROM messages
        WHERE session_id = ?
        ORDER BY timestamp ASC
    """, (session_id,)).fetchall()
    conn.close()
    return [dict(msg) for msg in messages]


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
    conn = get_db()
    conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
    conn.execute("DELETE FROM uploaded_files WHERE session_id = ?", (session_id,))
    conn.execute("DELETE FROM chats WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()


# ======================= Security Check =======================

def user_owns_session(username: str, session_id: int):
    conn = get_db()
    chat = conn.execute("SELECT * FROM chats WHERE id = ? AND username = ?", (session_id, username)).fetchone()
    conn.close()
    return chat is not None
