import os
import psycopg2

DATABASE_URL = "postgresql://postgres:admin@localhost/ClassBridge_db"

def check_constraints():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT
                tc.constraint_name, 
                tc.table_name, 
                kcu.column_name, 
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name 
            FROM 
                information_schema.table_constraints AS tc 
                JOIN information_schema.key_column_usage AS kcu
                  ON tc.constraint_name = kcu.constraint_name
                  AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage AS ccu
                  ON ccu.constraint_name = tc.constraint_name
                  AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_name='leave_requests';
        """)
        
        constraints = cursor.fetchall()
        if not constraints:
            print("No foreign key constraints found for 'leave_requests'.")
        else:
            print("Foreign Key Constraints for 'leave_requests':")
            for c in constraints:
                print(f"Constraint: {c[0]} | Column: {c[2]} -> References: {c[3]}({c[4]})")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    check_constraints()
