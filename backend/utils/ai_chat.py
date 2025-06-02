import openai
import os

openai.api_key = os.getenv("OPENAI_API_KEY")

def get_latest_model_name():
    try:
        with open("latest_model_name.txt", "r") as f:
            return f.read().strip()
    except Exception:
        return "gpt-3.5-turbo"  # fallback if file not found

def ask_gpt(question, context=""):
    # Detect if the question requires code
    question_lower = question.lower()
    needs_code = any(kw in question_lower for kw in [
        "visualize", "chart", "graph", "plot", "draw", "bar chart", "line chart", "heatmap", "code", "generate code"
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
            f'Context:\n{context}\n\n'
            f'User question: {question}\nAnswer:\n'
            'Provide the code wrapped in triple backticks with python, like:\n'
            '```python\n...code...\n```'
        )
    else:
        prompt = (
            'You are a helpful Streamlit chatbot assistant.\n'
            'You may assume the user has uploaded data already loaded into a DataFrame called `df`.\n'
            'If the user is asking for code or a chart, provide it using Plotly and Streamlit.\n'
            'If the user is asking for an explanation, interpretation, or insight, respond only with plain text.\n\n'
            f'Context:\n{context}\n\n'
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