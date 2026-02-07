
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv("class/.env")
db_url = os.getenv("DATABASE_URL")

try:
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    print("Adding 'acknowledged' column to quizzes table...")
    try:
        cur.execute("ALTER TABLE quizzes ADD COLUMN acknowledged BOOLEAN DEFAULT FALSE")
        conn.commit()
        print("Success.")
    except psycopg2.errors.DuplicateColumn:
        print("Column already exists.")
        conn.rollback()
    except Exception as e:
        print(f"Error adding column: {e}")
        conn.rollback()
    
    conn.close()
except Exception as e:
    print(f"Connection Error: {e}")
