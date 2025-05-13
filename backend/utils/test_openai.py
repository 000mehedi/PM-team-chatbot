import openai
import os
from dotenv import load_dotenv
import requests
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager

# Disabling SSL verification (not recommended for production)
class SSLAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        kwargs['ssl_context'] = None
        return super().init_poolmanager(*args, **kwargs)

# Load environment variables
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# Disable SSL verification for OpenAI API requests
session = requests.Session()
session.mount('https://', SSLAdapter())
openai.api_requestor._request = session.request

# Check if API key is set
if openai.api_key is None:
    print("API Key is not set!")
else:
    try:
        response = openai.Completion.create(
            engine="gpt-4.1", 
            prompt="Say hello to the user.",
            max_tokens=10
        )
        print("Response: ", response)
    except openai.error.OpenAIError as e:
        print("OpenAI Error: ", e)
    except Exception as e:
        print("Other Error: ", e)
