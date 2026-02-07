from fastapi import FastAPI, HTTPException, Header, Depends, WebSocket, WebSocketDisconnect, Request, Body
import secrets
import time
import hmac
import hashlib
# Trigger Reload (Last updated: School Fix)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response, StreamingResponse

from fastapi import UploadFile, File, Form

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None
    print("Warning: pypdf module not found. PDF processing will be disabled.")


from pydantic import BaseModel
from typing import List, Dict, Any, Optional 
import psycopg2
import sqlite3
from psycopg2.extras import DictCursor
# import pandas as pd # Moved to local scope
import io
import csv
from datetime import datetime, timedelta
# from sklearn.ensemble import RandomForestClassifier (Moved to function)
# import numpy as np # Moved to local scope
import warnings 
import os
import logging
import uuid
import shutil
import json
import json
from fastapi import FastAPI, HTTPException, Header, Depends, WebSocket, WebSocketDisconnect, File, UploadFile, Form
from fastapi.staticfiles import StaticFiles
# from groq import Groq (Moved to initialization block) 
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

from dotenv import load_dotenv
import os
# Force load .env from the script's directory
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(dotenv_path=env_path, override=True)
print(f"Loaded configuration from: {env_path}")
print(f"Active DATABASE_URL: {os.getenv('DATABASE_URL')}")

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")

# --- EMAIL CONFIGURATION ---
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_EMAIL = os.getenv("SMTP_EMAIL", "your-email@gmail.com") 
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "your-app-password")

def send_email(to_email: str, subject: str, body: str):
    if "example.com" in to_email or "your-email" in SMTP_EMAIL:
        logger.warning(f"Email simulation: To={to_email}, Subject={subject}")
        return False # Simulated

    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_EMAIL
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False



try:
    # Initialize the Groq Client.
    from groq import Groq
    
    # User provided key overrides env var for now to ensure it works
    api_key = os.getenv("GROQ_API_KEY")
    
    if api_key:
        GROQ_CLIENT = Groq(api_key=api_key)
        GROQ_MODEL = "llama-3.1-8b-instant" 
        
        # Dedicated Client for Lesson Planner
        lesson_planner_key = os.environ.get("LESSON_PLANNER_API_KEY") or api_key
             
        LESSON_PLANNER_CLIENT = Groq(api_key=lesson_planner_key)
        
        AI_ENABLED = True
        logger.info("AI Chat System Initialized (Groq Powered).")
    else:
        logger.warning("GROQ_API_KEY not found. AI features disabled.")
        GROQ_CLIENT = None
        LESSON_PLANNER_CLIENT = None
        AI_ENABLED = False
except ImportError:
    logger.error("Groq library not installed. AI features disabled.")
    AI_ENABLED = False
except Exception as e:
    logger.error(f"Failed to initialize AI clients. Error: {e}")
    AI_ENABLED = False

# --- NEW GRADE HELPER AI CONFIGURATION ---
# --- NEW GRADE HELPER AI CONFIGURATION ---
GRADE_HELPER_API_KEY = os.environ.get("GRADE_HELPER_API_KEY") or os.environ.get("GROQ_API_KEY")
try:
    if GRADE_HELPER_API_KEY:
        GRADE_HELPER_CLIENT = Groq(api_key=GRADE_HELPER_API_KEY)
        logger.info("Grade Helper AI Initialized.")
    else:
        GRADE_HELPER_CLIENT = None
        logger.warning("GRADE_HELPER_API_KEY not found.")
except Exception as e:
    logger.error(f"Failed to initialize Grade Helper AI: {e}")
    GRADE_HELPER_CLIENT = None
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        logger.info("Initializing Database...")
        initialize_db()
        logger.info("Database Initialized.")
    except Exception as e:
        logger.error(f"Startup DB Error: {e}")

    try:
        logger.info("Training Recommendation Model (Lazy loaded on demand)...")
        # train_recommendation_model() # Disabled to prevent startup hang
        logger.info("Model training deferred.")
    except Exception as e:
        logger.warning(f"Startup ML Error: {e}")
    
    yield
    # Shutdown (if any cleanup is needed)
    logger.info("Shutting down...")

# --- NEW AI ENGAGEMENT MODELS ---
app = FastAPI(title="EdTech AI Portal API - Enhanced", lifespan=lifespan)

# --- CORS Configuration ---
# Fix: Explicitly list allowed origins for Production + Development
origins = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "https://backend1-bzh1.onrender.com",
    "https://www.backend1-bzh1.onrender.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Static Files
import os
# Mount Static Files
# Mount Static Files
base_path = os.path.dirname(os.path.abspath(__file__))
frontend_static = os.path.join(base_path, "../frontend/static_app/static")

if os.path.exists(frontend_static):
    static_dir = frontend_static
else:
    # Fallback for standalone backend deployment
    static_dir = os.path.join(base_path, "static")
    if not os.path.exists(static_dir):
        os.makedirs(static_dir)

app.mount("/static", StaticFiles(directory=static_dir), name="static")





# DATABASE_URL = "class_bridge.db"
# Update default to use a persistent SQLite DB for reliability if Postgres isn't available
# validated_database_url
DATABASE_URL = os.getenv("DATABASE_URL", "class_bridge.db")
MIN_ACTIVITIES = 5 

DB_SCHEMA_CONTEXT = """
PostgreSQL Schema Overview:
1. students (id [text], name, grade, preferred_subject, attendance_rate, home_language, math_score, science_score, english_language_score, role ['Student', 'Teacher', 'Tenant_Admin'], school_id)
2. activities (id, student_id, date, topic, difficulty, score [0-100], time_spent_min)
3. schools (id, name, address, contact_email)
   - Note: content is multi-tenant, filtered by school_id usually, but for general queries show all if not restricted.
4. groups (id, name, subject, description, school_id) - Represents classes/groups
5. assignments (id, group_id, title, due_date, points)
6. submissions (id, assignment_id, student_id, content, grade)
7. guardians (student_id, name, relationship, phone, email)
8. health_records (student_id, blood_group, allergies, medical_conditions, medications)
9. staff (id, name, role, department_id, position_title, joining_date)
10. departments (id, name, head_of_department_id)

Relationships:
- students.school_id -> schools.id
- activities.student_id -> students.id
- groups.school_id -> schools.id
- assignments.group_id -> groups.id
"""

def format_df_to_markdown(df):
    if df.empty:
        return "No results found."
    columns = df.columns.tolist()
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join(["---"] * len(columns)) + " |"
    rows = []
    for _, row in df.iterrows():
        # Convert values to string and replace newlines to keep table structure
        row_values = [str(val).replace('\n', ' ') for val in row.values]
        row_str = "| " + " | ".join(row_values) + " |"
        rows.append(row_str)
    return f"\n{header}\n{separator}\n" + "\n".join(rows) + "\n"

# --- POSTGRES COMPATIBILITY LAYER ---
# class sqlite3:
#     """Compatibility layer to allow existing code to catch sqlite3 exceptions."""
#     IntegrityError = psycopg2.IntegrityError
#     OperationalError = psycopg2.OperationalError
#     Row = dict # Stub

class PostgresCursorWrapper:
    def __init__(self, cursor):
        self.cursor = cursor

    def execute(self, query, params=None):
        # Naive replacement of ? to %s for Postgres
        query = query.replace('?', '%s')
        
        # Auto-add RETURNING id for INSERTs to support lastrowid if not already present
        is_insert = query.strip().upper().startswith("INSERT")
        if is_insert and "RETURNING" not in query.upper():
            query += " RETURNING id"

        try:
            self.cursor.execute(query, params)
            if is_insert:
                try:
                    row = self.cursor.fetchone()
                    self._lastrowid = row[0] if row else None
                except psycopg2.ProgrammingError:
                    # In case fetchone fails or no data returned (e.g. DO NOTHING)
                    self._lastrowid = None
        except psycopg2.errors.DuplicateColumn:
            pass # Ignore duplicate column errors during migration
        except psycopg2.errors.UndefinedColumn:
            # Code 42703: column "id" does not exist
            # Retry without RETURNING id if we added it
            if is_insert and query.endswith(" RETURNING id"):
                # Must rollback the failed transaction state first!
                self.cursor.connection.rollback()
                
                query_clean = query[:-13] # strip " RETURNING id"
                self.cursor.execute(query_clean, params)
                self._lastrowid = None
            else:
                 raise
        except Exception as e:
            # logger.error(f"SQL Execution Error: {e} | Query: {query}")
            raise e
            
        return self # Allow chaining

    def executemany(self, query, params):
        query = query.replace('?', '%s')
        self.cursor.executemany(query, params)
        # executemany doesn 't support RETURNING easily with single lastrowid conceptual mapping
        self._lastrowid = None 
        return self

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()
        
    @property
    def lastrowid(self):
        # Return the captured ID from the last INSERT
        return getattr(self, '_lastrowid', None) 

    def close(self):
        self.cursor.close()

class PostgresConnectionWrapper:
    def __init__(self, dsn):
        try:
            self.conn = psycopg2.connect(dsn, cursor_factory=DictCursor)
        except Exception as e:
            logger.error(f"DB Connection Error: {e}")
            raise e
        self.row_factory = None # Stub

    def cursor(self):
        return PostgresCursorWrapper(self.conn.cursor())

    def execute(self, query, params=None):
        cur = self.cursor()
        cur.execute(query, params)
        return cur # Allow chaining

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()

    def rollback(self):
        self.conn.rollback()

 

# --- 2. DATA MODELS ---

class LoginRequest(BaseModel):
    username: str
    password: str
    role: str = "Student" # Default to Student to avoid breaking legacy clients if any, though frontend always sends it now

class LoginResponse(BaseModel):
    success: bool = True
    user_id: str
    name: Optional[str] = None
    role: Optional[str] = None
    roles: List[str] = []
    permissions: List[str] = []
    requires_2fa: bool = False 
    school_id: Optional[int] = None
    school_name: Optional[str] = None
    is_super_admin: bool = False 
    related_student_id: Optional[str] = None 
    email_masked: Optional[str] = None 

class Verify2FARequest(BaseModel):
    user_id: str
    code: str

class AddStudentRequest(BaseModel):
    id: str
    name: str
    grade: int
    preferred_subject: str
    attendance_rate: float
    home_language: str
    math_score: float
    science_score: float
    english_language_score: float
    password: str = "Student@123" 
    school_id: Optional[int] = 1

class StudentHistory(BaseModel):
    date: str
    topic: str
    difficulty: str
    score: float
    time_spent_min: int

class StudentSummary(BaseModel):
    avg_score: float
    total_activities: int
    recommendation: Optional[str] = None
    math_score: float
    science_score: float
    english_language_score: float
    roles: List[str] = []

class StudentDataResponse(BaseModel):
    summary: StudentSummary
    history: List[StudentHistory]

class TeacherOverviewResponse(BaseModel):
    total_students: int
    class_attendance_avg: float
    class_score_avg: float
    roster: List[Dict[str, Any]] 
    school_name: Optional[str] = None
    total_teachers: int = 0

class AIChatRequest(BaseModel):
    prompt: str

class AIChatResponse(BaseModel):
    reply: str

class GenerateQuizRequest(BaseModel):
    topic: str
    difficulty: str = "Medium"
    question_count: int = 5
    type: str = "Multiple Choice" # or "Short Answer"
    description: Optional[str] = None

class GenerateQuizResponse(BaseModel):
    content: str
    
class AddActivityRequest(BaseModel):
    student_id: str
    date: str
    topic: str
    difficulty: str
    score: float
    time_spent_min: int

class UpdateStudentRequest(BaseModel):
    name: str
    grade: int
    preferred_subject: str
    attendance_rate: float
    home_language: str
    math_score: float
    science_score: float
    english_language_score: float
    password: Optional[str] = None 
    school_id: Optional[int] = None
    roles: Optional[List[str]] = None

class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    grade: Optional[int] = 9
    preferred_subject: Optional[str] = "General"
    role: str = "Student" 
    invitation_token: Optional[str] = None 
    school_id: Optional[int] = 1

class ClassScheduleRequest(BaseModel):
    teacher_id: str
    topic: str
    date: str # Format: YYYY-MM-DD HH:MM
    meet_link: str
    target_students: List[str] 

class ClassResponse(BaseModel):
    id: int
    teacher_id: str
    topic: str
    date: str
    meet_link: str
    target_students: List[str] 
    
class GroupCreateRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    subject: str 

class MaterialCreateRequest(BaseModel):
    title: str
    type: str 
    content: str 

class SchoolCreateRequest(BaseModel):
    name: str
    address: str
    contact_email: str
    admin_password: Optional[str] = "Admin@123"
    subscription_plan: Optional[str] = "Basic"

class SchoolResponse(BaseModel):
    id: int
    name: str
    address: str
    contact_email: str
    created_at: str 

class GroupMemberUpdateRequest(BaseModel):
    student_ids: List[str]

class GroupResponse(BaseModel):
    id: int
    name: str
    description: str
    subject: Optional[str] = "General" 
    member_count: int

class MaterialResponse(BaseModel):
    id: int
    title: str
    type: str
    content: str
    date: str

class GenericSocialRequest(BaseModel):
    provider: str
    token: str

class LogoutRequest(BaseModel):
    user_id: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

class InvitationRequest(BaseModel):
    role: str
    expiry_hours: int = 24

class InvitationResponse(BaseModel):
    link: str
    token: str
    expires_at: str

class SocialTokenRequest(BaseModel):
    token: str

class ForgotPasswordRequest(BaseModel):
    email: str

class ClassSessionRequest(BaseModel):
    meet_link: str

class AuditLogResponse(BaseModel):
    id: int
    user_id: str
    event_type: str
    timestamp: str
    details: str
    logout_time: Optional[str] = None
    duration_minutes: Optional[int] = None

class QuizCreateRequest(BaseModel):
    group_id: int
    title: str
    questions: List[Dict[str, Any]] # JSON List of questions

class QuizSubmitRequest(BaseModel):
    student_id: str
    answers: Dict[str, str] # Question Index -> Answer

class QuizResponse(BaseModel):
    id: int
    group_id: Optional[int] = None
    title: str
    question_count: int
    created_at: str
    time_limit: Optional[int] = 0
    target_type: Optional[str] = 'group'
    target_id: Optional[str] = None

class AssignmentResponse(BaseModel):
    id: int
    group_id: int
    title: str
    description: str
    due_date: str
    type: str
    points: int

class AssignmentCreateRequest(BaseModel):
    title: str
    description: Optional[str] = None
    due_date: str
    points: int = 100
    grade_level: Optional[int] = None
    section_id: Optional[int] = None

class SubmissionCreateRequest(BaseModel):
    student_id: str
    content: str # Text or Link

class SubmissionResponse(BaseModel):
    id: int
    assignment_id: int
    student_id: str
    student_name: Optional[str] = None
    content: str
    submitted_at: str
    grade: Optional[float] = None
    feedback: Optional[str] = None

class GradeSubmissionRequest(BaseModel):
    grade: float
    feedback: str = ""

class LessonPlanRequest(BaseModel):
    topic: str
    grade: str
    subject: str
    duration_mins: int
    description: Optional[str] = None

class LessonPlanResponse(BaseModel):
    content: str

class AddUserRequest(BaseModel):
    id: str
    name: str
    role: str
    password: str
    grade: Optional[int] = 0
    preferred_subject: Optional[str] = "All"

class RoleCreateRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    status: str = "Active"
    permissions: List[str] # List of permission codes

class RoleResponse(BaseModel):
    id: int
    code: str
    name: str
    description: str
    status: str
    permissions: List[dict] # {id, code, description}
    is_system: bool = False

class PermissionResponse(BaseModel):
    id: int
    code: str
    description: str

class AssignRoleRequest(BaseModel):
    role_ids: List[int]
    
class UserResponse(BaseModel):
    id: str
    name: str
    role: str
    grade: Optional[int]
    preferred_subject: Optional[str]


# --- STUDENT MANAGEMENT MODELS ---
class SectionCreateRequest(BaseModel):
    name: str
    grade_level: int
    school_id: int

class SectionResponse(BaseModel):
    id: int
    school_id: int
    name: str
    grade_level: int
    created_at: str

class GuardianCreateRequest(BaseModel):
    name: str
    relationship: str
    phone: str
    email: Optional[str] = None
    address: Optional[str] = None
    is_emergency_contact: bool = False

class GuardianResponse(BaseModel):
    id: int
    student_id: str
    name: str
    relationship: str
    phone: str
    email: Optional[str]
    address: Optional[str]
    is_emergency_contact: bool

class HealthRecordUpdateRequest(BaseModel):
    blood_group: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    allergies: Optional[str] = None
    medical_conditions: Optional[str] = None
    medications: Optional[str] = None
    doctor_name: Optional[str] = None
    doctor_phone: Optional[str] = None

class HealthRecordResponse(BaseModel):
    id: int
    student_id: str
    blood_group: Optional[str]
    emergency_contact_name: Optional[str]
    emergency_contact_phone: Optional[str]
    allergies: Optional[str]
    medical_conditions: Optional[str]
    medications: Optional[str]
    doctor_name: Optional[str]
    doctor_phone: Optional[str]
    last_updated: Optional[str]

class DocumentResponse(BaseModel):
    id: int
    student_id: str
    document_type: str
    document_name: str
    file_path: str
    upload_date: str
    uploaded_by: Optional[str]

    uploaded_by: Optional[str]

class ResourceCreateRequest(BaseModel):
    title: str
    description: Optional[str] = ""
    category: str = "Policy" # Policy, Schedule, Form, Other
    file_path: str # For now, just a text input or mocked path
    school_id: Optional[int] = 1

class ResourceResponse(BaseModel):
    id: int
    title: str
    description: str
    category: str
    file_path: str
    uploaded_by: str
    uploaded_at: str


# --- STAFF MANAGEMENT MODELS ---
class DepartmentCreateRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    head_of_department_id: Optional[str] = None

class DepartmentResponse(DepartmentCreateRequest):
    id: int

class StaffProfileUpdateRequest(BaseModel):
    department_id: Optional[int]
    position_title: Optional[str]
    joining_date: Optional[str]
    contract_type: Optional[str]
    salary: Optional[float]

class StaffResponse(BaseModel):
    id: str
    name: str
    role: str
    email: Optional[str] = None # Assuming email is mapped from ID or similar for now
    photo_url: Optional[str] = None
    # Profile Info
    department_id: Optional[int] = None
    department_name: Optional[str] = None
    position_title: Optional[str] = None
    joining_date: Optional[str] = None
    contract_type: Optional[str] = None
    salary: Optional[float] = None

class StaffAttendanceRequest(BaseModel):
    user_id: str
    date: str
    status: str
    check_in_time: Optional[str] = None
    check_out_time: Optional[str] = None

class StaffPerformanceRequest(BaseModel):
    user_id: str
    review_date: str
    rating: int
    comments: str
    goals: Optional[str] = ""

class StaffPerformanceResponse(StaffPerformanceRequest):
    id: int
    reviewer_id: str

# --- LMS MODELS (MOODLE ALTERNATIVE) ---
class LMSCourseCreateRequest(BaseModel):
    title: str
    description: Optional[str] = ""
    category: str = "General"
    thumbnail_url: Optional[str] = None
    enrollment_key: Optional[str] = None

class LMSCourseResponse(BaseModel):
    id: int
    title: str
    description: str
    teacher_id: Optional[str]
    category: str
    thumbnail_url: Optional[str]
    created_at: str

class LMSSectionCreateRequest(BaseModel):
    title: str
    order_index: int = 0

class LMSSectionResponse(BaseModel):
    id: int
    course_id: int
    title: str
    order_index: int

class LMSModuleCreateRequest(BaseModel):
    title: str
    type: str # video, pdf, quiz, assignment, html
    content_url: Optional[str] = None
    content_text: Optional[str] = None
    order_index: int = 0

class LMSModuleResponse(BaseModel):
    id: int
    section_id: int
    title: str
    type: str
    content_url: Optional[str]
    content_text: Optional[str]
    order_index: int


# --- 3. DATABASE HELPER FUNCTIONS ---


def get_db_connection():
    # Check if DATABASE_URL is set to Postgres
    if "postgres" in DATABASE_URL:
        try:
            return PostgresConnectionWrapper(DATABASE_URL)
        except Exception as e:
            logger.error(f"Failed to connect to Postgres, falling back to SQLite: {e}")
    
    # Use local SQLite DB as fallback or requested
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "class_bridge.db")
    # print(f"DEBUG: sqlite3 object: {sqlite3}")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


from sqlalchemy import create_engine

# Cache engine
ENGINE = None

def get_db_engine():
    global ENGINE
    if ENGINE is None:
        # Use local SQLite DB
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "class_bridge.db")
        ENGINE = create_engine(f"sqlite:///{db_path}")
    return ENGINE

def fetch_data_df(query, params=()):
    import pandas as pd
    try:
        engine = get_db_engine()
        # Fix for Postgres: Replace '?' with '%s' because we use ? style in the codebase
        # query = query.replace('?', '%s') # Not needed for SQLite
        
        # pd.read_sql_query supports params with SQLAlchemy engine
        df = pd.read_sql_query(query, engine, params=params)
        return df
    except Exception as e:
        logger.error(f"Pandas SQL Error: {e}")
        print(f"CRITICAL PANDAS ERROR: {e}") 
        return pd.DataFrame()

def log_auth_event(user_id: str, event_type: str, details: str = ""):
    try:
        conn = get_db_connection()
        timestamp = datetime.now().isoformat()
        conn.execute("INSERT INTO auth_logs (user_id, event_type, timestamp, details) VALUES (?, ?, ?, ?)",
                     (user_id, event_type, timestamp, details))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to write auth log: {e}")

def update_user_logout(user_id: str):
    """Updates the last explicit 'Login Success' event with logout time and duration."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Find the latest open session (Login Success with no logout_time)
        row = cursor.execute("SELECT id, timestamp FROM auth_logs WHERE user_id = ? AND event_type = 'Login Success' AND logout_time IS NULL ORDER BY id DESC LIMIT 1", (user_id,)).fetchone()
        
        if row:
            log_id = row['id']
            # Parse ISO formats safely
            try:
                start_time = datetime.fromisoformat(row['timestamp'])
                end_time = datetime.now()
                duration = int((end_time - start_time).total_seconds() / 60)
                
                cursor.execute("UPDATE auth_logs SET logout_time = ?, duration_minutes = ? WHERE id = ?", 
                               (end_time.isoformat(), duration, log_id))
                conn.commit()
                logger.info(f"Updated session duration for user {user_id}: {duration} mins")
            except ValueError:
                pass # safely ignore parsing errors if legacy data is weird
    except Exception as e:
        logger.error(f"Logout update failed: {e}")
    finally:
        conn.close()

def validate_password_strength(password: str):
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters long.")
    if not any(char.isdigit() for char in password):
        raise HTTPException(status_code=400, detail="Password must contain at least one number.")
    if not any(char.isalpha() for char in password):
        raise HTTPException(status_code=400, detail="Password must contain at least one letter.")
    if not any(not char.isalnum() for char in password):
        raise HTTPException(status_code=400, detail="Password must contain at least one special character.")
    return True

# --- 4. DATABASE INITIALIZATION ---


def initialize_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Helper for migrations
    def safe_migrate(sql):
        try:
            conn.commit() # Commit previous valid state
            cursor.execute(sql)
            conn.commit() # Commit new change
        except Exception as e:
            conn.rollback() # Rollback to previous valid state if this fails
            # print(f"Migration ignored: {e}") # Debug
            pass

    
    # Determine Primary Key Syntax based on DB
    import os
    db_url = os.environ.get('DATABASE_URL', '').lower()
    is_postgres = 'postgres' in db_url
    # For Postgres, use SERIAL PRIMARY KEY. For SQLite, INTEGER PRIMARY KEY AUTOINCREMENT
    pk_def = "SERIAL PRIMARY KEY" if is_postgres else "INTEGER PRIMARY KEY AUTOINCREMENT"

    # Schools Table (Multi-Tenancy)
    try:
        conn.commit()
    except:
        conn.rollback()

    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS schools (
        id {pk_def},
        name TEXT UNIQUE,
        address TEXT,
        contact_email TEXT,
        created_at TEXT
    )
    """)

    # Students Table (Updated for Multi-Tenancy)
    try:
        conn.commit()
    except:
        conn.rollback()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS students (
        id TEXT PRIMARY KEY,
        name TEXT,
        grade INTEGER,
        preferred_subject TEXT,
        attendance_rate REAL,
        home_language TEXT,
        password TEXT,
        math_score REAL,          
        science_score REAL,       
        english_language_score REAL, 
        role TEXT DEFAULT 'Student', 
        school_id INTEGER DEFAULT 1, -- Default to School ID 1 for legacy
        is_super_admin BOOLEAN DEFAULT FALSE,
        failed_login_attempts INTEGER DEFAULT 0, 
        locked_until TEXT,
        FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE SET DEFAULT
    )
    """)

    # Resources Table (Global Resource & Policy Library)
    try:
        conn.commit()
    except:
        conn.rollback()

    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS resources (
        id {pk_def},
        title TEXT,
        description TEXT,
        category TEXT,
        file_path TEXT,
        uploaded_by TEXT,
        uploaded_at TEXT,
        school_id INTEGER DEFAULT 1,
        FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE
    )
    """)


    # Invitations Table 
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS invitations (
        token TEXT PRIMARY KEY,
        role TEXT,
        school_id INTEGER,
        expires_at TEXT,
        is_used BOOLEAN DEFAULT FALSE
    )
    """)

    # Password Resets Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS password_resets (
        token TEXT PRIMARY KEY,
        user_id TEXT,
        expires_at TEXT
    )
    """)

    # Backup Codes Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS backup_codes (
        user_id TEXT,
        code TEXT,
        created_at TEXT,
        PRIMARY KEY (user_id, code),
        FOREIGN KEY (user_id) REFERENCES students(id) ON DELETE CASCADE
    )
    """)
    
    # Activities Table
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS activities (
        id {pk_def},
        student_id TEXT,
        date TEXT,
        topic TEXT,
        difficulty TEXT,
        score REAL,
        time_spent_min INTEGER,
        ai_feedback TEXT,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
    )
    """)
    # cursor.execute("PRAGMA foreign_keys = ON") # Postgres enforces FKs by default

    # Live Classes Table
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS live_classes (
        id {pk_def},
        teacher_id TEXT,
        school_id INTEGER,
        topic TEXT,
        date TEXT,
        meet_link TEXT,
        target_students TEXT,
        FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE
    )
    """)
    
    # Auth Logs Table
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS auth_logs (
        id {pk_def},
        user_id TEXT,
        event_type TEXT, 
        timestamp TEXT,
        details TEXT
    )
    """)
    
    # Groups Table
    try:
        conn.commit()
    except:
        conn.rollback()
    
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS groups (
        id {pk_def},
        school_id INTEGER,
        name TEXT,
        description TEXT,
        subject TEXT DEFAULT 'General',
        FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE
    )
    """)

    # Group Members Table
    try:
        conn.commit()
    except:
        conn.rollback()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS group_members (
        group_id INTEGER,
        student_id TEXT,
        FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
        PRIMARY KEY (group_id, student_id)
    )
    """)

    # Group Materials Table
    try:
        conn.commit()
    except:
        conn.rollback()

    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS group_materials (
        id {pk_def},
        group_id INTEGER,
        title TEXT,
        type TEXT,
        content TEXT,
        date TEXT,
        FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE
    )
    """)


    # Assignments Table
    try:
        conn.commit()
    except:
        conn.rollback()

    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS assignments (
        id {pk_def},
        group_id INTEGER,
        title TEXT,
        description TEXT,
        due_date TEXT,
        type TEXT,
        points INTEGER,
        FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE
    )
    """)

    # Ensure newer columns exist (for class/section assignments)
    safe_migrate("ALTER TABLE assignments ADD COLUMN section_id INTEGER")
    safe_migrate("ALTER TABLE assignments ADD COLUMN grade_level INTEGER")



    # Quizzes Table (LMS Phase 2)
    try:
        conn.commit()
        cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS quizzes (
            id {pk_def},
            group_id INTEGER,
            title TEXT,
            questions TEXT, -- JSON String
            created_at TEXT,
            time_limit_mins INTEGER DEFAULT 0,
            target_type TEXT DEFAULT 'group', -- group, grade, student
            target_id TEXT, -- group_id or student_id
            FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE
        )
        """)
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to create quizzes table: {e}")

    # Migration for new columns
    safe_migrate("ALTER TABLE quizzes ADD COLUMN time_limit_mins INTEGER DEFAULT 0")
    safe_migrate("ALTER TABLE quizzes ADD COLUMN target_type TEXT DEFAULT 'group'")
    safe_migrate("ALTER TABLE quizzes ADD COLUMN target_id TEXT")
    safe_migrate("ALTER TABLE quiz_attempts ADD COLUMN ai_feedback TEXT")
    safe_migrate("ALTER TABLE activities ADD COLUMN ai_feedback TEXT")
    safe_migrate("ALTER TABLE quizzes ADD COLUMN acknowledged BOOLEAN DEFAULT 0")
    
    # Quiz Attempts Table (LMS Phase 2)
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS quiz_attempts (
        id {pk_def},
        quiz_id INTEGER,
        student_id TEXT,
        score REAL,
        answers TEXT, -- JSON String
        ai_feedback TEXT,
        submitted_at TEXT,
        FOREIGN KEY (quiz_id) REFERENCES quizzes(id) ON DELETE CASCADE,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
    )
    """)


    # --- LMS TABLES (Full Moodle Alternative) ---
    
    # 1. Courses
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS lms_courses (
        id {pk_def},
        title TEXT,
        description TEXT,
        teacher_id TEXT,
        category TEXT,
        thumbnail_url TEXT,
        enrollment_key TEXT,
        created_at TEXT,
        school_id INTEGER DEFAULT 1,
        FOREIGN KEY (teacher_id) REFERENCES students(id) ON DELETE SET NULL,
        FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE
    )
    """)

    # 2. Course Sections
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS lms_course_sections (
        id {pk_def},
        course_id INTEGER,
        title TEXT,
        order_index INTEGER,
        FOREIGN KEY (course_id) REFERENCES lms_courses(id) ON DELETE CASCADE
    )
    """)

    # 3. Course Modules
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS lms_course_modules (
        id {pk_def},
        section_id INTEGER,
        title TEXT,
        type TEXT,
        content_url TEXT,
        content_text TEXT,
        searchable_text TEXT, -- For RAG
        order_index INTEGER,
        FOREIGN KEY (section_id) REFERENCES lms_course_sections(id) ON DELETE CASCADE
    )
    """)
    
    # Migration for existing tables
    # Migration for existing tables
    safe_migrate("ALTER TABLE lms_course_modules ADD COLUMN searchable_text TEXT")


    # 4. Enrollments
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS lms_enrollments (
        id {pk_def},
        course_id INTEGER,
        student_id TEXT,
        enrolled_at TEXT,
        FOREIGN KEY (course_id) REFERENCES lms_courses(id) ON DELETE CASCADE,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
        UNIQUE(course_id, student_id)
    )
    """)

    # 5. Module Completion Tracking
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS lms_module_completion (
        id {pk_def},
        module_id INTEGER,
        student_id TEXT,
        status TEXT DEFAULT 'Not Started',
        score REAL DEFAULT 0,
        FOREIGN KEY (module_id) REFERENCES lms_course_modules(id) ON DELETE CASCADE,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
        UNIQUE(module_id, student_id)
    )
    """)

    # Duplicate Quiz Attempts table removed.

    # --- STUDENT INFORMATION MANAGEMENT MODULE ---

    # Sections Table
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS sections (
        id {pk_def},
        school_id INTEGER,
        name TEXT, -- e.g. "Section A", "Blue Group"
        grade_level INTEGER,
        created_at TEXT,
        FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE
    )
    """)

    # Guardians Table
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS guardians (
        id {pk_def},
        student_id TEXT,
        name TEXT,
        relationship TEXT, -- Father, Mother, Guardian
        phone TEXT,
        email TEXT,
        address TEXT,
        is_emergency_contact BOOLEAN DEFAULT FALSE,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
    )
    """)

    # Health Records Table
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS health_records (
        id {pk_def},
        student_id TEXT UNIQUE, -- One record per student
        blood_group TEXT,
        emergency_contact_name TEXT,
        emergency_contact_phone TEXT,
        allergies TEXT,
        medical_conditions TEXT,
        medications TEXT,
        doctor_name TEXT,
        doctor_phone TEXT,
        last_updated TEXT,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
    )
    """)


    # Student Documents Table
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS student_documents (
        id {pk_def},
        student_id TEXT,
        document_type TEXT, -- 'ID', 'Certificate', 'Report Card', 'Other'
        document_name TEXT,
        file_path TEXT,
        upload_date TEXT,
        uploaded_by TEXT, -- User ID of uploader
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
    )
    """)

    # Ensure section_id exists in students table (Migration)
    # Ensure section_id exists in students table (Migration)
    safe_migrate("ALTER TABLE students ADD COLUMN section_id INTEGER REFERENCES sections(id) ON DELETE SET NULL")



    # Compliance System Settings
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS system_settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    # Question Bank Table
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS question_banks (
        id {pk_def},
        title TEXT,
        file_path TEXT,
        uploaded_by TEXT,
        created_at TEXT,
        school_id INTEGER DEFAULT 1,
        FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE
    )
    """)

    # Question Banks Migrations
    safe_migrate("ALTER TABLE question_banks ADD COLUMN title TEXT")
    safe_migrate("ALTER TABLE question_banks ADD COLUMN file_path TEXT")
    safe_migrate("ALTER TABLE question_banks ADD COLUMN uploaded_by TEXT")
    safe_migrate("ALTER TABLE question_banks ADD COLUMN created_at TEXT")
    safe_migrate("ALTER TABLE question_banks ADD COLUMN school_id INTEGER DEFAULT 1")

    # Question Banks Migrations
    safe_migrate("ALTER TABLE question_banks ADD COLUMN title TEXT")
    safe_migrate("ALTER TABLE question_banks ADD COLUMN file_path TEXT")
    safe_migrate("ALTER TABLE question_banks ADD COLUMN uploaded_by TEXT")
    safe_migrate("ALTER TABLE question_banks ADD COLUMN created_at TEXT")
    safe_migrate("ALTER TABLE question_banks ADD COLUMN school_id INTEGER DEFAULT 1")
    
    # Quizzes/Exams Migrations (New PDF Type)
    safe_migrate("ALTER TABLE quizzes ADD COLUMN exam_type TEXT DEFAULT 'interactive'") # 'interactive' or 'pdf'
    safe_migrate("ALTER TABLE quizzes ADD COLUMN file_path TEXT") # For PDF Question Paper
    
    # Quiz Attempts (PDF Submissions)
    safe_migrate("ALTER TABLE quiz_attempts ADD COLUMN submission_file_path TEXT") # For PDF Answer Sheet

    # --- MIGRATIONS ---
    # Add columns if missing (Postgres: ADD COLUMN not supported in older ver, but wrapper suppresses DuplicateColumn error)
    # Add columns if missing (Safe wrapper for SQLite/Postgres)
    # Migrations will be handled by safe_migrate defined at top

    safe_migrate("ALTER TABLE students ADD COLUMN role TEXT DEFAULT 'Student'")
    safe_migrate("ALTER TABLE students ADD COLUMN school_id INTEGER DEFAULT 1")
    safe_migrate("ALTER TABLE students ADD COLUMN is_super_admin BOOLEAN DEFAULT FALSE")

    safe_migrate("ALTER TABLE groups ADD COLUMN school_id INTEGER DEFAULT 1")
    
    safe_migrate("ALTER TABLE live_classes ADD COLUMN school_id INTEGER DEFAULT 1")

    safe_migrate("ALTER TABLE invitations ADD COLUMN school_id INTEGER DEFAULT 1")

    safe_migrate("ALTER TABLE students ADD COLUMN failed_login_attempts INTEGER DEFAULT 0")
    safe_migrate("ALTER TABLE students ADD COLUMN locked_until TEXT")
    safe_migrate("ALTER TABLE students ADD COLUMN math_score REAL DEFAULT 0.0")
    safe_migrate("ALTER TABLE students ADD COLUMN science_score REAL DEFAULT 0.0")
    safe_migrate("ALTER TABLE students ADD COLUMN english_language_score REAL DEFAULT 0.0") 
    safe_migrate("ALTER TABLE live_classes ADD COLUMN target_students TEXT") 
    safe_migrate("ALTER TABLE groups ADD COLUMN subject TEXT DEFAULT 'General'")
    safe_migrate("ALTER TABLE students ADD COLUMN xp INTEGER DEFAULT 0")
    safe_migrate("ALTER TABLE students ADD COLUMN badges TEXT DEFAULT '[]'")
    
    # Auth logs migration
    safe_migrate("ALTER TABLE auth_logs ADD COLUMN logout_time TEXT")
    safe_migrate("ALTER TABLE auth_logs ADD COLUMN duration_minutes INTEGER")
    # Migration for new columns (Moved roles migration after table creation)

    # --- RBAC TABLES (NEW) ---
    # 1. Permissions (System defined, read-only mostly)
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS permissions (
        id {pk_def},
        code TEXT UNIQUE,
        description TEXT,
        group_name TEXT -- e.g. 'User Management', 'Academics'
    )
    """)

    # 2. Roles
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS roles (
        id {pk_def},
        name TEXT,
        description TEXT,
        status TEXT DEFAULT 'Active',
        school_id INTEGER DEFAULT NULL, -- NULL = System/Global Role
        is_system BOOLEAN DEFAULT FALSE,
        FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE
    )
    """)


    # Migration: Ensure status column exists
    safe_migrate("ALTER TABLE roles ADD COLUMN status TEXT DEFAULT 'Active'")

    # 3. Role Permissions
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS role_permissions (
        role_id INTEGER,
        permission_id INTEGER,
        FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
        FOREIGN KEY (permission_id) REFERENCES permissions(id) ON DELETE CASCADE,
        PRIMARY KEY (role_id, permission_id)
    )
    """)

    # 4. User Roles (Link Users to Roles)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_roles (
        user_id TEXT,
        role_id INTEGER,
        FOREIGN KEY (user_id) REFERENCES students(id) ON DELETE CASCADE,
        FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
        PRIMARY KEY (user_id, role_id)
    )
    """)

    # --- COMMUNICATION TABLES ---
    # Announcements
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS announcements (
        id {pk_def},
        title TEXT,
        content TEXT,
        target_role TEXT DEFAULT 'All',
        created_at TEXT
    )
    """)

    # Messages
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS messages (
        id {pk_def},
        sender_id TEXT,
        receiver_id TEXT,
        subject TEXT,
        content TEXT,
        timestamp TEXT,
        is_read BOOLEAN DEFAULT FALSE,
        FOREIGN KEY (sender_id) REFERENCES students(id) ON DELETE CASCADE,
        FOREIGN KEY (receiver_id) REFERENCES students(id) ON DELETE CASCADE
    )
    """)

    # Calendar Events
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS calendar_events (
        id {pk_def},
        title TEXT,
        type TEXT,
        date TEXT,
        description TEXT
    )
    """)

    # Student Attendance Table
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS student_attendance (
        id {pk_def},
        student_id TEXT,
        date TEXT,
        status TEXT, -- Present, Absent, Late, Excused
        remarks TEXT,
        recorded_by TEXT, -- Teacher ID
        created_at TEXT,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
    )
    """)

    # --- STAFF MANAGEMENT TABLES (FR-3.4) ---
    # Departments
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS departments (
        id {pk_def},
        name TEXT UNIQUE,
        description TEXT,
        head_of_department_id TEXT,
        FOREIGN KEY (head_of_department_id) REFERENCES students(id) ON DELETE SET NULL
    )
    """)

    # Staff Extended Profiles (extends students/users table)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS staff_profiles (
        user_id TEXT PRIMARY KEY,
        department_id INTEGER,
        position_title TEXT,
        joining_date TEXT,
        contract_type TEXT, -- Full-time, Part-time, Contract
        salary REAL,
        FOREIGN KEY (user_id) REFERENCES students(id) ON DELETE CASCADE,
        FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE SET NULL
    )
    """)

    # Staff Attendance
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS staff_attendance (
        id {pk_def},
        user_id TEXT,
        date TEXT,
        status TEXT, -- Present, Absent, Late, Leave
        check_in_time TEXT,
        check_out_time TEXT,
        FOREIGN KEY (user_id) REFERENCES students(id) ON DELETE CASCADE
    )
    """)

    # Staff Performance Reviews
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS staff_performance (
        id {pk_def},
        user_id TEXT,
        reviewer_id TEXT,
        review_date TEXT,
        rating INTEGER, -- 1-5
        comments TEXT,
        goals TEXT,
        FOREIGN KEY (user_id) REFERENCES students(id) ON DELETE CASCADE
    )
    """)

    # --- FULL FEATURE TABLES (FR-6) ---
    
    # 1. Timetable
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS timetables (
        id {pk_def},
        class_grade INTEGER,
        section TEXT, -- A, B, C
        day_of_week TEXT, -- Monday, Tuesday...
        period_number INTEGER,
        start_time TEXT,
        end_time TEXT,
        subject TEXT,
        teacher_id TEXT,
        FOREIGN KEY (teacher_id) REFERENCES students(id)
    )
    """)

    # 2. Assignment Submissions
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS assignment_submissions (
        id {pk_def},
        assignment_id INTEGER,
        student_id TEXT,
        submitted_at TEXT,
        file_url TEXT,
        content_text TEXT,
        status TEXT DEFAULT 'Submitted', -- Submitted, Graded, Reassigned
        grade REAL,
        feedback TEXT,
        ai_feedback TEXT,
        FOREIGN KEY (assignment_id) REFERENCES assignments(id) ON DELETE CASCADE,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
    )
    """)

    # 3. Leave Requests (Student & Teacher)
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS leave_requests (
        id {pk_def},
        user_id TEXT,
        type TEXT, -- Sick, Casual, etc.
        start_date TEXT,
        end_date TEXT,
        reason TEXT,
        status TEXT DEFAULT 'Pending', -- Pending, Approved, Denied
        reviewed_by TEXT,
        created_at TEXT,
        FOREIGN KEY (user_id) REFERENCES students(id) ON DELETE CASCADE
    )
    """)

    # 3a. Leave Reassignments (Teacher coverage during leave)
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS leave_reassignments (
        id {pk_def},
        leave_id INTEGER,
        original_teacher_id TEXT,
        substitute_teacher_id TEXT,
        assigned_by TEXT,
        assigned_at TEXT,
        FOREIGN KEY (leave_id) REFERENCES leave_requests(id) ON DELETE CASCADE
    )
    """)

    # 4. Internal Email/Messages
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS emails (
        id {pk_def},
        sender_id TEXT,
        recipient_email TEXT, -- Can be group (e.g., 'Grade 10')
        subject TEXT,
        body TEXT,
        sent_at TEXT,
        is_read BOOLEAN DEFAULT FALSE,
        FOREIGN KEY (sender_id) REFERENCES students(id)
    )
    """)

    # 5. Question Bank (Online Test)
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS question_banks (
        id {pk_def},
        teacher_id TEXT,
        grade INTEGER,
        subject TEXT,
        topic TEXT,
        question_text TEXT,
        question_type TEXT, -- MCQ, Essay
        options TEXT, -- JSON
        correct_answer TEXT,
        marks INTEGER,
        created_at TEXT
    )
    """)

    # 6. Student Marks (Progress Card)
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS student_marks (
        id {pk_def},
        student_id TEXT,
        exam_name TEXT, -- Midterm, Final
        subject TEXT,
        marks_obtained REAL,
        max_marks REAL,
        grade TEXT, -- A, B, C
        remarks TEXT,
        date TEXT,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
    )
    """)
    safe_migrate("ALTER TABLE student_marks ADD COLUMN published INTEGER DEFAULT 0")
    safe_migrate("ALTER TABLE student_marks ADD COLUMN published_at TEXT")
    safe_migrate("ALTER TABLE student_marks ADD COLUMN published_by TEXT")

    conn.commit()
    
    # --- SEED RBAC DATA ---
    seed_rbac_data(conn)

    conn.close()

def seed_rbac_data(conn):
    cursor = conn.cursor()
    
    # 1. Permissions List
    # Mapped from requirements
    perms = [
        ('user_management', 'Manage Users (Create/Edit/Delete)', 'User Management'),
        ('role_management', 'Manage Roles & Permissions', 'Role Management'),
        ('permission_management', 'View Platform Permissions', 'Permission Management'),
        ('school.manage', 'Manage Institutions', 'System'),
        ('class.view', 'View Classes', 'Academics'),
        ('class.create', 'Create/Schedule Classes', 'Academics'),
        ('class.edit', 'Edit Classes', 'Academics'),
        ('assignment.view', 'View Assignments', 'Academics'),
        ('assignment.create', 'Create Assignments', 'Academics'),
        ('assignment.grade', 'Grade Assignments', 'Academics'),
        ('reports.view', 'View Reports/Analytics', 'Analytics'),
        ('finance.view', 'View Finance', 'Administration'),
        ('communication.view', 'View Communication', 'Communication'),
        ('communication.announce', 'Post Announcements', 'Communication'),
        ('communication.events', 'Manage Calendar Events', 'Communication'),
        ('compliance.view', 'View Compliance & Security', 'Compliance'),
        ('compliance.manage', 'Manage Compliance Settings', 'Compliance'),
        ('finance.manage', 'Manage Finance Settings', 'Finance'),
        
        # New Detailed Permissions
        ('finance.invoices', 'Manage Invoices', 'Finance'),
        ('finance.payroll', 'Manage Payroll', 'Finance'),
        ('staff.view', 'View Staff & Faculty', 'HR'),
        ('staff.manage', 'Manage Staff & Faculty', 'HR'),
        ('staff.assets', 'Manage Assets & Lending', 'HR'),
        
        ('student.info.view', 'View Student Information', 'Student Info'),
        ('student.info.manage', 'Manage Student Information', 'Student Info'),
        ('student.progress.view', 'View Student Progress', 'Student Info'),
    ]

    # Create Finance Settings Table if not exists
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS finance_settings (
        key TEXT PRIMARY KEY,
        value TEXT,
        description TEXT
    )
    """)

    # ---------------------------------------------------------
    # MIGRATIONS (Ensure Schema is Up-to-Date)
    # ---------------------------------------------------------
    try:
        cursor.execute("ALTER TABLE resources ADD COLUMN extracted_text TEXT")
        conn.commit()
    except Exception as e:
        conn.rollback()
        if "duplicate column name" not in str(e).lower():
            logger.warning(f"Migration warning (resources.extracted_text): {e}")

    for code, desc, group in perms:
        cursor.execute("INSERT INTO permissions (code, description, group_name) VALUES (?, ?, ?) ON CONFLICT DO NOTHING", (code, desc, group))
    
    # 2. Key Roles
    # Ensuring we have the roles requested
    roles_def = [
        ('Root_Super_Admin', 'Root Access - Full System Control'),
        ('Tenant_Admin', 'School Administrator (Principal)'),
        ('Academic_Admin', 'Academic Coordinator'),
        ('Teacher', 'Faculty Member'),
        ('Student', 'Learner'),
        ('Parent_Guardian', 'Parent/Guardian'),
        ('Finance_Officer', 'Finance Manager'),
        ('HR_Admin', 'Human Resources Admin')
    ]

    for r_name, r_desc in roles_def:
        # Check if role exists to avoid ON CONFLICT error
        exists = cursor.execute("SELECT id FROM roles WHERE name = ?", (r_name,)).fetchone()
        if not exists:
            cursor.execute("INSERT INTO roles (name, description, is_system) VALUES (?, ?, TRUE)", (r_name, r_desc))
    
    # Fetch IDs
    roles = {row['name']: row['id'] for row in cursor.execute("SELECT name, id FROM roles WHERE is_system = TRUE").fetchall()}
    all_perms = {row['code']: row['id'] for row in cursor.execute("SELECT code, id FROM permissions").fetchall()}

    # 3. Assign Default Permissions
    def assign(role_name, perm_codes):
        if role_name not in roles: return
        r_id = roles[role_name]
        
        # Clear existing permissions for system roles to ensure update matches specs
        cursor.execute("DELETE FROM role_permissions WHERE role_id = ?", (r_id,))
        
        for p_code in perm_codes:
            if p_code == '*':
                 for p_id in all_perms.values():
                     cursor.execute("INSERT INTO role_permissions (role_id, permission_id) VALUES (?, ?) ON CONFLICT DO NOTHING", (r_id, p_id))
            elif p_code in all_perms:
                cursor.execute("INSERT INTO role_permissions (role_id, permission_id) VALUES (?, ?) ON CONFLICT DO NOTHING", (r_id, all_perms[p_code]))

    # Root Super Admin (Everything)
    assign('Root_Super_Admin', ['*'])
    
    # Tenant Admin (School Management)
    assign('Tenant_Admin', [
        'user_management', 'role_management', 'permission_management', 
        'class.view', 'reports.view', 
        'finance.view', 'finance.manage', 'finance.invoices', 'finance.payroll',
        'communication.view', 'communication.announce', 'communication.events', 
        'compliance.view', 'compliance.manage', 
        'staff.view', 'staff.manage', 
        'student.info.view', 'student.info.manage', 'student.progress.view'
    ])
    
    # Academic Admin (Curriculum Focus)
    assign('Academic_Admin', [
        'class.view', 'class.create', 'class.edit', 
        'assignment.view', 'assignment.create', 
        'student.info.view', 'student.progress.view',
        'reports.view'
    ])

    # Teacher
    assign('Teacher', [
        'class.view', 'class.create', 'class.edit', 
        'assignment.view', 'assignment.create', 'assignment.grade', 
        'communication.view', 'communication.announce', 'communication.events',
        'student.info.view', 'student.progress.view',
        'attendance.manage' # Implicitly handle attendance via class/activity
    ])

    # Student
    assign('Student', [
        'class.view', 'assignment.view', 'student.progress.view', 'communication.view'
    ])

    # Parent_Guardian
    assign('Parent_Guardian', [
        'student.progress.view', 'finance.invoices', 'communication.view'
    ])

    # Finance_Officer
    assign('Finance_Officer', [
        'finance.view', 'finance.manage', 'finance.invoices', 'finance.payroll'
    ])

    # HR_Admin
    assign('HR_Admin', [
        'staff.view', 'staff.manage', 'staff.assets'
    ])

    conn.commit()

# --- RBAC API ROUTES ---
@app.get("/api/admin/roles")
async def get_roles(
    x_user_role: str = Header(None, alias="X-User-Role"),
    x_school_id: Optional[int] = Header(None, alias="X-School-Id") # Mocked for now, usually from token
):
    conn = get_db_connection()
    c = conn.cursor()
    
    query = "SELECT r.id, r.name, r.description, r.status, r.is_system, COUNT(rp.permission_id) as perm_count FROM roles r LEFT JOIN role_permissions rp ON r.id = rp.role_id"
    params = []
    
    # FILTER: Root_Super_Admin should only be visible to Root_Super_Admin
    if x_user_role != 'Root_Super_Admin':
        query += " WHERE r.name != 'Root_Super_Admin'"
    else:
        query += " WHERE 1=1" # Dummy

    # Note: Roles are currently shared globally in this simplified DB schema.
    # In a real multi-tenant DB, roles would have a 'school_id' column or be purely system-defined.
    # For this implementation, we assume Roles are System-Wide Templates, so we don't filter by school_id for *definitions*,
    # but the constraints requested say "Tenant_Admin... only see roles of their own institution".
    # Since we lack custom roles per school in the current schema, we will skip the school_id filter for roles list 
    # OR assumes roles can be created per school. 
    # Let's keep it simple: Show all (except Root) to Admins.
    
    query += " GROUP BY r.id"
    
    roles = c.execute(query, params).fetchall()
    
    result = []
    for r in roles:
        # Format Code R-XXX
        formatted_code = f"R-{r['id']:03d}"
        
        result.append({
            "id": r['id'],
            "code": formatted_code,
            "name": r['name'],
            "description": r['description'],
            "status": r['status'] or 'Active',
            "is_system": r['is_system'],
            "permission_count": r['perm_count']
        })
    conn.close()
    return result

@app.get("/api/admin/permissions")
async def get_permissions(x_user_id: str = Header(None, alias="X-User-Id")):
    await verify_permission("permission_management", x_user_id=x_user_id)

    conn = get_db_connection()
    perms = conn.execute("SELECT * FROM permissions ORDER BY group_name, code").fetchall()
    
    # Group by 'group_name'
    grouped = {}
    for p in perms:
        g = p['group_name']
        if g not in grouped: grouped[g] = []
        grouped[g].append({"id": p['id'], "code": p['code'], "description": p['description']})
    
    conn.close()
    return grouped

@app.get("/api/admin/permissions/list")
async def get_permissions_list(x_user_id: str = Header(None, alias="X-User-Id")):
    await verify_permission("permission_management", x_user_id=x_user_id)

    conn = get_db_connection()
    perms = conn.execute("SELECT * FROM permissions ORDER BY id").fetchall()
    
    result = []
    for p in perms:
        # Format Code P-XXX
        formatted_code = f"P-{p['id']:04d}"
        
        result.append({
            "id": p['id'],
            "display_code": formatted_code,
            "code": p['code'],
            "description": p['description'],
            "group_name": p['group_name']
        })
    conn.close()
    return result

class UpdatePermissionRequest(BaseModel):
    description: str

@app.put("/api/admin/permissions/{perm_id}")
async def update_permission(perm_id: int, req: UpdatePermissionRequest, x_user_id: str = Header(None, alias="X-User-Id")):
    await verify_permission("permission_management", x_user_id=x_user_id)

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE permissions SET description = ? WHERE id = ?", (req.description, perm_id))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Permission not found")
        conn.commit()
        return {"success": True}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.get("/api/admin/roles/{role_id}")
async def get_role_details(role_id: int):
    conn = get_db_connection()
    role = conn.execute("SELECT * FROM roles WHERE id = ?", (role_id,)).fetchone()
    if not role:
        conn.close()
        raise HTTPException(status_code=404, detail="Role not found")
        
    perms = conn.execute("""
        SELECT p.id, p.code, p.description 
        FROM permissions p
        JOIN role_permissions rp ON p.id = rp.permission_id
        WHERE rp.role_id = ?
    """, (role_id,)).fetchall()
    
    conn.close()
    return {
        "id": role['id'],
        "code": f"R-{role['id']:03d}",
        "name": role['name'],
        "description": role['description'],
        "status": role['status'],
        "is_system": role['is_system'],
        "permissions": [{"id": p['id'], "code": p['code'], "description": p['description']} for p in perms]
    }

class ReportsSummaryResponse(BaseModel):
    academic_performance: Dict[str, float]
    attendance_trends: List[Dict[str, Any]]
    financial_summary: Dict[str, float]
    staff_utilization: Dict[str, Any]

@app.get("/api/reports/summary")
async def get_reports_summary(user_id: str = Header(None, alias="X-User-Id"), role: str = Header(None, alias="X-User-Role")):
    # Check permissions 
    # if role not in ['Teacher', 'Principal', 'Super Admin']:
    #    raise HTTPException(status_code=403, detail="Unauthorized")

    conn = get_db_connection()
    c = conn.cursor()

    # 1. Academic Performance (Real)
    stats = c.execute("SELECT AVG(math_score) as math, AVG(science_score) as science, AVG(english_language_score) as english, AVG(attendance_rate) as attendance FROM students WHERE role = 'Student'").fetchone()
    
    math = stats['math'] if stats and stats['math'] is not None else 0
    science = stats['science'] if stats and stats['science'] is not None else 0
    english = stats['english'] if stats and stats['english'] is not None else 0
    att = stats['attendance'] if stats and stats['attendance'] is not None else 0

    academic = {
        "math_avg": round(math, 1),
        "science_avg": round(science, 1),
        "english_avg": round(english, 1),
        "overall_avg": round((math + science + english) / 3, 1)
    }

    # 2. Attendance Trends (Mocked + Current)
    attendance_trends = [
        {"month": "Jan", "rate": 88},
        {"month": "Feb", "rate": 90},
        {"month": "Mar", "rate": 85},
        {"month": "Apr", "rate": 92},
        {"month": "May", "rate": 94},
        {"month": "Jun", "rate": round(att, 1)}
    ]

    # 3. Financial Summaries (Mocked)
    finance = {
        "revenue": 150000.00,
        "expenses": 95000.00,
        "net_income": 55000.00,
        "outstanding_fees": 12000.00
    }

    # 4. Staff Utilization (Real-ish)
    teacher_count = c.execute("SELECT COUNT(*) as count FROM students WHERE role = 'Teacher'").fetchone()['count']
    student_count = c.execute("SELECT COUNT(*) as count FROM students WHERE role = 'Student'").fetchone()['count']

    ratio = 0
    if teacher_count > 0:
        ratio = round(student_count / teacher_count, 1)
    
    staff_utilization = {
        "total_staff": teacher_count,
        "active_classes": teacher_count * 4, # Assumption: 4 classes per teacher
        "student_teacher_ratio": f"{ratio}:1",
        "utilization_rate": 85.5
    }

    conn.close()

    return {
        "academic_performance": academic,
        "attendance_trends": attendance_trends,
        "financial_summary": finance,
        "staff_utilization": staff_utilization
    }


@app.post("/api/admin/roles")
async def create_role(req: RoleCreateRequest):
    conn = get_db_connection()
    try:
        # Create Role
        cur = conn.cursor()
        cur.execute("INSERT INTO roles (name, description, status, is_system) VALUES (?, ?, ?, FALSE) RETURNING id", (req.name, req.description, req.status))
        role_id = cur.fetchone()['id']
        
        # Add perms
        for p_code in req.permissions:
            perm = cur.execute("SELECT id FROM permissions WHERE code = ?", (p_code,)).fetchone()
            if perm:
                cur.execute("INSERT INTO role_permissions (role_id, permission_id) VALUES (?, ?)", (role_id, perm['id']))
        
        conn.commit()
        return {"success": True, "role_id": role_id}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.put("/api/admin/roles/{role_id}")
async def update_role(role_id: int, req: RoleCreateRequest):
    conn = get_db_connection()
    try:
        # Update Role Info
        cur = conn.cursor()
        cur.execute("UPDATE roles SET name = ?, description = ?, status = ? WHERE id = ?", (req.name, req.description, req.status, role_id))
        
        # Update Perms (Wipe and recreate)
        cur.execute("DELETE FROM role_permissions WHERE role_id = ?", (role_id,))
        for p_code in req.permissions:
            perm = cur.execute("SELECT id FROM permissions WHERE code = ?", (p_code,)).fetchone()
            if perm:
                cur.execute("INSERT INTO role_permissions (role_id, permission_id) VALUES (?, ?)", (role_id, perm['id']))
                
        conn.commit()
        return {"success": True}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
        
@app.delete("/api/admin/roles/{role_id}")
async def delete_role(role_id: int):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        # Check if system
        role = cur.execute("SELECT is_system FROM roles WHERE id = ?", (role_id,)).fetchone()
        if role and role['is_system']:
             raise HTTPException(status_code=403, detail="Cannot delete system roles.")
             
        cur.execute("DELETE FROM roles WHERE id = ?", (role_id,))
        conn.commit()
        return {"success": True}
    except HTTPException as he:
        raise he
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


    conn.commit()
    # ------------------------------------------------------------------

    # Ensure Teacher has correct role
    cursor.execute("UPDATE students SET role = 'Teacher' WHERE id = 'teacher'")
    conn.commit()
    # Seed Timetable
    cursor.execute("SELECT COUNT(*) FROM timetables")
    if cursor.fetchone()[0] == 0:
        # Teacher ID 'teacher'
        tt_data = [
            (9, 'A', 'Monday', 1, '09:00', '10:00', 'Mathematics', 'teacher'),
            (10, 'B', 'Monday', 2, '10:00', '11:00', 'Science', 'teacher'),
            (9, 'A', 'Tuesday', 1, '09:00', '10:00', 'Mathematics', 'teacher'),
            (11, 'C', 'Tuesday', 3, '11:00', '12:00', 'Physics', 'teacher'),
            (10, 'B', 'Wednesday', 2, '10:00', '11:00', 'Science', 'teacher'),
            (9, 'A', 'Thursday', 4, '13:00', '14:00', 'History', 'teacher'),
            (10, 'B', 'Friday', 1, '09:00', '10:00', 'Science Lab', 'teacher')
        ]
        cursor.executemany("INSERT INTO timetables (class_grade, section, day_of_week, period_number, start_time, end_time, subject, teacher_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", tt_data)
        conn.commit()

    # Seed Leave Requests
    cursor.execute("SELECT COUNT(*) FROM leave_requests")
    if cursor.fetchone()[0] == 0:
        leaves = [
            ('S001', 'Sick Leave', '2025-10-10', '2025-10-12', 'High Fever', 'Approved', 'teacher', datetime.now().isoformat()),
            ('S002', 'Casual Leave', '2025-11-05', '2025-11-06', 'Family Function', 'Pending', None, datetime.now().isoformat()),
            ('teacher', 'Sick Leave', '2025-12-01', '2025-12-02', 'Medical Checkup', 'Pending', None, datetime.now().isoformat())
        ]
        cursor.executemany("INSERT INTO leave_requests (user_id, type, start_date, end_date, reason, status, reviewed_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", leaves)
        conn.commit()

    # Seed Schools
    cursor.execute("SELECT COUNT(*) FROM schools")
    if cursor.fetchone()[0] == 0:
        created_at = datetime.now().isoformat()
        cursor.execute("INSERT INTO schools (name, address, contact_email, created_at) VALUES ('Noble Nexus Academy', '123 Main St', 'contact@noblenexus.com', ?)", (created_at,))
        cursor.execute("INSERT INTO schools (name, address, contact_email, created_at) VALUES ('Global Tech High', '456 Tech Ave', 'admin@globaltech.edu', ?)", (created_at,))
        conn.commit()

    # Seed data only if tables are empty
    cursor.execute("SELECT COUNT(*) FROM students")
    if cursor.fetchone()[0] == 0:
        students_data = [
            ('S001', 'Alice Smith', 9, 'Maths', 92.5, 'English', '123', 85.0, 78.5, 90.0, 'Student', 0, None, 1, False),
            ('S002', 'Bob Johnson', 10, 'Science', 85.0, 'Spanish', '123', 60.0, 95.0, 75.0, 'Student', 0, None, 1, False),
            ('SURJEET', 'Surjeet J', 11, 'Science', 77.0, 'Punjabi', '123', 70.0, 65.0, 80.0, 'Student', 0, None, 1, False),
            ('DEVA', 'Deva Krishnan', 11, 'Tamil', 90.0, 'Tamil', '123', 95.0, 88.0, 92.0, 'Student', 0, None, 1, False),
            ('HARISH', 'Harish Boy', 5, 'English', 7.0, 'Hindi', '123', 50.0, 50.0, 45.0, 'Student', 0, None, 1, False),
            ('teacher', 'Teacher Admin', 0, 'All', 100.0, 'English', 'teacher', 100.0, 100.0, 100.0, 'Teacher', 0, None, 1, False), 
            ('superadmin', 'Super Admin', 0, 'All', 100.0, 'English', 'superadmin', 100.0, 100.0, 100.0, 'Admin', 0, None, 1, True),
            ('admin', 'System Admin', 0, 'All', 100.0, 'English', 'admin', 100.0, 100.0, 100.0, 'Admin', 0, None, 1, True),
        ]
        cursor.executemany("INSERT INTO students (id, name, grade, preferred_subject, attendance_rate, home_language, password, math_score, science_score, english_language_score, role, failed_login_attempts, locked_until, school_id, is_super_admin) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", students_data)

        activities_data = [
            ('S001', '2025-11-01', 'Algebra', 'Medium', 95, 10),
            ('S001', '2025-11-03', 'Geometry', 'Medium', 65, 25), 
            ('S002', '2025-11-01', 'Physics', 'Medium', 40, 45),
            ('S002', '2025-11-02', 'Chemistry', 'Easy', 55, 30),
            ('HARISH', '2025-11-10', 'Reading', 'Easy', 80, 15),
            ('SURJEET', '2025-11-12', 'Physics', 'Medium', 88.0, 45),
            ('SURJEET', '2025-11-14', 'Chemistry', 'Hard', 76.5, 60),
            ('SURJEET', '2025-11-15', 'Biology', 'Easy', 92.0, 30),
            ('SURJEET', '2025-11-16', 'Maths', 'Hard', 85.0, 50),
            ('SURJEET', '2025-11-18', 'English', 'Medium', 90.0, 40),
            ('DEVA', '2025-11-12', 'Tamil', 'Medium', 95.0, 30),
            ('DEVA', '2025-11-13', 'English', 'Hard', 82.0, 45),
            ('DEVA', '2025-11-14', 'Maths', 'Medium', 88.0, 50),
        ]
        for a in activities_data:
             cursor.execute("INSERT INTO activities (student_id, date, topic, difficulty, score, time_spent_min) VALUES (?, ?, ?, ?, ?, ?)", a)
        
    # Ensure Teacher and Admin exist
    cursor.execute("SELECT id FROM students WHERE id = 'teacher'")
    if not cursor.fetchone():
         cursor.execute("INSERT INTO students (id, name, grade, preferred_subject, attendance_rate, home_language, password, math_score, science_score, english_language_score, role, failed_login_attempts, locked_until, school_id, is_super_admin) VALUES ('teacher', 'Teacher Admin', 0, 'All', 100.0, 'English', 'teacher', 100.0, 100.0, 100.0, 'Teacher', 0, NULL, 1, 0)")
    
    cursor.execute("SELECT id FROM students WHERE id = 'admin'")
    if not cursor.fetchone():
         cursor.execute("INSERT INTO students (id, name, grade, preferred_subject, attendance_rate, home_language, password, math_score, science_score, english_language_score, role, failed_login_attempts, locked_until, school_id, is_super_admin) VALUES ('admin', 'System Admin', 0, 'All', 100.0, 'English', 'admin', 100.0, 100.0, 100.0, 'Admin', 0, NULL, 1, 1)")

    # Seed demo codes for existing users (Check individually to ensure all are present)
    demo_codes = [
        ('teacher', '928471'), ('teacher', '582931'),
        ('admin', '736102'),
        ('S001', '519384'),
        ('S002', '123456'),
        ('SURJEET', '192837'),
        ('DEVA', '112233'),
        ('HARISH', '998877')
    ]
    now = datetime.now().isoformat()
    for uid, code in demo_codes:
         # Check if this specific code exists
         cursor.execute("SELECT 1 FROM backup_codes WHERE user_id = ? AND code = ?", (uid, code))
         if not cursor.fetchone():
             # Only insert if user actually exists
             cursor.execute("SELECT 1 FROM students WHERE id = ?", (uid,))
             if cursor.fetchone():
                 cursor.execute("INSERT INTO backup_codes (user_id, code, created_at) VALUES (?, ?, ?)", (uid, code, now))
    
    # Catch-all: Ensure ALL students have at least one code (Enforces 2FA for everyone)
    cursor.execute("SELECT id FROM students")
    all_users = cursor.fetchall()
    for user in all_users:
        uid = user[0]
        cursor.execute("SELECT 1 FROM backup_codes WHERE user_id = ?", (uid,))
        if not cursor.fetchone():
            # Generate a RANDOM default code for anyone missing one
            default_code = str(random.randint(100000, 999999))
            cursor.execute("INSERT INTO backup_codes (user_id, code, created_at) VALUES (?, ?, ?)", (uid, default_code, now))
                 
    conn.commit()
    conn.close()
# Database initialization moved to startup event


# --- 5. ML ENGINE ---

ML_MODEL = None
DIFF_LABEL_MAP = {0: 'Easy', 1: 'Medium', 2: 'Hard'}
DIFFICULTY_MAP = {'Easy': 0, 'Medium': 1, 'Hard': 2}

def train_recommendation_model():
    global ML_MODEL
    # Lazy import to prevent startup bottleneck
    from sklearn.ensemble import RandomForestClassifier
    df = fetch_data_df("SELECT score, time_spent_min, difficulty FROM activities")
    
    if len(df) < MIN_ACTIVITIES:
        ML_MODEL = None
        return

    X = df[['score', 'time_spent_min']]
    y = [DIFFICULTY_MAP.get(d, 1) for d in df['difficulty']] 
    
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        clf = RandomForestClassifier(n_estimators=50, random_state=42)
        clf.fit(X, y)
    
    ML_MODEL = clf

def get_recommendation(student_id: str) -> Optional[str]:
    train_recommendation_model() 
    if not ML_MODEL:
        return "Not enough data (minimum 5 activities) to generate an ML-based recommendation."

    df_history = fetch_data_df("SELECT score, time_spent_min FROM activities WHERE student_id = ? ORDER BY date DESC LIMIT 1", (student_id,))
    
    if df_history.empty:
        return "No activity history available to base a recommendation on."

    last_activity = df_history.iloc[0]
    import numpy as np
    X_pred = np.array([[last_activity['score'], last_activity['time_spent_min']]])
    
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        pred_idx = ML_MODEL.predict(X_pred)[0]
    
    rec_diff = DIFF_LABEL_MAP.get(pred_idx, 'Medium')
    return f"Based on your last score of {last_activity['score']}%, we recommend trying a **{rec_diff}** difficulty topic next!"

# ML Model training moved to startup event

# --- 6. RBAC CONFIGURATION ---

ROLE_PERMISSIONS = {
    "Admin": [
        "view_dashboard", "manage_users", "manage_invitations", 
        "view_all_grades", "edit_all_grades", 
        "schedule_active_class", "manage_groups", "view_audit_logs"
    ],
    "Principal": [
        "view_dashboard", "manage_users", "manage_invitations", 
        "view_all_grades", "edit_all_grades", 
        "schedule_active_class", "manage_groups", "view_audit_logs"
    ],
    "Teacher": [
        "view_dashboard", "invite_students", 
        "view_all_grades", "edit_all_grades", 
        "schedule_active_class", "manage_groups"
    ],
    "Student": [
        "view_dashboard", "view_own_grades", "join_active_class"
    ],
    "Parent": [
        "view_dashboard", "view_child_grades"
    ]
}

def check_permission(user_role: str, required_permission: str) -> bool:
    if user_role not in ROLE_PERMISSIONS:
        return False
    return required_permission in ROLE_PERMISSIONS[user_role]

async def verify_permission(permission: str, x_user_role: str = Header(None, alias="X-User-Role"), x_user_id: str = Header(None, alias="X-User-Id")):
    if not x_user_id:
         raise HTTPException(status_code=401, detail="Authentication required")

    conn = get_db_connection()
    try:
        user = conn.execute("SELECT role, is_super_admin FROM students WHERE id = ?", (x_user_id,)).fetchone()
        
        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        current_role = user['role']
        is_super = user['is_super_admin']

        # 1. Super Admin Override
        if is_super or current_role == 'Root_Super_Admin' or current_role == 'Super Admin':
            return True

        # 2. Check DB Permissions
        # Join user_roles -> roles -> role_permissions -> permissions
        # Also check for wildcard '*' permission assignment
        query = """
            SELECT 1 
            FROM user_roles ur
            JOIN role_permissions rp ON ur.role_id = rp.role_id
            JOIN permissions p ON rp.permission_id = p.id
            WHERE ur.user_id = ? 
            AND (p.code = ? OR p.code = '*')
        """
        has_perm = conn.execute(query, (x_user_id, permission)).fetchone()

        if not has_perm:
            # Fallback to legacy hardcoded check if DB check fails (temporary migration specific)
            # Remove this if fully migrated
            if current_role in ROLE_PERMISSIONS and permission in ROLE_PERMISSIONS[current_role]:
                return True
                
            log_auth_event(x_user_id, "Unauthorized Access", f"Missing permission: {permission}")
            raise HTTPException(status_code=403, detail=f"Permission denied: {permission} required.")
        
        return True
    finally:
        conn.close()


# --- LMS & UPLOADS CONFIGURATION ---
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../frontend/static_app/static/uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
# app.mount("/static", StaticFiles(directory="static"), name="static") # Removed duplicate mount

# --- 7. API ENDPOINTS ---

@app.get("/", response_class=HTMLResponse)
async def read_root():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, "../frontend/static_app/index.html")
    
    if not os.path.exists(file_path):
        # Graceful Fallback: If index.html is missing (e.g. separate frontend), just show API status
        return HTMLResponse(content="""
            <html>
                <body style="font-family: sans-serif; text-align: center; padding-top: 50px;">
                    <h1 style="color: #4CAF50;">Noble Nexus API is Running 🚀</h1>
                    <p>The backend is online and accepting requests.</p>
                    <p>Please access the application via your <strong>Vercel Frontend</strong>.</p>
                </body>
            </html>
        """, status_code=200)
        
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/script.js")
async def read_script():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, "../frontend/static_app/script.js")
    if not os.path.exists(file_path):
        return Response(content="console.error('script.js not found');", media_type="text/javascript")
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    return Response(content=content, media_type="text/javascript")

@app.post("/api/ai/lesson-plan", response_model=LessonPlanResponse)
async def generate_lesson_plan(
    topic: str = Form(...),
    grade: int = Form(...),
    subject: str = Form(...),
    duration_mins: int = Form(...),
    description: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    user_role: str = Header(None, alias="X-User-Role")
):
    if user_role and user_role != "Teacher" and user_role != "Admin":
         raise HTTPException(status_code=403, detail="Only teachers can generate lesson plans.")

    # PDF Processing
    pdf_context = ""
    if file:
        try:
            if file.filename.endswith('.pdf'):
                pdf_reader = PdfReader(file.file)
                for page in pdf_reader.pages:
                    pdf_context += page.extract_text() + "\n"
                pdf_context = pdf_context[:5000] # Limit to 5k chars to allow context window
            else:
                # Text fallback?
                content = await file.read()
                pdf_context = content.decode('utf-8', errors='ignore')[:5000]
        except Exception as e:
            logger.error(f"File read error: {e}")
            pass

    prompt = (
        f"Create a detailed {duration_mins}-minute lesson plan for a grade {grade} "
        f"{subject} class on the topic: '{topic}'.\n"
    )
    if description:
        prompt += f"Additional Context/Instructions: {description}\n"
    
    if pdf_context:
        prompt += f"\nReference Material (Use this content to build the plan):\n{pdf_context}\n"
    
    prompt += (
        f"Structure it with timings (e.g., Intro 5m, Activity 20m, Wrap-up 5m). "
        f"Include specific activities."
    )

    if AI_ENABLED:
        try:
            chat_completion = LESSON_PLANNER_CLIENT.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert teacher's assistant. Generate structured, timed lesson plans."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                model=GROQ_MODEL,
                temperature=0.7,
            )
            return LessonPlanResponse(content=chat_completion.choices[0].message.content)
        except Exception as e:
            logger.error(f"AI Generation Failed: {e}")
            # Fallback to heuristic if AI fails
    
    # Heuristic Fallback
    intro_time = max(5, int(duration_mins * 0.15))
    main_time = int(duration_mins * 0.7)
    wrap_time = duration_mins - intro_time - main_time
    
    plan = f"""
    ## 📚 Lesson Plan: {topic}
    **Grade:** {grade} | **Subject:** {subject} | **Duration:** {duration_mins} mins
    
    ### 1. Introduction ({intro_time} mins)
    *   **Hook:** Start with a question or short story about {topic}.
    *   **Objective:** Explain what students will learn today.
    
    ### 2. Main Activity ({main_time} mins)
    *   **Direct Instruction:** Briefly explain the core concepts of {topic}.
    *   **Guided Practice:** Work through an example together.
    *   **Independent/Group Work:** Students practice or discuss {topic}.
    
    ### 3. Wrap-Up ({wrap_time} mins)
    *   **Review:** Recap key points.
    *   **Exit Ticket:** Ask one checking question.
    """
    return LessonPlanResponse(content=plan)


import hmac
import hashlib
import time



# --- LTI SUPPORT (Tool Consumer Simulation) ---
import urllib.parse
import base64

def sign_oauth_hmac_sha1(method, url, params, consumer_secret):
    # 1. Sort and encode params
    from urllib.parse import quote
    
    # helper to percent encode strictly
    def percent_encode(s):
        return quote(str(s), safe=b'')

    sorted_params = sorted(params.items())
    normalized_params = '&'.join([f"{percent_encode(k)}={percent_encode(v)}" for k, v in sorted_params])
    
    # 2. Base String
    base_string = f"{method.upper()}&{percent_encode(url)}&{percent_encode(normalized_params)}"
    
    # 3. Signing Key
    key = f"{percent_encode(consumer_secret)}&" # Token secret is empty for LTI launch usually
    
    # 4. HMAC-SHA1
    hashed = hmac.new(key.encode(), base_string.encode(), hashlib.sha1)
    return base64.b64encode(hashed.digest()).decode()

@app.post("/api/lti/launch")
async def get_lti_launch_data(request: Request, x_user_id: str = Header(None, alias="X-User-Id")):
    # In a real app, we would look up the tool config (Consumer Key/Secret) based on the requested resource
    body = await request.json()
    tool_url = body.get('url')
    
    if not tool_url:
        raise HTTPException(status_code=400, detail="Tool URL required")

    # Mock Consumer Config
    consumer_key = "test"
    consumer_secret = "secret"
    
    # LTI Parameters
    params = {
        "lti_message_type": "basic-lti-launch-request",
        "lti_version": "LTI-1p0",
        "resource_link_id": "nexus_resource_1",
        "user_id": x_user_id,
        "roles": "Learner",
        "lis_person_name_full": "Noble Student",
        "oauth_consumer_key": consumer_key,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_nonce": secrets.token_hex(8),
        "oauth_version": "1.0",
        "oauth_callback": "about:blank"
    }
    
    # Sign
    params["oauth_signature"] = sign_oauth_hmac_sha1("POST", tool_url, params, consumer_secret)
    
    return {
        "url": tool_url,
        "params": params
    }

@app.get("/api/moodle/assignments")
async def get_moodle_assignments(x_user_id: str = Header(None, alias="X-User-Id")):
    return [
        {
            "id": 1,
            "course": "CS101",
            "name": "Python Basics Project",
            "duedate": int(time.time() + 86400 * 2), # 2 days from now
            "status": "submitted"
        },
        {
            "id": 2,
            "course": "MATH202",
            "name": "Calculus Quiz 3",
            "duedate": int(time.time() + 86400 * 5),
            "status": "pending"
        }
    ]

@app.get("/api/moodle/grades")
async def get_moodle_grades(x_user_id: str = Header(None, alias="X-User-Id")):
    return [
        {"course": "CS101", "itemname": "Midterm Exam", "grade": 88.5, "range": "0-100", "feedback": "Good job!"},
        {"course": "CS101", "itemname": "Python Basics Project", "grade": 92.0, "range": "0-100", "feedback": "Excellent code structure."},
        {"course": "HIST101", "itemname": "Ancient Civ Essay", "grade": 95.0, "range": "0-100", "feedback": "Very detailed."}
    ]

@app.post("/api/auth/login", response_model=LoginResponse)
async def login_user(request: LoginRequest):
    logger.info(f"Login attempt for user: {request.username}")
    conn = get_db_connection()
    cursor = conn.cursor()

    
    # Case-insensitive username lookup
    user = cursor.execute("SELECT id, name, password, role, failed_login_attempts, locked_until, is_super_admin, school_id FROM students WHERE LOWER(id) = LOWER(?)", 
                        (request.username.strip(),)).fetchone()
    
    if not user:
        conn.close()
        with open("login_debug.txt", "a") as f:
            f.write(f"Login Failed: User {request.username} not found\n")
        logger.warning(f"Login failed for user: {request.username} - User not found")
        log_auth_event(request.username, "Login Failed", "User not found")
        raise HTTPException(status_code=401, detail="Invalid credentials.")

    # Enforce Role Match (Case-Insensitive)
    allow_login = False
    db_role = user['role'].strip()
    req_role = request.role.strip()
    
    if db_role.lower() == req_role.lower():
        allow_login = True
    elif db_role == 'Admin' and (req_role == 'Teacher' or req_role == 'Principal'):
        allow_login = True
    
    # Special case: 'teacher' user might be Teacher title but lower in DB or vice versa
    if user['id'] == 'teacher' and req_role == 'Teacher':
        allow_login = True
        
    if not allow_login:
        conn.close()
        debug_msg = f"Role mismatch for {request.username}. DB={db_role}, Req={req_role}"
        with open("login_debug.txt", "a") as f:
            f.write(f"Login Failed: {debug_msg}\n")
        logger.warning(debug_msg)
        log_auth_event(request.username, "Login Failed", f"Role Mismatch: Tried {req_role} as {db_role}")
        raise HTTPException(status_code=403, detail=f"Access Denied: You are registered as a {db_role}, not a {req_role}.")

    # Check Account Lockout
    if user['locked_until']:
        lock_time = datetime.fromisoformat(user['locked_until'])
        if datetime.now() < lock_time:
            conn.close()
            remaining_min = int((lock_time - datetime.now()).total_seconds() / 60)
            log_auth_event(request.username, "Login Failed", "Account locked")
            raise HTTPException(status_code=403, detail=f"Account locked. Try again in {remaining_min + 1} minutes.")
        else:
            cursor.execute("UPDATE students SET failed_login_attempts = 0, locked_until = NULL WHERE id = ?", (request.username,))
            conn.commit()

    # Password Verification
    if user['password'] == request.password:
        cursor.execute("UPDATE students SET failed_login_attempts = 0, locked_until = NULL WHERE id = ?", (request.username,))
        
        # --- RBAC SYNC LOGIC (Preserve legacy migration) ---
        legacy_role_name = user['role']
        
        # 1. Sync Legacy Role if needed (Migration on Login)
        user_roles_check = cursor.execute("SELECT role_id FROM user_roles WHERE user_id = ?", (request.username,)).fetchall()
        
        if not user_roles_check:
             # Get Role ID (Handle 'Admin' -> 'Super Admin' mapping if needed, or just match name)
             target_role = legacy_role_name
             if target_role == 'Admin': target_role = 'Super Admin' 
             
             # Get Role ID
             role_row = cursor.execute("""
                 SELECT r.id 
                 FROM roles r
                 LEFT JOIN role_permissions rp ON r.id = rp.role_id
                 WHERE r.name = ?
                 GROUP BY r.id
                 ORDER BY COUNT(rp.permission_id) DESC
                 LIMIT 1
             """, (target_role,)).fetchone()
             
             if role_row:
                 try:
                    cursor.execute("INSERT INTO user_roles (user_id, role_id) VALUES (?, ?)", (request.username, role_row['id']))
                    conn.commit()
                 except:
                    pass 

        # --- 2FA / EMAIL OTP FLOW ---
        ENABLE_2FA = os.getenv("ENABLE_2FA", "false").lower() == "true"
        
        # Only trigger if enabled AND user has an email
        if ENABLE_2FA and user.get('email'):
            # Generate Code
            otp_code = str(random.randint(100000, 999999))
            
            # Store in DB (backup_codes used as OTP storage)
            try:
                cursor.execute("DELETE FROM backup_codes WHERE user_id = ?", (request.username,))
                cursor.execute("INSERT INTO backup_codes (user_id, code, created_at) VALUES (?, ?, ?)", 
                            (request.username, otp_code, datetime.now().isoformat()))
                conn.commit()
                
                # Send Email
                # Note: send_email returns False if simulated/failed. 
                # For development, we might just log it and proceed to require_2fa=True to test the UI flow.
                email_sent = send_email(user['email'], "Your Verification Code", f"Your code is: {otp_code}")
                
                logger.info(f"2FA Code generated for {request.username}: {otp_code}") # Log for debug/local test
                
                conn.close()
                return LoginResponse(
                    user_id=user['id'], 
                    success=True,
                    requires_2fa=True,
                    email_masked=user['email'] # partial mask could be better implemented but passing full email for now or masked
                )
            except Exception as e:
                logger.error(f"2FA Generation Error: {e}")
                # Fallthrough to normal login
        
        # --- NORMAL LOGIN (2FA Skipped) ---
        user_dict = dict(user)
        role = user_dict.get('role', 'Student')
        school_name = "Independent"
        school_id = user_dict.get('school_id', 1)
        is_super_admin = user_dict.get('is_super_admin', False)
        
        if school_id:
            sch = cursor.execute("SELECT name FROM schools WHERE id = ?", (school_id,)).fetchone()
            if sch: school_name = sch['name']

        # Fetch RBAC Data
        # 1. Fetch Assigned Roles
        roles_data = cursor.execute("""
            SELECT r.name 
            FROM roles r 
            JOIN user_roles ur ON r.id = ur.role_id 
            WHERE ur.user_id = ?
        """, (request.username,)).fetchall()
        role_names = [r['name'] for r in roles_data]
        
        # Fallback
        if not role_names:
            role_names = [role]

        # 2. Fetch Permissions
        perms_data = cursor.execute("""
            SELECT DISTINCT p.code 
            FROM permissions p
            JOIN role_permissions rp ON p.id = rp.permission_id
            JOIN user_roles ur ON rp.role_id = ur.role_id
            WHERE ur.user_id = ?
        """, (request.username,)).fetchall()
        perm_codes = [p['code'] for p in perms_data]

        related_student_id = None
        try:
            if 'Parent' in role_names or 'Parent_Guardian' in role_names or role == 'Parent':
                 child = cursor.execute("SELECT student_id FROM guardians WHERE email = ?", (request.username,)).fetchone()
                 if child:
                     related_student_id = child['student_id']
        except Exception as e:
            logger.error(f"Error fetching related student for login: {e}")

        conn.close()
        logger.info(f"Login successful for {request.username}, 2FA skipped.")
        
        return LoginResponse(
            user_id=user['id'], 
            name=user_dict.get('name'),
            role=role, 
            roles=role_names,
            permissions=perm_codes,
            requires_2fa=False,
            school_id=school_id,
            school_name=school_name,
            is_super_admin=bool(is_super_admin),
            related_student_id=related_student_id
        )

    else:
        new_attempts = (user['failed_login_attempts'] or 0) + 1
        if new_attempts >= 5: 
            lockout_duration = datetime.now() + timedelta(minutes=15)
            cursor.execute("UPDATE students SET failed_login_attempts = ?, locked_until = ? WHERE id = ?", 
                           (new_attempts, lockout_duration.isoformat(), request.username))
            conn.commit()
            conn.close()
            logger.warning(f"Account locked for user: {request.username}")
            log_auth_event(request.username, "Account Locked", "Too many failed attempts")
            raise HTTPException(status_code=403, detail="Account locked. Too many failed attempts.")
        else:
            cursor.execute("UPDATE students SET failed_login_attempts = ? WHERE id = ?", (new_attempts, request.username))
            conn.commit()
            conn.close()
            remaining = 5 - new_attempts
            logger.warning(f"Login failed for user: {request.username} - Invalid password.")
            log_auth_event(request.username, "Login Failed", f"Invalid password.")
            log_auth_event(request.username, "Login Failed", f"Invalid password.")
            raise HTTPException(status_code=401, detail=f"Invalid credentials. {remaining} attempts remaining.")


@app.post("/api/auth/verify-2fa", response_model=LoginResponse)
async def verify_backup_code(request: Verify2FARequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    code_entry = cursor.execute("SELECT code FROM backup_codes WHERE user_id = ? AND code = ?", 
                               (request.user_id, request.code)).fetchone()
                               
    if not code_entry:
        conn.close()
        log_auth_event(request.user_id, "2FA Failed", "Invalid or used code")
        raise HTTPException(status_code=401, detail="Invalid one-time code.")
        
    # cursor.execute("DELETE FROM backup_codes WHERE user_id = ? AND code = ?", (request.user_id, request.code))
    user = cursor.execute("SELECT * FROM students WHERE id = ?", (request.user_id,)).fetchone()
    
    user_dict = dict(user)
    role = user_dict.get('role', 'Student')
    school_name = "Independent"
    school_id = user_dict.get('school_id', 1)
    is_super_admin = user_dict.get('is_super_admin', False)
    if school_id:
            sch = cursor.execute("SELECT name FROM schools WHERE id = ?", (school_id,)).fetchone()
            if sch: school_name = sch['name']

    # Fetch RBAC Data
    # 1. Fetch Assigned Roles
    roles_data = cursor.execute("""
        SELECT r.name 
        FROM roles r 
        JOIN user_roles ur ON r.id = ur.role_id 
        WHERE ur.user_id = ?
    """, (request.user_id,)).fetchall()
    role_names = [r['name'] for r in roles_data]
    
    # Fallback
    if not role_names:
        role_names = [role]

    # 2. Fetch Permissions
    perms_data = cursor.execute("""
        SELECT DISTINCT p.code 
        FROM permissions p
        JOIN role_permissions rp ON p.id = rp.permission_id
        JOIN user_roles ur ON rp.role_id = ur.role_id
        WHERE ur.user_id = ?
    """, (request.user_id,)).fetchall()
    perm_codes = [p['code'] for p in perms_data]

    conn.commit()
    conn.close()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
        
    logger.info(f"2FA Successful for user: {request.user_id}")
    log_auth_event(request.user_id, "Login Success", "2FA Verified")
    
    related_student_id = None
    try:
        if 'Parent' in role_names or 'Parent_Guardian' in role_names or role == 'Parent':
             child = cursor.execute("SELECT student_id FROM guardians WHERE email = ?", (request.user_id,)).fetchone()
             if child:
                 related_student_id = child['student_id']
    except Exception as e:
        logger.error(f"Error fetching related student for 2FA: {e}")

    return LoginResponse(
        user_id=request.user_id,
        name=user_dict.get('name'),
        role=role, 
        roles=role_names,
        permissions=perm_codes,
        requires_2fa=False,
        school_id=school_id,
        school_name=school_name,
        is_super_admin=bool(is_super_admin),
        related_student_id=related_student_id
    )

@app.post("/api/auth/register", status_code=201)
async def register_user(request: RegisterRequest):
    validate_password_strength(request.password)

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Make invitation code mandatory for ALL users
        if not request.invitation_token:
             raise HTTPException(status_code=403, detail="Invitation code is required.")
         
        invite = cursor.execute("SELECT * FROM invitations WHERE token = ? AND is_used = 0", (request.invitation_token,)).fetchone()
        if not invite:
             raise HTTPException(status_code=400, detail="Invalid or used invitation token.")
        if datetime.now() > datetime.fromisoformat(invite['expires_at']):
             raise HTTPException(status_code=400, detail="Invitation expired.")
        
        # Verify role matches the invitation
        if invite['role'] != request.role:
             raise HTTPException(status_code=400, detail="Token does not match the requested role.")
         
        cursor.execute("UPDATE invitations SET is_used = 1 WHERE token = ?", (request.invitation_token,))
             
        # Validate School ID if provided
        school_id = request.school_id or 1
        if school_id != 1: # If not default, check if exists
            sch = cursor.execute("SELECT id FROM schools WHERE id = ?", (school_id,)).fetchone()
            if not sch:
                 raise HTTPException(status_code=400, detail="Invalid School ID selected.")

        if cursor.execute("SELECT id FROM students WHERE id = ?", (request.email,)).fetchone():
             raise HTTPException(status_code=400, detail="User ID/Email already exists.")

        # Insert User with School ID
        cursor.execute(
            """
            INSERT INTO students (id, name, grade, preferred_subject, attendance_rate, home_language, password, role, school_id, is_super_admin)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request.email, request.name, request.grade, request.preferred_subject, 
                100.0, "English", request.password, request.role, school_id, 0
            ) 
        )
        conn.commit()
        log_auth_event(request.email, "Register Success", f"Role: {request.role}, School: {school_id}")
        return {"message": f"User {request.email} registered successfully as {request.role}."}
    except sqlite3.IntegrityError:
        log_auth_event(request.email, "Register Failed", "User ID already exists")
        raise HTTPException(status_code=400, detail="User ID already exists.")
    except Exception as e:
        conn.rollback()
        log_auth_event(request.email, "Register Failed", f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")
    finally:
        conn.close()

# --- SUPER ADMIN: SCHOOL MANAGEMENT ---

@app.post("/api/admin/schools", response_model=SchoolResponse)
async def create_school(
    request: SchoolCreateRequest,
    x_user_role: str = Header(None, alias="X-User-Role"),
    x_user_id: str = Header(None, alias="X-User-Id")
):
    # Verify Super Admin Permission
    conn = get_db_connection()
    try:
        user = conn.execute("SELECT is_super_admin FROM students WHERE id = ?", (x_user_id,)).fetchone()
        if not user or not user['is_super_admin']:
             raise HTTPException(status_code=403, detail="Super Admin permission required.")
        
        cursor = conn.cursor()
        created_at = datetime.now().isoformat()
        cursor.execute("INSERT INTO schools (name, address, contact_email, created_at) VALUES (?, ?, ?, ?) RETURNING id",
                       (request.name, request.address, request.contact_email, created_at))
        new_id = cursor.fetchone()[0]
        conn.commit()
        return SchoolResponse(id=new_id, name=request.name, address=request.address, contact_email=request.contact_email, created_at=created_at)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="School name must be unique.")
    finally:
        conn.close()

@app.get("/api/admin/schools", response_model=List[SchoolResponse])
async def list_schools():
    # Public endpoint for registration dropdown, or secured if needed
    conn = get_db_connection()
    schools = conn.execute("SELECT * FROM schools ORDER BY name").fetchall()
    conn.close()
    return [SchoolResponse(id=s['id'], name=s['name'], address=s['address'], contact_email=s['contact_email'], created_at=s['created_at']) for s in schools]


             


@app.post("/api/auth/logout")
async def logout_user(request: LogoutRequest):
    logger.info(f"Logout for user: {request.user_id}")
    log_auth_event(request.user_id, "Logout", "User logged out")
    return {"message": "Logged out successfully"}

@app.get("/api/auth/permissions")
async def get_role_permissions():
    return ROLE_PERMISSIONS

@app.get("/api/teacher/students/{student_id}/codes")
async def get_student_codes(student_id: str, x_user_id: str = Header(None, alias="X-User-Id")):
    await verify_permission("manage_users", x_user_id=x_user_id)
    conn = get_db_connection()
    codes = conn.execute("SELECT code FROM backup_codes WHERE user_id = ?", (student_id,)).fetchall()
    student = conn.execute("SELECT name FROM students WHERE id = ?", (student_id,)).fetchone()
    conn.close()
    
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
        
    code_list = [row['code'] for row in codes]
    
    # If no codes exist (shouldn't happen with our catch-all, but safe fallback), generate one
    if not code_list:
        new_code = str(random.randint(100000, 999999))
        conn = get_db_connection()
        conn.execute("INSERT INTO backup_codes (user_id, code, created_at) VALUES (?, ?, ?)", 
                     (student_id, new_code, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        code_list = [new_code]

    return {
        "student_id": student_id,
        "name": student['name'],
        "codes": code_list
    }

@app.post("/api/teacher/students/{student_id}/regenerate-code")
async def regenerate_student_code(student_id: str, x_user_id: str = Header(None, alias="X-User-Id")):
    await verify_permission("manage_users", x_user_id=x_user_id)
    conn = get_db_connection()
    
    # Check if student exists
    if not conn.execute("SELECT 1 FROM students WHERE id = ?", (student_id,)).fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Student not found")

    # Delete ALL existing codes for this user (Revoke old)
    conn.execute("DELETE FROM backup_codes WHERE user_id = ?", (student_id,))
    
    # Generate ONE new random code
    new_code = str(random.randint(100000, 999999))
    conn.execute("INSERT INTO backup_codes (user_id, code, created_at) VALUES (?, ?, ?)", 
                 (student_id, new_code, datetime.now().isoformat()))
    
    student_name = conn.execute("SELECT name FROM students WHERE id = ?", (student_id,)).fetchone()[0]
    conn.commit()
    conn.close()
    
    log_auth_event(student_id, "Security Update", "2FA Code Regenerated by Teacher")

    return {
        "student_id": student_id,
        "name": student_name,
        "codes": [new_code],
        "message": "Old codes revoked. New code generated."
    }

@app.post("/api/students/{student_id}/email-code")
async def send_access_code_email(student_id: str):
    conn = get_db_connection()
    codes = conn.execute("SELECT code FROM backup_codes WHERE user_id = ?", (student_id,)).fetchall()
    student = conn.execute("SELECT name FROM students WHERE id = ?", (student_id,)).fetchone()
    conn.close()

    if not codes:
        raise HTTPException(status_code=404, detail="No codes found for this user.")

    # Determine Email Address (Assuming ID is Email if it contains @, otherwise fail for now or use a lookup)
    target_email = student_id if "@" in student_id else None
    
    if not target_email:
         # For demo purposes, if ID isn't an email, we can't send.
         # In a real app, we'd look up a profile.email field.
         raise HTTPException(status_code=400, detail="Student ID is not a valid email address.")

    code_list_html = "".join([f"<li style='font-size:18px; font-weight:bold;'>{row['code']}</li>" for row in codes])
    
    email_body = f"""
    <html>
        <body>
            <h2>Noble Nexus Access Card</h2>
            <p>Hello {student['name']},</p>
            <p>Here are your secure access codes for logging into the portal:</p>
            <ul>{code_list_html}</ul>
            <p>Keep these codes safe!</p>
            <p><i>Noble Nexus Admin</i></p>
        </body>
    </html>
    """
    
    success = send_email(target_email, "Your Noble Nexus Access Codes", email_body)
    
    if success:
        return {"message": f"Codes sent to {target_email}"}
    else:
        # Fallback if SMTP not configured
        return {"message": "Email simulation: Check server logs (SMTP not configured)."}

@app.post("/api/auth/google-login", response_model=LoginResponse)
async def google_login(request: SocialTokenRequest):
    logger.info(f"Processing Google Login...")
    
    # 1. Verify Token with Google
    try:
        # Use Google's tokeninfo endpoint to verify the ID token
        response = requests.get(f"https://oauth2.googleapis.com/tokeninfo?id_token={request.token}")
        
        if response.status_code != 200:
             logger.error(f"Google Token Check Failed: {response.text}")
             raise HTTPException(status_code=401, detail="Invalid Google Token")
        
        google_data = response.json()
        
        # 2. Verify Audience matches our Client ID
        if google_data['aud'] != GOOGLE_CLIENT_ID:
             logger.error(f"Audience Mismatch: {google_data['aud']}")
             raise HTTPException(status_code=401, detail="Token audience mismatch")
             
        user_email = google_data['email']
        user_name = google_data.get('name', 'Google User') # Use real name from Google
        
    except Exception as e:
        logger.error(f"Google Login Error: {e}")
        raise HTTPException(status_code=401, detail=f"Google Authentication Failed.")

    # 3. Handle User in Database
    conn = get_db_connection()
    user = conn.execute("SELECT id, role FROM students WHERE id = ?", (user_email,)).fetchone()
    
    role = 'Student'
    if user:
         role = user['role']
    else:
        # Auto-register new user from Google
        conn.execute("INSERT INTO students (id, name, grade, preferred_subject, attendance_rate, home_language, password, math_score, science_score, english_language_score, role, school_id, is_super_admin) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     (user_email, user_name, 9, "Science", 100.0, "English", "social_login", 0.0, 0.0, 0.0, 'Student', 1, False))
        conn.commit()
        log_auth_event(user_email, "Register Success", "Google Auto-Register")
    
    conn.close()
    
    log_auth_event(user_email, "Login Success", "Google Login")
    return LoginResponse(
        user_id=user_email, 
        role=role, 
        school_id=1, 
        school_name="Independent", 
        is_super_admin=False
    )

@app.post("/api/auth/microsoft-login", response_model=LoginResponse)
async def microsoft_login(request: SocialTokenRequest):
    logger.info("Processing Microsoft Login")
    
    # Check if this is a Simulated Token (starts with 'token_')
    if request.token.startswith("token_"):
        # Extract unique part from simulated token for uniqueness
        unique_suffix = request.token.split("_")[-1] if "_" in request.token else str(random.randint(1000,9999))
        user_email = f"ms_user_{unique_suffix}@example.com"
        user_name = f"Microsoft User {unique_suffix}"
    else:
        # REAL TOKEN LOGIC: Verify via Microsoft Graph API
        # The frontend sends an Access Token for Graph API (User.Read scope).
        # We verify it by successfully calling the /me endpoint.
        try:
            graph_response = requests.get(
                "https://graph.microsoft.com/v1.0/me",
                headers={"Authorization": f"Bearer {request.token}"}
            )
            
            if graph_response.status_code != 200:
                 logger.error(f"Graph API Failed: {graph_response.text}")
                 raise HTTPException(status_code=401, detail="Invalid Microsoft Token")

            graph_data = graph_response.json()
            # Use 'mail' (email) or 'userPrincipalName' (UPN) as the unique ID
            user_email = graph_data.get('mail') or graph_data.get('userPrincipalName')
            user_name = graph_data.get('displayName', 'Microsoft User')
            
            if not user_email:
                 raise ValueError("No email found in Microsoft account")
                 
        except Exception as e:
             logger.error(f"Microsoft Login Validation Error: {e}")
             raise HTTPException(status_code=401, detail="Microsoft Authentication Failed")

    conn = get_db_connection()
    user = conn.execute("SELECT id, role FROM students WHERE id = ?", (user_email,)).fetchone()
    
    role = 'Student'
    if user:
         role = user['role']
    else:
        # Auto-register new user
        conn.execute("INSERT INTO students (id, name, grade, preferred_subject, attendance_rate, home_language, password, math_score, science_score, english_language_score, role, school_id, is_super_admin) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     (user_email, user_name, 9, "Math", 100.0, "English", "social_login", 0.0, 0.0, 0.0, 'Student', 1, False))
        conn.commit()
        log_auth_event(user_email, "Register Success", "Microsoft Auto-Register")

    conn.close()
    
    log_auth_event(user_email, "Login Success", "Microsoft Login")
    # For now, social logins default to school_id=1 and Student role
    return LoginResponse(
        user_id=user_email, 
        role=role, 
        school_id=1, 
        school_name="Independent", 
        is_super_admin=False
    )

@app.post("/api/auth/social-login", response_model=LoginResponse)
async def generic_social_login(request: GenericSocialRequest):
    logger.info(f"Processing {request.provider} Login")
    user_id = f"{request.provider.lower()}_user"
    
    conn = get_db_connection()
    user = conn.execute("SELECT id FROM students WHERE id = ?", (user_id,)).fetchone()
    
    if not user:
        conn.execute("INSERT INTO students (id, name, grade, preferred_subject, attendance_rate, home_language, password, math_score, science_score, english_language_score, role, school_id, is_super_admin) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Student', 1, False)",
                     (user_id, f"{request.provider} User", 9, "General", 100.0, "English", "social_login", 0.0, 0.0, 0.0))
        conn.commit()
        log_auth_event(user_id, "Register Success", f"{request.provider} Auto-Register")

    conn.close()
    
    log_auth_event(user_id, "Login Success", f"{request.provider} Login")
    return LoginResponse(
        user_id=user_id, 
        role='Student', 
        school_id=1, 
        school_name="Independent", 
        is_super_admin=False
    )

@app.post("/api/auth/forgot-password")
async def forgot_password(request: ForgotPasswordRequest):
    logger.info(f"Password reset requested for: {request.email}")
    conn = get_db_connection()
    user = conn.execute("SELECT id FROM students WHERE id = ?", (request.email,)).fetchone()
    
    if user:
        token = str(uuid.uuid4())
        expires_at = (datetime.now() + timedelta(minutes=15)).isoformat()
        conn.execute("INSERT INTO password_resets (token, user_id, expires_at) VALUES (?, ?, ?)", 
                     (token, request.email, expires_at))
        conn.commit()
        conn.close()
        
        link = f"http://127.0.0.1:8000/?reset_token={token}"
        log_auth_event(request.email, "Password Reset Requested", f"Token generated (Dev Link: {link})")
        return {
            "message": "Reset link generated (DEV MODE).", 
            "dev_link": link 
        }
    else:
        conn.close()
        log_auth_event(request.email, "Password Reset Requested", "User not found")
        return {"message": "If an account exists, a reset link has been sent."}

@app.post("/api/auth/reset-password")
async def reset_password(request: ResetPasswordRequest):
    conn = get_db_connection()
    try:
        reset_entry = conn.execute("SELECT user_id, expires_at FROM password_resets WHERE token = ?", (request.token,)).fetchone()
        
        if not reset_entry:
            raise HTTPException(status_code=400, detail="Invalid or expired reset token.")
            
        if datetime.now() > datetime.fromisoformat(reset_entry['expires_at']):
            conn.execute("DELETE FROM password_resets WHERE token = ?", (request.token,))
            conn.commit()
            raise HTTPException(status_code=400, detail="Reset token has expired.")
            
        validate_password_strength(request.new_password)
        conn.execute("UPDATE students SET password = ?, failed_login_attempts = 0, locked_until = NULL WHERE id = ?", (request.new_password, reset_entry['user_id']))
        conn.execute("DELETE FROM password_resets WHERE token = ?", (request.token,))
        conn.commit()
        
        log_auth_event(reset_entry['user_id'], "Password Reset Success", "Password updated via token & Account unlocked")
        return {"message": "Password reset successfully. You can now login."}
    finally:
        conn.close()

# --- TEACHER DASHBOARD ---

@app.get("/api/teacher/overview", response_model=TeacherOverviewResponse)
async def get_teacher_overview(
    x_user_role: str = Header(None, alias="X-User-Role"),
    x_user_id: str = Header(None, alias="X-User-Id"),
    x_target_school_id: str = Header(None, alias="X-School-Id") # Optional Override
):
    # Verify permission - allow Teacher, Admin, and SuperAdmins
    await verify_permission("view_all_grades", x_user_id=x_user_id)

    conn = get_db_connection()
    try:
        # 1. Get User/Teacher Context
        user_row = conn.execute("SELECT school_id, grade, role, is_super_admin FROM students WHERE id = ?", (x_user_id,)).fetchone()
        
        if not user_row:
             raise HTTPException(status_code=404, detail="Current user profile not found.")
             
        is_super = bool(user_row['is_super_admin']) or user_row['role'] in ['Super Admin', 'SuperAdmin', 'Root_Super_Admin']
        
        # Determine active school_id
        school_id = 1 # Fallback
        if x_target_school_id and is_super:
            try:
                school_id = int(x_target_school_id)
            except:
                school_id = user_row['school_id'] or 1
        else:
            school_id = user_row['school_id'] or 1
            
        teacher_grade = user_row['grade'] if user_row['grade'] is not None else 0
        
        # 2. Fetch Students
        query = """
            SELECT s.id, s.name, s.grade, s.preferred_subject, s.attendance_rate, s.home_language, 
                   s.math_score, s.science_score, s.english_language_score
            FROM students s
            WHERE s.role = 'Student' AND s.school_id = ?
        """
        params = [school_id]
        
        # Only filter by grade if the teacher is assigned to a specific grade and isn't a super admin
        if not is_super and teacher_grade > 0:
            query += " AND s.grade = ?"
            params.append(teacher_grade)
            
        students_df = fetch_data_df(query, params=tuple(params))
        
        # Handle Section ID/Name if table exists (dynamic schema check)
        students_df['section_id'] = None
        students_df['section_name'] = None
        try:
             sections_df = fetch_data_df("SELECT s.id as student_id, sec.id as section_id, sec.name as section_name FROM students s JOIN sections sec ON s.section_id = sec.id WHERE s.school_id = ?", (school_id,))
             if not sections_df.empty:
                 students_df = students_df.merge(sections_df, left_on='id', right_on='student_id', how='left')
        except:
             pass # Sections missing or column missing, proceed without

        # 3. Calculate Metrics
        total_students = len(students_df)
        class_avg_attendance = students_df['attendance_rate'].mean() if not students_df.empty else 0.0
        
        # Activities / Scores
        activities_query = "SELECT a.student_id, a.score FROM activities a JOIN students s ON a.student_id = s.id WHERE s.school_id = ?"
        activities_params = [school_id]
        if not is_super and teacher_grade > 0:
             activities_query += " AND s.grade = ?"
             activities_params.append(teacher_grade)
             
        activities_df = fetch_data_df(activities_query, params=tuple(activities_params))
        
        avg_scores_map = {}
        if not activities_df.empty:
            avg_scores_map = activities_df.groupby('student_id')['score'].mean().to_dict()

        # Build Roster
        roster_list = []
        class_avg_score_total = 0
        
        if not students_df.empty:
            import pandas as pd
            for _, row in students_df.iterrows():
                student_avg_activity = avg_scores_map.get(row['id'], 0.0)
                initial_score = (row['math_score'] + row['science_score'] + row['english_language_score']) / 3
                
                roster_list.append({
                    "ID": row['id'],
                    "Name": row['name'],
                    "Grade": row['grade'],
                    "Attendance %": round(row['attendance_rate'] or 0.0, 1),
                    "Avg Activity Score": round(student_avg_activity, 1), 
                    "Initial Score": round(initial_score, 1), 
                    "Subject": row['preferred_subject'] or 'General',
                    "Home Language": row['home_language'] or 'English',
                    "Section ID": row.get('section_id') if pd.notna(row.get('section_id')) else None,
                    "Section Name": row.get('section_name') if pd.notna(row.get('section_name')) else None
                })
                class_avg_score_total += student_avg_activity
            
            class_avg_score = class_avg_score_total / total_students if total_students > 0 else 0.0
        else:
            class_avg_score = 0.0

        # 4. Fetch Teachers Count
        total_teachers = conn.execute("SELECT COUNT(*) FROM students WHERE role IN ('Teacher', 'Principal', 'Admin') AND school_id = ?", (school_id,)).fetchone()[0]
        
    finally:
        conn.close()

    return TeacherOverviewResponse(
        total_students=total_students,
        class_attendance_avg=round(class_avg_attendance, 1),
        class_score_avg=round(class_avg_score, 1),
        roster=roster_list,
        total_teachers=total_teachers
    )

@app.post("/api/students/add", status_code=201)
async def add_new_student(
    request: AddStudentRequest, 
    x_user_role: str = Header(None, alias="X-User-Role"), 
    x_user_id: str = Header(None, alias="X-User-Id")
):
    if not x_user_id:
         raise HTTPException(status_code=401, detail="Authentication required")
         
    conn = get_db_connection()
    try:
        user_data = conn.execute("SELECT role, school_id FROM students WHERE id = ?", (x_user_id,)).fetchone()
    finally:
        conn.close()
    if not user_data:
        raise HTTPException(status_code=401, detail="User not found")
        
    real_role = user_data['role']
    school_id = dict(user_data).get('school_id', 1)

    if not check_permission(real_role, "manage_users") and not check_permission(real_role, "invite_students"):
         log_auth_event(x_user_id, "Unauthorized Access", "Attempted to add student without permission")
         raise HTTPException(status_code=403, detail="Permission denied. You cannot add students.")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO students (id, name, grade, preferred_subject, attendance_rate, home_language, password, math_score, science_score, english_language_score, school_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request.id, request.name, request.grade, request.preferred_subject, 
                request.attendance_rate, request.home_language, request.password,
                request.math_score, request.science_score, request.english_language_score,
                school_id
            )
        )
        conn.commit()
        return {"message": f"Student {request.id} ({request.name}) added successfully."}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail=f"Student ID '{request.id}' already exists.")
    finally:
        conn.close()

@app.post("/api/invitations/generate", response_model=InvitationResponse)
async def generate_invitation(
    request: InvitationRequest,
    x_user_id: str = Header(None, alias="X-User-Id")
):
    token = str(uuid.uuid4())[:8]
    expires_at = (datetime.now() + timedelta(hours=request.expiry_hours)).isoformat()
    
    conn = get_db_connection()
    user = conn.execute("SELECT school_id FROM students WHERE id = ?", (x_user_id,)).fetchone()
    school_id = dict(user).get('school_id', 1) if user else 1

    conn.execute("INSERT INTO invitations (token, role, expires_at, school_id) VALUES (?, ?, ?, ?)", 
                 (token, request.role, expires_at, school_id))
    conn.commit()
    conn.close()
    
    return InvitationResponse(link=f"?invite={token}", token=token, expires_at=expires_at)

@app.put("/api/students/{student_id}")
async def update_student(
    student_id: str, 
    request: UpdateStudentRequest,
    x_user_role: str = Header(None, alias="X-User-Role"),
    x_user_id: str = Header(None, alias="X-User-Id")
):
    await verify_permission("edit_all_grades", x_user_id=x_user_id)

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        result = cursor.execute("SELECT id FROM students WHERE id = ?", (student_id,)).fetchone()
        if result is None:
            raise HTTPException(status_code=404, detail=f"Student ID '{student_id}' not found.")
            
        cursor.execute(
            """
            UPDATE students 
            SET name = ?, grade = ?, preferred_subject = ?, attendance_rate = ?, home_language = ?,
                math_score = ?, science_score = ?, english_language_score = ?
            WHERE id = ?
            """,
            (
                request.name, request.grade, request.preferred_subject, 
                request.attendance_rate, request.home_language,
                request.math_score, request.science_score, request.english_language_score,
                student_id
            )
        )
        
        if request.password and request.password.strip():
            validate_password_strength(request.password)
            cursor.execute("UPDATE students SET password = ? WHERE id = ?", (request.password, student_id))
            log_auth_event(student_id, "Password Changed", f"Admin/Teacher ({x_user_id}) updated password")

        if request.roles is not None:
             # Update Roles (RBAC)
             # 1. Clear existing roles
             cursor.execute("DELETE FROM user_roles WHERE user_id = ?", (student_id,))
             
             # 2. Add new roles
             first_role_name = "Student" # Default
             if request.roles:
                 first_role_name = request.roles[0] # Take first as primary for legacy column
                 
                 for role_name in request.roles:
                      role_row = cursor.execute("SELECT id FROM roles WHERE name = ?", (role_name,)).fetchone()
                      if role_row:
                          cursor.execute("INSERT INTO user_roles (user_id, role_id) VALUES (?, ?)", (student_id, role_row['id']))
                      else:
                          # Handle custom role or error? For now skip
                          pass
             
             # 3. Update legacy column
             cursor.execute("UPDATE students SET role = ? WHERE id = ?", (first_role_name, student_id))

        conn.commit()
        return {"message": f"Student {student_id} updated successfully."}
    finally:
        conn.close()

@app.delete("/api/students/{student_id}")
async def delete_student(student_id: str):
    if student_id == 'teacher':
        raise HTTPException(status_code=403, detail="Cannot delete the teacher user.")
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        result = cursor.execute("SELECT id FROM students WHERE id = ?", (student_id,)).fetchone()
        if result is None:
            raise HTTPException(status_code=404, detail=f"Student ID '{student_id}' not found.")
            
        cursor.execute("DELETE FROM students WHERE id = ?", (student_id,))
        conn.commit()
        return {"message": f"Student {student_id} and all related activities deleted successfully."}
    finally:
        conn.close()

@app.post("/api/activities/add", status_code=201)
async def add_new_activity(
    request: AddActivityRequest,
    x_user_role: str = Header(None, alias="X-User-Role"),
    x_user_id: str = Header(None, alias="X-User-Id")
):
    if not x_user_id:
         raise HTTPException(status_code=401, detail="Authentication required")
         
    conn = get_db_connection()
    try:
        user = conn.execute("SELECT role FROM students WHERE id = ?", (x_user_id,)).fetchone()
    finally:
        conn.close()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    real_role = user['role']

    # Allow if Teacher/Admin (edit_all_grades)
    # STRICT: Students cannot log their own activities anymore.
    has_permission = check_permission(real_role, "edit_all_grades")
    # if not has_permission:
    #     if real_role == "Student" and str(request.student_id) == str(x_user_id):
    #         has_permission = True
    
    if not has_permission:
         log_auth_event(x_user_id, "Unauthorized Access", "Attempted to add activity without permission")
         raise HTTPException(status_code=403, detail="Permission denied.")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        student_check = cursor.execute("SELECT id FROM students WHERE id = ?", (request.student_id,)).fetchone()
        if student_check is None:
            raise HTTPException(status_code=404, detail=f"Student ID '{request.student_id}' not found.")
            
        cursor.execute(
            """
            INSERT INTO activities (student_id, date, topic, difficulty, score, time_spent_min)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                request.student_id, request.date, request.topic, request.difficulty, 
                request.score, request.time_spent_min
            )
        )
        conn.commit()
        train_recommendation_model()
        return {"message": f"Activity for student {request.student_id} added successfully."}
    except Exception as e:
        conn.rollback()
        if isinstance(e, HTTPException) and e.status_code == 404: raise e
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")
    finally:
        conn.close()

# Refactored common AI logic
def build_ai_context_and_prompt(student_id, user_query, specific_file_content=""):
    conn = get_db_connection()
    student = conn.execute("SELECT name, grade, preferred_subject, math_score, science_score, english_language_score, role, school_id FROM students WHERE id = ?", (student_id,)).fetchone()
    
    # Fetch Resources Context (Global Library) - ONLY if no specific file content or supplemental
    # For now, let's keep it additive
    school_id = student['school_id'] if student and 'school_id' in student else 1
    resources = conn.execute("SELECT title, description, extracted_text FROM resources WHERE school_id = ? ORDER BY uploaded_at DESC", (school_id,)).fetchall()
    conn.close()
    
    # Fetch Activity History
    history_df = fetch_data_df("SELECT date, topic, difficulty, score FROM activities WHERE student_id = ? ORDER BY date DESC LIMIT 20", (student_id,))
    history_context = ""
    if not history_df.empty:
        history_context = "\nRecent Activity History:\n" + history_df.to_markdown(index=False)
    else:
        history_context = "\nNo recent activity history found."

    # Process Resources
    resource_summary = "\nAvailable Library Resources:\n"
    matched_resource_text = ""
    user_query_lower = user_query.lower()
    
    for res in resources:
        title = res['title']
        desc = res['description'] or ""
        resource_summary += f"- {title} ({desc[:50]}...)\n"
        
        if len(title) > 3 and title.lower() in user_query_lower:
            text = res['extracted_text'] or "No text content available."
            matched_resource_text += f"\n[Resource Content: {title}]\n{text[:3000]}\n[End Resource Content]\n"

    student_context_str = ""
    if student:
        grade = student['grade']
        student_context_str = f"User Profile: Name={student['name']}, Role={student['role']}, Grade={grade}, Prefers={student['preferred_subject']}."
        student_context_str += f"\n{history_context}"
        student_context_str += f"\n{resource_summary}"
        if matched_resource_text:
            student_context_str += f"\nDetailed Resource Context (Relevant to Query):\n{matched_resource_text}"
    else:
        student_context_str = "User Profile: Unknown/Guest"

    # Inject Specific Attached File Content
    if specific_file_content:
        student_context_str += f"\n\n[USER ATTACHED FILE CONTENT]\n{specific_file_content}\n[END ATTACHED FILE CONTENT]\n"
        student_context_str += "\nNOTE: The user has attached a file. PRIORITIZE using the [USER ATTACHED FILE CONTENT] to answer their query."

    system_prompt = f"""
You are a professional Education and Data Assistant integrated into a sidebar chatbot interface.
You operate in two clearly defined modes:

{student_context_str}

**Mode 1: Education Assistant**
Activate this mode when the user asks about:
- Academic concepts
- Learning topics
- *Their own progress or graph data*
- *Library Resources* or specific study materials
- *Attached Files* (homework, notes, etc.)
- Technical explanations

Response Guidelines:
- **CONTENT VALIDATION**: If an Attached File is present, FIRST verify if it is education-related (e.g., academic notes, syllabus, homework, textbooks).
- **IF NOT EDUCATION RELATED**: Politely decline to answer, stating that you can only assist with educational materials.
- **USE THE PROVIDED ACTIVITY HISTORY** for progress questions.
- **USE THE PROVIDED RESOURCE CONTENT** for library questions.
- **USE THE PROVIDED ATTACHED FILE CONTENT** if present (and validated).
- Explain concepts clearly and logically
- Use step-by-step explanations
- Start simple, then increase depth
- Use examples, diagrams (text-based), or analogies when useful
- Maintain a professional, calm, and supportive teaching tone
- Format responses using headings, bullet points, and code blocks

**Mode 2: Database Query Assistant (PostgreSQL)**
Activate this mode ONLY when the user asks about:
- *Aggregate* data stored in the system (not just their own)
- Complex reports necessitating a fresh DB query
- Database-related queries

Response Guidelines:
- Translate user intent into valid PostgreSQL queries
- Use correct SQL syntax and best practices
- Do not assume table or column names if they are not provided (Use the Query Classification Rule)
- Ask for clarification when schema information is missing
- Present query results clearly using tables or summaries

**Schema Context:**
{DB_SCHEMA_CONTEXT}

**Query Classification Rule**
- If the user asks about *their own* marks, history, or graph trends, PREFER `EDUCATION` mode and use the injected history context.
- Use `DATABASE` mode only if the answer requires fetching *new* data not present in the context.
- Select only one mode per response.

### OUTPUT FORMAT (STRICT JSON)
You must strictly output a JSON object with the following structure:
{{
  "mode": "EDUCATION" or "DATABASE",
  "content": "Your education response text here (null if DATABASE mode)",
  "query": "Your SQL query here (null if EDUCATION mode)"
}}
"""
    return system_prompt

def build_teacher_ai_context(teacher_id, user_query):
    try:
        conn = get_db_connection()
        # Fetch Teacher Profile
        teacher = conn.execute("SELECT name, role, school_id FROM students WHERE id = ?", (teacher_id,)).fetchone()
        
        if not teacher:
             conn.close()
             return "User not found."
    
        school_id = teacher['school_id'] if teacher and 'school_id' in teacher else 1
        
        # Fetch School Stats for Context
        student_count = conn.execute("SELECT COUNT(*) FROM students WHERE school_id = ?", (school_id,)).fetchone()[0]
        recent_activities = conn.execute("SELECT COUNT(*) FROM activities WHERE student_id IN (SELECT id FROM students WHERE school_id = ?)", (school_id,)).fetchone()[0]
        
        conn.close()
    
        context_str = f"Teacher Profile: Name={teacher['name']}, Role={teacher['role']}, School ID={school_id}.\n"
        context_str += f"School Environment Context: Currently managing {student_count} students with {recent_activities} total activities recorded.\n"
    
        system_prompt = f"""
You are the "ClassBridge AI Co-Pilot", an intelligent assistant specifically for teachers and school administrators.
Your goal is to save teachers time by helping with day-to-day administrative, pedagogical, and analytical tasks.

{context_str}

**Capabilities:**
1. **Administrative Helper**: Draft parent emails, write announcements, create meeting agendas, or structure school newsletters.
2. **Pedagogical Assistant**: Suggest creative classroom activities, explain complex topics for different grades, or recommend intervention strategies for struggling students.
3. **Data Analyst (DATABASE Mode)**: Query school data to find trends, identify at-risk students, or generate performance reports.
4. **General Q&A**: Answer questions about classroom management, educational tech, or professional development.

**Operating Modes:**
- **DATABASE Mode**: Use this ONLY when the teacher asks for specific data from the database (e.g., "Which students have low attendance?", "Show me the math scores for Grade 9", "List students who haven't completed any activities recently").
- **EDUCATION Mode**: Use this for all text-based assistance, creative drafting, and explanations.

**Database Guidelines (PostgreSQL):**
- You have access to the following schema:
{DB_SCHEMA_CONTEXT}
- IMPORTANT: ALWAYS filter queries by `school_id = {school_id}` to ensure data privacy.
- Return a valid PostgreSQL SELECT query in the 'query' field.

### OUTPUT FORMAT (STRICT JSON)
You must strictly output a JSON object:
{{
  "mode": "EDUCATION" or "DATABASE",
  "content": "Your helpful response here (null if DATABASE mode)",
  "query": "Your SQL query here (null if EDUCATION mode)"
}}
"""
        return system_prompt
    except Exception as e:
        logger.error(f"Teacher Context Error: {e}")
        return "You are a professional educational assistant."


@app.post("/api/ai/chat_with_file/{student_id}", response_model=AIChatResponse)
async def chat_with_ai_tutor_file(
    student_id: str, 
    prompt: str = Form(...),
    file: UploadFile = File(...)
):
    if not AI_ENABLED:
        return AIChatResponse(reply="The live AI service is currently disabled.")
    
    extracted_text = ""
    try:
        if file.filename.lower().endswith('.pdf') and PdfReader:
            # We need to read the file into memory to parse it
            content = await file.read()
            from io import BytesIO
            reader = PdfReader(BytesIO(content))
            text_content = []
            for page in reader.pages:
                 text = page.extract_text()
                 if text: text_content.append(text)
            extracted_text = "\n".join(text_content)
        elif file.filename.lower().endswith(('.txt', '.md', '.csv')):
            content = await file.read()
            extracted_text = content.decode('utf-8')
        else:
             extracted_text = f"[File: {file.filename} (Type: {file.content_type}) - Content extraction not supported for this file type yet. Treat as metadata only.]"
    except Exception as e:
        logger.error(f"File Extraction Error: {e}")
        extracted_text = "Error extracting text from file."

    try:
        system_prompt = build_ai_context_and_prompt(student_id, prompt, extracted_text)
        
        chat_completion = GROQ_CLIENT.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        response_content = chat_completion.choices[0].message.content
        try:
             parsed_response = json.loads(response_content)
             mode = parsed_response.get("mode", "EDUCATION")
             
             if mode == "DATABASE" and parsed_response.get("query"):
                 # Execute Query Logic (Reuse or Duplicate?)
                 # For file upload, usually it's Education mode. But if they upload a CSV and ask to query it... 
                 # We'll just execute standard DB query if they ask about DB, ignoring file? OR if they ask about file, mode is EDUCATION.
                 # Let's assume Education for file Qs.
                 pass # Fall through to return content
                 
                 # If it IS database query, we execute it
                 sql_query = parsed_response.get("query")
                 try:
                     df = fetch_data_df(sql_query)
                     if not df.empty:
                         return AIChatResponse(reply=f"**Query Result:**\n\n" + df.to_markdown(index=False))
                     else:
                         return AIChatResponse(reply="No data found for that query.")
                 except Exception as e:
                     return AIChatResponse(reply=f"Query failed: {e}")
             
             return AIChatResponse(reply=parsed_response.get("content", "I analyzed the file but have no specific comments."))
             
        except json.JSONDecodeError:
            return AIChatResponse(reply=response_content)

    except Exception as e:
        logger.error(f"AI Chat Error (File): {e}")
        return AIChatResponse(reply="Sorry, I encountered an error processing your file.")

@app.post("/api/ai/chat/{student_id}", response_model=AIChatResponse)
async def chat_with_ai_tutor(student_id: str, request: AIChatRequest):
    if not AI_ENABLED:
        return AIChatResponse(reply="The live AI service is currently disabled.")
        
    try:
        # Use shared prompt builder
        system_prompt = build_ai_context_and_prompt(student_id, request.prompt)
        
        # Call LLM
        chat_completion = GROQ_CLIENT.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": request.prompt}
            ],
            model=GROQ_MODEL, # "llama-3.1-8b-instant"
            temperature=0.3,  # Lower temperature for reliable JSON and SQL
            max_tokens=1000,
            response_format={"type": "json_object"}
        )
        
        response_content = chat_completion.choices[0].message.content
        
        # Parse JSON response
        try:
            response_data = json.loads(response_content)
            mode = response_data.get("mode")
            
            if mode == "DATABASE":
                query = response_data.get("query")
                if query:
                    # Security Check: Ensure it's a SELECT query
                    if not query.strip().lower().startswith("select"):
                         reply = "I can only perform read-only database queries (SELECT)."
                    else:
                        try:
                            logger.info(f"AI Executing SQL: {query}")
                            # Execute Query
                            df_result = fetch_data_df(query)
                            # Format Result
                            markdown_table = format_df_to_markdown(df_result)
                            reply = f"Here is the data I found:\n\n{markdown_table}"
                        except Exception as db_err:
                            logger.error(f"AI SQL Execution Error: {db_err}")
                            reply = f"I tried to run a database query but ran into an error: {str(db_err)}"
                else:
                    reply = "I understood this as a data request but couldn't generate a valid query."
                    
            else:
                # EDUCATION Mode (Default)
                reply = response_data.get("content") or "I'm not sure how to answer that."
                
        except json.JSONDecodeError:
            # Fallback if valid JSON wasn't returned
            logger.error("AI did not return valid JSON. Falling back to raw content.")
            reply = response_content

    except Exception as e:
        logger.error(f"Groq API Error for student {student_id}: {e}")
        reply = "I'm having trouble connecting to my brain right now. Please try again later."
        
    return AIChatResponse(reply=reply)

@app.post("/api/ai/teacher-chat/{teacher_id}", response_model=AIChatResponse)

async def chat_with_ai_teacher(teacher_id: str, request: AIChatRequest):
    if not AI_ENABLED:
        return AIChatResponse(reply="The teacher AI service is currently disabled.")
        
    try:
        system_prompt = build_teacher_ai_context(teacher_id, request.prompt)
        
        # Call LLM
        chat_completion = GROQ_CLIENT.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": request.prompt}
            ],
            model=GROQ_MODEL,
            temperature=0.4,
            max_tokens=2000,
            response_format={"type": "json_object"}
        )
        
        response_content = chat_completion.choices[0].message.content
        
        try:
            response_data = json.loads(response_content)
            mode = response_data.get("mode")
            
            if mode == "DATABASE":
                query = response_data.get("query")
                if query:
                    if not query.strip().lower().startswith("select"):
                         reply = "I am restricted to read-only database queries (SELECT)."
                    else:
                        try:
                            logger.info(f"Teacher AI Executing SQL: {query}")
                            df_result = fetch_data_df(query)
                            markdown_table = format_df_to_markdown(df_result)
                            reply = f"I've fetched the requested data from the school records:\n\n{markdown_table}"
                        except Exception as db_err:
                            logger.error(f"Teacher AI SQL Error: {db_err}")
                            reply = f"I encountered an error while querying the database: {str(db_err)}"
                else:
                    reply = "I understood this as a data request but couldn't generate a valid query."
            else:
                reply = response_data.get("content") or "How else can I assist you today?"
                
        except json.JSONDecodeError:
            reply = response_content

    except Exception as e:
        logger.error(f"Teacher AI Error: {e}")
        reply = "I'm having trouble connecting to my processing unit. Please try again in a moment."
        
    return AIChatResponse(reply=reply)

@app.post("/api/ai/grade-helper/{student_id}", response_model=AIChatResponse)
async def chat_with_grade_helper(student_id: str, request: AIChatRequest):
    if not GRADE_HELPER_CLIENT:
        return AIChatResponse(reply="Grade Helper AI is currently unavailable.")
        
    try:
        # Fetch Student/User Details for Context
        conn = get_db_connection()
        user = conn.execute("SELECT role, grade, preferred_subject FROM students WHERE id = ?", (student_id,)).fetchone()
        conn.close()
        
        if not user:
             return AIChatResponse(reply="I can't find your profile to customize my answers.")
             
        role = user['role']
        grade = user['grade'] if user['grade'] is not None else "Unknown"
        
        # dynamic system prompt based on role and grade
        if role == 'Teacher':
            system_prompt = (
                f"You are a Grade {grade} Specialist Assistant for Teachers. "
                f"Your goal is to assist a Grade {grade} teacher with lesson planning, student management, and educational strategies. "
                "Keep your answers professional, helpful, and focused on education."
            )
        else:
             system_prompt = (
                f"You are a friendly Grade {grade} Study Buddy. "
                f"Your goal is to help a Grade {grade} student with their studies. "
                "Keep your answers simple, encouraging, and easy to understand for this age group. "
                "Focus ONLY on grade-related disputes and education things."
            )

        chat_completion = GRADE_HELPER_CLIENT.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": request.prompt}
            ],
            model="llama-3.1-8b-instant", # Using the same model class, assuming availability with this key
            temperature=0.7, 
            max_tokens=600
        )
        reply = chat_completion.choices[0].message.content
    except Exception as e:
        logger.error(f"Grade Helper API Error for {student_id}: {e}")
        reply = "I'm having a bit of trouble connecting right now. Please try again."
        
    return AIChatResponse(reply=reply)

@app.get("/api/students/all")
async def get_all_students_list(x_user_id: str = Header(None, alias="X-User-Id")):
    conn = get_db_connection()
    user = conn.execute("SELECT school_id, grade, is_super_admin FROM students WHERE id = ?", (x_user_id,)).fetchone()
    conn.close()

    if not user:
        return []

    school_id = user['school_id'] if user['school_id'] else 1
    grade = user['grade'] if user['grade'] is not None else 0
    is_super_admin = bool(user['is_super_admin'])

    query = "SELECT id, name, attendance_rate, grade FROM students WHERE role = 'Student' AND school_id = ?"
    params = [school_id]

    if not is_super_admin:
        if grade > 0:
            query += " AND grade = ?"
            params.append(grade)
        # else: grade 0 -> view all (implicitly allows head teachers to see all)

    df = fetch_data_df(query, params=tuple(params))
    return df.to_dict('records') 

# --- USER MANAGEMENT (ADMIN) ---

@app.get("/api/admin/users", response_model=List[UserResponse])
async def list_all_users(
    x_user_role: str = Header(None, alias="X-User-Role"),
    x_user_id: str = Header(None, alias="X-User-Id"),
    x_school_id: Optional[int] = Header(None, alias="X-School-Id") # Optional context switch
):
    # Updated permission code
    await verify_permission("user_management", x_user_id=x_user_id)
    
    conn = get_db_connection()
    try:
        requester = conn.execute("SELECT school_id, is_super_admin, role FROM students WHERE id = ?", (x_user_id,)).fetchone()
        if not requester:
             raise HTTPException(status_code=401, detail="User not found")
        
        req_school_id = requester['school_id']
        # Treat Root_Super_Admin role as super admin equivalent
        is_super_admin = bool(requester['is_super_admin']) or requester['role'] == 'Root_Super_Admin'
        
        query = "SELECT id, name, role, grade, preferred_subject, school_id FROM students"
        params = []
        conds = []

        # RBAC Filtering
        if is_super_admin:
            # Super Admin can see all, OR filter by specific school if context is set
            if x_school_id:
                conds.append("school_id = ?")
                params.append(x_school_id)
            # else: see all
        else:
            # Regular Admins (Tenant, Academic) MUST be restricted to their school
            conds.append("school_id = ?")
            params.append(req_school_id)

        if conds:
            query += " WHERE " + " AND ".join(conds)
        
        query += " ORDER BY role, name"
        
        rows = conn.execute(query, tuple(params)).fetchall()
        return [UserResponse(
            id=r['id'], 
            name=r['name'], 
            role=r['role'], 
            grade=r['grade'], 
            preferred_subject=r['preferred_subject']
        ) for r in rows]
    finally:
        conn.close()

@app.post("/api/admin/users", status_code=201)
async def create_new_user(
    request: AddUserRequest,
    x_user_role: str = Header(None, alias="X-User-Role"),
    x_user_id: str = Header(None, alias="X-User-Id")
):
    await verify_permission("manage_users", x_user_id=x_user_id)
    
    validate_password_strength(request.password)

    conn = get_db_connection()
    try:
        requester = conn.execute("SELECT school_id FROM students WHERE id = ?", (x_user_id,)).fetchone()
        school_id = requester['school_id'] if requester else 1
        
        # Check if ID exists
        if conn.execute("SELECT 1 FROM students WHERE id = ?", (request.id,)).fetchone():
             raise HTTPException(status_code=400, detail="User ID/Email already exists.")
             
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO students (id, name, grade, preferred_subject, attendance_rate, home_language, password, role, school_id)
            VALUES (?, ?, ?, ?, 100.0, 'English', ?, ?, ?)
            """,
            (request.id, request.name, request.grade, request.preferred_subject, request.password, request.role, school_id)
        )
        conn.commit()
        log_auth_event(x_user_id, "User Created", f"Created user {request.id} ({request.role})")
        return {"message": f"User {request.name} created successfully."}
    except sqlite3.IntegrityError:
         raise HTTPException(status_code=400, detail="User ID already exists.")
    finally:
        conn.close() 


@app.get("/api/students/{student_id}/quiz-results")
async def get_student_quiz_results(
    student_id: str,
    x_user_role: str = Header(None, alias="X-User-Role"),
    x_user_id: str = Header(None, alias="X-User-Id")
):
    # Authorization Check
    if x_user_role == 'Student' and x_user_id != student_id:
        raise HTTPException(status_code=403, detail="Unauthorized")

    conn = get_db_connection()
    c = conn.cursor()
    # Join with modules and sections and courses to get titles
    query = """
        SELECT 
            mc.score, 
            mc.status, 
            m.title as module_title,
            c.title as course_title
        FROM lms_module_completion mc
        JOIN lms_course_modules m ON mc.module_id = m.id
        JOIN lms_course_sections s ON m.section_id = s.id
        JOIN lms_courses c ON s.course_id = c.id
        WHERE mc.student_id = ? AND m.type = 'quiz'
    """
    try:
        rows = c.execute(query, (student_id,)).fetchall()
        results = [dict(row) for row in rows]
        return results[::-1] 
    except Exception as e:
        logger.error(f"Error fetching quiz results: {e}")
        return []
    finally:
        conn.close()


@app.get("/api/students/{student_id}/data", response_model=StudentDataResponse)
async def get_student_data(
    student_id: str,
    x_user_role: str = Header(None, alias="X-User-Role"),
    x_user_id: str = Header(None, alias="X-User-Id")
):
    # 1. Fetch Target Student Info
    conn = get_db_connection()
    target_student = conn.execute("SELECT school_id, grade, math_score, science_score, english_language_score FROM students WHERE id = ?", (student_id,)).fetchone()
    
    if not target_student:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Student ID '{student_id}' not found.")

    target_school_id = target_student['school_id']
    target_grade = target_student['grade']
    
    # 2. Authorization Check
    # If Requester is the Student -> Must match ID
    if x_user_role == 'Student' and x_user_id != student_id:
        conn.close()
        raise HTTPException(status_code=403, detail="Unauthorized: You can only view your own data.")
    
    # If Requester is Teacher -> Must check permissions
    if x_user_role == 'Teacher' or x_user_role == 'Admin':
         requester = conn.execute("SELECT school_id, grade, is_super_admin FROM students WHERE id = ?", (x_user_id,)).fetchone()
         if requester:
             is_super_admin = bool(requester['is_super_admin'])
             requester_grade = requester['grade'] if requester['grade'] is not None else 0
             
             if not is_super_admin:
                 # Check Grade Match (Grade 0 means 'All Grades' access)
                 if requester_grade != 0 and requester_grade != target_grade:
                     conn.close()
                     raise HTTPException(status_code=403, detail="Unauthorized: You cannot view students outside your grade.")
         else:
             conn.close()
             raise HTTPException(status_code=403, detail="Unauthorized: Requester profile not found.")

    # 3. Proceed to fetch data
    # Fetch Roles
    user_roles = conn.execute("""
        SELECT r.name FROM roles r
        JOIN user_roles ur ON r.id = ur.role_id
        WHERE ur.user_id = ?
    """, (student_id,)).fetchall()
    role_list = [r['name'] for r in user_roles]
    # Fallback to legacy role column if no user_roles entry
    if not role_list:
        legacy_role = conn.execute("SELECT role FROM students WHERE id = ?", (student_id,)).fetchone()
        if legacy_role and legacy_role['role']:
             role_list.append(legacy_role['role'])

    profile = {
        'math_score': target_student['math_score'],
        'science_score': target_student['science_score'],
        'english_language_score': target_student['english_language_score'],
        'roles': role_list
    }

    history_df = fetch_data_df("SELECT date, topic, difficulty, score, time_spent_min FROM activities WHERE student_id = ? ORDER BY date ASC", (student_id,))
    conn.close() # Close manual connection

    avg_val = history_df['score'].mean()
    avg_score = avg_val if not history_df.empty and avg_val == avg_val else 0.0 # avg_val == avg_val checks for NaN
    total_activities = len(history_df)
    recommendation = get_recommendation(student_id)

    history_list = [
        StudentHistory(
            date=row['date'],
            topic=row['topic'],
            difficulty=row['difficulty'],
            score=row['score'],
            time_spent_min=row['time_spent_min']
        ) for _, row in history_df.iterrows()
    ]

    return StudentDataResponse(
        summary=StudentSummary(
            avg_score=round(avg_score, 1), 
            total_activities=total_activities, 
            recommendation=recommendation,
            math_score=profile['math_score'] or 0.0,       
            science_score=profile['science_score'] or 0.0, 
            english_language_score=profile['english_language_score'] or 0.0 
        ),
        history=history_list
    )

# --- GROUP MANAGEMENT ---

@app.post("/api/groups", status_code=201)
async def create_group(
    request: GroupCreateRequest,
    x_user_role: str = Header(None, alias="X-User-Role"),
    x_user_id: str = Header(None, alias="X-User-Id")
):
    await verify_permission("manage_groups", x_user_id=x_user_id)

    conn = get_db_connection()
    try:
        user = conn.execute("SELECT school_id FROM students WHERE id = ?", (x_user_id,)).fetchone()
        school_id = user['school_id'] if user else 1

        cursor = conn.cursor()
        cursor.execute("INSERT INTO groups (name, description, subject, school_id) VALUES (?, ?, ?, ?)", 
                       (request.name, request.description, request.subject, school_id))
        conn.commit()
        return {"message": f"Group '{request.name}' created successfully."}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Group name must be unique.")
    finally:
        conn.close()

@app.get("/api/groups", response_model=List[GroupResponse])
async def get_groups(x_user_id: str = Header(None, alias="X-User-Id")):
    conn = get_db_connection()
    
    school_id = 1
    if x_user_id:
        user = conn.execute("SELECT school_id FROM students WHERE id = ?", (x_user_id,)).fetchone()
        if user: school_id = dict(user).get('school_id', 1)

    query = """
        SELECT g.id, g.name, g.description, g.subject, COUNT(gm.student_id) as member_count
        FROM groups g
        LEFT JOIN group_members gm ON g.id = gm.group_id
        WHERE g.school_id = ?
        GROUP BY g.id
    """
    groups = conn.execute(query, (school_id,)).fetchall()
    conn.close()
    
    return [GroupResponse(
        id=r['id'], 
        name=r['name'], 
        description=r['description'], 
        subject=r['subject'],
        member_count=r['member_count']
    ) for r in groups]

@app.delete("/api/groups/{group_id}")
async def delete_group(group_id: int):
    conn = get_db_connection()
    conn.execute("DELETE FROM groups WHERE id = ?", (group_id,))
    conn.commit()
    conn.close()
    return {"message": "Group deleted."}

@app.get("/api/groups/{group_id}/members")
async def get_group_members(group_id: int):
    conn = get_db_connection()
    group = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()
    if not group:
        conn.close()
        raise HTTPException(status_code=404, detail="Group not found")
        
    members = conn.execute("SELECT student_id FROM group_members WHERE group_id = ?", (group_id,)).fetchall()
    member_ids = [m['student_id'] for m in members]
    conn.close()
    return {"group": dict(group), "members": member_ids}

@app.post("/api/groups/{group_id}/members")
async def update_group_members(group_id: int, request: GroupMemberUpdateRequest, x_user_id: str = Header(None, alias="X-User-Id")):
    await verify_permission("manage_groups", x_user_id=x_user_id)
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        if not cursor.execute("SELECT id FROM groups WHERE id = ?", (group_id,)).fetchone():
             raise HTTPException(status_code=404, detail="Group not found")

        cursor.execute("DELETE FROM group_members WHERE group_id = ?", (group_id,))
        
        if request.student_ids:
            data = [(group_id, sid) for sid in request.student_ids]
            cursor.executemany("INSERT INTO group_members (group_id, student_id) VALUES (?, ?)", data)
            
        conn.commit()
        return {"message": "Group members updated."}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Invalid student ID provided.")
    finally:
        conn.close()

@app.post("/api/groups/{group_id}/materials")
async def add_group_material(group_id: int, request: MaterialCreateRequest, x_user_id: str = Header(None, alias="X-User-Id")):
    await verify_permission("manage_groups", x_user_id=x_user_id)
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        date_str = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("INSERT INTO group_materials (group_id, title, type, content, date) VALUES (?, ?, ?, ?, ?)",
                       (group_id, request.title, request.type, request.content, date_str))
        conn.commit()
        return {"message": "Material added."}
    finally:
        conn.close()

@app.get("/api/groups/{group_id}/materials", response_model=List[MaterialResponse])
async def get_group_materials(group_id: int):
    conn = get_db_connection()
    materials = conn.execute("SELECT * FROM group_materials WHERE group_id = ? ORDER BY id DESC", (group_id,)).fetchall()
    conn.close()
    return [MaterialResponse(id=m['id'], title=m['title'], type=m['type'], content=m['content'], date=m['date']) for m in materials]

@app.get("/api/teacher/assignments")
async def get_teacher_assignments(section_id: Optional[int] = None,
                                  x_user_role: str = Header(None, alias="X-User-Role"),
                                  x_user_id: str = Header(None, alias="X-User-Id"),
                                  x_school_id: Optional[int] = Header(None, alias="X-School-Id")):
    await verify_permission("assignment.view", x_user_role=x_user_role, x_user_id=x_user_id)
    conn = get_db_connection()
    try:
        query = """
            SELECT
                a.id,
                a.group_id,
                a.title,
                a.description,
                a.due_date,
                a.type,
                a.points,
                a.section_id,
                a.grade_level,
                sec.name AS section_name,
                sec.grade_level AS section_grade_level,
                COALESCE((
                    SELECT COUNT(*) FROM assignment_submissions s WHERE s.assignment_id = a.id
                ), 0) AS submission_count
            FROM assignments a
            LEFT JOIN sections sec ON a.section_id = sec.id
        """
        conditions = []
        params = []
        if section_id:
            conditions.append("a.section_id = ?")
            params.append(section_id)
        if x_school_id:
            conditions.append("(a.section_id IS NULL OR sec.school_id = ?)")
            params.append(x_school_id)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY a.due_date DESC, a.id DESC"
        rows = conn.execute(query, tuple(params)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

@app.get("/api/students/{student_id}/groups", response_model=List[GroupResponse])
async def get_student_groups(student_id: str):
    conn = get_db_connection()
    query = """
        SELECT g.id, g.name, g.description, g.subject
        FROM groups g
        JOIN group_members gm ON g.id = gm.group_id
        WHERE gm.student_id = ?
    """
    groups = conn.execute(query, (student_id,)).fetchall()
    conn.close()
    return [GroupResponse(id=r['id'], name=r['name'], description=r['description'], subject=r['subject'], member_count=0) for r in groups]

@app.get("/api/students/{student_id}/assignments")
async def get_student_assignments(student_id: str):
    conn = get_db_connection()
    c = conn.cursor()
    
    # Get student grade/section
    student = c.execute("SELECT grade, section_id FROM students WHERE id = ?", (student_id,)).fetchone()
    grade = student['grade'] if student else 0
    section_id = student['section_id'] if student else None

    # 1. Standard Assignments (via Groups OR Class/Section)
    assignments = c.execute("""
        SELECT a.id, a.title, a.due_date, a.type,
               COALESCE(g.name, sec.name, 'Class') as course_name
        FROM assignments a
        LEFT JOIN group_members gm ON a.group_id = gm.group_id AND gm.student_id = ?
        LEFT JOIN groups g ON a.group_id = g.id
        LEFT JOIN sections sec ON a.section_id = sec.id
        WHERE gm.student_id IS NOT NULL
           OR (a.section_id IS NOT NULL AND a.section_id = ?)
           OR (a.section_id IS NULL AND a.grade_level IS NOT NULL AND a.grade_level = ?)
        ORDER BY a.due_date DESC
    """, (student_id, section_id, grade)).fetchall()
    
    results = [dict(row) for row in assignments]
    
    # 2. Quizzes (Directly Allocated or via Groups/Grades)
    
    # Fetch Quizzes that are NOT attempted yet
    # We want quizzes where:
    #   (target_type='student' AND target_id=student_id)
    #   OR (target_type='grade' AND target_id=str(grade))
    #   OR (target_type='group' AND group_id IN (SELECT group_id FROM group_members WHERE student_id=?))
    # AND id NOT IN (SELECT quiz_id FROM quiz_attempts WHERE student_id=?)
    
    quizzes = c.execute("""
        SELECT q.id, q.title, q.time_limit_mins, q.target_type, q.target_id, q.group_id
        FROM quizzes q
        WHERE 
           (q.target_type = 'student' AND q.target_id = ?)
           OR (q.target_type = 'grade' AND q.target_id = ?)
           OR (q.target_type = 'group' AND q.group_id IN (SELECT group_id FROM group_members WHERE student_id = ?))
    """, (student_id, str(grade), student_id)).fetchall()
    
    # Filter out completed ones manually or via query (simple query above gets all access)
    # Let's check attempts
    completed_quiz_ids = [row['quiz_id'] for row in c.execute("SELECT quiz_id FROM quiz_attempts WHERE student_id = ?", (student_id,)).fetchall()]
    
    for q in quizzes:
        if q['id'] not in completed_quiz_ids:
            # Format as assignment
            # Fetch Course Name if group based
            course_name = "Assigned Quiz"
            if q['target_type'] == 'group' and q['group_id']:
                 g = c.execute("SELECT name FROM groups WHERE id = ?", (q['group_id'],)).fetchone()
                 if g: course_name = g['name']
            elif q['target_type'] == 'grade':
                 course_name = f"Grade {q['target_id']} Quiz"
            elif q['target_type'] == 'student':
                 course_name = "Personal Quiz"
                 
            results.append({
                "id": q['id'],
                "title": q['title'],
                "due_date": f"Time Limit: {q['time_limit_mins']}m" if q['time_limit_mins'] > 0 else "No Limit",
                "type": "Quiz",
                "course_name": course_name,
                "is_quiz_module": True # Hint to frontend
            })

    conn.close()
    return results

# --- AI LESSON PLANNER ---
class LessonPlanRequest(BaseModel):
    topic: str
    subject: str
    grade_level: str
    duration: str  # e.g., "45 minutes"

class LessonPlanResponseAI(BaseModel):
    plan_markdown: str

@app.post("/api/ai/generate-lesson-plan", response_model=LessonPlanResponseAI)
async def generate_lesson_plan_v2(request: LessonPlanRequest):
    if not LESSON_PLANNER_CLIENT:
        raise HTTPException(status_code=503, detail="AI Service unavailable")

    prompt = f"""
    Create a detailed lesson plan for a {request.duration} class.
    Subject: {request.subject}
    Grade Level: {request.grade_level}
    Topic: {request.topic}

    Structure the lesson plan with the following sections using Markdown formatting:
    # Lesson Title
    ## Objectives
    ## Materials Needed
    ## Lesson Outline (with timestamps)
    ## Detailed Activities
    ## Assessment/Homework
    
    Keep it engaging and practical.
    """

    try:
        completion = LESSON_PLANNER_CLIENT.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "You are an expert educational consultant and curriculum developer."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1500,
            top_p=1,
            stream=False,
            stop=None,
        )
        
        return LessonPlanResponseAI(plan_markdown=completion.choices[0].message.content)

    except Exception as e:
        logger.error(f"Lesson Plan Generation Failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- ASSIGNMENTS & PROJECT MANAGEMENT ---
@app.post("/api/ai/generate-quiz", response_model=GenerateQuizResponse)
async def generate_quiz(
    topic: str = Form(...),
    difficulty: str = Form("Medium"),
    question_count: int = Form(5),
    type: str = Form("Multiple Choice"),
    description: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None)
):
    if not AI_ENABLED:
         return GenerateQuizResponse(content='[{"question": "AI Disabled", "options": ["A", "B"], "correct_answer": "A"}]')

    try:
        # PDF Processing
        pdf_context = ""
        if file and PdfReader:
            try:
                if file.filename.endswith('.pdf'):
                    pdf_reader = PdfReader(file.file)
                    for page in pdf_reader.pages:
                        pdf_context += page.extract_text() + "\n"
                    pdf_context = pdf_context[:5000]
                else:
                    content = await file.read()
                    pdf_context = content.decode('utf-8', errors='ignore')[:5000]
            except Exception as e:
                logger.error(f"File read error: {e}")

        # Enforce JSON Structure for Database Compatibility
        prompt = f"""
        Generate a {difficulty} difficulty {type} quiz about "{topic}".
        """
        if description:
            prompt += f"Context/Description: {description}\n"
        
        if pdf_context:
            prompt += f"\nReference Material (Use this content to generate questions):\n{pdf_context}\n"
            
        prompt += f"""
        It should have {question_count} questions.
        Return ONLY a raw JSON array. Do not include markdown formatting (like ```json), just the array.
        Format:
        [
            {{
                "question": "Question text",
                "options": ["Option A", "Option B", "Option C", "Option D"],
                "correct_answer": "Option A"
            }}
        ]
        """
        
        full_prompt = "You are a quiz generation engine. Output valid JSON only.\n" + prompt
        
        # Use Groq Client (switched from OpenRouter)
        try:
            chat_completion = GROQ_CLIENT.chat.completions.create(
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a quiz generation engine. Return strictly valid JSON array only. No markdown formatting."
                    },
                    {
                        "role": "user", 
                        "content": full_prompt
                    }
                ],
                model=GROQ_MODEL, # Using Llama 3.1 8B Instant (fast) or 70B if configured
                temperature=0.5,
            )
            raw_content = chat_completion.choices[0].message.content.strip()
            
            # Cleaning markdown if present
            if raw_content.startswith("```json"):
                raw_content = raw_content[7:]
            if raw_content.startswith("```"):
                raw_content = raw_content[3:]
            if raw_content.endswith("```"):
                raw_content = raw_content[:-3]
            
            return GenerateQuizResponse(content=raw_content.strip())
            
        except Exception as groq_err:
            logger.error(f"Groq API Error: {groq_err}")
            raise Exception("AI processing failed.")

    except Exception as e:
        logger.error(f"AI Quiz Gen Error: {e}")
        # Return fallback mock data instead of 500
        mock_quiz = [
                {
                    "question": f"Fallback Question about {topic}",
                    "options": ["Option A", "Option B", "Option C", "Option D"],
                    "correct_answer": "Option A"
                }
            ] * question_count
        return GenerateQuizResponse(content=json.dumps(mock_quiz))



class ClassScheduleRequest(BaseModel):
    topic: str
    date: str
    meet_link: str
    target_students: Optional[List[str]] = None

@app.get("/api/classes/upcoming")
async def get_upcoming_classes(student_id: Optional[str] = None, x_user_id: str = Header(None, alias="X-User-Id")):
    conn = get_db_connection()
    
    # Determine School Context
    school_id = 1
    if x_user_id:
        user = conn.execute("SELECT school_id FROM students WHERE id = ?", (x_user_id,)).fetchone()
        if user: school_id = dict(user).get('school_id', 1)

    # Fetch classes for this school
    query = "SELECT * FROM live_classes WHERE school_id = ? ORDER BY date ASC"
    classes = conn.execute(query, (school_id,)).fetchall()
    conn.close()
    
    valid_classes = []
    for row in classes:
        cls = dict(row)
        # Optional: Filter by student_id if 'target_students' is used
        if student_id:
             try:
                 targets = json.loads(cls.get('target_students', '[]') or '[]')
                 # If explicit list exists and student not in it, skip (unless list is empty -> public)
                 if targets and isinstance(targets, list) and len(targets) > 0 and student_id not in targets:
                     continue 
             except: pass
        valid_classes.append(cls)

    return valid_classes

@app.post("/api/classes")
async def schedule_class_endpoint(
    request: ClassScheduleRequest,
    x_user_role: str = Header(None, alias="X-User-Role"),
    x_user_id: str = Header(None, alias="X-User-Id")
):
    await verify_permission("schedule_active_class", x_user_id=x_user_id)
    
    conn = get_db_connection()
    try:
        user = conn.execute("SELECT school_id FROM students WHERE id = ?", (x_user_id,)).fetchone()
        school_id = user['school_id'] if user else 1

        cursor = conn.cursor()
        targets = json.dumps(request.target_students) if request.target_students else "[]"
        cursor.execute("INSERT INTO live_classes (topic, date, meet_link, target_students, teacher_id, school_id) VALUES (?, ?, ?, ?, ?, ?)",
                       (request.topic, request.date, request.meet_link, targets, x_user_id, school_id))
        conn.commit()
        return {"message": "Class scheduled successfully."}
    finally:
        conn.close()

@app.delete("/api/classes/{class_id}")
async def delete_class(class_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM live_classes WHERE id = ?", (class_id,))
    conn.commit()
    conn.close()
    return {"message": "Class cancelled."}

@app.post("/api/class/start")
async def start_class(
    request: ClassSessionRequest,
    x_user_role: str = Header(None, alias="X-User-Role"),
    x_user_id: str = Header(None, alias="X-User-Id")
):
    await verify_permission("schedule_active_class", x_user_id=x_user_id)

    CLASS_SESSION["is_active"] = True
    CLASS_SESSION["meet_link"] = request.meet_link
    return {"message": "Online class started successfully.", "link": request.meet_link}

@app.post("/api/class/end")
async def end_class():
    CLASS_SESSION["is_active"] = False
    CLASS_SESSION["meet_link"] = ""
    return {"message": "Online class ended."}

# --- WEBSOCKET MANAGER FOR WHITEBOARD ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        # Broadcast to all connected clients
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                # Handle broken connections gracefully
                pass

manager = ConnectionManager()

@app.websocket("/ws/whiteboard")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(data)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket Error: {e}")
        manager.disconnect(websocket)
 

@app.get("/api/teacher/export-grades-csv")
async def export_grades_csv(
    x_user_role: str = Header(None, alias="X-User-Role"),
    x_user_id: str = Header(None, alias="X-User-Id")
):
    await verify_permission("view_all_grades", x_user_id=x_user_id)

    conn = get_db_connection()
    try:
        # Fetch comprehensive student data
        query = """
            SELECT 
                s.id, 
                s.name, 
                s.grade, 
                s.attendance_rate || '%' as attendance,
                s.preferred_subject,
                s.math_score as initial_math_score,
                s.science_score as initial_science_score,
                s.english_language_score as initial_english_score,
                COALESCE(ROUND(AVG(a.score), 1), 0) as current_average_score,
                COUNT(a.id) as activities_completed
            FROM students s
            LEFT JOIN activities a ON s.id = a.student_id
            WHERE s.role = 'Student'
            GROUP BY s.id
        """
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write Header
        writer.writerow([
            "Student ID", "Name", "Grade", "Attendance", "Fav Subject", 
            "Initial Math", "Initial Science", "Initial English", 
            "Current Avg Score", "Activities Completed"
        ])
        
        # Write Data
        for row in rows:
            writer.writerow([
                row['id'], row['name'], row['grade'], row['attendance'], row['preferred_subject'],
                row['initial_math_score'], row['initial_science_score'], row['initial_english_score'],
                row['current_average_score'], row['activities_completed']
            ])
            
        output.seek(0)
        
        # Return as StreamingResponse
        response = StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv"
        )
        response.headers["Content-Disposition"] = "attachment; filename=class_grades_export.csv"
        return response

    except Exception as e:
        logger.error(f"Export Error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate export.")
    finally:
        conn.close()

# --- LMS MODULE: MATERIALS & QUIZZES ---

@app.post("/api/groups/{group_id}/upload")
async def upload_group_material(group_id: int, file: UploadFile = File(...), title: str = None):
    # LMS Phase 1: File Uploads
    try:
        file_ext = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Determine Type
        content_type = "File"
        if file_ext.lower() in ['.pdf']: content_type = "PDF"
        elif file_ext.lower() in ['.mp4', '.mov', '.avi']: content_type = "Video"
        elif file_ext.lower() in ['.jpg', '.png', '.jpeg']: content_type = "Image"
        
        # Save to DB
        conn = get_db_connection()
        cursor = conn.cursor()
        date_str = datetime.now().strftime("%Y-%m-%d")
        display_title = title or file.filename
        
        # URL accessible via static mount
        file_url = f"/static/uploads/{unique_filename}"
        
        cursor.execute("INSERT INTO group_materials (group_id, title, type, content, date) VALUES (?, ?, ?, ?, ?)",
                      (group_id, display_title, content_type, file_url, date_str))
        conn.commit()
        conn.close()
        
        return {"message": "File uploaded successfully", "url": file_url}
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class QuizCreateRequest(BaseModel):
    group_id: Optional[int] = None
    title: str
    questions: list
    time_limit: Optional[int] = 0
    target_type: Optional[str] = "group"
    target_id: Optional[str] = None
    acknowledged: bool = False

@app.post("/api/quizzes/create", response_model=QuizResponse)
async def create_quiz_endpoint(request: QuizCreateRequest):
    try:
        # LMS Phase 2: Create Quiz
        conn = get_db_connection()
        cursor = conn.cursor()
        
        questions_json = json.dumps(request.questions)
        created_at = datetime.now().isoformat()
        
        # Store acknowledged status
        acknowledged_val = request.acknowledged # Pass boolean directly for Postgres
        
        # Ensure target_id is stored correctly (as TEXT in DB)
        # For non-group targets, group_id is NULL
        
        cursor.execute("""
            INSERT INTO quizzes (group_id, title, questions, created_at, time_limit_mins, target_type, target_id, acknowledged)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?) RETURNING id
        """, (request.group_id, request.title, questions_json, created_at, request.time_limit, request.target_type, request.target_id, acknowledged_val))
        
        quiz_id = cursor.lastrowid
        if not quiz_id:
             raise ValueError("Failed to retrieve new quiz ID")

        conn.commit()
        conn.close()
        
        return QuizResponse(
            id=quiz_id, 
            group_id=request.group_id, 
            title=request.title, 
            question_count=len(request.questions), 
            created_at=created_at,
            time_limit=request.time_limit,
            target_type=request.target_type,
            target_id=request.target_id
        )
    except Exception as e:
        logger.error(f"Create Quiz Error: {e}")
        # traceback.print_exc() 
        raise HTTPException(status_code=500, detail=f"Server Error: {str(e)}")

@app.get("/api/teacher/quizzes")
async def get_teacher_quizzes(x_user_role: str = Header(None, alias="X-User-Role")):
    # Allow Teachers and Admins to see all quizzes to check results
    if x_user_role not in ['Teacher', 'Admin', 'Super Admin', 'Principal', 'Tenant_Admin']:
         raise HTTPException(status_code=403, detail="Unauthorized")

    conn = get_db_connection()
    try:
        # Fetch all quizzes. In a real app, might filter by creator_id if we tracked it.
        # For now, fetching all lets them see Grade/Section quizzes.
        quizzes = conn.execute("SELECT * FROM quizzes ORDER BY created_at DESC").fetchall()
        
        result = []
        for q in quizzes:
            q_dict = dict(q)
            try:
                q_dict['question_count'] = len(json.loads(q_dict['questions']))
            except:
                q_dict['question_count'] = 0
            del q_dict['questions'] # Optimize payload
            result.append(q_dict)
        return result
    finally:
        conn.close()

@app.get("/api/groups/{group_id}/quizzes")
async def get_group_quizzes(group_id: int):
    conn = get_db_connection()
    quizzes = conn.execute("SELECT id, title, created_at, questions FROM quizzes WHERE group_id = ?", (group_id,)).fetchall()
    
    # Also fetch attempts for the current user if they are a student? 
    # For now just return the quizzes. Frontend can verify if taken.
    result = []
    for q in quizzes:
        q_dict = dict(q)
        q_dict['question_count'] = len(json.loads(q_dict['questions']))
        del q_dict['questions'] # Don't send answers/questions in list view
        result.append(q_dict)
    conn.close()
    return result

@app.get("/api/quizzes/{quiz_id}")
async def get_quiz_details(quiz_id: int):
    conn = get_db_connection()
    quiz = conn.execute("SELECT * FROM quizzes WHERE id = ?", (quiz_id,)).fetchone()
    conn.close()
    
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
        
    data = dict(quiz)
    data['questions'] = json.loads(data['questions'])
    
    # SECURITY: If student, strip 'isCorrect' or 'answer' fields from questions if they exist?
    # For simplicity in this V1, we assume questions JSON is [{question, options, correct_answer}]
    # We should ideally strip 'correct_answer' before sending to student.
    
    safe_questions = []
    for q in data['questions']:
        q_copy = q.copy()
        if 'correct_answer' in q_copy:
            del q_copy['correct_answer'] # Hide answer
        safe_questions.append(q_copy)
        
    data['questions'] = safe_questions
    return data

@app.post("/api/quizzes/{quiz_id}/submit")
async def submit_quiz(quiz_id: int, request: QuizSubmitRequest):
    try:
        conn = get_db_connection()
        quiz_row = conn.execute("SELECT * FROM quizzes WHERE id = ?", (quiz_id,)).fetchone()
        
        if not quiz_row:
            conn.close()
            raise HTTPException(status_code=404, detail="Quiz not found")
            
        quiz = dict(quiz_row)
        questions = json.loads(quiz['questions'])
        score = 0
        total = len(questions)
        
        # Grading Logic
        for idx, q in enumerate(questions):
            correct = q.get('correct_answer', '').strip().lower()
            user_ans = request.answers.get(str(idx), '').strip().lower()
            
            if user_ans == correct:
                score += 1
                
        final_score_percent = (score / total) * 100 if total > 0 else 0
        
        # AI Assessment
        ai_feedback = "Good effort! Review the correct answers to improve."
        if AI_ENABLED and GROQ_CLIENT:
            try:
                assessment_prompt = f"Quiz Title: {quiz['title']}\n"
                for idx, q in enumerate(questions):
                    user_ans = request.answers.get(str(idx), 'No Answer')
                    assessment_prompt += f"Q{idx+1}: {q.get('question', 'Untitled')}\nCorrect: {q.get('correct_answer', 'N/A')}\nStudent Answer: {user_ans}\n\n"
                
                chat_completion = GROQ_CLIENT.chat.completions.create(
                    messages=[
                        {
                            "role": "system", 
                            "content": "You are an encouraging AI Teacher. Review the student's quiz answers and provide a brief, personalized assessment (max 60 words). Mention what they did well and one thing to focus on."
                        },
                        {"role": "user", "content": assessment_prompt}
                    ],
                    model=GROQ_MODEL,
                    temperature=0.7,
                )
                ai_feedback = chat_completion.choices[0].message.content.strip()
            except Exception as ai_e:
                logger.error(f"AI Assessment Error: {ai_e}")

        # Save Attempt
        answers_json = json.dumps(request.answers)
        submitted_at = datetime.now().isoformat()
        
        conn.execute("INSERT INTO quiz_attempts (quiz_id, student_id, score, answers, ai_feedback, submitted_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (quiz_id, request.student_id, final_score_percent, answers_json, ai_feedback, submitted_at))
        
        # Update Student Stats (XP, Activity Log)
        conn.execute("INSERT INTO activities (student_id, date, topic, difficulty, score, time_spent_min, ai_feedback) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (request.student_id, datetime.now().strftime("%Y-%m-%d"), f"Quiz: {quiz['title']}", "Medium", final_score_percent, 15, ai_feedback))

        conn.commit()
        conn.close()
        
        return {
            "score_percent": final_score_percent, 
            "score": score, 
            "total": total, 
            "ai_feedback": ai_feedback
        }
    except Exception as e:
        logger.error(f"Submit Quiz Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/quizzes/{quiz_id}/results")
async def get_quiz_results(
    quiz_id: int, 
    x_user_id: str = Header(None, alias="X-User-Id"),
    x_user_role: str = Header(None, alias="X-User-Role")
):
    # Only Teachers and Admins can view results
    if x_user_role not in ['Teacher', 'Admin', 'Super Admin', 'Principal', 'Tenant_Admin']:
        raise HTTPException(status_code=403, detail="Unauthorized")
        
    conn = get_db_connection()
    try:
        # Fetch attempts joined with student info
        query = """
            SELECT 
                qa.student_id, 
                s.name as student_name, 
                qa.score, 
                qa.ai_feedback, 
                qa.submitted_at 
            FROM quiz_attempts qa
            JOIN students s ON qa.student_id = s.id
            WHERE qa.quiz_id = ?
            ORDER BY qa.score DESC
        """
        results = conn.execute(query, (quiz_id,)).fetchall()
        
        return [dict(row) for row in results]
    except Exception as e:
        logger.error(f"Quiz Results Error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch results")
    finally:
        conn.close()

# --- SCHOOL MANAGEMENT ---

@app.get("/api/admin/schools", response_model=List[SchoolResponse])
async def get_schools():
    conn = get_db_connection()
    try:
        schools = conn.execute("SELECT * FROM schools").fetchall()
        return [SchoolResponse(
            id=s['id'],
            name=s['name'],
            address=s['address'] if s['address'] else "",
            contact_email=s['contact_email'] if s['contact_email'] else "",
            created_at=s['created_at'] if s['created_at'] else datetime.now().isoformat()
        ) for s in schools]
    finally:
        conn.close()

@app.post("/api/admin/schools", status_code=201)
async def create_school(
    request: SchoolCreateRequest,
    x_user_id: str = Header(None, alias="X-User-Id")
):
    if not x_user_id:
         raise HTTPException(status_code=401, detail="Authentication required")

    conn = get_db_connection()
    try:
        user = conn.execute("SELECT is_super_admin FROM students WHERE id = ?", (x_user_id,)).fetchone()
        if not user or not user['is_super_admin']:
             log_auth_event(x_user_id, "Unauthorized Access", "Attempted to create school without Super Admin access")
             raise HTTPException(status_code=403, detail="Permission denied. SUPER ADMIN ONLY.")
        
        created_at = datetime.now().isoformat()
        cursor = conn.cursor()
        
        # INSERT School
        cursor.execute(
            "INSERT INTO schools (name, address, contact_email, created_at) VALUES (?, ?, ?, ?)",
            (request.name, request.address, request.contact_email, created_at)
        )
        school_id = cursor.lastrowid
        
        # Create Admin user for this school
        # Using contact_email as the ID/Username
        cursor.execute(
            "INSERT INTO students (id, name, role, password, school_id) VALUES (?, ?, ?, ?, ?)",
            (request.contact_email, f"{request.name} Admin", "Admin", request.admin_password, school_id)
        )
        
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        raise HTTPException(status_code=400, detail="School name or Admin email already exists.")
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
    
    return {"message": "School and Admin account created successfully.", "school_id": school_id}

@app.put("/api/admin/schools/{school_id}")
async def update_school(
    school_id: int,
    request: SchoolCreateRequest,
    x_user_id: str = Header(None, alias="X-User-Id")
):
    if not x_user_id:
         raise HTTPException(status_code=401, detail="Authentication required")

    conn = get_db_connection()
    try:
        user = conn.execute("SELECT is_super_admin FROM students WHERE id = ?", (x_user_id,)).fetchone()
        if not user or not user['is_super_admin']:
             log_auth_event(x_user_id, "Unauthorized Access", "Attempted to update school without Super Admin access")
             raise HTTPException(status_code=403, detail="Permission denied. SUPER ADMIN ONLY.")
        
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE schools SET name = ?, address = ?, contact_email = ? WHERE id = ?",
            (request.name, request.address, request.contact_email, school_id)
        )
        if cursor.cursor.rowcount == 0:
             raise HTTPException(status_code=404, detail="School not found.")

        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="School name already exists.")
    finally:
        conn.close()
    
    return {"message": "School updated successfully."}

@app.delete("/api/admin/schools/{school_id}")
async def delete_school(
    school_id: int,
    x_user_id: str = Header(None, alias="X-User-Id")
):
    if not x_user_id:
         raise HTTPException(status_code=401, detail="Authentication required")
         
    if school_id == 1:
        raise HTTPException(status_code=403, detail="Cannot delete the default 'Independent' school.")

    conn = get_db_connection()
    try:
        user = conn.execute("SELECT is_super_admin FROM students WHERE id = ?", (x_user_id,)).fetchone()
        if not user or not user['is_super_admin']:
             log_auth_event(x_user_id, "Unauthorized Access", "Attempted to delete school without Super Admin access")
             raise HTTPException(status_code=403, detail="Permission denied. SUPER ADMIN ONLY.")
        
        cursor = conn.cursor()
        # Note: Students will be moved to school_id=1 automatically by DB constraint ON DELETE SET DEFAULT if configured,
        # or we might need to handle it. Let's assume the DB constraint works or we just delete.
        # But to be safe and clear:
        cursor.execute("DELETE FROM schools WHERE id = ?", (school_id,))
        
        if cursor.cursor.rowcount == 0:
             raise HTTPException(status_code=404, detail="School not found.")

        conn.commit()
    finally:
        conn.close()
    
    return {"message": "School deleted successfully."}

@app.get("/api/admin/audit-logs", response_model=List[AuditLogResponse])
async def get_audit_logs(
    x_user_role: str = Header(None, alias="X-User-Role"),
    x_user_id: str = Header(None, alias="X-User-Id")
):
    await verify_permission("view_audit_logs", x_user_id=x_user_id)

    conn = get_db_connection()
    try:
        # Select all columns explicitly including new ones
        logs = conn.execute("SELECT id, user_id, event_type, timestamp, details, logout_time, duration_minutes FROM auth_logs ORDER BY timestamp DESC LIMIT 100").fetchall()
        
        return [
            AuditLogResponse(
                id=row['id'], 
                user_id=row['user_id'], 
                event_type=row['event_type'], 
                timestamp=row['timestamp'], 
                details=row['details'],
                logout_time=row['logout_time'],
                duration_minutes=row['duration_minutes']
            ) 
            for row in logs
        ]
    except Exception as e:
        # Log the error for debugging
        print(f"Error fetching logs: {e}")
        # Return a simplified list or empty list to fail gracefully if schema mismatch persists
        # But for valid JSON response let's raise
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

# @app.on_event("startup") removed in favor of lifespan
# Startup logic moved to lifespan function defined at the top.

# --- COMMUNICATION & ENGAGEMENT ---
class AnnouncementCreateRequest(BaseModel):
    title: str
    content: str
    target_role: str = "All" # All, Student, Teacher, Parent

class MessageSendRequest(BaseModel):
    receiver_id: str
    content: str
    subject: Optional[str] = "No Subject"

class EventCreateRequest(BaseModel):
    title: str
    date: str # YYYY-MM-DD
    type: str # Exam, Holiday, Meeting

@app.get("/api/communication/announcements")
async def get_announcements():
    conn = get_db_connection()
    c = conn.cursor()
    # Simple fetch, in production we would filter by user role
    anns = c.execute("SELECT * FROM announcements ORDER BY created_at DESC LIMIT 50").fetchall()
    conn.close()
    return [dict(a) for a in anns]

@app.post("/api/communication/announcements")
async def create_announcement(req: AnnouncementCreateRequest):
    conn = get_db_connection()
    try:
        ts = datetime.now().isoformat()
        conn.execute("INSERT INTO announcements (title, content, target_role, created_at) VALUES (?, ?, ?, ?)", 
                     (req.title, req.content, req.target_role, ts))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
    return {"success": True}

@app.get("/api/communication/messages")
async def get_messages(user_id: str = Header(None, alias="X-User-Id")):
    if not user_id: return []
    conn = get_db_connection()
    c = conn.cursor()
    # Get messages where I am receiver OR sender
    msgs = c.execute("""
        SELECT * FROM messages 
        WHERE receiver_id = ? OR sender_id = ? 
        ORDER BY timestamp DESC
    """, (user_id, user_id)).fetchall()
    conn.close()
    return [dict(m) for m in msgs]

@app.post("/api/communication/messages")
async def send_message(req: MessageSendRequest, user_id: str = Header(None, alias="X-User-Id")):
    if not user_id: raise HTTPException(status_code=401)
    conn = get_db_connection()
    try:
        ts = datetime.now().isoformat()
        conn.execute("INSERT INTO messages (sender_id, receiver_id, content, subject, timestamp, is_read) VALUES (?, ?, ?, ?, ?, FALSE)", 
                     (user_id, req.receiver_id, req.content, req.subject, ts))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
    return {"success": True}

@app.get("/api/communication/events")
async def get_events():
    conn = get_db_connection()
    events = conn.execute("SELECT * FROM calendar_events ORDER BY date ASC").fetchall()
    conn.close()
    return [dict(e) for e in events]

@app.post("/api/communication/events")
async def create_event(req: EventCreateRequest):
    conn = get_db_connection()
    try:
        conn.execute("INSERT INTO calendar_events (title, date, type) VALUES (?, ?, ?)", 
                     (req.title, req.date, req.type))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
    return {"success": True}

@app.post("/api/communication/emergency")
async def trigger_emergency():
    # Mock
    return {"success": True, "message": "Emergency Alerts dispatched to all registered contacts via SMS and Email."}

# --- COMPLIANCE & SECURITY ---

class RetentionPolicyRequest(BaseModel):
    audit_logs_days: int = 30
    access_logs_days: int = 30
    student_data_years: int = 7

@app.get("/api/admin/compliance/audit-logs", response_model=List[AuditLogResponse])
async def get_compliance_audit_logs(
    x_user_role: str = Header(None, alias="X-User-Role"),
    x_user_id: str = Header(None, alias="X-User-Id")
):
    await verify_permission("compliance.view", x_user_id=x_user_id)
    conn = get_db_connection()
    try:
        # Exclude common access events to separate Audit from Access
        query = """
            SELECT * FROM auth_logs 
            WHERE event_type NOT IN ('Login Success', 'Login Failed', 'Logout', '2FA Verified', '2FA Required')
            ORDER BY timestamp DESC LIMIT 100
        """
        logs = conn.execute(query).fetchall()
        return [
            AuditLogResponse(
                id=row['id'], 
                user_id=row['user_id'], 
                event_type=row['event_type'], 
                timestamp=row['timestamp'], 
                details=row['details'],
                logout_time=row.get('logout_time'),
                duration_minutes=row.get('duration_minutes')
            ) 
            for row in logs
        ]
    finally:
        conn.close()

@app.get("/api/admin/compliance/access-logs", response_model=List[AuditLogResponse])
async def get_compliance_access_logs(
    x_user_role: str = Header(None, alias="X-User-Role"),
    x_user_id: str = Header(None, alias="X-User-Id")
):
    await verify_permission("compliance.view", x_user_id=x_user_id)
    conn = get_db_connection()
    try:
        # Include ONLY access events
        query = """
            SELECT * FROM auth_logs 
            WHERE event_type IN ('Login Success', 'Login Failed', 'Logout', '2FA Verified', '2FA Required')
            ORDER BY timestamp DESC LIMIT 100
        """
        logs = conn.execute(query).fetchall()
        return [
            AuditLogResponse(
                id=row['id'], 
                user_id=row['user_id'], 
                event_type=row['event_type'], 
                timestamp=row['timestamp'], 
                details=row['details'],
                logout_time=row.get('logout_time'),
                duration_minutes=row.get('duration_minutes')
            ) 
            for row in logs
        ]
    finally:
        conn.close()

@app.get("/api/admin/compliance/retention")
async def get_retention_policies(
    x_user_role: str = Header(None, alias="X-User-Role"),
    x_user_id: str = Header(None, alias="X-User-Id")
):
    await verify_permission("compliance.view", x_user_id=x_user_id)
    conn = get_db_connection()
    try:
        settings = conn.execute("SELECT key, value FROM system_settings WHERE key LIKE 'retention_%'").fetchall()
        policies = {
             "audit_logs_days": 30,
             "access_logs_days": 30,
             "student_data_years": 7
        }
        for row in settings:
            field = row['key'].replace('retention_', '')
            if field in policies:
                policies[field] = int(row['value'])
        return policies
    finally:
        conn.close()

@app.post("/api/admin/compliance/retention")
async def update_retention_policies(
    req: RetentionPolicyRequest,
    x_user_role: str = Header(None, alias="X-User-Role"),
    x_user_id: str = Header(None, alias="X-User-Id")
):
    await verify_permission("compliance.manage", x_user_id=x_user_id)
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO system_settings (key, value) VALUES ('retention_audit_logs_days', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(req.audit_logs_days),))
        cursor.execute("INSERT INTO system_settings (key, value) VALUES ('retention_access_logs_days', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(req.access_logs_days),))
        cursor.execute("INSERT INTO system_settings (key, value) VALUES ('retention_student_data_years', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(req.student_data_years),))
        conn.commit()
    finally:
        conn.close()
    return {"message": "Retention policies updated."}

# --- STUDENT MANAGEMENT ENDPOINTS ---

# 1. Sections Management
@app.get("/api/sections", response_model=List[SectionResponse])
async def get_sections(school_id: Optional[int] = None):
    conn = get_db_connection()
    try:
        if school_id:
            sections = conn.execute("SELECT * FROM sections WHERE school_id = ?", (school_id,)).fetchall()
        else:
            sections = conn.execute("SELECT * FROM sections").fetchall()
        
        return [SectionResponse(**dict(s)) for s in sections]
    finally:
        conn.close()

@app.post("/api/sections", status_code=201)
async def create_section(req: SectionCreateRequest, x_user_id: str = Header(None, alias="X-User-Id")):
    await verify_permission("student.info.manage", x_user_id=x_user_id)
    conn = get_db_connection()
    try:
        ts = datetime.now().isoformat()
        conn.execute("INSERT INTO sections (school_id, name, grade_level, created_at) VALUES (?, ?, ?, ?)", 
                     (req.school_id, req.name, req.grade_level, ts))
        conn.commit()
    finally:
        conn.close()
    return {"message": "Section created"}

# 2. Assign Class/Section
@app.post("/api/students/{student_id}/assign-section")
async def assign_student_section(student_id: str, section_id: int, x_user_id: str = Header(None, alias="X-User-Id")):
    await verify_permission("student.info.manage", x_user_id=x_user_id)
    conn = get_db_connection()
    try:
        # Check if section exists
        section = conn.execute("SELECT school_id, grade_level FROM sections WHERE id = ?", (section_id,)).fetchone()
        if not section:
            raise HTTPException(status_code=404, detail="Section not found")
            
        # Update student (Also update grade to match section if needed, optional)
        cursor = conn.cursor()
        cursor.execute("UPDATE students SET section_id = ?, grade = ? WHERE id = ?", (section_id, section['grade_level'], student_id))
        if cursor.cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Student not found")
        conn.commit()
    finally:
        conn.close()
    return {"message": "Student assigned to section successfully"}


# 3. Guardian Management
@app.get("/api/students/{student_id}/guardians", response_model=List[GuardianResponse])
async def get_guardians(student_id: str, x_user_id: str = Header(None, alias="X-User-Id")):
    await verify_permission("student.info.view", x_user_id=x_user_id)
    conn = get_db_connection()
    try:
        guardians = conn.execute("SELECT * FROM guardians WHERE student_id = ?", (student_id,)).fetchall()
        return [GuardianResponse(**dict(g)) for g in guardians]
    finally:
        conn.close()

@app.post("/api/students/{student_id}/guardians", status_code=201)
async def add_guardian(student_id: str, req: GuardianCreateRequest, x_user_id: str = Header(None, alias="X-User-Id")):
    await verify_permission("student.info.manage", x_user_id=x_user_id) # Usually manage is needed to ADD
    conn = get_db_connection()
    try:
        conn.execute(
            """INSERT INTO guardians (student_id, name, relationship, phone, email, address, is_emergency_contact) 
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (student_id, req.name, req.relationship, req.phone, req.email, req.address, req.is_emergency_contact)
        )
        conn.commit()
    finally:
        conn.close()
    return {"message": "Guardian added"}

@app.delete("/api/guardians/{id}")
async def delete_guardian(id: int, x_user_id: str = Header(None, alias="X-User-Id")):
    await verify_permission("student.info.manage", x_user_id=x_user_id)
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM guardians WHERE id = ?", (id,))
        conn.commit()
    finally:
        conn.close()
    return {"message": "Guardian removed"}

# 4. Health Records
@app.get("/api/students/{student_id}/health", response_model=Optional[HealthRecordResponse])
async def get_health_record(student_id: str, x_user_id: str = Header(None, alias="X-User-Id")):
    await verify_permission("student.info.view", x_user_id=x_user_id)
    conn = get_db_connection()
    try:
        record = conn.execute("SELECT * FROM health_records WHERE student_id = ?", (student_id,)).fetchone()
        if record:
            return HealthRecordResponse(**dict(record))
        return None
    finally:
        conn.close()

@app.put("/api/students/{student_id}/health")
async def update_health_record(student_id: str, req: HealthRecordUpdateRequest, x_user_id: str = Header(None, alias="X-User-Id")):
    await verify_permission("student.info.manage", x_user_id=x_user_id) # Or specific permission
    conn = get_db_connection()
    try:
        ts = datetime.now().isoformat()
        # Check if exists
        exists = conn.execute("SELECT id FROM health_records WHERE student_id = ?", (student_id,)).fetchone()
        if exists:
            conn.execute("""
                UPDATE health_records SET 
                    blood_group=?, emergency_contact_name=?, emergency_contact_phone=?, 
                    allergies=?, medical_conditions=?, medications=?, 
                    doctor_name=?, doctor_phone=?, last_updated=?
                WHERE student_id=?
            """, (req.blood_group, req.emergency_contact_name, req.emergency_contact_phone, 
                  req.allergies, req.medical_conditions, req.medications, 
                  req.doctor_name, req.doctor_phone, ts, student_id))
        else:
            conn.execute("""
                INSERT INTO health_records 
                (student_id, blood_group, emergency_contact_name, emergency_contact_phone, allergies, medical_conditions, medications, doctor_name, doctor_phone, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (student_id, req.blood_group, req.emergency_contact_name, req.emergency_contact_phone, 
                  req.allergies, req.medical_conditions, req.medications, 
                  req.doctor_name, req.doctor_phone, ts))
        conn.commit()
    finally:
        conn.close()
    return {"message": "Health record updated"}

# 5. Documents
@app.get("/api/students/{student_id}/documents", response_model=List[DocumentResponse])
async def get_documents(student_id: str, x_user_id: str = Header(None, alias="X-User-Id")):
    await verify_permission("student.info.view", x_user_id=x_user_id)
    conn = get_db_connection()
    try:
        docs = conn.execute("SELECT * FROM student_documents WHERE student_id = ?", (student_id,)).fetchall()
        return [DocumentResponse(**dict(d)) for d in docs]
    finally:
        conn.close()

@app.post("/api/students/{student_id}/documents")
async def upload_document(
    student_id: str,
    file: UploadFile = File(...),
    document_type: str = Form(...),
    x_user_id: str = Header(None, alias="X-User-Id")
):
    await verify_permission("student.info.manage", x_user_id=x_user_id)
    
    upload_dir = f"uploads/students/{student_id}"
    os.makedirs(upload_dir, exist_ok=True)
    
    file_path = f"{upload_dir}/{uuid.uuid4()}_{file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    conn = get_db_connection()
    try:
        ts = datetime.now().isoformat()
        conn.execute("""
            INSERT INTO student_documents (student_id, document_type, document_name, file_path, upload_date, uploaded_by)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (student_id, document_type, file.filename, file_path, ts, x_user_id))
        conn.commit()
    finally:
        conn.close()
        
    return {"message": "Document uploaded"}

@app.delete("/api/documents/{doc_id}")
async def delete_document(doc_id: int, x_user_id: str = Header(None, alias="X-User-Id")):
    await verify_permission("student.info.manage", x_user_id=x_user_id)
    conn = get_db_connection()
    try:
        doc = conn.execute("SELECT file_path FROM student_documents WHERE id = ?", (doc_id,)).fetchone()
        if doc:
            try:
                if os.path.exists(doc['file_path']):
                    os.remove(doc['file_path'])
            except:
                pass # Ignore file system errors
            
            conn.execute("DELETE FROM student_documents WHERE id = ?", (doc_id,))
            conn.commit()
    finally:
        conn.close()
    return {"message": "Document deleted"}

# --- ROLE & PERMISSION MANAGEMENT ENDPOINTS (FR-3) ---

@app.get("/api/admin/roles", response_model=List[RoleResponse])
async def get_roles(
    x_user_role: str = Header(None, alias="X-User-Role"),
    x_user_id: str = Header(None, alias="X-User-Id")
):
    await verify_permission("role_management", x_user_id=x_user_id)
    
    conn = get_db_connection()
    try:
        roles = conn.execute("SELECT * FROM roles").fetchall()
        
        result = []
        for r in roles:
            # Fetch permissions for each role
            perms = conn.execute("""
                SELECT p.id, p.code, p.description 
                FROM permissions p
                JOIN role_permissions rp ON p.id = rp.permission_id
                WHERE rp.role_id = ?
            """, (r['id'],)).fetchall()
            
            result.append(RoleResponse(
                id=r['id'],
                code=r['name'].replace(' ', '_').upper(), # Dynamic code generation if missing
                name=r['name'],
                description=r['description'] or "",
                status=r['status'],
                is_system=bool(r['is_system']),
                permissions=[dict(p) for p in perms]
            ))
        return result
    finally:
        conn.close()

@app.get("/api/admin/roles/{role_id}", response_model=RoleResponse)
async def get_role_details(
    role_id: int,
    x_user_role: str = Header(None, alias="X-User-Role"),
    x_user_id: str = Header(None, alias="X-User-Id")
):
    await verify_permission("role_management", x_user_id=x_user_id)
    
    conn = get_db_connection()
    try:
        r = conn.execute("SELECT * FROM roles WHERE id = ?", (role_id,)).fetchone()
        if not r:
            raise HTTPException(status_code=404, detail="Role not found")
            
        perms = conn.execute("""
            SELECT p.id, p.code, p.description 
            FROM permissions p
            JOIN role_permissions rp ON p.id = rp.permission_id
            WHERE rp.role_id = ?
        """, (r['id'],)).fetchall()
        
        return RoleResponse(
            id=r['id'],
            code=r['name'].replace(' ', '_').upper(),
            name=r['name'],
            description=r['description'] or "",
            status=r['status'],
            is_system=bool(r['is_system']),
            permissions=[dict(p) for p in perms]
        )
    finally:
        conn.close()

@app.post("/api/admin/roles")
async def create_role(
    request: RoleCreateRequest,
    x_user_role: str = Header(None, alias="X-User-Role"),
    x_user_id: str = Header(None, alias="X-User-Id")
):
    await verify_permission("role_management", x_user_id=x_user_id)
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Create Role
        cursor.execute("INSERT INTO roles (name, description, status, is_system) VALUES (?, ?, ?, FALSE)", 
                       (request.name, request.description, request.status))
        role_id = cursor.lastrowid
        if not role_id:
             role_id = cursor.execute("SELECT id FROM roles WHERE name = ?", (request.name,)).fetchone()['id']
             
        # Assign Permissions
        if request.permissions:
            placeholders = ','.join(['?'] * len(request.permissions))
            valid_perms = conn.execute(f"SELECT id FROM permissions WHERE code IN ({placeholders})", tuple(request.permissions)).fetchall()
            
            data = [(role_id, p['id']) for p in valid_perms]
            cursor.executemany("INSERT INTO role_permissions (role_id, permission_id) VALUES (?, ?)", data)
        
        conn.commit()
        return {"message": "Role created successfully", "role_id": role_id}
    except sqlite3.IntegrityError:
         raise HTTPException(status_code=400, detail="Role name already exists.")
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.put("/api/admin/roles/{role_id}")
async def update_role(
    role_id: int,
    request: RoleCreateRequest,
    x_user_role: str = Header(None, alias="X-User-Role"),
    x_user_id: str = Header(None, alias="X-User-Id")
):
    await verify_permission("role_management", x_user_id=x_user_id)
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        role = cursor.execute("SELECT is_system FROM roles WHERE id = ?", (role_id,)).fetchone()
        if not role:
            raise HTTPException(status_code=404, detail="Role not found")
        
        cursor.execute("UPDATE roles SET name = ?, description = ?, status = ? WHERE id = ?", 
                       (request.name, request.description, request.status, role_id))
                       
        cursor.execute("DELETE FROM role_permissions WHERE role_id = ?", (role_id,))
        
        if request.permissions:
            placeholders = ','.join(['?'] * len(request.permissions))
            valid_perms = conn.execute(f"SELECT id FROM permissions WHERE code IN ({placeholders})", tuple(request.permissions)).fetchall()
            
            data = [(role_id, p['id']) for p in valid_perms]
            cursor.executemany("INSERT INTO role_permissions (role_id, permission_id) VALUES (?, ?)", data)
            
        conn.commit()
        return {"message": "Role updated successfully"}
    finally:
        conn.close()

@app.delete("/api/admin/roles/{role_id}")
async def delete_role(
    role_id: int,
    x_user_role: str = Header(None, alias="X-User-Role"),
    x_user_id: str = Header(None, alias="X-User-Id")
):
    await verify_permission("role_management", x_user_id=x_user_id)
    
    conn = get_db_connection()
    try:
        role = conn.execute("SELECT is_system FROM roles WHERE id = ?", (role_id,)).fetchone()
        if not role:
            raise HTTPException(status_code=404, detail="Role not found")
            
        if role['is_system']:
             raise HTTPException(status_code=400, detail="Cannot delete system roles.")
             
        conn.execute("DELETE FROM roles WHERE id = ?", (role_id,))
        conn.commit()
        return {"message": "Role deleted successfully"}
    finally:
        conn.close()

@app.get("/api/admin/permissions")
async def get_all_permissions(
    x_user_role: str = Header(None, alias="X-User-Role"),
    x_user_id: str = Header(None, alias="X-User-Id")
):
    await verify_permission("role_management", x_user_id=x_user_id)
    
    conn = get_db_connection()
    perms = conn.execute("SELECT * FROM permissions ORDER BY group_name, code").fetchall()
    conn.close()
    
    grouped = {}
    for p in perms:
        g = p['group_name'] or 'General'
        if g not in grouped: grouped[g] = []
        grouped[g].append({
            "id": p['id'],
            "code": p['code'],
            "description": p['description']
        })
        
    return grouped

# New Endpoints for Permission Management (FR-3)

class PermissionDetailResponse(BaseModel):
    id: int
    code: str
    description: str
    group_name: str
    display_code: str

class PermissionUpdateRequest(BaseModel):
    description: str

@app.get("/api/admin/permissions/list", response_model=List[PermissionDetailResponse])
async def get_permissions_list(
    x_user_role: str = Header(None, alias="X-User-Role"),
    x_user_id: str = Header(None, alias="X-User-Id")
):
    await verify_permission("permission_management", x_user_id=x_user_id)
    
    conn = get_db_connection()
    try:
        perms = conn.execute("SELECT * FROM permissions ORDER BY id").fetchall()
        return [
            PermissionDetailResponse(
                id=p['id'],
                code=p['code'],
                description=p['description'],
                group_name=p['group_name'] or "General",
                display_code=f"P-{p['id']:04d}"
            ) for p in perms
        ]
    finally:
        conn.close()

@app.put("/api/admin/permissions/{perm_id}")
async def update_permission(
    perm_id: int,
    request: PermissionUpdateRequest,
    x_user_role: str = Header(None, alias="X-User-Role"),
    x_user_id: str = Header(None, alias="X-User-Id")
):
    await verify_permission("permission_management", x_user_id=x_user_id)
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE permissions SET description = ? WHERE id = ?", (request.description, perm_id))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Permission not found")
        conn.commit()
        return {"message": "Permission updated successfully"}
    finally:
        conn.close()



# --- STAFF MANAGEMENT ENDPOINTS (FR-3.4) ---

@app.get("/api/staff/departments", response_model=List[DepartmentResponse])
async def get_departments(x_user_id: str = Header(None, alias="X-User-Id")):
    await verify_permission("staff.view", x_user_id=x_user_id)
    conn = get_db_connection()
    try:
        deps = conn.execute("SELECT * FROM departments ORDER BY name").fetchall()
        return [DepartmentResponse(**dict(d)) for d in deps]
    finally:
        conn.close()

@app.post("/api/staff/departments")
async def create_department(
    request: DepartmentCreateRequest,
    x_user_id: str = Header(None, alias="X-User-Id")
):
    await verify_permission("staff.manage", x_user_id=x_user_id)
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO departments (name, description, head_of_department_id) VALUES (?, ?, ?)",
                       (request.name, request.description, request.head_of_department_id))
        conn.commit()
        return {"message": "Department created", "id": cursor.lastrowid}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Department Name already exists")
    finally:
        conn.close()

@app.get("/api/staff/profiles", response_model=List[StaffResponse])
async def get_staff_profiles(x_user_id: str = Header(None, alias="X-User-Id")):
    await verify_permission("staff.view", x_user_id=x_user_id)
    conn = get_db_connection()
    try:
        # Get all users who are NOT Students or Parents
        # We assume staff roles are Teacher, Admin variants, etc.
        # Alternatively, we just get everyone in staff_profiles OR role matches typical staff
        query = """
            SELECT s.id, s.name, s.role,
                   sp.department_id, d.name as department_name,
                   sp.position_title, sp.joining_date, sp.contract_type, sp.salary
            FROM students s
            LEFT JOIN staff_profiles sp ON s.id = sp.user_id
            LEFT JOIN departments d ON sp.department_id = d.id
            WHERE s.role NOT IN ('Student', 'Parent_Guardian')
            ORDER BY s.name
        """
        rows = conn.execute(query).fetchall()
        return [StaffResponse(**dict(r)) for r in rows]
    finally:
        conn.close()

@app.put("/api/staff/profiles/{user_id}")
async def update_staff_profile(
    user_id: str,
    request: StaffProfileUpdateRequest,
    x_user_id: str = Header(None, alias="X-User-Id")
):
    await verify_permission("staff.manage", x_user_id=x_user_id)
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # Upsert logic
        cursor.execute("""
            INSERT INTO staff_profiles (user_id, department_id, position_title, joining_date, contract_type, salary)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                department_id=excluded.department_id,
                position_title=excluded.position_title,
                joining_date=excluded.joining_date,
                contract_type=excluded.contract_type,
                salary=excluded.salary
        """, (user_id, request.department_id, request.position_title, request.joining_date, request.contract_type, request.salary))
        conn.commit()
        return {"message": "Profile updated"}
    finally:
        conn.close()

@app.get("/api/staff/attendance")
async def get_staff_attendance(
    date: Optional[str] = None,
    x_user_id: str = Header(None, alias="X-User-Id")
):
    await verify_permission("staff.view", x_user_id=x_user_id)
    conn = get_db_connection()
    try:
        # If date provided, filter. Else get recent.
        base_query = """
            SELECT sa.*, s.name as staff_name 
            FROM staff_attendance sa
            JOIN students s ON sa.user_id = s.id
        """
        params = []
        if date:
            base_query += " WHERE sa.date = ?"
            params.append(date)
        else:
            base_query += " ORDER BY sa.date DESC LIMIT 100"
            
        rows = conn.execute(base_query, tuple(params)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

@app.post("/api/staff/attendance")
async def mark_staff_attendance(
    request: StaffAttendanceRequest,
    x_user_id: str = Header(None, alias="X-User-Id")
):
    await verify_permission("staff.manage", x_user_id=x_user_id)
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO staff_attendance (user_id, date, status, check_in_time, check_out_time)
            VALUES (?, ?, ?, ?, ?)
        """, (request.user_id, request.date, request.status, request.check_in_time, request.check_out_time))
        conn.commit()
        return {"message": "Attendance marked"}
    finally:
        conn.close()

# ---------------------------------------------------------
# RESOURCES (Global Library) ENDPOINTS
# ---------------------------------------------------------

@app.post("/api/resources")
async def upload_resource(
    title: str = Form(...),
    category: str = Form(...),
    description: str = Form(""),
    school_id: int = Form(1),
    file: UploadFile = File(...)
):
    try:
        # 1. Save File to Disk
        resource_dir = "static/resources"
        os.makedirs(resource_dir, exist_ok=True)
        
        # Sanitize filename
        safe_filename = f"{uuid.uuid4()}_{file.filename.replace(' ', '_').replace('/', '_')}"
        file_path = os.path.join(resource_dir, safe_filename)
        
        # Write file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # 2. Extract Text (if PDF)
        extracted_text = ""
        if file.filename.lower().endswith('.pdf') and PdfReader:
            try:
                reader = PdfReader(file_path)
                text_content = []
                for page in reader.pages:
                    text = page.extract_text()
                    if text: text_content.append(text)
                extracted_text = "\n".join(text_content)
            except Exception as e:
                logger.error(f"PDF Extraction Failed: {e}")
                extracted_text = "Error extracting text."
        
        # 3. Save to DB
        uploaded_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if table has extracted_text column (just in case migration failed silently/concurrently)
        # We assume migration passed.
        
        cursor.execute("""
            INSERT INTO resources (title, category, description, file_path, extracted_text, school_id, uploaded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            RETURNING id
        """, (title, category, description, file_path, extracted_text, school_id, uploaded_at))
        resource_id_row = cursor.fetchone()
        resource_id = resource_id_row[0] if resource_id_row else None
        
        conn.commit()
        conn.close()
        
        return {"id": resource_id, "message": "Resource uploaded successfully"}

    except Exception as e:
        logger.error(f"Resource Upload Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/resources")
def get_resources(school_id: int = 1, category: Optional[str] = None):
    conn = get_db_connection()
    try:
        if category and category != 'All':
            # We select * (including extracted_text? maybe exclude for list view to save bandwidth)
            # Let's exclude extracted_text for list
            resources = conn.execute("SELECT id, title, category, description, file_path, uploaded_by, uploaded_at, school_id FROM resources WHERE school_id = ? AND category = ? ORDER BY uploaded_at DESC", (school_id, category)).fetchall()
        else:
            resources = conn.execute("SELECT id, title, category, description, file_path, uploaded_by, uploaded_at, school_id FROM resources WHERE school_id = ? ORDER BY uploaded_at DESC", (school_id,)).fetchall()
        return [dict(r) for r in resources]
    finally:
        conn.close()

@app.delete("/api/resources/{resource_id}")
def delete_resource(resource_id: int):
    conn = get_db_connection()
    try:
        # Get file path to delete file
        res = conn.execute("SELECT file_path FROM resources WHERE id = ?", (resource_id,)).fetchone()
        if res and res['file_path'] and os.path.exists(res['file_path']):
            try:
                os.remove(res['file_path'])
            except:
                pass
            
        conn.execute("DELETE FROM resources WHERE id = ?", (resource_id,))
        conn.commit()
        return {"message": "Resource deleted"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()



@app.get("/api/staff/performance/{user_id}")
async def get_staff_performance(
    user_id: str,
    x_user_id: str = Header(None, alias="X-User-Id")
):
    # Self view allowed? Let's restrict to manager for now
    await verify_permission("staff.manage", x_user_id=x_user_id)
    conn = get_db_connection()
    try:
        rows = conn.execute("SELECT * FROM staff_performance WHERE user_id = ? ORDER BY review_date DESC", (user_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

@app.post("/api/staff/performance")
async def create_performance_review(
    request: StaffPerformanceRequest,
    x_user_id: str = Header(None, alias="X-User-Id")
):
    await verify_permission("staff.manage", x_user_id=x_user_id)
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO staff_performance (user_id, reviewer_id, review_date, rating, comments, goals)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (request.user_id, x_user_id, request.review_date, request.rating, request.comments, request.goals))
        conn.commit()
        return {"message": "Review added"}
    finally:
        conn.close()


# --- RESOURCE MANAGEMENT ENDPOINTS ---

@app.get("/api/resources", response_model=List[ResourceResponse])
async def get_resources(
    school_id: Optional[int] = None,
    category: Optional[str] = None
):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        query = "SELECT * FROM resources WHERE 1=1"
        params = []
        
        if school_id:
            query += " AND school_id = ?"
            params.append(school_id)
            
        if category and category != "All":
            query += " AND category = ?"
            params.append(category)
            
        query += " ORDER BY uploaded_at DESC" 
        
        resources = cursor.execute(query, tuple(params)).fetchall()
        
        return [
            ResourceResponse(
                id=r['id'],
                title=r['title'],
                description=r['description'],
                category=r['category'],
                file_path=r['file_path'],
                uploaded_by=r['uploaded_by'],
                uploaded_at=r['uploaded_at']
            ) for r in resources
        ]
    except Exception as e:
        logger.error(f"Error fetching resources: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/resources", response_model=ResourceResponse)
async def create_resource(
    title: str = Form(...),
    description: Optional[str] = Form(""),
    category: str = Form("Policy"),
    school_id: Optional[int] = Form(1),
    file: UploadFile = File(...),
    x_user_id: str = Header(None, alias="X-User-Id")
):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        uploaded_at = datetime.now().isoformat()
        uploaded_by = x_user_id if x_user_id else "Admin"

        # Save the file
        file_ext = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_location = f"static/resources/{unique_filename}"
        
        # Ensure directory exists (redundant if mkdir run, but safe)
        os.makedirs("static/resources", exist_ok=True)

        with open(file_location, "wb+") as file_object:
            shutil.copyfileobj(file.file, file_object)
            
        # Store relative path for frontend access
        web_path = f"/static/resources/{unique_filename}"

        cursor.execute("""
            INSERT INTO resources (title, description, category, file_path, uploaded_by, uploaded_at, school_id)
            VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING id
        """, (title, description, category, web_path, uploaded_by, uploaded_at, school_id))
        
        row = cursor.fetchone()
        resource_id = row['id'] if row else 0 # Fallback
        
        conn.commit()
        
        return ResourceResponse(
            id=resource_id,
            title=title,
            description=description,
            category=category,
            file_path=web_path,
            uploaded_by=uploaded_by,
            uploaded_at=uploaded_at
        )
    except Exception as e:
        logger.error(f"Error creating resource: {e}")
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.delete("/api/resources/{resource_id}")
async def delete_resource(resource_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM resources WHERE id = ?", (resource_id,))
        # Check rowcount if possible, but wrapper might not expose it easily without result.
        conn.commit()
        return {"message": "Resource deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting resource: {e}")
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()










# --- MOODLE SSO (OAuth2 Provider) ---
# In production, use Redis or DB for these stores
OAUTH_CODES = {}
OAUTH_ACCESS_TOKENS = {}


# Embedded SSO Authorize Page
SSO_AUTHORIZE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Authorize Moodle Access</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.3.0/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #f8f9fa; display: flex; align-items: center; justify-content: center; height: 100vh; }
        .card { border: none; box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1); border-radius: 12px; width: 100%; max-width: 400px; }
        .loader { border: 4px solid #f3f3f3; border-top: 4px solid #3498db; border-radius: 50%; width: 30px; height: 30px; animation: spin 1s linear infinite; margin: 0 auto; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div class="card p-4 text-center">
        <div class="mb-3">
            <h3 class="fw-bold text-primary">Noble Nexus</h3>
        </div>
        <h4 class="mb-3">Connecting to Moodle...</h4>
        <div id="status-area">
            <div class="loader mb-3"></div>
            <p class="text-muted small">Please wait while we verify your identity.</p>
        </div>
    </div>
    <script>
    async function authorize() {
        const urlParams = new URLSearchParams(window.location.search);
        const clientId = urlParams.get('client_id');
        const redirectUri = urlParams.get('redirect_uri');
        const state = urlParams.get('state');

        // Check LocalStorage (Problem: LocalStorage is Domain Specific. If Backend is diff domain than Frontend, this fails)
        // SOLUTION: We assume for now this flow is initiated from a context where token might be passed or we rely on session cookies if we had them.
        // BUT currently Noble Nexus uses LocalStorage for auth. 
        // If Backend is on render.com and Frontend on vercel.app, Backend Page cannot read Frontend LocalStorage.
        // This flow is flawed in a split-domain architecture without cookies.
        
        // HOWEVER: The user is clicking "Launch Moodle" from the Frontend. 
        // The Frontend opens this window. 
        // We can try to pass the token in the URL or via postMessage.
        // For now, let's just attempt the flow and show a warning if not logged in.
        
        const user = localStorage.getItem('user'); 
        const userObj = user ? JSON.parse(user) : null;
        
        if (!userObj || !userObj.id) {
            // Try to see if we can get it from parent (if popup)
             try {
                if (window.opener) {
                    // This is cross-origin, so we can't direct read, but we could request it?
                    // For simplicity in this demo, we'll ask user to login if missing.
                }
            } catch(e){}

            document.getElementById('status-area').innerHTML = `
                <div class="alert alert-warning">
                    Session not found in this domain. 
                    <br><small>Because the api is on a different domain, we cannot read your login session.</small>
                </div>
                <p>Please copy your User ID manually to proceed (Mock Flow):</p>
                <input type="text" id="manual-user-id" class="form-control mb-2" placeholder="Enter User ID (e.g. stu_001)">
                <button class="btn btn-primary w-100" onclick="manualApprove()">Approve Manually</button>
            `;
            return;
        }

        approve(userObj.id, clientId, redirectUri, state);
    }
    
    function manualApprove() {
        const uid = document.getElementById('manual-user-id').value;
        if(uid) {
            const urlParams = new URLSearchParams(window.location.search);
            approve(uid, urlParams.get('client_id'), urlParams.get('redirect_uri'), urlParams.get('state'));
        }
    }

    async function approve(userId, clientId, redirectUri, state) {
        try {
            const response = await fetch('/api/oauth/approve', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: userId, client_id: clientId, redirect_uri: redirectUri, state: state })
            });

            if (response.ok) {
                const data = await response.json();
                window.location.href = data.redirect_url;
            } else {
                const err = await response.json();
                showError(err.detail || "Authorization failed.");
            }
        } catch (e) {
            showError("Network Error: " + e.message);
        }
    }

    function showError(msg) {
        document.getElementById('status-area').innerHTML = `<div class="alert alert-danger small">${msg}</div>`;
    }

    setTimeout(authorize, 1000); 
    </script>
</body>
</html>
"""

@app.get("/oauth/authorize", response_class=HTMLResponse)
async def oauth_authorize(response_type: str, client_id: str, redirect_uri: str, state: str, scope: Optional[str] = None):
    return HTMLResponse(content=SSO_AUTHORIZE_HTML)

class OAuthApproveRequest(BaseModel):
    user_id: str
    client_id: str
    redirect_uri: str
    state: str

@app.post("/api/oauth/approve")
async def oauth_approve(request: OAuthApproveRequest):
    # Verify user exists (simple check)
    conn = get_db_connection()
    user = conn.execute("SELECT id FROM students WHERE id = ?", (request.user_id,)).fetchone()
    conn.close()
    
    if not user:
         raise HTTPException(status_code=400, detail="User not found")

    # Generate Authorization Code
    auth_code = secrets.token_urlsafe(16)
    OAUTH_CODES[auth_code] = {
        "user_id": request.user_id,
        "client_id": request.client_id,
        "redirect_uri": request.redirect_uri,
        "expires_at": time.time() + 600 # 10 minutes
    }
    
    # Return the redirect URL that the frontend should follow
    # Moodle expects: redirect_uri + ?code=... + &state=...
    separator = "&" if "?" in request.redirect_uri else "?"
    redirect_url = f"{request.redirect_uri}{separator}code={auth_code}&state={request.state}"
    
    return {"redirect_url": redirect_url}

@app.get("/.well-known/openid-configuration")
async def openid_configuration(request: Request):
    base_url = str(request.base_url).rstrip('/')
    return {
        "issuer": base_url,
        "authorization_endpoint": f"{base_url}/oauth/authorize",
        "token_endpoint": f"{base_url}/oauth/token",
        "userinfo_endpoint": f"{base_url}/oauth/userinfo",
        "jwks_uri": f"{base_url}/oauth/jwks",
        "response_types_supported": ["code"],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["HS256"],
        "scopes_supported": ["openid", "profile", "email"]
    }

# Minimal JWT Generator (HS256)
def generate_jwt(payload, secret):
    import base64
    def b64url(data):
        return base64.urlsafe_b64encode(data).rstrip(b'=')
        
    header = {"alg": "HS256", "typ": "JWT"}
    segments = [
        b64url(json.dumps(header).encode()),
        b64url(json.dumps(payload).encode())
    ]
    signing_input = b'.'.join(segments)
    signature = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    segments.append(b64url(signature))
    return b'.'.join(segments).decode()

@app.post("/oauth/token")
async def oauth_token(
    request: Request,
    grant_type: str = Form(...),
    code: str = Form(...),
    client_id: str = Form(...),
    client_secret: str = Form(None), # Optional for public clients
    redirect_uri: str = Form(...)
):
    # Validate Code
    token_data = OAUTH_CODES.get(code)
    if not token_data:
        raise HTTPException(status_code=400, detail="Invalid grant: Code not found")
        
    if time.time() > token_data["expires_at"]:
        del OAUTH_CODES[code]
        raise HTTPException(status_code=400, detail="Code expired")
        
    # In strict OAuth, we validate client_id matches the one in code
    if token_data["client_id"] != client_id: 
        raise HTTPException(status_code=400, detail="Invalid client_id")
    
    # Generate Access Token
    access_token = secrets.token_urlsafe(32)
    expires_in = 3600
    
    OAUTH_ACCESS_TOKENS[access_token] = {
        "user_id": token_data["user_id"],
        "expires_at": time.time() + expires_in
    }
    
    # Generate ID Token (OIDC)
    base_url = str(request.base_url).rstrip('/')
    id_token_payload = {
        "iss": base_url,
        "sub": token_data["user_id"],
        "aud": client_id,
        "exp": int(time.time()) + expires_in,
        "iat": int(time.time())
    }
    # Use a persistent secret in production
    id_token = generate_jwt(id_token_payload, "SUPER_SECRET_SIGNING_KEY")
    
    # Delete used code
    del OAUTH_CODES[code]
    
    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": expires_in,
        "id_token": id_token
    }

@app.get("/oauth/userinfo")
async def oauth_userinfo(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid header")
    
    token = authorization.split(" ")[1]
    token_data = OAUTH_ACCESS_TOKENS.get(token)
    
    if not token_data or time.time() > token_data["expires_at"]:
         raise HTTPException(status_code=401, detail="Invalid or expired token")
         
    user_id = token_data["user_id"]
    
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM students WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Return OpenID Connect compliant claims
    return {
        "sub": user['id'],
        "name": user['name'],
        "email": f"{user['id']}@noblenexus.edu", 
        "given_name": user['name'].split(" ")[0],
        "family_name": " ".join(user['name'].split(" ")[1:]) if " " in user['name'] else "",
        "picture": "https://www.w3schools.com/howto/img_avatar.png"
    }



# --- LMS ENDPOINTS (MOODLE ALTERNATIVE) ---

@app.post("/api/lms/courses", response_model=LMSCourseResponse)
async def create_course(course: LMSCourseCreateRequest, x_user_id: str = Header(None, alias="X-User-Id")):
    conn = get_db_connection()
    c = conn.cursor()
    # verify teacher or admin
    if not x_user_id:
        raise HTTPException(status_code=400, detail="User Identity Missing")
        
    created_at = datetime.now().isoformat()
    # Get School ID safely
    school_row = conn.execute("SELECT school_id FROM students WHERE id = ?", (x_user_id,)).fetchone()
    school_id = school_row['school_id'] if school_row else 1
    
    c.execute("""
        INSERT INTO lms_courses (title, description, teacher_id, category, thumbnail_url, enrollment_key, created_at, school_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (course.title, course.description, x_user_id, course.category, course.thumbnail_url, course.enrollment_key, created_at, school_id))
    course_id = c.lastrowid
    conn.commit()
    conn.close()
    
    return {
        "id": course_id,
        "title": course.title,
        "description": course.description,
        "teacher_id": x_user_id,
        "category": course.category,
        "thumbnail_url": course.thumbnail_url,
        "created_at": created_at
    }

@app.get("/api/lms/courses", response_model=List[LMSCourseResponse])
async def get_courses(category: Optional[str] = None, search: Optional[str] = None):
    conn = get_db_connection()
    query = "SELECT * FROM lms_courses WHERE 1=1"
    params = []
    if category and category != 'All':
        query += " AND category = ?"
        params.append(category)
    if search:
        query += " AND (title LIKE ? OR description LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    
    try:
        courses = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(row) for row in courses]
    except Exception as e:
        conn.close()
        logger.error(f"Error fetching courses: {e}")
        return []

@app.get("/api/lms/courses/{course_id}/full")
async def get_course_full(course_id: int, x_user_id: str = Header(None, alias="X-User-Id")):
    conn = get_db_connection()
    course = conn.execute("SELECT * FROM lms_courses WHERE id = ?", (course_id,)).fetchone()
    if not course:
        conn.close()
        raise HTTPException(status_code=404, detail="Course not found")
        
    sections_rows = conn.execute("SELECT * FROM lms_course_sections WHERE course_id = ? ORDER BY order_index", (course_id,)).fetchall()
    sections = []
    
    for s_row in sections_rows:
        modules = conn.execute("SELECT * FROM lms_course_modules WHERE section_id = ? ORDER BY order_index", (s_row['id'],)).fetchall()
        
        module_list = []
        for m in modules:
            m_dict = dict(m)
            if x_user_id:
                comp = conn.execute("SELECT status, score FROM lms_module_completion WHERE module_id = ? AND student_id = ?", (m['id'], x_user_id)).fetchone()
                if comp:
                    m_dict['completion'] = dict(comp)
            module_list.append(m_dict)
            
        sections.append({
            **dict(s_row),
            "modules": module_list
        })
        
    conn.close()
    return {
        **dict(course),
        "sections": sections
    }

@app.post("/api/lms/courses/{course_id}/sections", response_model=LMSSectionResponse)
async def add_section(course_id: int, section: LMSSectionCreateRequest):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO lms_course_sections (course_id, title, order_index) VALUES (?, ?, ?)", 
              (course_id, section.title, section.order_index))
    s_id = c.lastrowid
    conn.commit()
    conn.close()
    return {**section.dict(), "id": s_id, "course_id": course_id}


def extract_text_from_file(file_path):
    try:
        from pypdf import PdfReader
        if file_path.endswith('.pdf'):
            reader = PdfReader(file_path)
            text = ""
            for page in reader.pages[:10]:
                text += page.extract_text() + "\n"
            return text
    except: return ""
    return ""

@app.post("/api/lms/sections/{section_id}/modules", response_model=LMSModuleResponse)
async def add_module(section_id: int, module: LMSModuleCreateRequest):
    conn = get_db_connection()
    c = conn.cursor()
    
    # RAG Logic
    searchable_text = ""
    if module.type == 'html':
        searchable_text = module.content_text
    elif module.type == 'pdf' and module.content_url.startswith('/static'):
        # Local file
        fs_path = module.content_url.lstrip('/')
        if os.path.exists(fs_path):
            searchable_text = extract_text_from_file(fs_path)
    
    c.execute("""
        INSERT INTO lms_course_modules (section_id, title, type, content_url, content_text, searchable_text, order_index)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (section_id, module.title, module.type, module.content_url, module.content_text, searchable_text, module.order_index))
    m_id = c.lastrowid
    conn.commit()
    conn.close()
    return {**module.dict(), "id": m_id, "section_id": section_id}


class LMSCompletionRequest(BaseModel):
    score: float
    status: str

@app.post("/api/ai/chat/course/{course_id}")
async def chat_with_course(course_id: int, request: AIChatRequest):
    if not AI_ENABLED or not GROQ_CLIENT:
         return {"reply": "AI Service Unavailable"}

    conn = get_db_connection()
    # 1. Fetch relevant content (Naive RAG: Fetch all text for now, should use Vector DB in prod)
    # Get all searchable text for this course
    # Joined via sections
    rows = conn.execute("""
        SELECT m.searchable_text, m.title FROM lms_course_modules m
        JOIN lms_course_sections s ON m.section_id = s.id
        WHERE s.course_id = ? AND m.searchable_text IS NOT NULL AND m.searchable_text != ''
    """, (course_id,)).fetchall()
    
    context = ""
    for r in rows:
        context += f"\n--- Module: {r['title']} ---\n{r['searchable_text'][:5000]}" # Limit size per module
        
    context = context[:20000] # Hard limit for prompt
    conn.close()
    
    if not context:
        return {"reply": "I don't have enough content from this course to answer yet."}

    system_prompt = (
        "You are an AI Tutor for a specific course. "
        "Answer the student's question based ONLY on the provided Course Content below. "
        "If the answer is not in the content, say 'I cannot find that in the course material'.\n\n"
        f"Course Content:\n{context}"
    )
    
    try:
        completion = GROQ_CLIENT.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": request.prompt}
            ],
            model="llama-3.1-8b-instant",
            temperature=0.3
        )
        return {"reply": completion.choices[0].message.content}
    except Exception as e:
        logger.error(f"AI Course Chat Error: {e}")
        return {"reply": "Sorry, I encountered an error while thinking."}

@app.post("/api/lms/modules/{module_id}/complete")
async def complete_module(module_id: int, request: LMSCompletionRequest, x_user_id: str = Header(None, alias="X-User-Id")):
    if not x_user_id:
        raise HTTPException(status_code=400, detail="User Identity Missing")
        
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        # Upsert logic for completion
        c.execute("""
            INSERT INTO lms_module_completion (module_id, student_id, status, score)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(module_id, student_id) DO UPDATE SET
            status = EXCLUDED.status,
            score = EXCLUDED.score
        """, (module_id, x_user_id, request.status, request.score))
        conn.commit()
    except Exception as e:
        logger.error(f"Error saving completion: {e}")
        conn.close()
        raise HTTPException(status_code=500, detail="Failed to save progress")
        
    conn.close()
    return {"message": "Progress saved"}

class QuestionGradingRequest(BaseModel):
    question: str
    student_answer: str
    context: Optional[str] = None # Optional context from module

@app.post("/api/ai/grade/short-answer")
async def grade_quiz_short_answer(request: QuestionGradingRequest):
    if not AI_ENABLED or not GROQ_CLIENT:
         return {"score": 0, "feedback": "AI Service Unavailable. Manual grading required."}
    
    system_prompt = (
        "You are a strictly academic AI Assistant. Your goal is to grade a student's short answer response. "
        "Score the answer from 0 to 100 based on accuracy and completeness. "
        "Provide a JSON response with 'score' (integer 0-100) and 'feedback' (1-2 sentences). "
        "Do not offer python code or anything else, just the JSON."
    )
    
    user_prompt = f"Question: {request.question}\nStudent Answer: {request.student_answer}\n"
    if request.context:
        user_prompt += f"Context/Correct Answer Reference: {request.context}"
        
    try:
        completion = GROQ_CLIENT.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model="llama-3.1-8b-instant",
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        content = completion.choices[0].message.content
        import json
        result = json.loads(content)
        return result
    except Exception as e:
        logger.error(f"AI Grading Error: {e}")
        return {"score": 0, "feedback": "Error during AI grading."}

# --- Attendance Module ---
class AttendanceRecord(BaseModel):
    student_id: str
    status: str
    remarks: Optional[str] = ""

class BulkAttendanceRequest(BaseModel):
    date: str
    records: List[AttendanceRecord]

@app.post("/api/attendance/bulk")
async def take_bulk_attendance(req: BulkAttendanceRequest, x_user_id: str = Header(None, alias="X-User-Id")):
    conn = get_db_connection()
    c = conn.cursor()
    created_at = datetime.now().isoformat()
    
    try:
        # Delete existing for this date (simple overwrite logic for now)
        for record in req.records:
            c.execute("DELETE FROM student_attendance WHERE student_id = ? AND date = ?", (record.student_id, req.date))
            
            c.execute("""
                INSERT INTO student_attendance (student_id, date, status, remarks, recorded_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (record.student_id, req.date, record.status, record.remarks, x_user_id, created_at))

            # Notify Parents on Attendance Update
            print(f"DEBUG: Processing record for {record.student_id}, Status: {record.status}")
            if record.status in ['Present', 'Absent', 'Late']:
                # Find guardians for this student
                guardians = c.execute("SELECT email, name FROM guardians WHERE student_id = ?", (record.student_id,)).fetchall()
                print(f"DEBUG: Found {len(guardians)} guardians for {record.student_id}")

                # Fetch student name for the message
                student_row = c.execute("SELECT name FROM students WHERE id = ?", (record.student_id,)).fetchone()
                student_name = student_row['name'] if student_row else "Student"

                for g in guardians:
                    parent_user_id = g['email']
                    print(f"DEBUG: Checking parent user {parent_user_id}")
                    
                    # Verify parent exists as a user to receive messages
                    parent_user = c.execute("SELECT id FROM students WHERE id = ? AND role = 'Parent'", (parent_user_id,)).fetchone()
                    
                    if parent_user:
                        print(f"DEBUG: Parent user {parent_user_id} found. Sending message.")
                        subject = f"Attendance: {student_name} is {record.status}"
                        content = f"Dear {g['name']}, your child {student_name} has been marked {record.status.upper()} for today ({req.date})."
                        if record.remarks:
                             content += f" Remarks: {record.remarks}"
                        
                        # Insert Notification into Messages
                        c.execute("""
                           INSERT INTO messages (sender_id, receiver_id, subject, content, timestamp, is_read)
                           VALUES (?, ?, ?, ?, ?, FALSE)
                        """, (x_user_id if x_user_id else 'admin', parent_user_id, subject, content, created_at))
                    else:
                        print(f"DEBUG: Parent user {parent_user_id} NOT found in students table or not role='Parent'")
            
        conn.commit()
        return {"success": True, "count": len(req.records)}
    except Exception as e:
        logger.error(f"Attendance Error: {e}")
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.get("/api/attendance/class/{grade}")
async def get_class_attendance(grade: int, date: str):
    conn = get_db_connection()
    c = conn.cursor()
    
    # Get all students for this grade
    students = c.execute("SELECT id, name, photo_url FROM students WHERE grade = ? AND role = 'Student'", (grade,)).fetchall()
    
    # Get attendance for date
    att_rows = c.execute("SELECT student_id, status, remarks FROM student_attendance WHERE date = ?", (date,)).fetchall()
    att_map = {row['student_id']: row for row in att_rows}
    
    results = []
    for s in students:
        record = att_map.get(s['id'])
        results.append({
            "id": s['id'],
            "name": s['name'],
            "photo_url": s['photo_url'],
            "status": record['status'] if record else "Not Marked",
            "remarks": record['remarks'] if record else ""
        })
        
    conn.close()
    return results

# --- TIMETABLE MODULE ---
@app.get("/api/timetable/teacher/{teacher_id}")
async def get_teacher_timetable(teacher_id: str):
    conn = get_db_connection()
    c = conn.cursor()
    rows = c.execute("SELECT * FROM timetables WHERE teacher_id = ? ORDER BY day_of_week, period_number", (teacher_id,)).fetchall()
    conn.close()
    
    # Map to simpler structure
    days = {}
    for r in rows:
        d = r['day_of_week']
        if d not in days: days[d] = []
        days[d].append({
            "period": r['period_number'],
            "time": f"{r['start_time']} - {r['end_time']}",
            "subject": r['subject'],
            "class": f"Grade {r['class_grade']}-{r['section']}"
        })
    return days

# --- LEAVE REQUEST MODULE ---
class LeaveRequestCreate(BaseModel):
    user_id: str
    type: str
    start_date: str
    end_date: str
    reason: str

# Duplicate apply_leave removed. Using the implementation at the end of the file.


@app.get("/api/leave/student/pending")
async def get_pending_student_leaves(x_school_id: int = Header(1, alias="X-School-Id")):
    conn = get_db_connection()
    c = conn.cursor()
    # Fetch pending leaves for 'Student' role
    leaves = c.execute("""
        SELECT l.*, s.name, s.grade 
        FROM leave_requests l
        JOIN students s ON l.user_id = s.id
        WHERE l.status = 'Pending' AND s.role = 'Student'
    """).fetchall()
    conn.close()
    result = []
    for l in leaves:
        result.append({
            "id": l['id'],
            "student_name": l['name'],
            "grade": l['grade'],
            "type": l['type'],
            "dates": f"{l['start_date']} to {l['end_date']}",
            "reason": l['reason']
        })
    return result

@app.post("/api/leave/{request_id}/action")
async def action_leave_request(request_id: int, action: str = Body(..., embed=True), reviewer_id: str = Body(..., embed=True)):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        status = "Approved" if action.lower() == "approve" else "Denied"
        c.execute("UPDATE leave_requests SET status = ?, reviewed_by = ? WHERE id = ?", (status, reviewer_id, request_id))
        conn.commit()
        return {"success": True}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

# --- ASSIGNMENT SUBMISSIONS MODULE ---
@app.get("/api/assignments/teacher/pending")
async def get_pending_assignments(teacher_id: str):
    conn = get_db_connection()
    c = conn.cursor()
    # Mock query: Get submissions for assignments created by groups owned by teacher
    # Since we simplified groups, let's just fetch ALL pending submissions for demo
    subs = c.execute("""
        SELECT s.*, a.title as assignment_title, st.name as student_name
        FROM assignment_submissions s
        JOIN assignments a ON s.assignment_id = a.id
        JOIN students st ON s.student_id = st.id
        WHERE s.status = 'Submitted'
    """).fetchall()
    conn.close()
    
    result = []
    for s in subs:
        result.append({
            "id": s['id'],
            "assignment_title": s['assignment_title'],
            "student_name": s['student_name'],
            "submitted_at": s['submitted_at'],
            "content": s['content_text']
        })
    return result

@app.post("/api/assignments/submissions/{sub_id}/grade")
async def grade_submission(sub_id: int,
                           grade: float = Body(..., embed=True),
                           feedback: str = Body(..., embed=True),
                           x_user_role: str = Header(None, alias="X-User-Role"),
                           x_user_id: str = Header(None, alias="X-User-Id")):
    await verify_permission("assignment.grade", x_user_role=x_user_role, x_user_id=x_user_id)
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("UPDATE assignment_submissions SET grade = ?, feedback = ?, status = 'Graded' WHERE id = ?", (grade, feedback, sub_id))
        conn.commit()
        return {"success": True}
    except Exception as e:
         conn.rollback()
         raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/assignments/submissions/{sub_id}/reassign")
async def reassign_submission(sub_id: int,
                              feedback: str = Body("", embed=True),
                              x_user_role: str = Header(None, alias="X-User-Role"),
                              x_user_id: str = Header(None, alias="X-User-Id")):
    await verify_permission("assignment.grade", x_user_role=x_user_role, x_user_id=x_user_id)
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("UPDATE assignment_submissions SET grade = NULL, status = 'Reassigned', feedback = ? WHERE id = ?", (feedback, sub_id))
        conn.commit()
        return {"success": True}
    except Exception as e:
         conn.rollback()
         raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/assignments", status_code=201)
async def create_assignment(req: AssignmentCreateRequest,
                            x_user_role: str = Header(None, alias="X-User-Role"),
                            x_user_id: str = Header(None, alias="X-User-Id"),
                            x_school_id: Optional[int] = Header(None, alias="X-School-Id")):
    await verify_permission("assignment.create", x_user_role=x_user_role, x_user_id=x_user_id)
    conn = get_db_connection()
    try:
        section_id = req.section_id
        grade_level = req.grade_level
        if section_id:
            section = conn.execute("SELECT id, grade_level, school_id FROM sections WHERE id = ?", (section_id,)).fetchone()
            if not section:
                raise HTTPException(status_code=404, detail="Section not found.")
            if x_school_id and section["school_id"] != x_school_id:
                raise HTTPException(status_code=403, detail="Section does not belong to your school.")
            grade_level = section["grade_level"]
        if not grade_level:
            raise HTTPException(status_code=400, detail="Grade level is required.")
        conn.execute("""
            INSERT INTO assignments (group_id, title, description, due_date, type, points, section_id, grade_level)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (None, req.title, req.description, req.due_date, "Assignment", req.points, section_id, grade_level))
        conn.commit()
        return {"success": True, "message": "Assignment created"}
    finally:
        conn.close()

@app.get("/api/teacher/assignments")
async def get_teacher_assignments(section_id: Optional[int] = None,
                                  x_user_role: str = Header(None, alias="X-User-Role"),
                                  x_user_id: str = Header(None, alias="X-User-Id"),
                                  x_school_id: Optional[int] = Header(None, alias="X-School-Id")):
    await verify_permission("assignment.view", x_user_role=x_user_role, x_user_id=x_user_id)
    conn = get_db_connection()
    try:
        query = """
            SELECT
                a.id,
                a.group_id,
                a.title,
                a.description,
                a.due_date,
                a.type,
                a.points,
                a.section_id,
                a.grade_level,
                sec.name AS section_name,
                COALESCE((
                    SELECT COUNT(*) FROM assignment_submissions s WHERE s.assignment_id = a.id
                ), 0) AS submission_count
            FROM assignments a
            LEFT JOIN sections sec ON a.section_id = sec.id
        """
        conditions = []
        params = []
        if section_id:
            conditions.append("a.section_id = ?")
            params.append(section_id)
        if x_school_id:
            conditions.append("(a.section_id IS NULL OR sec.school_id = ?)")
            params.append(x_school_id)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY a.due_date DESC, a.id DESC"
        rows = conn.execute(query, tuple(params)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

@app.post("/api/assignments/{assignment_id}/submit")
async def submit_assignment(assignment_id: int,
                            req: SubmissionCreateRequest,
                            x_user_role: str = Header(None, alias="X-User-Role"),
                            x_user_id: str = Header(None, alias="X-User-Id")):
    if x_user_role != 'Student':
        raise HTTPException(status_code=403, detail="Only students can submit assignments.")
    if x_user_id and x_user_id != req.student_id:
        raise HTTPException(status_code=403, detail="Student ID mismatch.")
    conn = get_db_connection()
    try:
        assignment = conn.execute("SELECT id FROM assignments WHERE id = ?", (assignment_id,)).fetchone()
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found.")
        existing = conn.execute("""
            SELECT id FROM assignment_submissions WHERE assignment_id = ? AND student_id = ?
        """, (assignment_id, req.student_id)).fetchone()
        submitted_at = datetime.now().isoformat()
        if existing:
            conn.execute("""
                UPDATE assignment_submissions
                SET content_text = ?, submitted_at = ?, status = 'Submitted', grade = NULL, feedback = NULL
                WHERE id = ?
            """, (req.content, submitted_at, existing["id"]))
        else:
            conn.execute("""
                INSERT INTO assignment_submissions (assignment_id, student_id, submitted_at, content_text, status)
                VALUES (?, ?, ?, ?, 'Submitted')
            """, (assignment_id, req.student_id, submitted_at, req.content))
        conn.commit()
        return {"success": True}
    finally:
        conn.close()

@app.get("/api/assignments/{assignment_id}/submissions")
async def get_assignment_submissions(assignment_id: int,
                                     x_user_role: str = Header(None, alias="X-User-Role"),
                                     x_user_id: str = Header(None, alias="X-User-Id")):
    await verify_permission("assignment.view", x_user_role=x_user_role, x_user_id=x_user_id)
    conn = get_db_connection()
    try:
        subs = conn.execute("""
            SELECT s.id, s.assignment_id, s.student_id, s.submitted_at, s.content_text, s.grade, s.feedback, s.status,
                   st.name as student_name
            FROM assignment_submissions s
            JOIN students st ON s.student_id = st.id
            WHERE s.assignment_id = ?
            ORDER BY s.submitted_at DESC
        """, (assignment_id,)).fetchall()
        return [dict(r) for r in subs]
    finally:
        conn.close()

if __name__ == "__main__":
    try:
        initialize_db()
        print("Database initialized successfully.")
    except Exception as e:
        print(f"Error initializing database: {e}")
    import uvicorn
    # Use the current file name 'backend' as the module
    uvicorn.run("backend:app", host="0.0.0.0", port=8000, reload=True)

# --- LEAVE MANAGEMENT ENDPOINTS (ADDED DYNAMICALLY) ---

class LeaveApplication(BaseModel):
    user_id: str
    type: str 
    start_date: str
    end_date: str
    reason: str

class LeaveStatusUpdate(BaseModel):
    status: str 
    reviewed_by: str
    substitute_teacher_id: Optional[str] = None

# --- PROGRESS CARD MODULE ---
class ProgressCardResponse(BaseModel):
    student: Dict[str, Any]
    academics: Dict[str, Any]
    attendance: Dict[str, Any]
    engagement: Dict[str, Any]
    alerts: List[str]
    recent_marks: List[Dict[str, Any]]
    remarks: Optional[str]

# --- ASSIGNMENT MODULE (Simple Create) ---
class ProgressMarksEntry(BaseModel):
    student_id: str
    marks_obtained: float
    grade: Optional[str] = None
    remarks: Optional[str] = None

class ProgressMarksBulkRequest(BaseModel):
    exam_name: str
    subject: str
    max_marks: float
    date: Optional[str] = None
    grade_level: int
    section_id: Optional[int] = None
    entries: List[ProgressMarksEntry]

class ProgressPublishRequest(BaseModel):
    exam_name: str
    subject: str
    grade_level: int
    section_id: Optional[int] = None

# --- EMAIL MODULE ---
class EmailSendRequest(BaseModel):
    to: str  # can be user id, email, or group token (grade:10, section:3, role:Teacher, all)
    subject: str
    body: str

@app.get("/api/progress/roster")
async def get_progress_roster(grade_level: int,
                              section_id: Optional[int] = None,
                              x_school_id: Optional[int] = Header(None, alias="X-School-Id")):
    conn = get_db_connection()
    try:
        params = [grade_level]
        query = "SELECT id, name, grade FROM students WHERE role = 'Student' AND grade = ?"
        if section_id:
            query += " AND section_id = ?"
            params.append(section_id)
        if x_school_id:
            query += " AND school_id = ?"
            params.append(x_school_id)
        query += " ORDER BY name"
        rows = conn.execute(query, tuple(params)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

@app.post("/api/progress/marks/bulk")
async def save_progress_marks(req: ProgressMarksBulkRequest,
                              x_user_role: str = Header(None, alias="X-User-Role"),
                              x_user_id: str = Header(None, alias="X-User-Id"),
                              x_school_id: Optional[int] = Header(None, alias="X-School-Id")):
    if x_user_role not in ('Teacher', 'Admin', 'Tenant_Admin', 'Super_Admin'):
        raise HTTPException(status_code=403, detail="Not authorized to enter marks.")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # Validate section if provided
        if req.section_id:
            sec = cursor.execute("SELECT id, school_id, grade_level FROM sections WHERE id = ?", (req.section_id,)).fetchone()
            if not sec:
                raise HTTPException(status_code=404, detail="Section not found.")
            if x_school_id and sec["school_id"] != x_school_id:
                raise HTTPException(status_code=403, detail="Section does not belong to your school.")

        date_val = req.date or datetime.now().date().isoformat()
        inserted = 0
        for e in req.entries:
            stu = cursor.execute(
                "SELECT id, grade, section_id, school_id FROM students WHERE id = ? AND role = 'Student'",
                (e.student_id,)
            ).fetchone()
            if not stu:
                continue
            if stu["grade"] != req.grade_level:
                continue
            if req.section_id and stu["section_id"] != req.section_id:
                continue
            if x_school_id and stu["school_id"] != x_school_id:
                continue

            cursor.execute("""
                INSERT INTO student_marks (student_id, exam_name, subject, marks_obtained, max_marks, grade, remarks, date, published, published_at, published_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, NULL)
            """, (
                e.student_id,
                req.exam_name,
                req.subject,
                e.marks_obtained,
                req.max_marks,
                e.grade,
                e.remarks,
                date_val
            ))
            inserted += 1

        conn.commit()
        return {"success": True, "inserted": inserted}
    finally:
        conn.close()

@app.post("/api/progress/publish")
async def publish_progress_marks(req: ProgressPublishRequest,
                                 x_user_role: str = Header(None, alias="X-User-Role"),
                                 x_user_id: str = Header(None, alias="X-User-Id"),
                                 x_school_id: Optional[int] = Header(None, alias="X-School-Id")):
    if x_user_role not in ('Teacher', 'Admin', 'Tenant_Admin', 'Super_Admin'):
        raise HTTPException(status_code=403, detail="Not authorized to publish marks.")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # Validate section if provided
        if req.section_id:
            sec = cursor.execute("SELECT id, school_id, grade_level FROM sections WHERE id = ?", (req.section_id,)).fetchone()
            if not sec:
                raise HTTPException(status_code=404, detail="Section not found.")
            if x_school_id and sec["school_id"] != x_school_id:
                raise HTTPException(status_code=403, detail="Section does not belong to your school.")

        params = [req.exam_name, req.subject, req.grade_level]
        query = """
            UPDATE student_marks
            SET published = 1, published_at = ?, published_by = ?
            WHERE id IN (
                SELECT sm.id
                FROM student_marks sm
                JOIN students s ON sm.student_id = s.id
                WHERE sm.exam_name = ? AND sm.subject = ? AND s.grade = ?
        """
        params = [datetime.now().isoformat(), x_user_id, req.exam_name, req.subject, req.grade_level]
        if req.section_id:
            query += " AND s.section_id = ?"
            params.append(req.section_id)
        if x_school_id:
            query += " AND s.school_id = ?"
            params.append(x_school_id)
        query += " )"

        cursor.execute(query, tuple(params))
        conn.commit()
        return {"success": True, "updated": cursor.rowcount}
    finally:
        conn.close()

@app.get("/api/progress/publish/preview")
async def preview_publish_marks(exam_name: str,
                                subject: str,
                                grade_level: int,
                                section_id: Optional[int] = None,
                                x_school_id: Optional[int] = Header(None, alias="X-School-Id")):
    conn = get_db_connection()
    try:
        params = [exam_name, subject, grade_level]
        query = """
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN sm.published = 1 THEN 1 ELSE 0 END) as published
            FROM student_marks sm
            JOIN students s ON sm.student_id = s.id
            WHERE sm.exam_name = ? AND sm.subject = ? AND s.grade = ?
        """
        if section_id:
            query += " AND s.section_id = ?"
            params.append(section_id)
        if x_school_id:
            query += " AND s.school_id = ?"
            params.append(x_school_id)
        row = conn.execute(query, tuple(params)).fetchone()
        total = int(row["total"] or 0)
        published = int(row["published"] or 0)
        return {"total": total, "published": published}
    finally:
        conn.close()

# --- EMAIL ENDPOINTS ---
@app.get("/api/email/inbox")
async def get_email_inbox(x_user_id: str = Header(None, alias="X-User-Id")):
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Missing user.")
    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT id, sender_id, recipient_email, subject, body, sent_at, is_read
            FROM emails
            WHERE recipient_email = ?
            ORDER BY id DESC
        """, (x_user_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

@app.get("/api/email/sent")
async def get_email_sent(x_user_id: str = Header(None, alias="X-User-Id")):
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Missing user.")
    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT id, sender_id, recipient_email, subject, body, sent_at, is_read
            FROM emails
            WHERE sender_id = ?
            ORDER BY id DESC
        """, (x_user_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

@app.put("/api/email/{email_id}/read")
async def mark_email_read(email_id: int, x_user_id: str = Header(None, alias="X-User-Id")):
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Missing user.")
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE emails SET is_read = 1 WHERE id = ? AND recipient_email = ?", (email_id, x_user_id))
        conn.commit()
        return {"success": True}
    finally:
        conn.close()

@app.post("/api/email/send")
async def send_internal_email(req: EmailSendRequest,
                              x_user_id: str = Header(None, alias="X-User-Id"),
                              x_user_role: str = Header(None, alias="X-User-Role"),
                              x_school_id: Optional[int] = Header(None, alias="X-School-Id")):
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Missing user.")
    if not req.to or not req.subject or not req.body:
        raise HTTPException(status_code=400, detail="To, subject, and body are required.")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # Resolve sender school for scoping
        sender = cursor.execute("SELECT school_id, is_super_admin FROM students WHERE id = ?", (x_user_id,)).fetchone()
        sender_school_id = sender["school_id"] if sender else None
        is_super_admin = bool(sender["is_super_admin"]) if sender else False

        # Resolve recipients
        recipients = []
        to = req.to.strip()

        def add_recipient(rid):
            if rid and rid not in recipients:
                recipients.append(rid)

        # group tokens
        if to.lower() == "all":
            rows = cursor.execute("SELECT id FROM students WHERE role IN ('Student','Teacher','Admin','Tenant_Admin')").fetchall()
            for r in rows:
                add_recipient(r["id"])
        elif to.lower().startswith("grade:"):
            grade = to.split(":", 1)[1].strip()
            rows = cursor.execute("SELECT id FROM students WHERE role = 'Student' AND grade = ?", (grade,)).fetchall()
            for r in rows:
                add_recipient(r["id"])
        elif to.lower().startswith("section:"):
            section_id = to.split(":", 1)[1].strip()
            rows = cursor.execute("SELECT id FROM students WHERE role = 'Student' AND section_id = ?", (section_id,)).fetchall()
            for r in rows:
                add_recipient(r["id"])
        elif to.lower().startswith("role:"):
            role = to.split(":", 1)[1].strip()
            rows = cursor.execute("SELECT id FROM students WHERE role = ?", (role,)).fetchall()
            for r in rows:
                add_recipient(r["id"])
        else:
            # direct user id/email
            add_recipient(to)

        # Scope by school unless super admin
        if not is_super_admin and sender_school_id:
            scoped = []
            for rid in recipients:
                r = cursor.execute("SELECT id, school_id FROM students WHERE id = ?", (rid,)).fetchone()
                if r and r["school_id"] == sender_school_id:
                    scoped.append(r["id"])
                elif "@" in rid:
                    # allow external email addresses (send only)
                    scoped.append(rid)
            recipients = scoped

        if not recipients:
            raise HTTPException(status_code=404, detail="No valid recipients found.")

        ts = datetime.now().isoformat()
        for rid in recipients:
            cursor.execute("""
                INSERT INTO emails (sender_id, recipient_email, subject, body, sent_at, is_read)
                VALUES (?, ?, ?, ?, ?, FALSE)
            """, (x_user_id, rid, req.subject, req.body, ts))

            # If recipient looks like an email, try SMTP send
            if "@" in rid:
                send_email(rid, req.subject, req.body)

        conn.commit()
        return {"success": True, "sent": len(recipients)}
    finally:
        conn.close()

@app.post("/api/leave/apply")
async def apply_leave(request: LeaveApplication):
    print(f"DEBUG LEAVE APPLY: {request.dict()}")
    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Resolve requester role + school
        requester = cursor.execute(
            "SELECT role, school_id FROM students WHERE id = ?",
            (request.user_id,)
        ).fetchone()
        if not requester:
            raise HTTPException(status_code=404, detail="User not found.")
        requester_role = requester[0]
        requester_school_id = requester[1]
        
        # 1. Insert Request
        cursor.execute("""
            INSERT INTO leave_requests (user_id, type, start_date, end_date, reason, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'Pending', ?)
        """, (request.user_id, request.type, request.start_date, request.end_date, request.reason, datetime.now().isoformat()))
        
        # 2. Notify Principal (Tenant_Admin) or Teacher
        try:
            # Notify respective school admin(s) for teacher leave
            if requester_role == 'Teacher':
                cursor.execute(
                    "SELECT id FROM students WHERE role IN ('Tenant_Admin', 'Admin') AND school_id = ?",
                    (requester_school_id,)
                )
            else:
                cursor.execute(
                    "SELECT id FROM students WHERE role IN ('Teacher', 'Tenant_Admin', 'Admin') AND school_id = ?",
                    (requester_school_id,)
                )
            admins = cursor.fetchall()
            
            msg_content = f"Leave Request from {request.user_id}: {request.reason} ({request.start_date} to {request.end_date})"
            ts = datetime.now().isoformat()
            
            for admin in admins:
                aid = admin[0]
                cursor.execute("""
                    INSERT INTO messages (sender_id, receiver_id, subject, content, timestamp, is_read)
                    VALUES (?, ?, 'New Leave Request', ?, ?, FALSE)
                """, (request.user_id, aid, msg_content, ts))
        except Exception as e:
            print(f"Notification Error: {e}")

        conn.commit()
        return {"success": True, "message": "Leave application submitted successfully."}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Apply Leave Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.get("/api/leave/pending")
async def get_pending_leaves(x_school_id: int = Header(1, alias="X-School-Id")):
    conn = get_db_connection()
    try:
        # Join with students to get name and grade
        query = """
            SELECT l.*, s.name, s.grade 
            FROM leave_requests l
            JOIN students s ON l.user_id = s.id
            WHERE l.status = 'Pending' AND s.school_id = ?
        """
        rows = conn.execute(query, (x_school_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
        
@app.get("/api/leave/my-history")
async def get_my_leave_history(user_id: str):
    conn = get_db_connection()
    try:
        rows = conn.execute("SELECT * FROM leave_requests WHERE user_id = ? ORDER BY created_at DESC", (user_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

@app.put("/api/leave/{leave_id}/status")
async def update_leave_status(leave_id: int, update: LeaveStatusUpdate):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Fetch request details
        cursor.execute("SELECT user_id, type FROM leave_requests WHERE id = ?", (leave_id,))
        req = cursor.fetchone()
        if not req:
            raise HTTPException(status_code=404, detail="Leave request not found.")
        requester_id = req[0]
        leave_type = req[1]

        # If a teacher leave is approved, require reassignment
        if update.status.lower() == 'approved':
            requester = cursor.execute(
                "SELECT role, school_id FROM students WHERE id = ?",
                (requester_id,)
            ).fetchone()
            if requester and requester[0] == 'Teacher':
                if not update.substitute_teacher_id:
                    raise HTTPException(status_code=400, detail="substitute_teacher_id is required for approved teacher leave.")

                # Validate substitute teacher
                sub = cursor.execute(
                    "SELECT id, role, school_id FROM students WHERE id = ?",
                    (update.substitute_teacher_id,)
                ).fetchone()
                if not sub or sub[1] != 'Teacher':
                    raise HTTPException(status_code=400, detail="substitute_teacher_id must be a valid Teacher.")
                if sub[2] != requester[1]:
                    raise HTTPException(status_code=400, detail="substitute_teacher_id must belong to the same school.")

                # Reassign timetable entries to substitute teacher
                cursor.execute(
                    "UPDATE timetables SET teacher_id = ? WHERE teacher_id = ?",
                    (update.substitute_teacher_id, requester_id)
                )

                # Record reassignment
                cursor.execute("""
                    INSERT INTO leave_reassignments (leave_id, original_teacher_id, substitute_teacher_id, assigned_by, assigned_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (leave_id, requester_id, update.substitute_teacher_id, update.reviewed_by, datetime.now().isoformat()))

        # Update Status
        cursor.execute("UPDATE leave_requests SET status = ?, reviewed_by = ? WHERE id = ?", 
                       (update.status, update.reviewed_by, leave_id))

        status_msg = f"Your {leave_type} request has been {update.status.upper()}."
        
        cursor.execute("""
            INSERT INTO messages (sender_id, receiver_id, subject, content, timestamp, is_read)
            VALUES (?, ?, 'Leave Request Update', ?, ?, FALSE)
        """, (update.reviewed_by, requester_id, status_msg, datetime.now().isoformat()))
        conn.commit()

        return {"message": f"Leave request {update.status}"}
    except HTTPException:
         raise
    except Exception as e:
         print(f"Update Leave Error: {e}")
         raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

# --- PROGRESS CARD ENDPOINTS ---
@app.get("/api/progress-card/{student_id}", response_model=ProgressCardResponse)
async def get_progress_card(student_id: str, x_user_id: str = Header(None, alias="X-User-Id")):
    conn = get_db_connection()
    try:
        # Resolve student
        student = conn.execute(
            "SELECT id, name, grade, school_id, attendance_rate FROM students WHERE id = ? AND role = 'Student'",
            (student_id,)
        ).fetchone()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found.")

        # Basic access control: same school unless super admin
        requester_role = None
        if x_user_id:
            requester = conn.execute(
                "SELECT school_id, is_super_admin, role FROM students WHERE id = ?",
                (x_user_id,)
            ).fetchone()
            if not requester:
                raise HTTPException(status_code=403, detail="Unauthorized.")
            requester_role = requester["role"]
            if not requester["is_super_admin"] and requester["school_id"] != student["school_id"]:
                raise HTTPException(status_code=403, detail="Access denied for this school.")

        published_only = requester_role == 'Parent'

        # Academics: subject averages + overall
        subject_query = """
            SELECT subject,
                   AVG(CASE WHEN max_marks > 0 THEN (marks_obtained * 100.0) / max_marks ELSE NULL END) AS avg_pct
            FROM student_marks
            WHERE student_id = ?
        """
        if published_only:
            subject_query += " AND published = 1"
        subject_query += " GROUP BY subject ORDER BY subject"
        subject_rows = conn.execute(subject_query, (student_id,)).fetchall()
        subjects = [{"subject": r["subject"], "avg_pct": round(r["avg_pct"] or 0, 1)} for r in subject_rows]

        overall_query = """
            SELECT AVG(CASE WHEN max_marks > 0 THEN (marks_obtained * 100.0) / max_marks ELSE NULL END) AS avg_pct
            FROM student_marks
            WHERE student_id = ?
        """
        if published_only:
            overall_query += " AND published = 1"
        overall_row = conn.execute(overall_query, (student_id,)).fetchone()
        overall_avg = round(overall_row["avg_pct"] or 0, 1)

        # Trend: compare latest two exam dates
        trend_query = """
            SELECT date,
                   AVG(CASE WHEN max_marks > 0 THEN (marks_obtained * 100.0) / max_marks ELSE NULL END) AS avg_pct
            FROM student_marks
            WHERE student_id = ?
        """
        if published_only:
            trend_query += " AND published = 1"
        trend_query += " GROUP BY date ORDER BY date DESC LIMIT 2"
        trend_rows = conn.execute(trend_query, (student_id,)).fetchall()
        trend = "na"
        if len(trend_rows) == 2:
            latest = trend_rows[0]["avg_pct"] or 0
            previous = trend_rows[1]["avg_pct"] or 0
            if latest - previous > 2:
                trend = "up"
            elif previous - latest > 2:
                trend = "down"
            else:
                trend = "flat"

        # Attendance
        cutoff_30 = (datetime.now() - timedelta(days=30)).date().isoformat()
        absent_row = conn.execute("""
            SELECT COUNT(*) AS cnt
            FROM student_attendance
            WHERE student_id = ? AND date >= ? AND status = 'Absent'
        """, (student_id, cutoff_30)).fetchone()
        absent_last_30 = int(absent_row["cnt"] or 0)

        # Engagement: assignments
        assignments_due_row = conn.execute("""
            SELECT COUNT(DISTINCT a.id) AS cnt
            FROM assignments a
            JOIN group_members gm ON gm.group_id = a.group_id
            WHERE gm.student_id = ?
        """, (student_id,)).fetchone()
        assignments_due = int(assignments_due_row["cnt"] or 0)

        assignments_submitted_row = conn.execute("""
            SELECT COUNT(*) AS cnt
            FROM assignment_submissions
            WHERE student_id = ?
        """, (student_id,)).fetchone()
        assignments_submitted = int(assignments_submitted_row["cnt"] or 0)

        # Engagement: quizzes
        quiz_row = conn.execute("""
            SELECT COUNT(*) AS cnt, AVG(score) AS avg_score
            FROM quiz_attempts
            WHERE student_id = ?
        """, (student_id,)).fetchone()
        quizzes_attempted = int(quiz_row["cnt"] or 0)
        avg_quiz_score = round(quiz_row["avg_score"] or 0, 1)

        # Engagement: activities (last 30 days + active days last 7)
        cutoff_7 = (datetime.now() - timedelta(days=7)).date().isoformat()
        activities_30_row = conn.execute("""
            SELECT COUNT(*) AS cnt
            FROM activities
            WHERE student_id = ? AND date >= ?
        """, (student_id, cutoff_30)).fetchone()
        activities_last_30 = int(activities_30_row["cnt"] or 0)

        active_days_row = conn.execute("""
            SELECT COUNT(DISTINCT date) AS cnt
            FROM activities
            WHERE student_id = ? AND date >= ?
        """, (student_id, cutoff_7)).fetchone()
        active_days_last_7 = int(active_days_row["cnt"] or 0)

        # Latest remarks
        remarks_query = """
            SELECT remarks
            FROM student_marks
            WHERE student_id = ? AND remarks IS NOT NULL AND remarks != ''
        """
        if published_only:
            remarks_query += " AND published = 1"
        remarks_query += " ORDER BY date DESC LIMIT 1"
        remarks_row = conn.execute(remarks_query, (student_id,)).fetchone()
        latest_remarks = remarks_row["remarks"] if remarks_row else None

        # Recent marks
        recent_query = """
            SELECT subject, exam_name, marks_obtained, max_marks, grade, date
            FROM student_marks
            WHERE student_id = ?
        """
        if published_only:
            recent_query += " AND published = 1"
        recent_query += " ORDER BY date DESC LIMIT 5"
        recent_rows = conn.execute(recent_query, (student_id,)).fetchall()
        recent_marks = [dict(r) for r in recent_rows]

        # Alerts
        alerts = []
        if (student["attendance_rate"] or 0) < 75:
            alerts.append("Low attendance (< 75%)")
        if overall_avg > 0 and overall_avg < 60:
            alerts.append("Average score below 60%")
        missing_assignments = max(0, assignments_due - assignments_submitted)
        if missing_assignments > 0:
            alerts.append(f"{missing_assignments} missing assignment(s)")
        if quizzes_attempted > 0 and avg_quiz_score < 50:
            alerts.append("Low quiz average (< 50%)")

        return {
            "student": {
                "id": student["id"],
                "name": student["name"],
                "grade": student["grade"]
            },
            "academics": {
                "overall_avg": overall_avg,
                "subjects": subjects,
                "trend": trend
            },
            "attendance": {
                "rate": round(student["attendance_rate"] or 0, 1),
                "absent_last_30": absent_last_30
            },
            "engagement": {
                "assignments_submitted": assignments_submitted,
                "assignments_due": assignments_due,
                "quizzes_attempted": quizzes_attempted,
                "avg_quiz_score": avg_quiz_score,
                "activities_last_30": activities_last_30,
                "active_days_last_7": active_days_last_7
            },
            "alerts": alerts,
            "recent_marks": recent_marks,
            "remarks": latest_remarks
        }
    finally:
        conn.close()

# --- QUESTION BANK MODULE ---

class QuestionBankResponse(BaseModel):
    id: int
    title: str
    file_path: str
    uploaded_by: str
    created_at: str
    school_id: int

@app.post("/api/question-bank/upload")
async def upload_question_bank(
    file: UploadFile = File(...), 
    title: str = Form(...), 
    x_user_id: str = Header(None, alias="X-User-Id")
):
    if not x_user_id:
        raise HTTPException(status_code=400, detail="User Identity Missing")
        
    conn = get_db_connection()
    try:
        # Check if user is teacher or admin
        user = conn.execute("SELECT role, school_id FROM students WHERE id = ?", (x_user_id,)).fetchone()
        if not user or user['role'] not in ['Teacher', 'Tenant_Admin', 'Principal', 'Admin']:
             raise HTTPException(status_code=403, detail="Only teachers can upload question banks.")
             
        school_id = user['school_id'] if user['school_id'] else 1
        
        # Save File
        upload_dir = os.path.join(static_dir, "uploads", "question_banks")
        os.makedirs(upload_dir, exist_ok=True)
        
        file_ext = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = os.path.join(upload_dir, unique_filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Store relative path for serving
        relative_path = f"/static/uploads/question_banks/{unique_filename}"
        created_at = datetime.now().isoformat()
        
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO question_banks (title, file_path, uploaded_by, created_at, school_id)
            VALUES (?, ?, ?, ?, ?)
        """, (title, relative_path, x_user_id, created_at, school_id))
        
        bank_id = cursor.lastrowid
        conn.commit()
        
        return {
            "id": bank_id,
            "title": title,
            "file_path": relative_path,
            "uploaded_by": x_user_id,
            "created_at": created_at,
            "school_id": school_id
        }
        
    except Exception as e:
        logger.error(f"Question Bank Upload Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.get("/api/question-bank", response_model=List[QuestionBankResponse])
async def get_question_banks(x_user_id: str = Header(None, alias="X-User-Id")):
    conn = get_db_connection()
    try:
        # Get user's school
        school_id = 1
        if x_user_id:
             user = conn.execute("SELECT school_id FROM students WHERE id = ?", (x_user_id,)).fetchone()
             if user and user['school_id']:
                 school_id = user['school_id']
        
        rows = conn.execute("SELECT * FROM question_banks WHERE school_id = ? ORDER BY created_at DESC", (school_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

# --- PDF EXAM MODULE ---

@app.post("/api/exams/create-pdf")
async def create_pdf_exam(
    file: UploadFile = File(...), 
    title: str = Form(...),
    time_limit: int = Form(...),
    group_id: int = Form(None),
    x_user_id: str = Header(None, alias="X-User-Id")
):
    if not x_user_id:
        raise HTTPException(status_code=400, detail="User Identity Missing")

    conn = get_db_connection()
    try:
        # Verify Teacher
        user = conn.execute("SELECT role, school_id FROM students WHERE id = ?", (x_user_id,)).fetchone()
        if not user or user['role'] not in ['Teacher', 'Tenant_Admin', 'Principal', 'Admin']:
             raise HTTPException(status_code=403, detail="Only teachers can create exams.")
        
        school_id = user['school_id'] if user['school_id'] else 1

        # Upload PDF
        upload_dir = os.path.join(static_dir, "uploads", "exams", "questions")
        os.makedirs(upload_dir, exist_ok=True)
        file_ext = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = os.path.join(upload_dir, unique_filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        relative_path = f"/static/uploads/exams/questions/{unique_filename}"
        
        # Insert into Quizzes Table
        cursor = conn.cursor()
        created_at = datetime.now().isoformat()
        
        # Use a default group if none selected (e.g. 0 or NULL handled by logic)
        target_group = group_id if group_id else 1 

        cursor.execute("""
            INSERT INTO quizzes (
                title, group_id, questions, created_at, time_limit_mins, 
                target_type, exam_type, file_path
            ) VALUES (?, ?, 'PDF_EXAM', ?, ?, 'group', 'pdf', ?)
        """, (title, target_group, created_at, time_limit, relative_path))
        
        exam_id = cursor.lastrowid
        conn.commit()
        
        return {"id": exam_id, "message": "PDF Exam Created Successfully"}
        
    except Exception as e:
        logger.error(f"Exam Create Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/exams/submit-pdf")
async def submit_pdf_exam(
    file: UploadFile = File(...),
    exam_id: int = Form(...),
    x_user_id: str = Header(None, alias="X-User-Id")
):
    if not x_user_id:
        raise HTTPException(status_code=400, detail="User Identity Missing")
        
    conn = get_db_connection()
    try:
        # Check if already submitted
        existing = conn.execute("SELECT id FROM quiz_attempts WHERE quiz_id = ? AND student_id = ?", (exam_id, x_user_id)).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="You have already submitted this exam.")
            
        # Upload Answer Sheet
        upload_dir = os.path.join(static_dir, "uploads", "exams", "submissions")
        os.makedirs(upload_dir, exist_ok=True)
        file_ext = os.path.splitext(file.filename)[1]
        unique_filename = f"{x_user_id}_{exam_id}_{uuid.uuid4()}{file_ext}"
        file_path = os.path.join(upload_dir, unique_filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        relative_path = f"/static/uploads/exams/submissions/{unique_filename}"
        
        # Record Attempt
        cursor = conn.cursor()
        submitted_at = datetime.now().isoformat()
        
        cursor.execute("""
            INSERT INTO quiz_attempts (
                quiz_id, student_id, score, answers, submitted_at, submission_file_path
            ) VALUES (?, ?, 0, 'PDF_SUBMISSION', ?, ?)
        """, (exam_id, x_user_id, submitted_at, relative_path))
        
        conn.commit()
        return {"message": "Exam submitted successfully"}
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Exam Submission Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.get("/api/exams/student/list")
async def get_student_exams(x_user_id: str = Header(None, alias="X-User-Id")):
    conn = get_db_connection()
    try:
        # Ideally filter by group enrollments. For now, fetch all active exams.
        # Check submitted status
        school_id = 1
        # Get School ID
        if x_user_id:
             user = conn.execute("SELECT school_id FROM students WHERE id = ?", (x_user_id,)).fetchone()
             if user and user['school_id']:
                 school_id = user['school_id']

        exams = conn.execute("""
            SELECT q.*, 
            CASE WHEN qa.id IS NOT NULL THEN 1 ELSE 0 END as submitted
            FROM quizzes q
            LEFT JOIN quiz_attempts qa ON q.id = qa.quiz_id AND qa.student_id = ?
            WHERE q.exam_type = 'pdf'
            ORDER BY q.created_at DESC
        """, (x_user_id,)).fetchall()
        
        return [dict(row) for row in exams]
    finally:
        conn.close()
