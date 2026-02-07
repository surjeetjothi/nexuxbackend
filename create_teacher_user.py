import sqlite3
import os

DB_PATH = "class_bridge.db"

def create_teacher():
    if not os.path.exists(DB_PATH):
        print(f"Error: {DB_PATH} not found!")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        user_id = "teacher"
        # Check if exists
        cursor.execute("SELECT id FROM students WHERE id = ?", (user_id,))
        if cursor.fetchone():
            print(f"User '{user_id}' already exists. Updating password...")
            cursor.execute("UPDATE students SET password = 'teacher', role = 'Teacher' WHERE id = ?", (user_id,))
        else:
            print(f"Creating user '{user_id}'...")
            # Using some defaults for other fields based on schema in backend.py
            cursor.execute("""
                INSERT INTO students (id, name, grade, preferred_subject, attendance_rate, home_language, math_score, science_score, english_language_score, role, school_id, password)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, "Teacher Admin", 0, "All", 100.0, "English", 0, 0, 0, "Teacher", 1, "teacher"))
        
        conn.commit()
        print(f"User '{user_id}' created/updated successfully.")
        
        # Verify
        cursor.execute("SELECT id, name, role, password FROM students WHERE id = ?", (user_id,))
        print("Verification:", cursor.fetchone())
        
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    create_teacher()
