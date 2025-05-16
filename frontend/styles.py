import streamlit as st

def inject_styles():
    st.markdown("""
    <style>
    .user-msg {
        background-color: #5e4b8b;
        color: white;
        padding: 14px 18px;
        border-radius: 18px;
        margin-bottom: 12px;
        max-width: 75%;
        font-family: -apple-system, BlinkMacSystemFont, "San Francisco", "Helvetica Neue", Helvetica, Arial, sans-serif;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.15);
    }
                

    .bot-msg {
        background-color: #7b8ca3;
        color: white;
        padding: 14px 18px;
        border-radius: 18px;
        margin-bottom: 12px;
        max-width: 75%;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
    }
    /* Add other styles here */
    </style>
    """, unsafe_allow_html=True)
