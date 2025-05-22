import openai
import os

openai.api_key = os.getenv("OPENAI_API_KEY")

def ask_gpt(question, context=""):
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
    '```python\n...code...\n```\n'
)



    response = openai.ChatCompletion.create(

        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant for data analysis in Streamlit."},
            {"role": "user", "content": prompt}
        ]
    )

    return response.choices[0].message.content.strip()
