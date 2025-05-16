import streamlit as st

def show_faqs(faqs_df):
    st.subheader("📌 Frequently Asked Questions")
    for _, row in faqs_df.iterrows():
        with st.expander(row["Question"]):
            st.write(row["Answer"])

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
