import streamlit as st
import requests

def auth_sidebar():
    st.markdown('<div class="sidebar-title">🔐 Login</div>', unsafe_allow_html=True)

    if "token" not in st.session_state or st.session_state.token is None:
        tab = st.radio("Select Action", ["Login", "Sign Up"], index=0)

        if tab == "Login":
            username_input = st.text_input("Username", placeholder="Enter your username")
            password_input = st.text_input("Password", type="password", placeholder="Enter your password")

            if st.button("Login"):
                try:
                    res = requests.post(
                        "http://localhost:8000/auth/login",
                        data={"username": username_input, "password": password_input},
                        headers={"Content-Type": "application/x-www-form-urlencoded"}
                    )
                    if res.status_code == 200:
                        data = res.json()
                        st.session_state.token = data["access_token"]
                        st.session_state.username = data["username"]
                        st.session_state.name = data["name"]
                        st.session_state.messages = []
                        st.session_state.selected_session = None
                        st.success(f"Welcome, {st.session_state.name}!")
                        st.rerun()
                    else:
                        st.error("Invalid username or password")
                except Exception as e:
                    st.error(f"Login failed: {e}")

        else:  # Sign Up
            st.subheader("Create a new account")
            new_username = st.text_input("Choose a username", key="signup_username")
            new_name = st.text_input("Your full name", key="signup_name")
            new_password = st.text_input("Choose a password", type="password", key="signup_password")

            if st.button("Sign Up"):
                if not new_username or not new_password or not new_name:
                    st.error("Please fill all fields")
                else:
                    try:
                        res = requests.post(
                            "http://localhost:8000/auth/register",
                            json={"username": new_username, "password": new_password, "name": new_name},
                            headers={"Content-Type": "application/json"}
                        )
                        if res.status_code == 201:
                            st.success("User created successfully! Logging you in...")

                            # Auto login after signup
                            login_res = requests.post(
                                "http://localhost:8000/auth/login",
                                data={"username": new_username, "password": new_password},
                                headers={"Content-Type": "application/x-www-form-urlencoded"}
                            )
                            if login_res.status_code == 200:
                                data = login_res.json()
                                st.session_state.token = data["access_token"]
                                st.session_state.username = data["username"]
                                st.session_state.name = data["name"]
                                st.session_state.messages = []
                                st.session_state.selected_session = None
                                st.rerun()  # Refresh the app
                            else:
                                st.error("Signup succeeded but auto-login failed. Please login manually.")
                        else:
                            detail = res.json().get("detail", "Signup failed")
                            st.error(f"Error: {detail}")
                    except Exception as e:
                        st.error(f"Signup failed: {e}")


    else:
        st.markdown(f"**Logged in as:** {st.session_state.name}")
        if st.button("Logout", key="logout_button"):
            st.session_state.token = None
            st.session_state.username = None
            st.session_state.name = None
            st.session_state.messages = []
            st.session_state.selected_session = None
            st.rerun()
