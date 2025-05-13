import openai
import os
import time  # ✅ Import time module
from dotenv import load_dotenv
from backend.utils.logger import log_unanswered

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

if not openai.api_key:
    print("Error: OPENAI_API_KEY is not set")

def ask_gpt(question, context=""):
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    messages = [
        {"role": "system", "content": f"You are a helpful assistant for Preventive Maintenance (PM) support. Use the context below to answer questions:\n\n{context}"},
        {"role": "user", "content": question}
    ]

    for _ in range(3):  # Retry up to 3 times
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                temperature=0.3,
                max_tokens=300
            )
            print(response)  # Debugging line to print the raw response
            return response.choices[0].message.content.strip()
        except openai.APIConnectionError as e:
            print("API Connection Error: ", e)  # Show detailed error
            log_unanswered(question)
            time.sleep(5)  # Optional: wait before retrying
            continue
        except Exception as e:
            print("Other Error: ", e)  # Handle all other errors
            log_unanswered(question)
            return f"Error: {str(e)}"
    return "Connection error. Please try again later."