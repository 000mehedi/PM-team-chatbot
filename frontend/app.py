import streamlit as st
import sys
import os
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.utils.content_loader import load_faqs, load_definitions, load_links, search_content
from backend.utils.logger import log_unanswered
from backend.utils.ai_chat import ask_gpt

load_dotenv()

faqs = load_faqs()
definitions = load_definitions()
links = load_links()

st.set_page_config(page_title="PM Support Chatbot", page_icon="🔧")

st.title("PM Support Chatbot")
st.markdown("Helping the PM team get quick answers.")

option = st.sidebar.radio("Choose a topic", ["FAQs", "Definitions", "Forms & Docs", "Ask a Question"])

if option == "FAQs":
    st.subheader("Frequently Asked Questions")
    for _, row in faqs.iterrows():
        with st.expander(row['Question']):
            st.write(row['Answer'])
    

elif option == "Definitions":
    st.subheader("EAM Terminology")

    search_term = st.text_input("Search terms or definitions:")

    # Filter as user types
    filtered_definitions = definitions[
        definitions['Term'].str.contains(search_term, case=False, na=False) |
        definitions['Definition'].str.contains(search_term, case=False, na=False)
    ] if search_term else definitions

    if filtered_definitions.empty:
        st.info("No matching terms found.")
    else:
        # Group terms alphabetically into 4 tab buckets
        tabs = st.tabs(["A–F", "G–L", "M–R", "S–Z"])

        groups = {
            "A–F": filtered_definitions[filtered_definitions["Term"].str[0].str.upper().between("A", "F")],
            "G–L": filtered_definitions[filtered_definitions["Term"].str[0].str.upper().between("G", "L")],
            "M–R": filtered_definitions[filtered_definitions["Term"].str[0].str.upper().between("M", "R")],
            "S–Z": filtered_definitions[filtered_definitions["Term"].str[0].str.upper().between("S", "Z")]
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
    st.subheader("Ask a Question")
    mode = st.radio("Choose response mode", ["Rule-based", "AI-powered"])

    question = st.text_input("Type your question:")
    if question:
   

        if mode == "Rule-based":
 
            answer = search_content(question, faqs, definitions)
       
            if answer:
                st.success(answer)
            else:
                st.warning("I don’t know that yet. Logging for review.")
                log_unanswered(question)

        elif mode == "AI-powered":
            context_data = "\n".join(f"Q: {q}\nA: {a}" for q, a in zip(faqs['Question'], faqs['Answer']))

            with st.spinner("Asking GPT..."):
                try:
                    answer = ask_gpt(question, context=context_data)
                    st.success(answer)
                except Exception as e:
                    st.error(f"AI error: {str(e)}")
                    log_unanswered(question)  # ✅ DO NOT pass 'e' or anything else
