
import os
import psycopg2
from dotenv import load_dotenv

# Load env from class folder
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "class", ".env")
load_dotenv(dotenv_path=env_path)

db_url = os.getenv("DATABASE_URL")
if not db_url:
    # Fallback or try to read from backend.py's default
    print("No DATABASE_URL found in env, trying default local db if exists")
    db_url = "class_bridge.db" 

print(f"Checking DB: {db_url}")

try:
    if "postgres" in db_url:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'assignments';")
        columns = cur.fetchall()
        print("Columns in assignments table:")
        for col in columns:
            print(f"- {col[0]} ({col[1]})")
        conn.close()
    else:
        import sqlite3
        conn = sqlite3.connect(db_url)
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(assignments);")
        columns = cur.fetchall()
        print("Columns in assignments table (SQLite):")
        for col in columns:
            print(f"- {col[1]} ({col[2]})")
        conn.close()

except Exception as e:
    print(f"Error: {e}")
