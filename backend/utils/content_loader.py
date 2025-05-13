
# 📁 backend/utils/content_loader.py
import pandas as pd
import os
from .knowledge_base import search_learned_qa

def load_faqs():
    data_path = os.path.join(os.path.dirname(__file__), "..", "data", "faqs.csv")
    return pd.read_csv(os.path.abspath(data_path))


def load_definitions():
    data_path = os.path.join(os.path.dirname(__file__), '..', "data", "definitions.csv")
    return pd.read_csv(os.path.abspath(data_path))

def load_links():
    data_path = os.path.join(os.path.dirname(__file__), '..', "data", "links.csv")
    return pd.read_csv(os.path.abspath(data_path))



def search_content(query, faqs, definitions):
    for _, row in faqs.iterrows():
        if query.lower() in row['Question'].lower():
            return row['Answer']
    for _, row in definitions.iterrows():
        if query.lower() in row['Term'].lower() or query.lower() in row['Definition'].lower():
            return f"{row['Term']}: {row['Definition']}"
    learned_answer = search_learned_qa(query)
    if learned_answer:
        return learned_answer
    return None
