import os
import psycopg2

DATABASE_URL = "postgresql://postgres:admin@localhost/ClassBridge_db"

def check():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, name, grade, role FROM students WHERE grade=1")
        rows = cursor.fetchall()
        print("Grade 1 Students:")
        for r in rows:
            print(r)
            
        cursor.execute("SELECT id, name FROM students WHERE id='parent_g1'")
        p = cursor.fetchone()
        print(f"\nParent g1: {p}")
        
    except Exception as e:
        print(e)
    finally:
        conn.close()

if __name__ == "__main__":
    check()
