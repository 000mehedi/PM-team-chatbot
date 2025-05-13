# 📁 backend/utils/knowledge_base.py
import os
import pandas as pd
import csv

LEARNED_QA_PATH = os.path.join(os.path.dirname(__file__), "learned_qa.csv")

def load_learned_qa():
    if os.path.exists(LEARNED_QA_PATH):
        return pd.read_csv(LEARNED_QA_PATH)
    else:
        return pd.DataFrame(columns=["Question", "Answer", "Source"])

def save_learned_qa(question, answer, source="AI"):
    with open(LEARNED_QA_PATH, mode="a", newline='', encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([question.strip(), answer.strip(), source])

def search_learned_qa(query):
    df = load_learned_qa()
    for _, row in df.iterrows():
        if query.lower() in row["Question"].lower():
            return row["Answer"]
    return None