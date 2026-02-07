import os
import psycopg2

DATABASE_URL = "postgresql://postgres:admin@localhost/ClassBridge_db"

def run():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        # 1. Delete Baby Yoda
        print("Deleting Baby Yoda...")
        cursor.execute("DELETE FROM students WHERE id = 'S_G1'")
        cursor.execute("DELETE FROM student_attendance WHERE student_id = 'S_G1'")
        cursor.execute("DELETE FROM guardians WHERE student_id = 'S_G1'")
        
        # 2. Clear messages
        print("Clearing messages...")
        cursor.execute("DELETE FROM messages WHERE receiver_id = 'parent_g1'")
        
        # 3. Link parent_g1 to student_g1_2 (Student 2)
        print("Linking parent_g1 to student_g1_2...")
        # Check if parent_g1 exists
        cursor.execute("SELECT name FROM students WHERE id = 'parent_g1'")
        res = cursor.fetchone()
        if res:
            parent_name = res[0] 
            
            # Insert guardian link (delete old first just in case)
            cursor.execute("DELETE FROM guardians WHERE email = 'parent_g1'")
            cursor.execute("""
                INSERT INTO guardians (student_id, name, relationship, email, phone, is_emergency_contact)
                VALUES (%s, %s, 'Parent', 'parent_g1', '555-0102', TRUE)
            """, ('student_g1_2', parent_name))
        else:
            print("Error: parent_g1 not found!")

        conn.commit()
        conn.close()
        print("Done. Linked to Student 2 (student_g1_2).")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    run()
