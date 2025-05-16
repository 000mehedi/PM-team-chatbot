import streamlit as st
import re
import io
import matplotlib.pyplot as plt
from backend.utils.ai_chat import ask_gpt
from backend.utils.db import save_message

def run_ai_response(code: str, context_vars: dict):
    # Prepare safe environment for code execution
    local_vars = {}
    if context_vars:
        local_vars.update(context_vars)

    def show_fig():
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        st.image(buf)
        plt.close()

    local_vars['plt'] = plt
    local_vars['show_fig'] = show_fig
    local_vars['plt'].show = show_fig  # override plt.show()

    try:
        exec(code, {}, local_vars)
    except Exception as e:
        st.error(f"Error running AI code: {e}")


def chat_interface(uploaded_df=None):
    # Display chat messages with custom bubbles
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.markdown(f"<div class='user-msg'>🧑‍💼 You:<br>{msg['content']}</div>", unsafe_allow_html=True)
        else:
            code_blocks = re.findall(r"```(?:python)?\s*([\s\S]*?)```", msg["content"])
            non_code_text = re.sub(r"```(?:python)?\s*[\s\S]*?```", "", msg["content"]).strip()

            if non_code_text:
                st.markdown(f"<div class='bot-msg'>🤖 PM Bot:<br>{non_code_text}</div>", unsafe_allow_html=True)

            if code_blocks:
                for code in code_blocks:
                    context_vars = {"df": uploaded_df} if uploaded_df is not None else {}
                    run_ai_response(code, context_vars)


    prompt = st.text_area("Your question:", height=100, placeholder="Type your question here and press Enter or the button below.")
    if st.button("Send"):
        if prompt.strip() == "":
            st.warning("Please enter a question.")
        else:
            st.session_state.messages.append({"role": "user", "content": prompt})
            save_message(st.session_state.selected_session, "user", prompt)

            response = ask_gpt(st.session_state.messages, uploaded_df)
            st.session_state.messages.append({"role": "assistant", "content": response})
            save_message(st.session_state.selected_session, "assistant", response)
            st.rerun()
