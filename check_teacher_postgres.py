import os
import psycopg2
from dotenv import load_dotenv

# Load env from .env in the same directory
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(dotenv_path=env_path)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("Error: DATABASE_URL not found in .env")
    exit(1)

print(f"Connecting to {DATABASE_URL}")

try:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    print("Checking for teachers in Postgres...")
    cursor.execute("SELECT id, name, role, password FROM students WHERE id = 'teacher' OR role LIKE '%Teacher%' LIMIT 10")
    rows = cursor.fetchall()
    
    if not rows:
        print("No teacher users found in Postgres!")
    else:
        print("Found Users in Postgres:")
        for row in rows:
            print(row)
            
    conn.close()
    
except Exception as e:
    print(f"Error: {e}")
