import os
import psycopg2

DATABASE_URL = "postgresql://postgres:admin@localhost/ClassBridge_db"

def check_guardians():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        cursor.execute("SELECT student_id, name, relationship FROM guardians WHERE email = 'parent_g1'")
        rows = cursor.fetchall()
        print(f"Guardians entries for parent_g1: {len(rows)}")
        for r in rows:
            print(f"Linked Student ID: {r[0]} (Guardian Name in Record: {r[1]})")

    except Exception as e:
        print(e)
    finally:
        conn.close()

if __name__ == "__main__":
    check_guardians()
