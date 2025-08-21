import streamlit as st
import pandas as pd
import os
import requests
from dotenv import load_dotenv
from urllib.parse import urlparse

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
SEARCH_ENGINE_ID = os.getenv("SEARCH_ENGINE_ID")

def show_guidance_section():
    st.subheader("📘 Regulations & Bylaws Guidance")

    try:
        xls = pd.ExcelFile("backend/data/Dictionary Format 2024_Jun 20.xlsm")
        df = pd.read_excel(xls, sheet_name="Summary")
        df.columns = [col.strip().lower().replace(' ', '_') for col in df.columns]
    except Exception as e:
        st.error(f"Could not load regulations dictionary: {e}")
        return

    search = st.text_input("Search by Equipment, Regulation, or Code", key="guidance_search")
    if search:
        filtered = df[
            df['equipment_description'].str.contains(search, case=False, na=False) |
            df['code_/_regulatory_body'].str.contains(search, case=False, na=False) |
            df['reference_/_links'].str.contains(search, case=False, na=False)
        ]
    else:
        filtered = df

    def make_link(ref):
        if isinstance(ref, str) and (ref.startswith("http://") or ref.startswith("https://")):
            return f'<a href="{ref}" target="_blank">Open Link</a>'
        elif isinstance(ref, str) and ref.strip():
            safe_ref = ref.replace("\\", "/")
            if safe_ref.startswith("//") or safe_ref.startswith("\\\\"):
                file_url = f"file:{safe_ref}"
            elif ":" in safe_ref:
                file_url = f"file:///{safe_ref}"
            else:
                file_url = ""
            if file_url:
                return f'<a href="{file_url}" target="_blank">{ref}</a>'
            else:
                return ref
        else:
            return ""

    filtered = filtered.copy()
    filtered['Reference'] = filtered['reference_/_links'].apply(make_link)

    display_df = filtered[['equipment_description', 'code_/_regulatory_body', 'Reference']].rename(
        columns={
            'equipment_description': 'Equipment',
            'code_/_regulatory_body': 'Regulation/Code'
        }
    )


    st.write("### Results")
    st.dataframe(display_df, use_container_width=True)

def show_best_practices_section():
    # Place back button in a small column at the top-left
    col1, col2 = st.columns([1, 10])
    with col1:
        if st.button("←", help="Back to Dashboard", use_container_width=True):
            st.session_state["current_page"] = "main"
            st.rerun()

    st.subheader("🌟 Best Practices (Google/OEM Search)")

    # (Optional) Load regulations dictionary if you want to use it elsewhere
    try:
        reg_xls = pd.ExcelFile("backend/data/Dictionary Format 2024_Jun 20.xlsm")
        reg_df = pd.read_excel(reg_xls, sheet_name="Summary")
        reg_df.columns = [col.strip().lower().replace(' ', '_') for col in reg_df.columns]
    except Exception as e:
        st.error(f"Could not load regulations dictionary: {e}")
        return

    search = st.text_input("🔎 Search Best Practices (Google/OEM)", key="bp_search")
    if not search:
        st.info("Type a keyword (e.g. 'hvac filter maintenance') to find best practices from Google or OEM sources.")
        return

    # Query Google Custom Search API
    params = {
        "key": GOOGLE_API_KEY,
        "cx": SEARCH_ENGINE_ID,
        "q": search,
        "num": 10
    }
    with st.spinner("Searching online for best practices..."):
        try:
            response = requests.get("https://www.googleapis.com/customsearch/v1", params=params)
            data = response.json()
            items = data.get("items", [])
        except Exception as e:
            st.error(f"Could not fetch Google results: {e}")
            return

    st.markdown("#### 🧑‍🔧 ")
    if not items:
        st.info("No best practices found online for your search. Try a different keyword or check OEM manuals.")
    else:
        for item in items:
            title = item.get("title", "")
            link = item.get("link", "")
            snippet = item.get("snippet", "")
            domain = urlparse(link).netloc.replace("www.", "")
            snippet = (snippet[:200] + '...') if len(snippet) > 200 else snippet
            st.markdown(
                f"""
<div style="
    border-left: 5px solid #2b8ae2;
    border-radius: 8px;
    box-shadow: 0 2px 8px rgba(44,62,80,0.05);
    padding: 16px 18px 12px 18px;
    margin-bottom: 18px;
    background: #fafdff;
    ">
    <div style="display: flex; align-items: center;">
        <span style="font-size:1.3em; margin-right: 8px;">🔗</span>
        <span style="font-size:1.1em;">
            <b><a href="{link}" target="_blank" style="color:#2b8ae2;text-decoration:none;">{title}</a></b>
        </span>
    </div>
    <div style="color: #888; font-size:0.95em; margin-bottom: 6px;">Source: {domain}</div>
    <div style="font-size:1em; color:#222;">{snippet}</div>
</div>
""", unsafe_allow_html=True)
            


def get_guidance_results(search, limit=3):
    try:
        xls = pd.ExcelFile("backend/data/Dictionary Format 2024_Jun 20.xlsm")
        df = pd.read_excel(xls, sheet_name="Summary")
        df.columns = [col.strip().lower().replace(' ', '_') for col in df.columns]
        filtered = df[
            df['equipment_description'].str.contains(search, case=False, na=False) |
            df['code_/_regulatory_body'].str.contains(search, case=False, na=False) |
            df['reference_/_links'].str.contains(search, case=False, na=False)
        ].head(limit)
        results = []
        for _, row in filtered.iterrows():
            results.append({
                "Equipment": row['equipment_description'],
                "Regulation/Code": row['code_/_regulatory_body'],
                "Reference": row['reference_/_links']
            })
        return results
    except Exception:
        return []

def get_best_practices_results(search, limit=3):
    params = {
        "key": GOOGLE_API_KEY,
        "cx": SEARCH_ENGINE_ID,
        "q": search,
        "num": limit
    }
    try:
        response = requests.get("https://www.googleapis.com/customsearch/v1", params=params)
        data = response.json()
        items = data.get("items", [])
        results = []
        for item in items:
            results.append({
                "title": item.get("title", ""),
                "link": item.get("link", ""),
                "domain": urlparse(item.get("link", "")).netloc.replace("www.", "")
            })
        return results
    except Exception:
        return []