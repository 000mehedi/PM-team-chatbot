import streamlit as st
import requests
import os
import sys  
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.utils.supabase_client import supabase 

def auth_sidebar():
    st.markdown('<div class="sidebar-title">🔐 Login</div>', unsafe_allow_html=True)

    if "user" not in st.session_state or st.session_state.user is None:
        tab = st.radio("Select Action", ["Login", "Sign Up"], index=0)

        if tab == "Login":
            email = st.text_input("Email", placeholder="you@calgary.ca")
            password = st.text_input("Password", type="password")

            if st.button("Login"):
                if not email.endswith("@calgary.ca"):
                    st.warning("Only @calgary.ca emails are allowed.")
                else:
                    try:
                        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                        st.session_state.user = res.user
                        st.session_state.token = res.session.access_token
                        st.session_state.username = res.user.email  # ✅ Needed for chat sessions
                        st.success(f"Welcome, {res.user.email}!")
                        st.rerun()

                    except Exception as e:
                        st.error(f"Login failed: {e}")

        else:  # Sign Up
            email = st.text_input("Email", key="signup_email")
            password = st.text_input("Password", type="password", key="signup_password")

            if st.button("Sign Up"):
                if not email or not password:
                    st.error("Please fill in all fields.")
                elif not email.endswith("@calgary.ca"):
                    st.warning("Only @calgary.ca emails are allowed.")
                else:
                    try:
                        res = supabase.auth.sign_up({"email": email, "password": password})
                        st.success("Check your email to confirm your account.")
                    except Exception as e:
                        st.error(f"Signup failed: {e}")
    else:
        email = st.session_state.user.email
        st.markdown(f"**Logged in as:** {email}")
        if st.button("Logout"):
            try:
                supabase.auth.sign_out()
            except Exception as e:
                st.warning(f"Logout error: {e}")
            for key in ["user", "token", "messages", "username", "name", "selected_session"]:
                st.session_state.pop(key, None)

            st.rerun()
