import streamlit as st
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.utils.db import load_faqs, add_faq, delete_faq

def show_faqs():
    st.subheader("📌 Frequently Asked Questions")
    faqs_df = load_faqs()

    if not faqs_df.empty and "category" in faqs_df.columns:
        categories = sorted(faqs_df["category"].dropna().unique())

        for category in categories:
            with st.expander(f"🗂️ {category}", expanded=False):
                category_df = faqs_df[faqs_df["category"] == category]
                for i, row in category_df.iterrows():
                    faq_id = row.get("id", f"{category}_{i}")
                    is_open = st.toggle(f"{row['question']}", key=f"toggle_{faq_id}")
                    if is_open:
                        st.markdown(row["answer"], unsafe_allow_html=True)

                        # Admin delete button
                        if st.session_state.get("username") == "admin@calgary.ca":
                            delete_col, _ = st.columns([1, 9])
                            with delete_col:
                                if st.button("🗑️", key=f"delete_{faq_id}", help="Delete this FAQ"):
                                    delete_faq(faq_id)
                                    st.success("FAQ deleted.")
                                    st.rerun()
    else:
        st.info("No FAQs found.")

    # Admin: Add New FAQ
    if st.session_state.get("username") == "admin@calgary.ca":
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
