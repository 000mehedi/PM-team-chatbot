import streamlit as st
import pandas as pd
from io import BytesIO, StringIO
import sys, os

# Import custom modules and styles
from styles import inject_styles
from auth import auth_sidebar
from sidebar import chat_sessions_sidebar
from chat import chat_interface, load_dictionary_corpus  # Import load_dictionary_corpus
from sidebar_sections import show_faqs, show_definitions, show_forms_and_docs, show_user_feedback, show_session_analytics, show_dictionary_lookup, show_dashboard
from manual_lookup import show_manual_lookup
from frontend.dashboard_viewer import display_dashboard_page  # Import the dashboard viewer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from admin_upload import show_admin_upload
import numpy as np

# Initialize session state for page navigation
if "current_page" not in st.session_state:
    st.session_state["current_page"] = "main"

if "generate_new_dashboard" not in st.session_state:
    st.session_state["generate_new_dashboard"] = False

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

# Load the dictionary corpus from Supabase
dictionary_corpus = load_dictionary_corpus()

# Apply styles
inject_styles()

# Render the authentication sidebar
with st.sidebar:
    auth_sidebar()

# --------------------
# Main App Body
# --------------------
if st.session_state.get("token") and st.session_state.get("user_id"):
    user_id = st.session_state["user_id"]
    user_name = st.session_state.get("name", "User")
    
    # Check if we should display dashboard page or main interface
    if st.session_state.get("current_page") == "dashboard":
        # Display the dashboard page
        generate_new = st.session_state.get("generate_new_dashboard", False)
        display_dashboard_page(generate_new=generate_new)
        # Reset the flag after use
        st.session_state["generate_new_dashboard"] = False
    else:
        # Display the main chat interface and sidebar options
        st.title("🤖 PM Support Chatbot")
        st.markdown("Ask questions or explore project management resources.")

        sidebar_options = ["Ask AI", "FAQs", "Definitions", "Forms & Docs", "Manual Lookup(broken)", 
                          "User Feedback", "Dictionary Lookup", "Upload Dictionary", "Show Dashboard"]
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
        elif option == "Upload Dictionary":
            show_admin_upload()
        elif option == "Show Dashboard":
            show_dashboard()
        
else:
    st.info("🔐 Please login or sign up using the sidebar to start chatting.")