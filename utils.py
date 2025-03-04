import sqlite3
from datetime import datetime

DATABASE = "database.db"

def text_similarity(doc1, doc2):
    return sum(1 for word in doc1.split() if word in doc2.split()) / max(len(doc1.split()), len(doc2.split()))

def reset_daily_credits():
    with sqlite3.connect(DATABASE) as conn:
        cur = conn.cursor()
        cur.execute("UPDATE users SET credits = 20")
        conn.commit()
