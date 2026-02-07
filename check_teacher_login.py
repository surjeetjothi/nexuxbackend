# FIXED: Checking noble_nexus.db (SQLite) as used by backend.py
import sqlite3
import os

DB_PATH = "class_bridge.db"

try:
    if not os.path.exists(DB_PATH):
        print(f"Error: {DB_PATH} not found!")
        exit(1)
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Check for teacher
    cursor.execute("SELECT id, name, role, password FROM students WHERE id = 'teacher' OR role LIKE '%Teacher%' LIMIT 10")
    rows = cursor.fetchall()
    print("Found Users in noble_nexus.db:")
    for row in rows:
        print(row)
    conn.close()
except Exception as e:
    print(f"Error: {e}")
