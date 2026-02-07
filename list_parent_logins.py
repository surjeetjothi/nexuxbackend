import os
import psycopg2
from tabulate import tabulate # Assuming tabulate is not installed, I'll use simple print or try/except

DATABASE_URL = "postgresql://postgres:admin@localhost/ClassBridge_db"

def list_parents():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        query = """
        SELECT 
            p.id as parent_user_id,
            p.password as parent_password,
            p.name as parent_name,
            s.name as student_name,
            s.id as student_id,
            s.grade as student_grade
        FROM students p
        JOIN guardians g ON g.email = p.id
        JOIN students s ON g.student_id = s.id
        WHERE p.role = 'Parent'
        ORDER BY s.grade ASC, s.name ASC
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        print("\n--- Parent Login Details ---")
        print(f"{'User ID':<20} | {'Password':<10} | {'Student Name':<25} | {'Grade':<5}")
        print("-" * 70)
        
        for r in rows:
            # r: (id, pass, p_name, s_name, s_id, grade)
            print(f"{r[0]:<20} | {r[1]:<10} | {r[3]:<25} | {r[5]:<5}")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    list_parents()
