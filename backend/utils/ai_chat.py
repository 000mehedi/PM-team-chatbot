import openai
import os

openai.api_key = os.getenv("OPENAI_API_KEY")

def ask_gpt(question, context=""):
    prompt = (
        "You are a Streamlit data assistant. "
        
        "When asked questions involving data analysis or visualizations, "
        "use Python (with pandas, matplotlib, or seaborn). "
        "Always return code inside a Python code block using triple backticks like this: ```python ... ```.\n\n"
        f"Context:\n{context}\n\n"
        f"User question: {question}\nAnswer:"
    )

    response = openai.ChatCompletion.create(

        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant for data analysis in Streamlit."},
            {"role": "user", "content": prompt}
        ]
    )

    return response.choices[0].message.content.strip()
