import streamlit as st
import re
from backend.utils.ai_chat import ask_gpt
from backend.utils.db import save_message, get_user_memory, update_user_memory
from backend.utils.faq_semantics import get_faq_match

def run_ai_response(code: str, context_vars: dict):
    local_vars = {}
    output = None
    if context_vars:
        local_vars.update(context_vars)
    try:
        exec(code, {}, local_vars)
        # Check for result variable
        if "result" in local_vars:
            output = local_vars["result"]
        # Check for DataFrame preview
        for key in ["clean_df", "result_df", "filtered_df"]:
            if key in local_vars and hasattr(local_vars[key], "head"):
                return local_vars[key]
    except Exception as e:
        st.error(f"❌ Error running AI code: {e}")
        st.code(code, language="python")
    return output


def chat_interface(uploaded_df=None, faqs_context="", faqs_df=None):
    # Display chat messages
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.markdown(f"<div class='user-msg'>🧑‍💼 You:<br>{msg['content']}</div>", unsafe_allow_html=True)
        else:
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

    # Use a form to handle Enter and clearing input
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
                # --- Conversational context enhancement ---
        # Try to extract a subject (e.g., equipment name) from the prompt
        import pandas as pd
        if "last_subject" not in st.session_state:
            st.session_state["last_subject"] = None

        subject = None
        if uploaded_df is not None:
            # Try to match any value from the first column (assuming it's equipment name)
            first_col = uploaded_df.columns[0]
            for val in uploaded_df[first_col].astype(str).unique():
                if val.lower() in prompt.lower():
                    subject = val
                    break
        if subject:
            st.session_state["last_subject"] = subject

        # If the prompt is ambiguous but we have a last subject, append it
        ambiguous_keywords = ["serial number", "model number", "manual", "tell me more", "details", "info"]
        if any(kw in prompt.lower() for kw in ambiguous_keywords) and st.session_state["last_subject"]:
            prompt = f"{prompt} for {st.session_state['last_subject']}"




        # Save user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        save_message(session_id, "user", prompt)

        # --- Semantic FAQ matching ---
        faq_answer = None
        if faqs_df is not None:
            faq_answer = get_faq_match(prompt, faqs_df)

        if faq_answer:
            response = faq_answer
        else:
            # Build prompt with memory if enabled
            memory = ""
            if memory_enabled and user_id:
                memory = get_user_memory(user_id)

            # Combine uploaded data and FAQ context
            context = ""
            if uploaded_df is not None:
                context += uploaded_df.to_csv(index=False) + "\n"
            if faqs_context:
                context += "\nFAQs:\n" + faqs_context

            full_prompt = memory + f"\nUser: {prompt}\nBot:"

            # Get GPT response
            response = ask_gpt(prompt, context=context)

        st.session_state.messages.append({"role": "assistant", "content": response})
        save_message(session_id, "assistant", response)

        # Update memory
        if memory_enabled and user_id:
            updated_memory = memory + f"\nUser: {prompt}\nBot: {response}\n"
            update_user_memory(user_id, updated_memory)

        st.rerun()

    # --- Add chat export button at the end ---
    if st.session_state.get("messages"):
        header = "PM Support Chatbot Conversation Export\n(Note: Figures and charts are only visible in the app, not in this text file.)\n\n"
        chat_lines = []
        for msg in st.session_state.messages:
            role = "You" if msg["role"] == "user" else "PM Bot"
            chat_lines.append(f"{role}: {msg['content']}\n")
        chat_text = header + "\n".join(chat_lines)
        st.download_button(
            label="⬇️ Download Chat History",
            data=chat_text.encode("utf-8"),
            file_name="pm_chat_history.txt",
            mime="text/plain"
        )