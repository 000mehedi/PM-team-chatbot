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
            st.button("Was this helpful?", key=f"faq_{row['Question']}")

elif option == "Definitions":
    st.subheader("EAM Terminology")
    for _, row in definitions.iterrows():
        st.write(f"**{row['Term']}**: {row['Definition']}")
        st.button("Was this helpful?", key=f"definition_{row['Term']}")

elif option == "Forms & Docs":
    st.subheader("Reference Links")
    for _, row in links.iterrows():
        st.markdown(f"- [{row['Resource']}]({row['Link']})")
        st.button("Was this helpful?", key=f"link_{row['Resource']}")

elif option == "Ask a Question":
    st.subheader("Ask a Question")
    mode = st.radio("Choose response mode", ["Rule-based", "AI-powered"])

    question = st.text_input("Type your question:")
    if question:
        st.write(f"Question entered: {question}")  # Debugging line

        if mode == "Rule-based":
            st.write("Triggering Rule-based mode...")  # Debugging line
            answer = search_content(question, faqs, definitions)
            st.write(f"Answer from rule-based search: {answer}")  # Debugging line
            if answer:
                st.success(answer)
            else:
                st.warning("I don’t know that yet. Logging for review.")
                log_unanswered(question)

        elif mode == "AI-powered":
            st.write("Triggering AI-powered mode...")  # Debugging line
            context_data = "\n".join(f"Q: {q}\nA: {a}" for q, a in zip(faqs['Question'], faqs['Answer']))
            st.write(f"Context data: {context_data[:500]}")  # Show a snippet of the context
            with st.spinner("Asking GPT..."):
                try:
                    answer = ask_gpt(question, context=context_data)
                    st.success(answer)
                except Exception as e:
                    st.error(f"AI error: {str(e)}")
        st.button("Was this helpful?", key=f"question_{question}")
