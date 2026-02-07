import os
import psycopg2

DATABASE_URL = "postgresql://postgres:admin@localhost/ClassBridge_db"

def check():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, name, role FROM students")
        rows = cursor.fetchall()
        print(f"Total Users: {len(rows)}")
        found = False
        for r in rows:
            print(r)
            if r[0] == 'S001':
                found = True
        
        if not found:
            print("\nWARNING: S001 NOT FOUND!")
            
    except Exception as e:
        print(e)
    finally:
        conn.close()

if __name__ == "__main__":
    check()
