from db import save_message, get_last_messages, update_session_name
from openai_utils import generate_session_title  # Your OpenAI title generation function
from backend.utils.db import get_db

def handle_new_message(session_id, role, content, openai_api_key):
    conn = get_db()
    
    # Save the message first
    save_message(session_id, role, content)
    
    # Fetch recent messages
    recent_msgs = get_last_messages(conn, session_id, n=10)
    
    # Generate a new session title based on recent conversation
    new_title = generate_session_title(recent_msgs, openai_api_key)
    
    # Update the session name in DB
    update_session_name(conn, session_id, new_title)
    
    conn.close()
