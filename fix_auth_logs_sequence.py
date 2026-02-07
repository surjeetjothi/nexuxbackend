import os
import psycopg2
from dotenv import load_dotenv

# Load env from .env in the same directory
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(dotenv_path=env_path)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("Error: DATABASE_URL not found in .env")
    exit(1)

print(f"Connecting to {DATABASE_URL}")

try:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    # 1. Get current max id
    cursor.execute("SELECT MAX(id) FROM auth_logs")
    result = cursor.fetchone()
    if result:
        max_id = result[0]
    else:
        max_id = 0
    
    print(f"Current max id in auth_logs: {max_id}")
    
    if max_id is None:
        max_id = 0
    
    # 2. Reset sequence
    # Try to find the sequence name dynamically
    cursor.execute("SELECT pg_get_serial_sequence('auth_logs', 'id')")
    seq_name_row = cursor.fetchone()
    
    if seq_name_row and seq_name_row[0]:
        actual_seq = seq_name_row[0]
        print(f"Found actual sequence name: {actual_seq}")
        
        # Reset safe
        new_val = max_id + 1
        cursor.execute(f"SELECT setval('{actual_seq}', %s, false)", (new_val,)) # false means next val will be new_val
        # Actually standard is true, so next is new_val + 1? No.
        # setval(seq, 100, true) -> nextval is 101.
        # setval(seq, 100, false) -> nextval is 100.
        # We want nextval to be max_id + 1. So we can do setval(seq, max_id, true).
        
        cursor.execute(f"SELECT setval('{actual_seq}', %s, true)", (max_id,))
        print(f"Sequence {actual_seq} reset to {max_id} (next will be {max_id+1})")
        
    else:
        # Fallback if allowed
        print("Could not find sequence name via pg_get_serial_sequence. Trying 'auth_logs_id_seq'...")
        try:
             cursor.execute(f"SELECT setval('auth_logs_id_seq', %s, true)", (max_id,))
             print(f"Sequence auth_logs_id_seq reset to {max_id}")
        except Exception as e:
            print(f"Failed fallback: {e}")

    conn.commit()
    conn.close()
    print("Done.")
    
except Exception as e:
    print(f"Error: {e}")
