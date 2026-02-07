import os
import psycopg2

DATABASE_URL = "postgresql://postgres:admin@localhost/ClassBridge_db"

def create_all_parents():
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    # Get all students who are NOT parents/teachers/admins
    cursor.execute("SELECT id, name, grade FROM students WHERE role = 'Student' ORDER BY grade, name")
    students = cursor.fetchall()
    
    print("\nProcessing Parent Accounts...")
    print(f"{'Student Name':<30} | {'Grade':<5} | {'Parent User ID':<25} | {'Password':<10}")
    print("-" * 80)
    
    for s in students:
        sid, sname, grade = s
        
        # Check if guardian already exists with a valid user account
        cursor.execute("SELECT email FROM guardians WHERE student_id = %s", (sid,))
        guardian = cursor.fetchone()
        
        parent_id = None
        
        if guardian:
            email = guardian[0]
            # Check if this email is a valid user ID in students table
            cursor.execute("SELECT id FROM students WHERE id = %s AND role = 'Parent'", (email,))
            user = cursor.fetchone()
            if user:
                parent_id = user[0]
        
        # If no valid parent account found, create one
        if not parent_id:
            # Generate Parent ID, cleaning special characters if needed
            clean_sid = sid.replace(" ", "").lower()
            parent_id = f"p_{clean_sid}" # generic parent id
            
            pname = f"Parent of {sname}"
            
            # Create Parent User (upsert not needed if we check, but good for safety)
            cursor.execute("DELETE FROM students WHERE id = %s", (parent_id,))
            cursor.execute("""
                INSERT INTO students (id, name, role, password, school_id)
                VALUES (%s, %s, 'Parent', '123', 1)
            """, (parent_id, pname))
            
            # Link Guardian (overwrite existing non-user guardian if any)
            cursor.execute("DELETE FROM guardians WHERE student_id = %s", (sid,))
            cursor.execute("""
                INSERT INTO guardians (student_id, name, relationship, email, phone, is_emergency_contact)
                VALUES (%s, %s, 'Parent', %s, '555-0000', TRUE)
            """, (sid, pname, parent_id))
            
            # add backup code
            cursor.execute("INSERT INTO backup_codes (user_id, code, created_at) VALUES (%s, '123456', NOW())", (parent_id,))
            conn.commit()

        print(f"{sname:<30} | {grade:<5} | {parent_id:<25} | 123")
        
    conn.close()

if __name__ == "__main__":
    create_all_parents()
