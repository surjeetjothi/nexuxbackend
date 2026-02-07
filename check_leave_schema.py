import os
import psycopg2

DATABASE_URL = "postgresql://postgres:admin@localhost/ClassBridge_db"

def check_schema():
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    # Check if leave_requests table exists
    cursor.execute("SELECT to_regclass('public.leave_requests')")
    exists = cursor.fetchone()[0]
    
    if exists:
        print("Table 'leave_requests' exists.")
        # Get columns
        cursor.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'leave_requests'")
        cols = cursor.fetchall()
        print("Columns:")
        for c in cols:
            print(f"- {c[0]} ({c[1]})")
    else:
        print("Table 'leave_requests' does NOT exist.")

    conn.close()

if __name__ == "__main__":
    check_schema()
