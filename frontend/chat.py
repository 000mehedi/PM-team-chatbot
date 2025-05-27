import streamlit as st
import re
from backend.utils.ai_chat import ask_gpt
from backend.utils.db import save_message

def run_ai_response(code: str, context_vars: dict):
    # Prepare safe environment for code execution
    local_vars = {}
    if context_vars:
        local_vars.update(context_vars)

    try:
        exec(code, {}, local_vars)
    except Exception as e:
        st.error(f"❌ Error running AI code: {e}")
        st.code(code, language="python")  # Show faulty code for debugging

def chat_interface(uploaded_df=None):
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
                run_ai_response(code, context_vars)

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
        st.session_state.messages.append({"role": "user", "content": prompt})
        save_message(st.session_state.selected_session, "user", prompt)
        context = uploaded_df.to_csv(index=False) if uploaded_df is not None else ""
        response = ask_gpt(prompt, context=context)
        st.session_state.messages.append({"role": "assistant", "content": response})
        save_message(st.session_state.selected_session, "assistant", response)
        st.rerun()