import os
import psycopg2

DATABASE_URL = "postgresql://postgres:admin@localhost/ClassBridge_db"

def run():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        # 1. Create Grade 1 Student
        sid = "S_G1"
        cursor.execute("INSERT INTO students (id, name, grade, role, password, school_id, attendance_rate, home_language) VALUES (%s, 'Baby Yoda', 1, 'Student', '123', 1, 100.0, 'English') ON CONFLICT(id) DO UPDATE SET grade=1", (sid,))
        
        # 2. Create Parent
        pid = "parent_g1"
        cursor.execute("INSERT INTO students (id, name, role, password, school_id) VALUES (%s, 'Mandalorian', 'Parent', '123', 1) ON CONFLICT(id) DO NOTHING", (pid,))
        
        # 3. Link Guardian
        cursor.execute("DELETE FROM guardians WHERE email = %s", (pid,))
        cursor.execute("""
            INSERT INTO guardians (student_id, name, relationship, email, phone, is_emergency_contact)
            VALUES (%s, 'Mandalorian', 'Father', %s, '999-999-9999', TRUE)
        """, (sid, pid))

        # 4. Add Backup Code
        cursor.execute("INSERT INTO backup_codes (user_id, code, created_at) VALUES (%s, '123456', NOW()) ON CONFLICT DO NOTHING", (pid,))
        
        conn.commit()
        conn.close()
        print("Created Grade 1 Demo.")
        print("Student: S_G1")
        print("Parent: parent_g1")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    run()
