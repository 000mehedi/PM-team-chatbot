import streamlit as st
import matplotlib.pyplot as plt

def run_ai_response(code: str, context_vars: dict):
    import io
    import matplotlib.pyplot as plt
    import pandas as pd

    # Prepare local environment
    local_vars = {}
    if context_vars:
        local_vars.update(context_vars)
    local_vars["df"] = context_vars.get("df")  # if df is passed directly

    # Capture plt.show()
    def show_fig():
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        st.image(buf)
        plt.clf()  # Clear the figure for next plot

    local_vars["plt"] = plt
    local_vars["show_fig"] = show_fig
    plt.show = show_fig  # <-- THIS is the important fix

    try:
        exec(code, {}, local_vars)
    except Exception as e:
        st.error(f"Error running AI code: {e}")
