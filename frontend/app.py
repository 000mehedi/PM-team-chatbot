import streamlit as st
import pandas as pd
from io import BytesIO
import sys
import os

from styles import inject_styles
from auth import auth_sidebar
from sidebar import chat_sessions_sidebar
from chat import chat_interface
from sidebar_sections import show_faqs, show_definitions, show_forms_and_docs

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.utils.db import save_uploaded_file, load_uploaded_file

# Load data files
faqs = pd.read_csv("backend/data/faqs.csv")
definitions = pd.read_csv("backend/data/definitions.csv")
links = pd.read_csv("backend/data/links.csv")

# Page config
st.set_page_config(page_title="PM Support Chatbot", page_icon="🤖", layout="wide")

# Inject CSS
inject_styles()

# Sidebar: Auth
with st.sidebar:
    auth_sidebar()

# Main App
if st.session_state.get("token"):
    st.title("🤖 PM Support Chatbot")
    st.markdown("Ask questions or explore project management resources.")

    # Navigation options
    option = st.sidebar.radio("Navigate", ["Ask AI", "FAQs", "Definitions", "Forms & Docs"])

    if option == "Ask AI":
        with st.sidebar:
            st.markdown("---")
            chat_sessions_sidebar()

        selected_session = st.session_state.get("selected_session")
        if selected_session is None:
            st.warning("Please create or select a chat session to start chatting.")
        else:
            uploaded_file = st.file_uploader("Upload an Excel file", type=["xlsx", "xls"])
            if uploaded_file is not None:
                try:
                    bytes_data = uploaded_file.read()
                    save_uploaded_file(selected_session, uploaded_file.name, bytes_data)
                    st.session_state.uploaded_df = pd.read_excel(BytesIO(bytes_data))
                    st.success("File uploaded and saved for session.")
                    st.dataframe(st.session_state.uploaded_df.head())
                except Exception as e:
                    st.error(f"Error reading file: {e}")
            else:
                # Load previously uploaded file only if not already loaded in session_state
                if "uploaded_df" not in st.session_state or st.session_state.uploaded_df is None:
                    df_from_db = load_uploaded_file(selected_session)
                    if df_from_db is not None:
                        st.session_state.uploaded_df = df_from_db
                        st.info("Loaded previously uploaded file for this session.")
                        st.dataframe(st.session_state.uploaded_df.head())
                    else:
                        st.session_state.uploaded_df = None

            chat_interface(st.session_state.uploaded_df)

    elif option == "FAQs":
        show_faqs(faqs)

    elif option == "Definitions":
        show_definitions(definitions)

    elif option == "Forms & Docs":
        show_forms_and_docs(links)

else:
    st.info("Please login or sign up using the sidebar to start chatting.")
