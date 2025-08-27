import streamlit as st
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.utils.db import get_all_sessions, delete_session, create_new_session, load_messages_by_session, rename_session

# Import the guidance section
from frontend.guidance_section import show_guidance_section, show_best_practices_section

def full_sidebar():
    st.markdown("# Preventive Maintenance")
    
    # Check if user is admin
    user_email = st.session_state.get("email", "").lower()
    is_admin = (user_email == "admin@calgary.ca")
    
    # --- Move Chat with AI to the top ---
    if st.button("💬 Chat with AI", key="chat_btn_top", use_container_width=True):
        st.session_state["current_page"] = "chat"
        st.rerun()
    
    # Documentation - expandable section with direct buttons
    with st.expander("📚 Documentation", expanded=False):
        if st.button("Process Maps", key="proc_maps_btn", use_container_width=True):
            st.session_state["current_page"] = "process_maps"
            st.rerun()
            
        if st.button("FAQs", key="faqs_btn", use_container_width=True):
            st.session_state["current_page"] = "faqs"
            st.rerun()
    
    # Operational Data - expandable section with direct buttons and sub-options where needed
    with st.expander("📊 Operational Data", expanded=False):
        # Dictionary data needs sub-options
        st.markdown("#### Dictionary Data")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("View Dictionary", key="view_dict_btn", use_container_width=True):
                st.session_state["current_page"] = "dictionary"
                st.rerun()
        with col2:
            # Only show Upload Dictionary button if user is admin@calgary.ca
            if is_admin:
                if st.button("Upload Dictionary", key="upload_dict_btn", use_container_width=True):
                    st.session_state["current_page"] = "dictionary_upload"
                    st.rerun()
        
        # Work Order data needs sub-options
        st.markdown("#### Work Order Data")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("View Work Orders", key="dash_btn", use_container_width=True):
                st.session_state["current_page"] = "dashboard"
                st.rerun()
        with col2:
            # Only show Upload Work Orders button if user is admin@calgary.ca
            if is_admin:
                if st.button("Upload Work Orders", key="upload_wo_btn", use_container_width=True):
                    st.session_state["current_page"] = "work_order_upload"
                    st.rerun()
        
        # PM Data section
        st.markdown("#### PM Data")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("View PM Data", key="view_pm_btn", use_container_width=True):
                st.session_state["current_page"] = "pm_data"
                st.rerun()
        with col2:
            # Only show Upload PM Data button if user is admin@calgary.ca
            if is_admin:
                if st.button("Upload PM Data", key="upload_pm_btn", use_container_width=True):
                    st.session_state["current_page"] = "pm_data_upload"
                    st.rerun()
    
    # Guidance - expandable section with direct buttons
    with st.expander("📘 Guidance", expanded=False):
        if st.button("Regulations & Bylaws", key="reg_btn", use_container_width=True):
            st.session_state["current_page"] = "regulations"
            st.rerun()
            
        if st.button("Best Practices", key="practices_btn", use_container_width=True):
            st.session_state["current_page"] = "best_practices"
            st.rerun()
    
    # ADHOC - expandable section with direct buttons (Chat with AI removed)
    with st.expander("⚙️ ADHOC", expanded=False):
        if st.button("User Feedback", key="feedback_btn", use_container_width=True):
            st.session_state["current_page"] = "user_feedback"
            st.rerun()
            

    
    # Add a direct link to the main page if needed
    if st.session_state["current_page"] != "main":
        if st.button("Main Dashboard", use_container_width=True):
            st.session_state["current_page"] = "main"
            st.rerun()



def chat_sessions_sidebar():
    if not st.session_state.get("user_id"):
        st.warning("🔐 Please log in to see your chat sessions.")
        return

    # Add a button to return to navigation sidebar
    
    st.markdown("---")  # Add a separator
    
    st.subheader("🕘 Chat Sessions")

    user_id = st.session_state["user_id"]
    sessions = get_all_sessions(user_id)

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
                delete_session(session_id, user_id)
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
        new_id = create_new_session(user_id, new_session_name)
        st.session_state.selected_session = new_id
        st.session_state.messages = []
        st.rerun()

# --- Show Guidance Section in Main Area if selected ---
if st.session_state.get("current_page") == "regulations":
    show_guidance_section()
    
if st.session_state.get("current_page") == "best_practices":
    show_best_practices_section()