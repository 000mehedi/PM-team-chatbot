import streamlit as st
import re
import json
from backend.utils.ai_chat import ask_gpt
from backend.utils.db import save_message, get_user_memory, update_user_memory
from backend.utils.faq_semantics import get_faq_match
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from backend.utils.supabase_client import supabase
from frontend.process_maps import display_pdf_from_data, display_pdf_from_url

def load_dictionary_corpus():
    response = supabase.table("dictionary").select("sequence, description").execute()
    # Safely check for an error attribute; if not present then assume no error
    error = getattr(response, "error", None)
    if error:
        return []
    # Alternatively, if response is a dict-like object, you can do:
    # if response.get("error"):
    #    return []
    data = getattr(response, "data", [])
    corpus = []
    for row in data:
        sequence = row.get("sequence") or ""
        description = row.get("description") or ""
        corpus.append(f"{sequence} – {description}")
    return corpus

def run_ai_response(code: str, context_vars: dict):
    local_vars = {}
    output = None
    if context_vars:
        local_vars.update(context_vars)
    try:
        exec(code, {}, local_vars)
        if "result" in local_vars:
            output = local_vars["result"]
        for key in ["clean_df", "result_df", "filtered_df"]:
            if key in local_vars and hasattr(local_vars[key], "head"):
                return local_vars[key]
    except Exception as e:
        st.error(f"❌ Error running AI code: {e}")
        st.code(code, language="python")
    return output

# Modified retrieve_relevant_dictionary with flexible sheet-code filtering
def retrieve_relevant_dictionary(query, corpus, top_k=3):
    query_lower = query.lower()
    # List of known sheet codes (add any new ones here)
    sheet_codes = ["fc-q-01", "fa-a-01f", "eg-s-01", "eg-m-01", "eg-a-01", "safety-w-q-01"]
    matched_code = None
    for code in sheet_codes:
        if code in query_lower:
            matched_code = code
            break
    if matched_code:
        filtered_corpus = [entry for entry in corpus if matched_code in entry.lower()]
        # Optional debug:
        # st.write(f"Matched code: {matched_code}")
        # st.write("Filtered Corpus:", filtered_corpus)
        if not filtered_corpus:
            filtered_corpus = corpus
    else:
        filtered_corpus = corpus

    vectorizer = TfidfVectorizer(stop_words="english")
    corpus_vectors = vectorizer.fit_transform(filtered_corpus)
    query_vector = vectorizer.transform([query])
    scores = cosine_similarity(query_vector, corpus_vectors).flatten()
    top_indices = [i for i in np.argsort(scores)[-top_k:][::-1] if scores[i] > 0.15]
    relevant_rows = [filtered_corpus[i] for i in top_indices]
    return "\n".join(relevant_rows)

def chat_interface(uploaded_df=None, faqs_context="", faqs_df=None, dictionary_corpus=None):
    # Display previous chat messages
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.markdown(f"<div class='user-msg'>🧑‍💼 You:<br>{msg['content']}</div>", unsafe_allow_html=True)
        else:
            # Check if this is a structured response with process maps
            if isinstance(msg["content"], dict) and msg["content"].get("type") == "process_maps":
                process_map_response = msg["content"]
                # Display the intro message
                st.markdown(f"<div class='bot-msg'>🤖 PM Bot:<br>{process_map_response['message']}</div>", unsafe_allow_html=True)
                
                # Display each process map in an expander
                for i, result in enumerate(process_map_response.get("results", []), 1):
                    with st.expander(f"{i}. {result.get('title', 'Untitled')}"):
                        if result.get('description'):
                            st.write(result.get('description'))
                        
                        # Display the PDF based on available data
                        if result.get('file_data'):
                            display_pdf_from_data(result['file_data'], result['title'])
                        elif result.get('pdf_data'):
                            display_pdf_from_data(result['pdf_data'], result['title'])
                        elif result.get('file_url'):
                            display_pdf_from_url(result['file_url'], result['title'])
                        else:
                            st.warning("No document content available.")
                            
            elif isinstance(msg["content"], str) and msg["content"].startswith("**Here are relevant regulations/bylaws:**"):
                # Parse and render as cards (optional)
                for line in msg["content"].split("\n"):
                    if line.startswith("- **"):
                        st.markdown(f"<div style='border-left:4px solid #2b8ae2;padding:8px 0 8px 12px;margin-bottom:8px;background:#fafdff;'>{line[2:]}</div>", unsafe_allow_html=True)
                    else:
                        st.markdown(line)
            else:
                # Regular text message handling
                code_blocks = re.findall(r"```(?:python)?\s*([\s\S]*?)```", msg["content"])
                non_code_text = re.sub(r"```(?:python)?\s*[\s\S]*?```", "", msg["content"]).strip()
                if non_code_text:
                    st.markdown(f"<div class='bot-msg'>🤖 PM Bot:<br>{non_code_text}</div>", unsafe_allow_html=True)
                for i, code in enumerate(code_blocks):
                    context_vars = {"df": uploaded_df} if uploaded_df is not None else {}
                    with st.expander(f"🔧 Show code block {i+1}", expanded=False):
                        st.code(code, language="python")
                        df_preview = run_ai_response(code, context_vars)
                        if df_preview is not None:
                            st.info("Preview of resulting DataFrame:")
                            st.dataframe(df_preview.head(10))

    session_id = st.session_state.get("selected_session", "default_session")
    prompt_key = f"chat_input_{session_id}"

    with st.form(key=f"form_{prompt_key}", clear_on_submit=True):
        prompt = st.text_input(
            "Your question:",
            value="",
            placeholder="Type your question here and press Enter.",
            key=prompt_key
        )
        submitted = st.form_submit_button("Send")

    if submitted and prompt:
        user_id = st.session_state.get("user_id")
        memory_enabled = True
        session_id = st.session_state.selected_session
        
        # Conversational context enhancement
        import pandas as pd
        if "last_subject" not in st.session_state:
            st.session_state["last_subject"] = None

        subject = None
        if uploaded_df is not None:
            first_col = uploaded_df.columns[0]
            for val in uploaded_df[first_col].astype(str).unique():
                if val.lower() in prompt.lower():
                    subject = val
                    break
        if subject:
            st.session_state["last_subject"] = subject

        ambiguous_keywords = ["serial number", "model number", "manual", "tell me more", "details", "info"]
        if any(kw in prompt.lower() for kw in ambiguous_keywords) and st.session_state["last_subject"]:
            prompt = f"{prompt} for {st.session_state['last_subject']}"

        st.session_state.messages.append({"role": "user", "content": prompt})
        save_message(session_id, "user", prompt)

        memory = ""
        if memory_enabled and user_id:
            memory = get_user_memory(user_id)

        faq_answer = None
        if faqs_df is not None:
            faq_answer = get_faq_match(prompt, faqs_df)

        if faq_answer:
            response = faq_answer
        else:
            # Build context from uploaded data, FAQs, and dictionary corpus (RAG)
            context = ""
            if uploaded_df is not None:
                context += uploaded_df.to_csv(index=False) + "\n"
            if faqs_context:
                context += "\nFAQs:\n" + faqs_context
            if dictionary_corpus is not None and len(dictionary_corpus) > 0:
                relevant_dictionary_context = retrieve_relevant_dictionary(prompt, dictionary_corpus, top_k=3)
                if relevant_dictionary_context:
                    context += "\nData Dictionary (relevant):\n" + relevant_dictionary_context

            full_prompt = memory + f"\nUser: {prompt}\nBot:"
            response = ask_gpt(prompt, context=context)

        # Save to session state and database (handle both string and dict responses)
        st.session_state.messages.append({"role": "assistant", "content": response})
        
        # For database storage, convert dict to JSON string if needed
        if isinstance(response, dict):
            save_message(session_id, "assistant", json.dumps(response))
        else:
            save_message(session_id, "assistant", response)

        if memory_enabled and user_id:
            # For memory, only store the message text or a summary of structured content
            if isinstance(response, dict) and response.get("type") == "process_maps":
                memory_text = f"I found {len(response.get('results', []))} process maps related to your query."
            else:
                memory_text = response
            
            updated_memory = memory + f"\nUser: {prompt}\nBot: {memory_text}\n"
            update_user_memory(user_id, updated_memory)

        st.rerun()

    if st.session_state.get("messages"):
        header = "PM Support Chatbot Conversation Export\n(Note: Figures and charts are only visible in the app, not in this text file.)\n\n"
        chat_lines = []
        for msg in st.session_state.messages:
            role = "You" if msg["role"] == "user" else "PM Bot"
            
            # Handle dict content for export
            content = msg["content"]
            if isinstance(content, dict) and content.get("type") == "process_maps":
                export_content = content.get("message", "")
                # Add titles of process maps
                for i, result in enumerate(content.get("results", []), 1):
                    export_content += f"\n{i}. {result.get('title', 'Untitled')}"
                    if result.get('description'):
                        export_content += f" - {result.get('description')[:50]}..."
            else:
                export_content = content
                
            chat_lines.append(f"{role}: {export_content}\n")
            
        chat_text = header + "\n".join(chat_lines)
        st.download_button(
            label="⬇️ Download Chat History",
            data=chat_text.encode("utf-8"),
            file_name="pm_chat_history.txt",
            mime="text/plain"
        )