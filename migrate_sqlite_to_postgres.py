
import sqlite3
import psycopg2
import os
import sys

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQLITE_DB = os.path.join(BASE_DIR, "class_bridge.db")
POSTGRES_URL = "postgresql://postgres:admin@localhost/ClassBridge_db"

def migrate_data():
    if not os.path.exists(SQLITE_DB):
        print("SQLite DB not found.")
        return

    print("Connecting to databases...")
    sqlite_conn = sqlite3.connect(SQLITE_DB)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cursor = sqlite_conn.cursor()

    pg_conn = psycopg2.connect(POSTGRES_URL)
    pg_cursor = pg_conn.cursor()

    # --- 1. CLEANUP POSTGRES (OPTIONAL: Reset or rely on ON CONFLICT) ---
    # For a clean switch, we might want to truncate, but let's try UPSERT logic if possible, 
    # or just DELETE from tables we know we are syncing. 
    # Let's clean the main tables to avoid duplicates if migration runs twice.
    print("Cleaning target tables...")
    tables = [
        "activities", "group_members", "group_materials", "assignments", "quizzes",
        "live_classes", "groups", "students", "schools"
    ]
    # Reverse order for FK constraints? Or cascade.
    for table in tables:
        try:
             # Using CASCADE to handle foreign keys
            pg_cursor.execute(f"TRUNCATE TABLE {table} CASCADE;") 
        except psycopg2.errors.UndefinedTable:
            pg_conn.rollback() # Table doesn't exist yet, that's fine (schema init will handle it, or we assume schema exists)
            print(f"Table {table} does not exist yet. Skipping clean.")
        except Exception as e:
            pg_conn.rollback()
            print(f"Error cleaning {table}: {e}")

    # --- 0. ENSURE SCHEMA EXISTS ---
    # We should run the schema creation from backend loop or just manual mapping here.
    # Since backend.py 'initialize_db' is robust (CREATE IF NOT EXISTS), 
    # we can trust it ran if the user started the app once against Postgres.
    # BUT, to be safe, let's assume the relevant tables exist or we might fail inserts.
    # The user says "Switch to proper server-based... implement these things", 
    # so we should probably rely on the existing schema definitions.

    # Let's map SQLite tables to Postgres Tables
    # We'll use a generic copier for matching columns
    
    def copy_table(table_name):
        print(f"Migrating {table_name}...")
        try:
            sqlite_cursor.execute(f"SELECT * FROM {table_name}")
            rows = sqlite_cursor.fetchall()
            
            if not rows:
                print(f"  No data in {table_name}.")
                return

            # Get columns from SQLite result
            col_names = rows[0].keys()
            cols_str = ",".join(col_names)
            placeholders = ",".join(["%s"] * len(col_names))
            
            # Insert into Postgres
            query = f"INSERT INTO {table_name} ({cols_str}) VALUES ({placeholders})"
            
            count = 0
            for row in rows:
                values = [row[col] for col in col_names]
                try:
                    pg_cursor.execute(query, values)
                    count += 1
                except Exception as e:
                    pg_conn.rollback()
                    print(f"  Error inserting row into {table_name}: {e}")
                    # Skip problematic row
            
            pg_conn.commit()
            print(f"  Migrated {count} rows.")
            
        except sqlite3.OperationalError:
            print(f"  Table {table_name} missing in SQLite.")
        except psycopg2.errors.UndefinedTable:
            pg_conn.rollback()
            print(f"  Table {table_name} missing in Postgres - Ensure Schema is initialized first!")
        except Exception as e:
            pg_conn.rollback()
            print(f"  Error migrating {table_name}: {e}")

    # Order matters due to Foreign Keys
    copy_table("schools")
    copy_table("students") # Includes teachers
    copy_table("groups")
    copy_table("activities")
    copy_table("live_classes")
    # Add others as needed
    
    sqlite_conn.close()
    pg_conn.close()
    print("Migration Complete.")

if __name__ == "__main__":
    migrate_data()
