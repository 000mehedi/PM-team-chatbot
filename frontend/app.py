import streamlit as st
import pandas as pd
from io import BytesIO, StringIO
import sys, os

# Import custom modules and styles
from styles import inject_styles
from auth import auth_sidebar
from sidebar import chat_sessions_sidebar
from chat import chat_interface, load_dictionary_corpus  # Import load_dictionary_corpus
from sidebar_sections import show_faqs, show_definitions, show_forms_and_docs, show_user_feedback, show_session_analytics,show_dictionary_lookup
from manual_lookup import show_manual_lookup
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# --------------------
# Remove local dictionary loading.
# Old code that loads the XLSX file would go here – remove it.
# --------------------
# For example, delete or comment out the following block:
# dictionary_path = "Dictionary Format 2024_Jun 20.xlsx"
# try:
#     st.session_state.dictionary_sheets = pd.read_excel(dictionary_path, sheet_name=None)
#     st.success("✅ Dictionary (all sheets) loaded from project root.")
# except Exception as e:
#     st.error(f"❌ Failed to load dictionary: {e}")
#
# [Also remove the old composite dictionary_context block and build_dictionary_corpus() function.]

# Instead, load the dictionary corpus from Supabase:
dictionary_corpus = load_dictionary_corpus()

# --------------------
# Backend and Static Data Setup
# --------------------
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.utils.db import save_uploaded_file, load_uploaded_file, load_faqs
definitions = pd.read_csv("backend/data/definitions.csv")
links = pd.read_csv("backend/data/links.csv")
faqs_df = load_faqs()
faqs_context = ""
if faqs_df is not None and not faqs_df.empty:
    faqs_context = "\n".join(
        f"Q: {row['question']}\nA: {row['answer']}"
        for _, row in faqs_df.iterrows()
    )

inject_styles()
with st.sidebar:
    auth_sidebar()

# --------------------
# Main App Body
# --------------------
if st.session_state.get("token") and st.session_state.get("user_id"):
    user_id = st.session_state["user_id"]
    user_name = st.session_state.get("name", "User")
    st.title("🤖 PM Support Chatbot")
    st.markdown("Ask questions or explore project management resources.")

    sidebar_options = ["Ask AI", "FAQs", "Definitions", "Forms & Docs", "Manual Lookup(broken)", "User Feedback", "Dictionary Lookup"]
    if st.session_state.get("email") == "admin@calgary.ca":
        sidebar_options.append("Session Analytics")
    option = st.sidebar.radio("📌 **Navigate to:**", sidebar_options,
                              format_func=lambda x: f"💬 {x}" if x=="Ask AI" else x)

    if option == "Ask AI":
        with st.sidebar:
            st.markdown("---")
            chat_sessions_sidebar()
        selected_session = st.session_state.get("selected_session")
        if selected_session is None:
            st.warning("Please create or select a chat session to start chatting.")
        else:
            df = None
            uploaded_file = st.file_uploader("📂 Upload a data file", type=["xlsx", "xls", "csv"])
            if uploaded_file is not None:
                try:
                    with st.spinner("Reading uploaded file..."):
                        bytes_data = uploaded_file.read()
                        save_uploaded_file(selected_session, uploaded_file.name, bytes_data, user_id=user_id)
                        if uploaded_file.name.endswith(".csv"):
                            df = pd.read_csv(BytesIO(bytes_data))
                        else:
                            df = pd.read_excel(BytesIO(bytes_data))
                        st.session_state.uploaded_df = df
                        st.success("✅ File uploaded and saved for this session.")
                        st.dataframe(df.head())
                except Exception as e:
                    st.error(f"❌ Error reading file: {e}")
            else:
                if "uploaded_df" not in st.session_state or st.session_state.uploaded_df is None:
                    with st.spinner("Loading previous session data..."):
                        df_from_db = load_uploaded_file(selected_session, user_id=user_id)
                        if df_from_db is not None:
                            st.session_state.uploaded_df = df_from_db
                            st.info("📁 Loaded previously uploaded file for this session.")
                            st.dataframe(df_from_db.head())
                        else:
                            st.session_state.uploaded_df = None
                            st.info("ℹ️ No uploaded file found. Please upload a file to start.")
            chat_interface(
                st.session_state.get("uploaded_df"),
                faqs_context=faqs_context,
                faqs_df=faqs_df,
                dictionary_corpus=dictionary_corpus
            )
    elif option == "FAQs":
        show_faqs()
    elif option == "Definitions":
        show_definitions(definitions)
    elif option == "Forms & Docs":
        show_forms_and_docs(links)
    elif option == "Manual Lookup":
        show_manual_lookup()
    elif option == "User Feedback":
        show_user_feedback()
    elif option == "Session Analytics":
        show_session_analytics()
    elif option == "Dictionary Lookup":
        show_dictionary_lookup()
else:
    st.info("🔐 Please login or sign up using the sidebar to start chatting.")