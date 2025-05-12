# backend/utils/content_loader.py
import pandas as pd
import os
from difflib import get_close_matches

DATA_PATH = os.path.join(os.path.dirname(__file__), '..', 'data')

def load_faqs():
    return pd.read_csv(os.path.join(DATA_PATH, 'faqs.csv'))

def load_definitions():
    return pd.read_csv(os.path.join(DATA_PATH, 'definitions.csv'))

def load_links():
    return pd.read_csv(os.path.join(DATA_PATH, 'links.csv'))

def search_content(query, faqs, definitions):
    q_matches = get_close_matches(query.lower(), faqs['Question'].str.lower(), n=1, cutoff=0.6)
    if q_matches:
        return faqs[faqs['Question'].str.lower() == q_matches[0]]['Answer'].values[0]

    t_matches = get_close_matches(query.lower(), definitions['Term'].str.lower(), n=1, cutoff=0.6)
    if t_matches:
        return definitions[definitions['Term'].str.lower() == t_matches[0]]['Definition'].values[0]

    return None