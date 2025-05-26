import streamlit as st
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.utils.db import get_all_sessions, delete_session, create_new_session, load_messages_by_session, rename_session
from sidebar_sections import show_faqs, show_definitions, show_forms_and_docs

def full_sidebar():
    st.markdown("# Welcome to PM Bot")

    faqs_section()
    definitions_section()
    forms_and_docs_section()
    ask_a_question_section()



def chat_sessions_sidebar():
    if not st.session_state.get("username"):

        st.warning("🔐 Please log in to see your chat sessions.")
        return

    st.subheader("🕘 Chat Sessions")

    username = st.session_state["username"]
    sessions = get_all_sessions(username)

    for i, session in enumerate(sessions):
        session_id = session["id"]
        session_name = session.get("session_name", "Unnamed Session")
        created_at = session.get("created_at", "")[:10]

        col1, col2, col3 = st.columns([2, 1, 1])

        # Select session
        with col1:
            if st.button(f"{session_name} ({created_at})", key=f"select_{session_id}_{i}"):
                st.session_state.selected_session = session_id
                st.session_state.messages = [
                    {"role": m["role"], "content": m["content"]}
                    for m in load_messages_by_session(session_id)
                ]
                st.rerun()

        # Rename session
        with col2:
            if st.button("✏️", key=f"rename_btn_{session_id}_{i}"):
                st.session_state[f"renaming_{session_id}"] = True

        # Delete session
        with col3:
            if st.button("🗑️", key=f"delete_{session_id}_{i}"):
                delete_session(session_id, username)
                if st.session_state.get("selected_session") == session_id:
                    st.session_state.selected_session = None
                    st.session_state.messages = []
                st.rerun()

        # Rename input box
        if st.session_state.get(f"renaming_{session_id}", False):
            new_name = st.text_input("New session name:", value=session_name, key=f"rename_input_{session_id}")
            if st.button("💾 Save", key=f"save_rename_{session_id}"):
                rename_session(session_id, new_name)
                st.session_state[f"renaming_{session_id}"] = False
                st.rerun()

    # New chat session
    if st.button("➕ New Chat"):
        new_session_name = f"Session {len(sessions) + 1}"
        new_id = create_new_session(username, new_session_name)
        st.session_state.selected_session = new_id
        st.session_state.messages = []
        st.rerun()
