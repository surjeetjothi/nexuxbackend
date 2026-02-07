import psycopg2
import os

DB_URL = "postgresql://postgres:admin@localhost/ClassBridge_db"

try:
    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()
    # Check for teacher
    cursor.execute("SELECT id, name, role, password FROM students WHERE id = 'teacher' OR role LIKE '%Teacher%' LIMIT 10")
    rows = cursor.fetchall()
    print("Found Users in Postgres:")
    for row in rows:
        print(row)
    conn.close()
except Exception as e:
    print(f"Error: {e}")
