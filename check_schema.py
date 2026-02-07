
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv("class/.env")
db_url = os.getenv("DATABASE_URL")
if not db_url:
    print("No DATABASE_URL found")
    exit(1)

try:
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'quizzes';")
    columns = cur.fetchall()
    print("Columns in quizzes table:")
    for col in columns:
        print(f"- {col[0]} ({col[1]})")
    conn.close()
except Exception as e:
    print(f"Error: {e}")
