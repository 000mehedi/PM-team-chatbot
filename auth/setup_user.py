import streamlit_authenticator as stauth
from backend.utils.db import create_users_table
import sqlite3

def add_user(username, name, password):
    hashed_pw = stauth.Hasher().hash([password])[0]  # fix here
    conn = sqlite3.connect("auth_users.db")
    c = conn.cursor()
    c.execute("INSERT INTO users (username, name, password) VALUES (?, ?, ?)",
              (username, name, hashed_pw))
    conn.commit()
    conn.close()
