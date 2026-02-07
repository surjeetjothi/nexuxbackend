
import sys
import os
# Add the current directory to sys.path so we can import backend
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend import get_db_connection, initialize_db

def debug_students():
    print("--- DEBUGGING DATABASE CONNECTION ---")
    try:
        conn = get_db_connection()
        print(f"Connection Type: {type(conn)}")
        
        # Check students
        cursor = conn.cursor()
        
        # Count students
        count = cursor.execute("SELECT COUNT(*) as c FROM students").fetchone()
        if hasattr(count, 'keys'): # dict-like (sqlite/postgres dictcursor)
             total = count['c'] if 'c' in count else count[0]
        else:
             total = count[0]
             
        print(f"Total Students in DB: {total}")
        
        # List first 10 students with grade
        print("\n--- Students by Grade Count ---")
        counts = cursor.execute("SELECT grade, COUNT(*) as c FROM students GROUP BY grade ORDER BY grade").fetchall()
        for row in counts:
             g = row['grade'] if hasattr(row, 'keys') else row[0]
             c = row['c'] if hasattr(row, 'keys') else row[1]
             print(f"Grade {g}: {c} students")
        
        print("\n--- Students in Grade 10 ---")
        g10 = cursor.execute("SELECT id, name, grade FROM students WHERE grade = '10' OR grade = 10").fetchall()
        if not g10:
             print("No students found in Grade 10.")
        for r in g10:
             print(r)

        conn.close()
        
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    debug_students()
