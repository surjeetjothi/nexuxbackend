
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def add_column():
    print(f"Connecting to {DATABASE_URL}")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()
    
    try:
        cur.execute("ALTER TABLE students ADD COLUMN photo_url TEXT DEFAULT NULL")
        print("Successfully added column 'photo_url' to 'students' table.")
    except psycopg2.errors.DuplicateColumn:
        print("Column 'photo_url' already exists.")
    except Exception as e:
        print(f"Error adding column: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    add_column()
