import psycopg2

DATABASE_URL = "postgresql://postgres:admin@localhost/ClassBridge_db"

def restore():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        # Check if exists
        cursor.execute("SELECT id FROM students WHERE id = 'S001'")
        if cursor.fetchone():
            print("S001 already exists.")
        else:
            print("Restoring S001...")
            # Insert S001 (standard demo student)
            cursor.execute("""
                INSERT INTO students (id, name, grade, preferred_subject, role, school_id, password)
                VALUES ('S001', 'Alice Smith (Demo)', 10, 'Maths', 'Student', 1, '123')
            """)
            conn.commit()
            print("Done.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'conn' in locals(): conn.close()

if __name__ == "__main__":
    restore()
