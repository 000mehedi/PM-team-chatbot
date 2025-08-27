import streamlit as st
from backend.utils.user_status import get_pending_users, approve_user, block_user

ADMIN_EMAILS = ["admin@calgary.ca"]  # Add more admin emails as needed

def show_admin_user_approval():
    user_email = st.session_state.get("email", "").lower()
    if user_email not in ADMIN_EMAILS:
        st.error("⛔ Access Denied: You don't have permission to access this page.")
        return

    st.title("👤 Admin: User Approval")
    pending_users = get_pending_users()
    if not pending_users:
        st.success("No pending users.")
        return

    for user in pending_users:
        email = user.get('email', user.get('user_id', ''))
        with st.expander(f"{email}", expanded=False):
            st.write(f"**Email:** {email}")
            st.write(f"**User ID:** {user.get('user_id', '')}")
            st.write(f"**Status:** {user.get('status', 'pending')}")
            col1, col2 = st.columns(2)
            with col1:
                if st.button(f"✅ Approve {email}"):
                    approve_user(user['user_id'])
                    st.success(f"User {email} approved.")
                    st.rerun()
            with col2:
                if st.button(f"⛔ Block {email}"):
                    block_user(user['user_id'])
                    st.warning(f"User {email} blocked.")
                    st.rerun()
