
import os
import sqlite3
import random
from datetime import datetime, timedelta

# Explicitly use the combined database
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "class_bridge.db")

def seed_data():
    if not os.path.exists(DB_PATH):
        print(f"Error: {DB_PATH} not found.")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 1. Get all students
        cursor.execute("SELECT id FROM students WHERE role = 'Student' OR role is NULL")
        students = cursor.fetchall()
        
        print(f"Seeding data for {len(students)} students in {DB_PATH}...")
        
        topics = ["Math Quiz", "Science Lab", "History Essay", "English Reading", "Physics Test"]
        difficulties = ["Easy", "Medium", "Hard"]
        
        for (student_id,) in students:
            # A. Update Static Scores (Math, Science, English)
            # Generate random scores between 40 and 100
            math = random.randint(40, 99)
            science = random.randint(40, 99)
            english = random.randint(40, 99)
            
            cursor.execute("""
                UPDATE students 
                SET math_score = ?, science_score = ?, english_language_score = ?
                WHERE id = ?
            """, (math, science, english, student_id))

            # B. Seed Activities (History)
            # Check existing count
            cursor.execute("SELECT COUNT(*) FROM activities WHERE student_id = ?", (student_id,))
            count = cursor.fetchone()[0]
            
            # Ensure every student has at least 5 activities
            needed = 5 - count
            if needed > 0:
                print(f"  Adding {needed} activities for {student_id}...")
                for _ in range(needed):
                    topic = random.choice(topics)
                    difficulty = random.choice(difficulties)
                    score = random.randint(50, 100)
                    time_spent = random.randint(15, 60)
                    days_ago = random.randint(0, 30)
                    date_str = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
                    
                    cursor.execute("""
                        INSERT INTO activities (student_id, date, topic, difficulty, score, time_spent_min)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (student_id, date_str, topic, difficulty, score, time_spent))
                
        conn.commit()
        conn.close()
        print("Success! Updated subject scores and seeded activities for all students.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    seed_data()
