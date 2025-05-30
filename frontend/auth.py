import streamlit as st
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
                elif not email or not password:
                    st.warning("Please enter both email and password.")
                else:
                    try:
                        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                        user = res.user
                        if user is None:
                            st.error("Login failed: Check your credentials or confirm your email.")
                        else:
                            st.session_state.user = user
                            st.session_state.token = res.session.access_token
                            st.session_state.user_id = user.id
                            st.session_state.email = user.email

                            # Fetch or prompt for user's name from user_profiles
                            profile = supabase.table("user_profiles").select("*").eq("user_id", user.id).execute()

                            if profile.data:
                                st.session_state.name = profile.data[0]["name"]
                            else:

                                if name:
                                    st.session_state.name = name
                                    supabase.table("user_profiles").insert({
                                        "user_id": user.id,
                                        "email": user.email,
                                        "name": name
                                    }).execute()
                                    st.success(f"Name saved! Welcome, {name} 🎉")
                                    st.rerun()
                                return  # Wait for name input before rerunning app

                            st.success(f"Welcome, {st.session_state.name}!")
                            st.rerun()

                    except Exception as e:
                        st.error(f"Login failed: {e}")

        else:  # Sign Up
            email = st.text_input("Email", key="signup_email")
            password = st.text_input("Password", type="password", key="signup_password")
            name = st.text_input("Full Name", key="signup_name")  # <-- Add name field

            if st.button("Sign Up"):
                if not email or not password or not name:
                    st.error("Please fill in all fields.")
                elif not email.endswith("@calgary.ca"):
                    st.warning("Only @calgary.ca emails are allowed.")
                else:
                    try:
                        res = supabase.auth.sign_up({"email": email, "password": password})
                        user = res.user
                        if user:
                            # Save name to user_profiles table
                            supabase.table("user_profiles").insert({
                                "user_id": user.id,
                                "email": email,
                                "name": name
                            }).execute()
                            st.success("Account Created.")

                            # --- Auto login after signup ---
                            try:
                                login_res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                                login_user = login_res.user
                                if login_user:
                                    st.session_state.user = login_user
                                    st.session_state.token = login_res.session.access_token
                                    st.session_state.user_id = login_user.id
                                    st.session_state.email = login_user.email
                                    st.session_state.name = name
                                    st.success(f"Welcome, {name}! You are now logged in.")
                                    st.rerun()
                            except Exception as login_e:
                                st.warning(f"Auto-login failed: {login_e}")
                    except Exception as e:
                        st.error(f"Signup failed: {e}")

    else:
        email = st.session_state.user.email if st.session_state.user else "Unknown"
        name = st.session_state.get("name", email)
        st.markdown(f"**Logged in as:** {name}")
       


        if st.button("Logout"):
            try:
                supabase.auth.sign_out()
            except Exception as e:
                st.warning(f"Logout error: {e}")

            for key in ["user", "token", "messages", "username", "name", "selected_session", "user_id", "email"]:
                st.session_state.pop(key, None)

            st.rerun()


            