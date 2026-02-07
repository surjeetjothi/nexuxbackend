import os
import psycopg2

DATABASE_URL = "postgresql://postgres:admin@localhost/ClassBridge_db"

def check_users():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, name, role FROM students LIMIT 20")
        users = cursor.fetchall()
        
        print(f"Found {len(users)} users:")
        for u in users:
            print(f"- {u[0]} ({u[1]}) [{u[2]}]")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    check_users()
