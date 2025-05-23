import streamlit as st
import pandas as pd
from io import BytesIO, StringIO
import sys
import os

from styles import inject_styles
from auth import auth_sidebar
from sidebar import chat_sessions_sidebar
from chat import chat_interface
from sidebar_sections import show_faqs, show_definitions, show_forms_and_docs
from manual_lookup import show_manual_lookup

# Fix pandas.compat.StringIO for old code compatibility
pd.compat.StringIO = StringIO

# Add backend to system path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.utils.db import save_uploaded_file, load_uploaded_file

# Load static data once
#faqs = pd.read_csv("backend/data/faqs.csv", encoding="utf-8-sig")
definitions = pd.read_csv("backend/data/definitions.csv")
links = pd.read_csv("backend/data/links.csv")

# Streamlit config
st.set_page_config(page_title="PM Support Chatbot", page_icon="🤖", layout="wide")

# Inject custom CSS styles
inject_styles()

# Sidebar: User Authentication
with st.sidebar:
    auth_sidebar()

# Main App Body
if st.session_state.get("token"):
    st.title("🤖 PM Support Chatbot")
    st.markdown("Ask questions or explore project management resources.")

    # Sidebar navigation radio buttons
    option = st.sidebar.radio(
        "📌 **Navigate to:**",
        ["Ask AI", "FAQs", "Definitions", "Forms & Docs", "Manual Lookup"],
        format_func=lambda x: f"💬 {x}" if x == "Ask AI" else x
    )

    if option == "Ask AI":
        # Show chat sessions sidebar inside the sidebar container
        with st.sidebar:
            st.markdown("---")
            chat_sessions_sidebar()

        selected_session = st.session_state.get("selected_session")
        if selected_session is None:
            st.warning("Please create or select a chat session to start chatting.")
        else:
            df = None

            # File uploader for this session
            uploaded_file = st.file_uploader("📂 Upload a data file", type=["xlsx", "xls", "csv"])

            if uploaded_file is not None:
                try:
                    with st.spinner("Reading uploaded file..."):
                        bytes_data = uploaded_file.read()

                        # Save file bytes to Supabase (or DB)
                        save_uploaded_file(selected_session, uploaded_file.name, bytes_data)

                        # Read uploaded file into DataFrame
                        if uploaded_file.name.endswith(".csv"):
                            df = pd.read_csv(BytesIO(bytes_data))
                        else:
                            df = pd.read_excel(BytesIO(bytes_data))

                        # Save DataFrame in session state
                        st.session_state.uploaded_df = df

                        st.success("✅ File uploaded and saved for this session.")
                        st.dataframe(df.head())
                except Exception as e:
                    st.error(f"❌ Error reading file: {e}")
            else:
                # No new file uploaded; try loading previously saved file for session
                if "uploaded_df" not in st.session_state or st.session_state.uploaded_df is None:
                    with st.spinner("Loading previous session data..."):
                        df_from_db = load_uploaded_file(selected_session)
                        if df_from_db is not None:
                            st.session_state.uploaded_df = df_from_db
                            st.info("📁 Loaded previously uploaded file for this session.")
                            st.dataframe(df_from_db.head())
                        else:
                            st.session_state.uploaded_df = None
                            st.info("ℹ️ No uploaded file found. Please upload a file to start.")

            # Pass the DataFrame (or None) to the chat interface
            chat_interface(st.session_state.get("uploaded_df"))

    elif option == "FAQs":
        show_faqs()

    elif option == "Definitions":
        show_definitions(definitions)

    elif option == "Forms & Docs":
        show_forms_and_docs(links)

    elif option == "Manual Lookup":
        show_manual_lookup()


else:
    st.info("🔐 Please login or sign up using the sidebar to start chatting.")
