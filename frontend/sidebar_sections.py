import streamlit as st
import sys
import base64
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.utils.db import load_faqs, add_faq, delete_faq, get_all_sessions_analytics
from backend.utils.ai_chat import ask_gpt
from chat import load_dictionary_corpus, retrieve_relevant_dictionary
def show_faqs():
    st.subheader("📌 Frequently Asked Questions")
 
    faqs_df = load_faqs()

    search_query = st.text_input("🔍 Search FAQs (by question or answer):", "")

    if not faqs_df.empty and "category" in faqs_df.columns:
        # Apply search filter
        if search_query:
            faqs_df = faqs_df[
                faqs_df["question"].str.contains(search_query, case=False, na=False) |
                faqs_df["answer"].str.contains(search_query, case=False, na=False)
            ]

        if faqs_df.empty:
            st.info("No FAQs matched your search.")
        else:
            categories = sorted(faqs_df["category"].dropna().unique())
            for category in categories:
                category_df = faqs_df[faqs_df["category"] == category]
                if category_df.empty:
                    continue

                with st.expander(f"🗂️ {category}", expanded=False):
                    for i, row in category_df.iterrows():
                        faq_id = row.get("id", f"{category}_{i}")
                        is_open = st.toggle(f"{row['question']}", key=f"toggle_{faq_id}")
                        if is_open:
                            st.markdown(row["answer"], unsafe_allow_html=True)

                        # Admin delete button (per FAQ)
                        if st.session_state.get("email") == "admin@calgary.ca":
                            if st.button("🗑️ Delete", key=f"delete_{faq_id}"):
                                delete_faq(faq_id)
                                st.success("FAQ deleted!")
                                st.rerun()

    # Admin: Add New FAQ (always shown for admin, even if no FAQs)
    if st.session_state.get("email") == "admin@calgary.ca":
        st.markdown("---")
        st.markdown("### ➕ Add a New FAQ")
        with st.form("add_faq_form"):
            category = st.selectbox(
                "Select Category",
                options=[
                    "PM Process & Workflow",
                    "Navigation and Reference Help",
                    "PM Schedule and Setup and Components",
                    "Work Order Generation and Status",
                    "Change Requests and Issue Escalation",
                    "Roles, Permissions and Responsibilities",
                    "Document and Record Handling",
                    "Special Cases"
                ]
            )
            question = st.text_input("New Question")
            answer = st.text_area("New Answer (Markdown supported)")

            col1, col2, col3 = st.columns([5, 2, 5])
            with col2:
                submitted = st.form_submit_button("➕", use_container_width=True)

            if submitted and category and question and answer:
                add_faq(category, question, answer)
                st.success("FAQ added!")
                st.rerun()


def show_definitions(def_df):
    st.subheader("📘 EAM Terminology")
    search_term = st.text_input("Search terms or definitions:")
    filtered = def_df[
        def_df['Term'].str.contains(search_term, case=False, na=False) |
        def_df['Definition'].str.contains(search_term, case=False, na=False)
    ] if search_term else def_df

    tabs = st.tabs(["A–F", "G–L", "M–R", "S–Z"])
    groups = {
        "A–F": filtered[filtered['Term'].str[0].str.upper().between("A", "F")],
        "G–L": filtered[filtered['Term'].str[0].str.upper().between("G", "L")],
        "M–R": filtered[filtered['Term'].str[0].str.upper().between("M", "R")],
        "S–Z": filtered[filtered['Term'].str[0].str.upper().between("S", "Z")],
    }
    for tab, label in zip(tabs, groups.keys()):
        with tab:
            if groups[label].empty:
                st.info("No definitions in this range.")
            else:
                for _, row in groups[label].iterrows():
                    st.write(f"**{row['Term']}**: {row['Definition']}")

def show_forms_and_docs(links_df):
    st.subheader("📎 Reference Links")
    for _, row in links_df.iterrows():
        st.markdown(f"- [{row['Resource']}]({row['Link']})")



def show_user_feedback():
    st.subheader("📝 User Feedback")
    with st.form("feedback_form"):
        title = st.text_input("Title")
        feedback = st.text_area("Your Feedback")
        attachment = st.file_uploader("Attach a file (optional)")
        submitted = st.form_submit_button("Submit Feedback")

    if submitted:
        file_bytes = attachment.read() if attachment else None
        file_name = attachment.name if attachment else None
        from backend.utils.db import save_user_feedback
        save_user_feedback(
            user_id=st.session_state.get("user_id"),
             user_name=st.session_state.get("name"),
            title=title,
            feedback=feedback,
            file_bytes=file_bytes,
            file_name=file_name
        )
        st.success("Thank you for your feedback!")

    # Admin view
    if st.session_state.get("email") == "admin@calgary.ca":
        from backend.utils.db import load_all_feedback
        feedback_list = load_all_feedback()
        st.markdown("---")
        st.header("📬 User Feedback Inbox")
        for fb in feedback_list:
            st.subheader(fb["title"])
            st.write(f"**From:** {fb.get('user_name', 'Unknown')}")
            st.write(fb["feedback"])

            if fb.get("file_name") and fb.get("file_bytes"):
                try:
                    file_bytes = base64.b64decode(fb["file_bytes"])
                    file_name = fb["file_name"].lower()
                    if file_name.endswith((".txt", ".csv")):
                        st.markdown("**Preview:**")
                        st.code(file_bytes.decode("utf-8", errors="replace"))
                    elif file_name.endswith((".png", ".jpg", ".jpeg")):
                        st.markdown("**Preview:**")
                        st.image(file_bytes)
                    elif file_name.endswith(".pdf"):
                        st.markdown("**Preview:**")
                        # Streamlit's st.pdf is not available, but you can use st.download_button for PDF
                        st.info("PDF preview not supported. Please download to view.")
                        st.download_button(
                            f"Download {fb['file_name']}",
                            data=file_bytes,
                            file_name=fb["file_name"]
                        )
                    else:
                        st.download_button(
                            f"Download {fb['file_name']}",
                            data=file_bytes,
                            file_name=fb["file_name"]
                        )
                except Exception:
                    st.warning(f"Attachment for {fb['file_name']} is corrupted or invalid.")
            st.markdown("---")


def show_session_analytics():
    if st.session_state.get("email") != "admin@calgary.ca":
        st.info("Session analytics are only available to admins.")
        return

    st.subheader("📊 Session Analytics (All Users)")
    from backend.utils.db import get_all_sessions_analytics
    analytics = get_all_sessions_analytics()
    if not analytics:
        st.info("No sessions to analyze.")
        return
    for a in analytics:
        st.markdown(f"**{a['session_name']}**")
        st.write(f"- User: {a['user_name']} ({a['user_id']})")
        st.write(f"- Messages: {a['num_messages']} (User: {a['user_messages']}, Bot: {a['bot_messages']})")
        st.write(f"- Duration: {a['duration_min']} min")
        st.write(f"- Avg. Response Time: {a['avg_response_time_sec']} sec")
        st.write(f"- Last Activity: {a['last_activity']}")
        st.write(f"- Top Topics: {a['top_words']}")
        st.markdown("---")

def show_dictionary_lookup():
    from backend.utils.ai_chat import ask_gpt  # <-- add this import if not at the top
    st.header("🔍 Dictionary Lookup")
    with st.form("dictionary_lookup_form"):
        user_query = st.text_input("Enter your dictionary query:")
        submitted = st.form_submit_button("Search")
    context = ""  # or pass any context you want
    if submitted and user_query:
        response = ask_gpt(user_query, context)
        st.markdown(response)