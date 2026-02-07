import os
import psycopg2

DATABASE_URL = "postgresql://postgres:admin@localhost/ClassBridge_db"

def check_messages():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        cursor.execute("SELECT to_regclass('public.messages')")
        exists = cursor.fetchone()[0]
        
        if exists:
            print("Table 'messages' exists.")
            cursor.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'messages'")
            cols = cursor.fetchall()
            print("Columns:")
            for c in cols:
                print(f"- {c[0]} ({c[1]})")
        else:
            print("Table 'messages' does NOT exist.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    check_messages()
