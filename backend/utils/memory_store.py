import os
import faiss
import pandas as pd
from sentence_transformers import SentenceTransformer

EMBEDDING_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
KB_FILE = "knowledge_base.csv"
INDEX_FILE = "kb.index"

def embed(texts):
    return EMBEDDING_MODEL.encode(texts, convert_to_numpy=True)

def load_kb():
    if not os.path.exists(KB_FILE):
        return [], [], None
    df = pd.read_csv(KB_FILE)
    if os.path.exists(INDEX_FILE):
        index = faiss.read_index(INDEX_FILE)
    else:
        index = None
    return list(df["question"]), list(df["answer"]), index

def add_to_kb(question, answer):
    q_list, a_list, _ = load_kb()
    new_df = pd.DataFrame({"question": q_list + [question], "answer": a_list + [answer]})
    new_df.to_csv(KB_FILE, index=False)

    # Update index
    embeddings = embed(new_df["question"].tolist())
    index = faiss.IndexFlatL2(embeddings.shape[1])
    index.add(embeddings)
    faiss.write_index(index, INDEX_FILE)

def query_kb(user_question, top_k=3):
    questions, answers, index = load_kb()
    if not index or not questions:
        return []
    
    query_embedding = embed([user_question])
    distances, indices = index.search(query_embedding, top_k)
    
    return [(questions[i], answers[i]) for i in indices[0] if i < len(questions)]
