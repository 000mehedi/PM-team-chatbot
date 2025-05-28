from sentence_transformers import SentenceTransformer, util

# Load the model once (fast and lightweight)
model = SentenceTransformer('all-MiniLM-L6-v2')

def get_faq_match(user_question, faqs_df, threshold=0.7):
    faq_questions = faqs_df['question'].tolist()
    faq_embeddings = model.encode(faq_questions, convert_to_tensor=True)
    user_embedding = model.encode(user_question, convert_to_tensor=True)
    similarities = util.cos_sim(user_embedding, faq_embeddings)[0]
    best_idx = int(similarities.argmax())
    best_score = float(similarities[best_idx])
    if best_score >= threshold:
        return faqs_df.iloc[best_idx]['answer']
    return None