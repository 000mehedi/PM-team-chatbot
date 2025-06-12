import openai
import os
import re
import pandas as pd
from backend.utils.supabase_client import supabase  # adjust if needed

openai.api_key = os.getenv("OPENAI_API_KEY")

def get_latest_model_name():
    try:
        with open("latest_model_name.txt", "r") as f:
            return f.read().strip()
    except Exception:
        return "gpt-3.5-turbo"

def suggest_pm_names(partial_name: str, limit=5):
    query = supabase.table("dictionary") \
        .select("pm_name") \
        .ilike("pm_name", f"%{partial_name}%") \
        .limit(limit) \
        .execute()
    if query.data:
        # Remove duplicates and empty names
        names = list({row["pm_name"] for row in query.data if row["pm_name"]})
        return names
    return []

def get_pm_tasks(search_term: str, search_pm_code=True, search_pm_name=True):
    # Try pm_code first if allowed
    if search_pm_code:
        query = supabase.table("dictionary") \
            .select("pm_code, pm_name, sequence, description") \
            .ilike("pm_code", f"%{search_term}%") \
            .execute()
        if query.data and len(query.data) > 0:
            return query.data
    # Try pm_name if allowed
    if search_pm_name:
        query = supabase.table("dictionary") \
            .select("pm_code, pm_name, sequence, description") \
            .ilike("pm_name", f"%{search_term}%") \
            .execute()
        if query.data and len(query.data) > 0:
            return query.data
    return []

def ask_gpt(question, context=""):
    pm_match = re.search(r"([A-Z]+[-]\w+[-]\d{2})", question)
    if pm_match:
        search_term = pm_match.group(1)
        tasks = get_pm_tasks(search_term, search_pm_code=True, search_pm_name=True)
        label = "PM Code"
    else:
        # Search both pm_code and pm_name for the user's input
        search_term = question.strip()
        tasks = get_pm_tasks(search_term, search_pm_code=True, search_pm_name=True)
        label = "PM Name or Code"

    if tasks and len(tasks) > 0:
        df = pd.DataFrame(tasks)
        df = df.sort_values("sequence")
        pm_code = df.iloc[0]['pm_code']
        pm_name = df.iloc[0]['pm_name']
        table_md = df[["sequence", "description"]].to_markdown(index=False)
        response_text = (
            f"**PM Code:** {pm_code}\n\n"
            f"**PM Name:** {pm_name}\n\n"
            "**Tasks:**\n"
            f"{table_md}"
        )
        return response_text
    # ...rest of your code...
    # If not found, continue with code/gen AI as fallback
    # Remove the plain "code" keyword from triggering code snippet output.
    question_lower = question.lower()
    needs_code = any(kw in question_lower for kw in [
        "visualize", "chart", "graph", "plot", "draw", "bar chart", "line chart", "heatmap", "generate code"
    ])
    if needs_code:
        prompt = (
            'You are a Streamlit data assistant.\n'
            'When answering, provide a complete Python code snippet that includes all necessary imports:\n'
            '```python\nimport streamlit as st\nimport pandas as pd\nimport plotly.express as px\n```\n\n'
            'For all visualizations, use Plotly and display figures using `st.plotly_chart(fig, key="unique_key")`.\n'
            'Do NOT use matplotlib or seaborn.\n'
            'IMPORTANT: Do NOT read any data from local files. Assume the uploaded data is already loaded '
            'into a pandas DataFrame called `df`.\n\n'
            f'Context (including Data Dictionary):\n{context}\n\n'
            f'User question: {question}\nAnswer:\n'
            'Provide the code wrapped in triple backticks with python, like:\n'
            '```python\n...code...\n```'
        )
    else:
        prompt = (
            'You are a helpful Streamlit chatbot assistant.\n'
            'You may assume the user has uploaded data already loaded into a DataFrame called `df`.\n'
            'Please review the provided context—including the Data Dictionary below—to answer the user\'s question.\n\n'
            f'Context (including Data Dictionary):\n{context}\n\n'
            f'User question: {question}\nAnswer:'
        )
    model_name = get_latest_model_name()
    response = openai.ChatCompletion.create(
        model=model_name,
        messages=[
            {"role": "system", "content": "You are a helpful assistant for data analysis in Streamlit."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content.strip()