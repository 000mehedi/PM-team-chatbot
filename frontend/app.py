import streamlit as st
import sys
import os
from dotenv import load_dotenv
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import sqlite3

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))
from utils.content_loader import load_faqs, load_definitions, load_links, search_content
from utils.logger import log_unanswered  # Optional logging
from utils.ai_chat import ask_gpt
from utils.knowledge_base import save_learned_qa

load_dotenv()

faqs = load_faqs()
definitions = load_definitions()
links = load_links()

st.set_page_config(page_title="PM Support Chatbot", page_icon="🤖")
st.title("PM Support Chatbot")
st.markdown("Ask questions or explore project management resources.")

option = st.sidebar.radio("Choose a topic", ["FAQs", "Definitions", "Forms & Docs", "Ask a Question"])

# Function to connect to SQLite database and create a table for chat history
def create_chat_history_db():
    conn = sqlite3.connect("chat_history.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT,
            content TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

# Function to save chat history to SQLite
def save_chat_history(messages):
    conn = sqlite3.connect("chat_history.db")
    c = conn.cursor()
    
    for msg in messages:
        c.execute("INSERT INTO chat_history (role, content) VALUES (?, ?)", (msg["role"], msg["content"]))
    
    conn.commit()
    conn.close()

# Function to load chat history from SQLite
def load_chat_history():
    conn = sqlite3.connect("chat_history.db")
    c = conn.cursor()
    c.execute("SELECT role, content, timestamp FROM chat_history ORDER BY timestamp DESC")
    rows = c.fetchall()
    conn.close()
    return rows

# Initialize the database (create table if not exists)
create_chat_history_db()

if option == "FAQs":
    st.subheader("Frequently Asked Questions")
    for _, row in faqs.iterrows():
        with st.expander(row['Question']):
            st.write(row['Answer'])

elif option == "Definitions":
    st.subheader("EAM Terminology")
    search_term = st.text_input("Search terms or definitions:")
    filtered_definitions = definitions[
        definitions['Term'].str.contains(search_term, case=False, na=False) |
        definitions['Definition'].str.contains(search_term, case=False, na=False)
    ] if search_term else definitions

    tabs = st.tabs(["A–F", "G–L", "M–R", "S–Z"])
    groups = {
        "A–F": filtered_definitions[filtered_definitions['Term'].str[0].str.upper().between("A", "F")],
        "G–L": filtered_definitions[filtered_definitions['Term'].str[0].str.upper().between("G", "L")],
        "M–R": filtered_definitions[filtered_definitions['Term'].str[0].str.upper().between("M", "R")],
        "S–Z": filtered_definitions[filtered_definitions['Term'].str[0].str.upper().between("S", "Z")],
    }
    for tab, label in zip(tabs, groups.keys()):
        with tab:
            if groups[label].empty:
                st.info("No definitions in this range.")
            else:
                for _, row in groups[label].iterrows():
                    st.write(f"**{row['Term']}**: {row['Definition']}")

elif option == "Forms & Docs":
    st.subheader("Reference Links")
    for _, row in links.iterrows():
        st.markdown(f"- [{row['Resource']}]({row['Link']})")

elif option == "Ask a Question":
    st.subheader("🧠 PM Assistant Chat")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "uploaded_df" not in st.session_state:
        st.session_state.uploaded_df = None

    uploaded_file = st.file_uploader("Upload an Excel file", type=["xlsx", "xls"])
    if uploaded_file:
        try:
            df = pd.read_excel(uploaded_file)
            
            st.session_state.uploaded_df = df
            st.success("File uploaded and stored for context.")
            st.write("Preview:")
            st.dataframe(df.head())
        except Exception as e:
            st.error(f"Upload error: {e}")

    # Display chat messages
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.markdown(f"""
                <div style="background-color:#462969;padding:10px;border-radius:10px;margin-bottom:10px">
                    <strong>🧑‍💼 You:</strong><br>{msg['content']}
                </div>
            """, unsafe_allow_html=True)
        else:
            import re
            code_blocks = re.findall(r"```(?:python)?\s*([\s\S]*?)```", msg["content"])

            if code_blocks:
                try:
                    exec_globals = {
                        "pd": pd,
                        "plt": plt,
                        "sns": sns,
                        "st": st,
                        "__builtins__": __builtins__,
                    }
                    if st.session_state.uploaded_df is not None:
                        exec_globals["df"] = st.session_state.uploaded_df

                    exec(code_blocks[0], exec_globals)

                    if plt.get_fignums():
                        st.pyplot(plt.gcf())
                        plt.clf()

                    elif "num_rows" in exec_globals:
                        st.markdown(f"""
                            <div style="background-color:#4A4F9E;padding:10px;border-radius:10px;margin-bottom:10px">
                                <strong>🤖 PM Bot:</strong><br>Total rows: {exec_globals['num_rows']}
                            </div>
                        """, unsafe_allow_html=True)
                    elif "result" in exec_globals:
                        st.markdown(f"""
                            <div style="background-color:#4A4F9E;padding:10px;border-radius:10px;margin-bottom:10px">
                                <strong>🤖 PM Bot:</strong><br>{exec_globals['result']}
                            </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.info("✅ Code executed — but no displayable output.")
                except Exception as e:
                    st.error(f"⚠️ Error while executing response code: {e}")
            else:
                st.markdown(f"""
                    <div style="background-color:#4A4F9E;padding:10px;border-radius:10px;margin-bottom:10px">
                        <strong>🤖 PM Bot:</strong><br>{msg['content']}
                    </div>
                """, unsafe_allow_html=True)

    # Chat history in sidebar
    with st.sidebar:
        st.subheader("Chat History")
        chat_history = load_chat_history()
        for msg in chat_history:
            role, content, timestamp = msg
            short_preview = " ".join(content.split()[:10]) + ("..." if len(content.split()) > 10 else "")
            st.markdown(f"**{role.capitalize()}** [{timestamp.split(' ')[1][:5]}]: {short_preview}")

    # Input form
    with st.form("chat_form", clear_on_submit=True):
        user_input = st.text_input("Ask something:")
        submitted = st.form_submit_button("Send")

        if submitted and user_input:
            st.session_state.messages.append({"role": "user", "content": user_input})
            response = None

            # Rule-based attempt
            try:
                response = search_content(user_input, faqs, definitions)
            except:
                response = None

            # Fallback to AI
            if not response or response.strip() == "":
                context = "\n".join(f"Q: {q}\nA: {a}" for q, a in zip(faqs['Question'], faqs['Answer']))
                if st.session_state.uploaded_df is not None:
                    context += "\n\nThe dataset is loaded into a variable called 'df'. Use the full DataFrame for all calculations and visualizations."

                with st.spinner("Thinking..."):
                    try:
                        response = ask_gpt(user_input, context=context)
                        save_learned_qa(user_input, response)
                    except Exception as e:
                        log_unanswered(user_input)
                        response = "Sorry, I couldn't find an answer right now."

            # Append response and save
            st.session_state.messages.append({"role": "assistant", "content": response})
            save_chat_history(st.session_state.messages)
            st.rerun()

