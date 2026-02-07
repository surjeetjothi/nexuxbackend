
import psycopg2
import os
import sys

# Try the commented out URL from .env (assuming user wants this one)
# Or we can try to parse it from the file content we just read.
# The previous view_file showed: # DATABASE_URL=postgresql://postgres:admin@localhost/ClassBridge_db

DB_URL = "postgresql://postgres:admin@localhost/ClassBridge_db"

def test_connection():
    try:
        print(f"Attempting to connect to: {DB_URL}")
        conn = psycopg2.connect(DB_URL)
        print("Successfully connected to PostgreSQL!")
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"Postgres Version: {version[0]}")
        conn.close()
        return True
    except psycopg2.OperationalError as e:
        print(f"Connection failed: {e}")
        # check if it's because database doesn't exist
        if 'does not exist' in str(e):
             print("Database 'ClassBridge_db' does not exist. Trying to connect to 'postgres' db to create it.")
             return "CREATE_DB_NEEDED"
        return False
    except Exception as e:
        print(f"An error occurred: {e}")
        return False

if __name__ == "__main__":
    result = test_connection()
    if result == "CREATE_DB_NEEDED":
        sys.exit(2) # Signal to create DB
    elif result is True:
        sys.exit(0) # Success
    else:
        sys.exit(1) # Failure
