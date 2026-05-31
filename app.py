from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime, timedelta
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from io import BytesIO
import logging
from functools import wraps
import secrets
import re
from typing import Optional, Dict, Any
import json
import requests
from urllib.parse import urlencode

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('quiz_system.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Rate limiting configuration
RATE_LIMIT = {
    'login': {'max_attempts': 5, 'window': 300},  # 5 attempts per 5 minutes
    'test_submission': {'max_attempts': 3, 'window': 60}  # 3 attempts per minute
}

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', "10741631728-acc151piih0epd1a6kdu4hb32biar5qq.apps.googleusercontent.com")
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', "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")
GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI', "http://localhost:5000/google/callback")
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

# Admin email configuration - Add admin emails here
ADMIN_EMAILS = [
    'admin@somaiya.edu',
    'principal@somaiya.edu',
    'director@somaiya.edu',
    'dhruv.navadiya@somaiya.edu',
    'purushottam.nar@somaiya.edu',
    'shrinidhi.malli@somaiya.edu',# Add specific admin emails here
    # Add more admin emails as needed
]

def generate_csrf_token() -> str:
    """Generate a new CSRF token."""
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_urlsafe(32)
    return session['csrf_token']

# Register csrf_token function with Jinja2
app.jinja_env.globals['csrf_token'] = generate_csrf_token

class DatabaseConnection:
    def __init__(self):
        self.db_path = os.path.join(os.path.dirname(__file__), 'quiz_system.db')
    
    def __enter__(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        return self.conn
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if hasattr(self, 'conn'):
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
            self.conn.close()
        if exc_type:
            logger.error(f"Database error: {exc_val}")
            return False

def rate_limit(action: str) -> bool:
    """Check if the current request should be rate limited."""
    if action not in RATE_LIMIT:
        return False
    
    current_time = datetime.now()
    ip = request.remote_addr
    
    # Get existing attempts from session
    attempts = session.get(f'{action}_attempts', [])
    
    # Remove old attempts outside the window
    window = RATE_LIMIT[action]['window']
    attempts = [t for t in attempts if (current_time - datetime.fromisoformat(t)).total_seconds() < window]
    
    # Check if max attempts exceeded
    if len(attempts) >= RATE_LIMIT[action]['max_attempts']:
        return True
    
    # Add current attempt
    attempts.append(current_time.isoformat())
    session[f'{action}_attempts'] = attempts
    return False

def validate_email(email: str) -> bool:
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def validate_password(password: str) -> bool:
    """Validate password strength."""
    if len(password) < 6:
        return False
    if not re.search(r'[A-Z]', password):
        return False
    if not re.search(r'[a-z]', password):
        return False
    if not re.search(r'\d', password):
        return False
    return True

def sanitize_input(text: str) -> str:
    """Sanitize user input to prevent XSS."""
    return re.sub(r'<[^>]+>', '', text)

def validate_csrf_token(token: str) -> bool:
    """Validate the provided CSRF token."""
    if not token or 'csrf_token' not in session:
        return False
    return secrets.compare_digest(token, session['csrf_token'])

def validate_somaiya_email(email: str) -> bool:
    """Validate that email is from @somaiya.edu domain."""
    return email.lower().endswith('@somaiya.edu')

def is_admin_email(email: str) -> bool:
    """Check if the email should be treated as an admin account."""
    return email.lower() in [admin_email.lower() for admin_email in ADMIN_EMAILS]

def determine_user_role(email: str) -> str:
    """Determine if an email should be admin or student."""
    if is_admin_email(email):
        return 'admin'
    else:
        return 'student'  # All other @somaiya.edu emails become students

def get_google_auth_url() -> str:
    """Generate Google OAuth authorization URL."""
    params = {
        'client_id': GOOGLE_CLIENT_ID,
        'redirect_uri': GOOGLE_REDIRECT_URI,
        'scope': 'openid email profile',
        'response_type': 'code',
        'access_type': 'offline',
        'prompt': 'consent'
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

def exchange_code_for_token(code: str) -> Optional[Dict[str, Any]]:
    """Exchange authorization code for access token."""
    try:
        data = {
            'client_id': GOOGLE_CLIENT_ID,
            'client_secret': GOOGLE_CLIENT_SECRET,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': GOOGLE_REDIRECT_URI
        }
        
        response = requests.post(GOOGLE_TOKEN_URL, data=data)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Error exchanging code for token: {e}")
        return None

def get_google_user_info(access_token: str) -> Optional[Dict[str, Any]]:
    """Get user information from Google using access token."""
    try:
        headers = {'Authorization': f'Bearer {access_token}'}
        response = requests.get(GOOGLE_USERINFO_URL, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Error getting user info from Google: {e}")
        return None

# Authentication decorators
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            flash('Please login first', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated') or session.get('role') != 'admin':
            flash('Admin access required', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def student_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated') or session.get('role') != 'student':
            flash('Student access required', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def init_db():
    """Initialize the database with required tables and default data."""
    try:
        with DatabaseConnection() as conn:
            # Read and execute schema.sql
            schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
            with open(schema_path, 'r') as f:
                schema_sql = f.read()
            
            # Split the SQL file into individual statements
            statements = schema_sql.split(';')
            
            # Execute each statement
            for statement in statements:
                if statement.strip():
                    conn.execute(statement)
            
            # Set default hashed passwords for admin and student
            default_password = 'password'
            hashed_password = generate_password_hash(default_password)
            
            # Update admin password
            conn.execute("""
                UPDATE admins 
                SET password = ? 
                WHERE email = 'admin@example.com'
            """, (hashed_password,))
            
            # Update student password
            conn.execute("""
                UPDATE students 
                SET password = ? 
                WHERE email = 'student@example.com'
            """, (hashed_password,))
            
            conn.commit()
            
            # Verify that the accounts were created
            admin = conn.execute("SELECT admin_id FROM admins WHERE email = 'admin@example.com'").fetchone()
            student = conn.execute("SELECT student_id FROM students WHERE email = 'student@example.com'").fetchone()
            
            if not admin or not student:
                logger.warning("Default accounts not found after initialization")
            else:
                logger.info("Database initialized successfully")
                
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise

@app.route('/')
def index():
    # If already authenticated, redirect to appropriate dashboard
    if session.get('authenticated'):
        role = session.get('role')
        if role == 'admin':
            return redirect(url_for('admin'))
        elif role == 'student':
            return redirect(url_for('student'))
    
    # If not authenticated, show login page
    return render_template('login.html', csrf_token=generate_csrf_token())

@app.route('/login', methods=['POST'])
def login():
    if not validate_csrf_token(request.form.get('csrf_token')):
        flash('Invalid request', 'danger')
        return redirect(url_for('index'))
    
    if rate_limit('login'):
        flash('Too many login attempts. Please try again later.', 'danger')
        return redirect(url_for('index'))
    
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()
    
    logger.info(f"Login attempt - Email: {email}")
    
    # Input validation
    if not all([email, password]):
        flash('Please fill in all fields', 'danger')
        return redirect(url_for('index'))
    
    if not validate_email(email):
        flash('Invalid email format', 'danger')
        return redirect(url_for('index'))
    
    # Determine role based on email
    role = determine_user_role(email)
    
    try:
        with DatabaseConnection() as conn:
            c = conn.cursor()
            table = 'admins' if role == 'admin' else 'students'
            id_field = f"{role}_id"
            name_field = f"{role}_name"
            
            c.execute(f"""
                SELECT {id_field}, {name_field}, password, is_active
                FROM {table} 
                WHERE email = ? 
                LIMIT 1
            """, (email,))
            user = c.fetchone()
            
            if not user:
                logger.warning(f"Login failed - User not found: {email}")
                flash('Invalid email or password', 'danger')
                return redirect(url_for('index'))
            
            if not user['is_active']:
                logger.warning(f"Login failed - Account deactivated: {email}")
                flash('Account is deactivated. Please contact support.', 'danger')
                return redirect(url_for('index'))
            
            if check_password_hash(user['password'], password):
                # Clear any existing session data
                session.clear()
                
                # Update last login
                c.execute(f"UPDATE {table} SET last_login = datetime('now') WHERE {id_field} = ?", 
                         (user[id_field],))
                
                # Set new session data
                session.update({
                    'email': email,
                    'role': role,
                    f"{role}_id": user[id_field],
                    f"{role}_name": user[name_field],
                    'authenticated': True,
                    'csrf_token': generate_csrf_token()
                })
                session.permanent = True
                
                logger.info(f"{role.capitalize()} login successful: {email}")
                return redirect(url_for(role))
            
            logger.warning(f"Login failed - Invalid password for user: {email}")
            flash('Invalid email or password', 'danger')
            return redirect(url_for('index'))
            
    except Exception as e:
        logger.error(f"Login error: {e}")
        flash('An error occurred during login', 'danger')
        return redirect(url_for('index'))

@app.route('/google/login')
def google_login():
    """Redirect to Google OAuth authorization page."""
    auth_url = get_google_auth_url()
    return redirect(auth_url)

@app.route('/google/callback')
def google_callback():
    """Handle Google OAuth callback."""
    try:
        # Get authorization code from callback
        code = request.args.get('code')
        if not code:
            flash('Authorization failed. Please try again.', 'danger')
            return redirect(url_for('index'))
        
        # Exchange code for access token
        token_data = exchange_code_for_token(code)
        if not token_data or 'access_token' not in token_data:
            flash('Failed to authenticate with Google. Please try again.', 'danger')
            return redirect(url_for('index'))
        
        # Get user information from Google
        user_info = get_google_user_info(token_data['access_token'])
        if not user_info:
            flash('Failed to get user information from Google. Please try again.', 'danger')
            return redirect(url_for('index'))
        
        email = user_info.get('email', '').strip()
        name = user_info.get('name', '').strip()
        
        # Validate email domain
        if not validate_somaiya_email(email):
            flash('Only @somaiya.edu email addresses are allowed for Google Sign-In.', 'danger')
            return redirect(url_for('index'))
        
        logger.info(f"Google login attempt - Email: {email}")
        
        # Check if user exists in database
        with DatabaseConnection() as conn:
            c = conn.cursor()
            
            # Check in both admin and student tables
            c.execute("SELECT 'admin' as role, admin_id, admin_name, is_active FROM admins WHERE email = ?", (email,))
            admin_user = c.fetchone()
            
            c.execute("SELECT 'student' as role, student_id, student_name, is_active FROM students WHERE email = ?", (email,))
            student_user = c.fetchone()
            
            user = admin_user or student_user
            
            if not user:
                # Determine if this should be an admin or student account
                if is_admin_email(email):
                    # Create new admin account for Google user
                    c.execute("""
                        INSERT INTO admins (admin_name, email, password, created_at)
                        VALUES (?, ?, ?, datetime('now'))
                    """, (name, email, generate_password_hash(secrets.token_urlsafe(32))))
                    
                    admin_id = c.lastrowid
                    conn.commit()
                    
                    # Set session for new admin
                    session.clear()
                    session.update({
                        'email': email,
                        'role': 'admin',
                        'admin_id': admin_id,
                        'admin_name': name,
                        'authenticated': True,
                        'csrf_token': generate_csrf_token(),
                        'google_login': True
                    })
                    session.permanent = True
                    
                    logger.info(f"New admin account created via Google: {email}")
                    flash(f'Welcome {name}! Your admin account has been created successfully.', 'success')
                    return redirect(url_for('admin'))
                else:
                    # Create new student account for Google user
                    c.execute("""
                        INSERT INTO students (student_name, email, password, created_at)
                        VALUES (?, ?, ?, datetime('now'))
                    """, (name, email, generate_password_hash(secrets.token_urlsafe(32))))
                    
                    student_id = c.lastrowid
                    conn.commit()
                    
                    # Set session for new student
                    session.clear()
                    session.update({
                        'email': email,
                        'role': 'student',
                        'student_id': student_id,
                        'student_name': name,
                        'authenticated': True,
                        'csrf_token': generate_csrf_token(),
                        'google_login': True
                    })
                    session.permanent = True
                    
                    logger.info(f"New student account created via Google: {email}")
                    flash(f'Welcome {name}! Your account has been created successfully.', 'success')
                    return redirect(url_for('student'))
            
            # User exists, check if account is active
            if not user['is_active']:
                logger.warning(f"Google login failed - Account deactivated: {email}")
                flash('Account is deactivated. Please contact support.', 'danger')
                return redirect(url_for('index'))
            
            # Update last login
            table = 'admins' if user['role'] == 'admin' else 'students'
            id_field = f"{user['role']}_id"
            name_field = f"{user['role']}_name"
            
            c.execute(f"UPDATE {table} SET last_login = datetime('now') WHERE {id_field} = ?", 
                     (user[id_field],))
            
            # Set session data
            session.clear()
            session.update({
                'email': email,
                'role': user['role'],
                f"{user['role']}_id": user[id_field],
                f"{user['role']}_name": user[name_field],
                'authenticated': True,
                'csrf_token': generate_csrf_token(),
                'google_login': True
            })
            session.permanent = True
            
            conn.commit()
            
            logger.info(f"{user['role'].capitalize()} Google login successful: {email}")
            flash(f'Welcome back {user[name_field]}!', 'success')
            return redirect(url_for(user['role']))
            
    except Exception as e:
        logger.error(f"Google callback error: {e}")
        flash('An error occurred during Google authentication. Please try again.', 'danger')
        return redirect(url_for('index'))

@app.route('/admin')
@admin_required
def admin():
    try:
        with DatabaseConnection() as conn:
            c = conn.cursor()
            
            # Get admin details
            c.execute("""
                SELECT admin_id, admin_name, email 
                FROM admins 
                WHERE email = ?
            """, (session['email'],))
            admin = c.fetchone()
            
            if not admin:
                session.clear()
                flash('Admin record not found', 'danger')
                return redirect(url_for('index'))
                
            # Get all subjects with test counts
            c.execute("""
                SELECT s.subject_id, s.subject_name, 
                       COUNT(t.test_id) as test_count
                FROM subjects s
                LEFT JOIN tests t ON s.subject_id = t.subject_id
                GROUP BY s.subject_id, s.subject_name
                ORDER BY s.subject_name
            """)
            subjects = c.fetchall()
            
            # Get all tests with subject names and admin names
            c.execute("""
                SELECT t.test_id, t.test_name, s.subject_name, t.total_marks, 
                       a.admin_name, t.created_at, 
                       (SELECT COUNT(*) FROM questions WHERE test_id = t.test_id) as question_count,
                       (SELECT COUNT(*) FROM student_results WHERE test_id = t.test_id) as attempt_count
                FROM tests t
                JOIN subjects s ON t.subject_id = s.subject_id
                JOIN admins a ON t.admin_id = a.admin_id
                ORDER BY t.created_at DESC
            """)
            tests = c.fetchall()
            
            # Get tests created by current admin
            c.execute("""
                SELECT t.test_id, t.test_name, s.subject_name, t.total_marks, 
                       t.created_at, 
                       (SELECT COUNT(*) FROM questions WHERE test_id = t.test_id) as question_count,
                       (SELECT COUNT(*) FROM student_results WHERE test_id = t.test_id) as attempt_count
                FROM tests t
                JOIN subjects s ON t.subject_id = s.subject_id
                WHERE t.admin_id = ?
                ORDER BY t.created_at DESC
            """, (admin['admin_id'],))
            admin_tests = c.fetchall()
            
            # Format dates for admin_tests
            formatted_admin_tests = []
            for test in admin_tests:
                test_list = list(test)
                if test_list[4]:  # created_at
                    try:
                        created_at = datetime.strptime(test_list[4], '%Y-%m-%d %H:%M:%S')
                        test_list[4] = created_at.strftime('%B %d, %Y')
                    except (ValueError, TypeError):
                        test_list[4] = 'Unknown date'
                formatted_admin_tests.append(tuple(test_list))
            
            # Generate new CSRF token
            csrf_token = generate_csrf_token()
            
            return render_template('admin.html',
                                 admin=admin,
                                 subjects=subjects,
                                 tests=tests,
                                 admin_tests=formatted_admin_tests,
                                 csrf_token=csrf_token)
                                 
    except Exception as e:
        logger.error(f"Error in admin dashboard: {e}")
        flash('Error accessing dashboard', 'danger')
        return redirect(url_for('index'))

@app.route('/student')
@student_required
def student():
    try:
        with DatabaseConnection() as conn:
            c = conn.cursor()
            
            # Get student's details
            c.execute("""
                SELECT student_id, student_name, email 
                FROM students 
                WHERE email = ?
            """, (session['email'],))
            student = c.fetchone()
            
            if not student:
                session.clear()
                flash('Student record not found', 'danger')
                return redirect(url_for('index'))
            
            # Get available tests with their subjects
            c.execute("""
                SELECT t.test_id, s.subject_name, t.test_name, t.total_marks 
                FROM tests t 
                JOIN subjects s ON t.subject_id = s.subject_id
                WHERE t.test_id NOT IN (
                    SELECT test_id 
                    FROM student_results 
                    WHERE student_id = ?
                )
            """, (student['student_id'],))
            tests = c.fetchall()
            
            # Get test history
            c.execute("""
                SELECT 
                    t.test_name,
                    s.subject_name,
                    sr.marks_obtained,
                    t.total_marks,
                    sr.attempt_date,
                    t.test_id
                FROM student_results sr
                JOIN tests t ON sr.test_id = t.test_id
                JOIN subjects s ON t.subject_id = s.subject_id
                WHERE sr.student_id = ?
                ORDER BY sr.attempt_date DESC
            """, (student['student_id'],))
            history = c.fetchall()
            
            # Format dates in history
            formatted_history = []
            for result in history:
                result_list = list(result)
                if result_list[4]:  # attempt_date
                    try:
                        attempt_date = datetime.strptime(result_list[4], '%Y-%m-%d %H:%M:%S')
                        result_list[4] = attempt_date.strftime('%B %d, %Y')
                    except (ValueError, TypeError):
                        result_list[4] = 'Unknown date'
                formatted_history.append(tuple(result_list))
            
            return render_template('student.html',
                                 student_name=student['student_name'],
                                 student_email=student['email'],
                                 tests=tests,
                                 history=formatted_history)
    except Exception as e:
        logger.error(f"Error in student dashboard: {e}")
        flash('Error loading dashboard', 'danger')
        return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully', 'success')
    return redirect(url_for('index'))

@app.route('/admin/subjects/delete/<int:subject_id>', methods=['POST'])
@admin_required
def delete_subject(subject_id):
    try:
        with DatabaseConnection() as conn:
            c = conn.cursor()
            
            # Check if subject has any tests
            c.execute("SELECT COUNT(*) FROM tests WHERE subject_id = ?", (subject_id,))
            test_count = c.fetchone()[0]
            
            if test_count > 0:
                return jsonify({
                    'success': False,
                    'message': 'Cannot delete subject with existing tests'
                }), 400
            
            # Delete the subject
            c.execute("DELETE FROM subjects WHERE subject_id = ?", (subject_id,))
            conn.commit()
            
            return jsonify({'success': True})
            
    except Exception as e:
        logger.error(f"Error deleting subject: {e}")
        return jsonify({
            'success': False,
            'message': 'An error occurred while deleting the subject'
        }), 500

@app.route('/create_subject', methods=['POST'])
@admin_required
def create_subject():
    subject_name = request.form.get('subject_name', '').strip()
    
    if not subject_name:
        flash('Subject name is required', 'danger')
        return redirect(url_for('admin'))
    
    try:
        with DatabaseConnection() as conn:
            c = conn.cursor()
            
            # Check if subject already exists
            c.execute("SELECT subject_id FROM subjects WHERE subject_name = ?", (subject_name,))
            if c.fetchone():
                flash('Subject already exists', 'danger')
                return redirect(url_for('admin'))
            
            # Insert new subject
            c.execute("INSERT INTO subjects (subject_name) VALUES (?)", (subject_name,))
            conn.commit()
            
            flash('Subject added successfully', 'success')
            
    except Exception as e:
        logger.error(f"Error creating subject: {e}")
        flash('Error creating subject', 'danger')
    
    return redirect(url_for('admin'))

@app.route('/create_test', methods=['POST'])
@admin_required
def create_test():
    if not validate_csrf_token(request.form.get('csrf_token')):
        return jsonify({
            "success": False,
            "error": "Invalid request"
        })
    
    try:
        # Get form data
        test_name = request.form.get('test_name', '').strip()
        subject_id = request.form.get('subject_id')
        total_marks = request.form.get('total_marks')
        time_limit = request.form.get('time_limit', 30)
        admin_id = session.get('admin_id')
        
        # Validate required fields
        if not all([test_name, subject_id, total_marks, admin_id]):
            return jsonify({
                "success": False, 
                "error": "Please fill in all required fields"
            })
        
        # Validate subject exists
        with DatabaseConnection() as conn:
            c = conn.cursor()
            c.execute("SELECT subject_id FROM subjects WHERE subject_id = ?", (subject_id,))
            if not c.fetchone():
                return jsonify({
                    "success": False,
                    "error": "Selected subject does not exist"
                })
        
        # Get questions data
        questions = request.form.getlist('questions[]')
        marks = request.form.getlist('marks[]')
        
        # Validate questions data
        if not questions or not marks:
            return jsonify({
                "success": False,
                "error": "Please add at least one question"
            })
        
        # Validate total marks match sum of question marks
        try:
            total_marks = int(total_marks)
            sum_marks = sum(int(mark) for mark in marks)
            if total_marks != sum_marks:
                return jsonify({
                    "success": False,
                    "error": "Total marks must equal the sum of individual question marks"
                })
        except ValueError:
            return jsonify({
                "success": False,
                "error": "Invalid marks values provided"
            })
        
        with DatabaseConnection() as conn:
            c = conn.cursor()
            
            # Check for duplicate test name under the same subject
            c.execute("""
                SELECT test_name 
                FROM tests 
                WHERE test_name = ? AND subject_id = ?
            """, (test_name, subject_id))
            
            if c.fetchone():
                return jsonify({
                    "success": False, 
                    "error": "A test with this name already exists in this subject. Please choose a different name."
                })
            
            # Insert test
            c.execute("""
                INSERT INTO tests (test_name, subject_id, total_marks, admin_id, time_limit) 
                VALUES (?, ?, ?, ?, ?)
            """, (test_name, subject_id, total_marks, admin_id, time_limit))
            test_id = c.lastrowid
            
            # Insert questions and options
            for i, (question, mark) in enumerate(zip(questions, marks)):
                if not question.strip():
                    continue
                    
                try:
                    # Insert question first
                    c.execute("""
                        INSERT INTO questions (test_id, question_text, marks) 
                        VALUES (?, ?, ?)
                    """, (test_id, question.strip(), int(mark)))
                    question_id = c.lastrowid
                    
                    # Get options for this question
                    options = request.form.getlist(f'options[{i}][]')
                    correct = request.form.get(f'correct[{i}]')
                    
                    if not options or correct is None:
                        return jsonify({
                            "success": False,
                            "error": f"Please provide all options and select a correct answer for question {i + 1}"
                        })
                    
                    # Validate all 4 options are provided
                    if len(options) != 4:
                        return jsonify({
                            "success": False,
                            "error": f"Question {i + 1} must have exactly 4 options"
                        })
                    
                    correct_option_id = None
                    
                    # Insert all options
                    for j, option_text in enumerate(options):
                        if not option_text.strip():
                            return jsonify({
                                "success": False,
                                "error": f"Option {j + 1} for question {i + 1} cannot be empty"
                            })
                        
                        is_correct = (j == int(correct))
                        c.execute("""
                            INSERT INTO options (question_id, option_text, is_correct) 
                            VALUES (?, ?, ?)
                        """, (question_id, option_text.strip(), is_correct))
                        
                        if is_correct:
                            correct_option_id = c.lastrowid
                    
                    # Update the question with the correct_option_id
                    c.execute("""
                        UPDATE questions 
                        SET correct_option_id = ? 
                        WHERE question_id = ?
                    """, (correct_option_id, question_id))
                    
                except ValueError as e:
                    logger.error(f"Error processing question {i + 1}: {e}")
                    return jsonify({
                        "success": False,
                        "error": f"Invalid data for question {i + 1}"
                    })
            
            conn.commit()
            logger.info(f"Test '{test_name}' created successfully with ID {test_id}")
            return jsonify({"success": True, "test_id": test_id})
            
    except ValueError as e:
        logger.error(f"Value error while creating test: {e}")
        return jsonify({
            "success": False,
            "error": "Invalid input values provided"
        })
    except Exception as e:
        logger.error(f"Error creating test: {e}")
        return jsonify({
            "success": False,
            "error": "An error occurred while creating the test"
        })

@app.route('/take_test/<int:test_id>')
@student_required
def take_test(test_id):
    try:
        with DatabaseConnection() as conn:
            c = conn.cursor()
            
            # Get test details and check if it's active
            c.execute("""
                SELECT t.test_id, t.test_name, s.subject_name, t.total_marks, 
                       t.time_limit, t.passing_percentage
                FROM tests t 
                JOIN subjects s ON t.subject_id = s.subject_id 
                WHERE t.test_id = ? AND t.is_active = 1
            """, (test_id,))
            test = c.fetchone()
            
            if not test:
                flash('Test not found or is inactive', 'danger')
                return redirect(url_for('student'))
            
            # Check if student has already taken this test
            c.execute("""
                SELECT 1 FROM student_results 
                WHERE student_id = ? AND test_id = ?
            """, (session['student_id'], test_id))
            if c.fetchone():
                flash('You have already taken this test', 'warning')
                return redirect(url_for('student'))
            
            # Check for any abandoned attempts
            c.execute("""
                SELECT attempt_id, start_time 
                FROM test_attempts 
                WHERE student_id = ? AND test_id = ? AND status = 'abandoned'
                ORDER BY start_time DESC LIMIT 1
            """, (session['student_id'], test_id))
            abandoned_attempt = c.fetchone()
            
            if abandoned_attempt:
                # Delete abandoned attempt
                c.execute("DELETE FROM test_attempts WHERE attempt_id = ?", (abandoned_attempt['attempt_id'],))
                conn.commit()
            
            # Check if there's an active attempt
            c.execute("""
                SELECT attempt_id, start_time 
                FROM test_attempts 
                WHERE student_id = ? AND test_id = ? AND status = 'in_progress'
                ORDER BY start_time DESC LIMIT 1
            """, (session['student_id'], test_id))
            active_attempt = c.fetchone()
            
            if active_attempt:
                # Check if the attempt is within time limit
                start_time = datetime.strptime(active_attempt['start_time'], '%Y-%m-%d %H:%M:%S')
                time_elapsed = (datetime.now() - start_time).total_seconds()
                
                if time_elapsed > test['time_limit'] * 60:
                    # Mark attempt as abandoned
                    c.execute("""
                        UPDATE test_attempts 
                        SET status = 'abandoned', end_time = datetime('now')
                        WHERE attempt_id = ?
                    """, (active_attempt['attempt_id'],))
                    conn.commit()
                    flash('Previous attempt has expired. Starting a new attempt.', 'warning')
                else:
                    # Resume the attempt
                    time_remaining = test['time_limit'] * 60 - time_elapsed
                    
                    # Get questions and options
                    c.execute("""
                        SELECT q.question_id, q.question_text, q.marks, q.explanation,
                               o.option_id, o.option_text
                        FROM questions q
                        JOIN options o ON q.question_id = o.question_id
                        WHERE q.test_id = ?
                        ORDER BY q.question_id
                    """, (test_id,))
                    questions_data = c.fetchall()
                    
                    # Organize questions and options
                    questions = {}
                    for row in questions_data:
                        q_id, q_text, marks, explanation, o_id, o_text = row
                        if q_id not in questions:
                            questions[q_id] = {
                                'text': q_text,
                                'marks': marks,
                                'explanation': explanation,
                                'options': []
                            }
                        questions[q_id]['options'].append({'id': o_id, 'text': o_text})
                    
                    return render_template('take_test.html', 
                                         test=test, 
                                         questions=questions,
                                         attempt_id=active_attempt['attempt_id'],
                                         time_remaining=time_remaining)
            
            # Create new attempt
            c.execute("""
                INSERT INTO test_attempts (student_id, test_id, start_time, status)
                VALUES (?, ?, datetime('now'), 'in_progress')
            """, (session['student_id'], test_id))
            attempt_id = c.lastrowid
            conn.commit()
            
            # Get questions and options
            c.execute("""
                SELECT q.question_id, q.question_text, q.marks, q.explanation,
                       o.option_id, o.option_text
                FROM questions q
                JOIN options o ON q.question_id = o.question_id
                WHERE q.test_id = ?
                ORDER BY q.question_id
            """, (test_id,))
            questions_data = c.fetchall()
            
            # Organize questions and options
            questions = {}
            for row in questions_data:
                q_id, q_text, marks, explanation, o_id, o_text = row
                if q_id not in questions:
                    questions[q_id] = {
                        'text': q_text,
                        'marks': marks,
                        'explanation': explanation,
                        'options': []
                    }
                questions[q_id]['options'].append({'id': o_id, 'text': o_text})
            
            return render_template('take_test.html', 
                                 test=test, 
                                 questions=questions,
                                 attempt_id=attempt_id,
                                 time_remaining=test['time_limit'] * 60)
                                 
    except Exception as e:
        logger.error(f"Error loading test: {e}")
        flash('Error loading test', 'danger')
        return redirect(url_for('student'))

@app.route('/submit_test/<int:test_id>', methods=['POST'])
@student_required
def submit_test(test_id):
    if rate_limit('test_submission'):
        logger.warning(f"Rate limit exceeded for test submission - Test ID: {test_id}, Student ID: {session.get('student_id')}")
        flash('Too many submission attempts. Please try again later.', 'danger')
        return redirect(url_for('student'))
    
    if not validate_csrf_token(request.form.get('csrf_token')):
        logger.warning(f"Invalid CSRF token for test submission - Test ID: {test_id}, Student ID: {session.get('student_id')}")
        flash('Invalid request', 'danger')
        return redirect(url_for('student'))
    
    try:
        with DatabaseConnection() as conn:
            c = conn.cursor()
            
            # Get test details
            c.execute("""
                SELECT t.test_name, t.total_marks, t.passing_percentage, s.subject_name, t.time_limit
                FROM tests t
                JOIN subjects s ON t.subject_id = s.subject_id
                WHERE t.test_id = ? AND t.is_active = 1
            """, (test_id,))
            test_info = c.fetchone()
            
            if not test_info:
                logger.warning(f"Test not found or inactive - Test ID: {test_id}")
                flash('Test not found or is inactive', 'danger')
                return redirect(url_for('student'))
            
            # Verify attempt
            attempt_id = request.form.get('attempt_id')
            if not attempt_id:
                logger.warning(f"Missing attempt ID for test submission - Test ID: {test_id}, Student ID: {session.get('student_id')}")
                flash('Invalid test attempt', 'danger')
                return redirect(url_for('student'))
            
            # Get attempt details
            c.execute("""
                SELECT start_time, status
                FROM test_attempts
                WHERE attempt_id = ? AND student_id = ? AND test_id = ?
            """, (attempt_id, session['student_id'], test_id))
            attempt = c.fetchone()
            
            if not attempt:
                logger.warning(f"Attempt not found - Attempt ID: {attempt_id}, Test ID: {test_id}, Student ID: {session.get('student_id')}")
                flash('Invalid test attempt', 'danger')
                return redirect(url_for('student'))
            
            # Check if attempt is already completed
            if attempt['status'] == 'completed':
                logger.warning(f"Attempt already completed - Attempt ID: {attempt_id}, Test ID: {test_id}, Student ID: {session.get('student_id')}")
                flash('This test has already been submitted', 'warning')
                return redirect(url_for('student'))
            
            # Check time limit
            start_time = datetime.strptime(attempt['start_time'], '%Y-%m-%d %H:%M:%S')
            time_taken = (datetime.now() - start_time).total_seconds()
            time_exceeded = time_taken > test_info['time_limit'] * 60
            
            if time_exceeded:
                logger.warning(f"Time limit exceeded - Test ID: {test_id}, Student ID: {session.get('student_id')}")
                flash('Test time limit exceeded, but your answers will still be processed', 'warning')
            
            total_score = 0
            question_results = []
            
            # Process answers
            answers = request.form
            if not answers:
                logger.warning(f"No answers submitted - Test ID: {test_id}, Student ID: {session.get('student_id')}")
                flash('No answers submitted', 'danger')
                return redirect(url_for('take_test', test_id=test_id))
            
            # Process each answer
            for question_id, selected_option_id in answers.items():
                if not question_id.startswith('question-'):
                    continue
                    
                try:
                    question_id = int(question_id.split('-')[1])
                    selected_option_id = int(selected_option_id)
                except ValueError:
                    logger.warning(f"Invalid question or option ID format - Test ID: {test_id}, Question ID: {question_id}")
                    continue
                    
                # Get question details including the correct option
                c.execute("""
                    SELECT 
                        q.question_text, 
                        q.marks,
                        q.explanation,
                        q.correct_option_id,
                        o_selected.option_text as selected_answer,
                        o_correct.option_text as correct_answer
                    FROM questions q
                    LEFT JOIN options o_selected ON o_selected.option_id = ?
                    LEFT JOIN options o_correct ON o_correct.option_id = q.correct_option_id
                    WHERE q.question_id = ?
                """, (selected_option_id, question_id))
                
                question_data = c.fetchone()
                
                if not question_data:
                    logger.warning(f"Question data not found - Question ID: {question_id}, Test ID: {test_id}")
                    continue
                    
                question_text, marks, explanation, correct_option_id, selected_answer, correct_answer = question_data
                
                # Check if answer is correct
                is_correct = (selected_option_id == correct_option_id)
                
                # Update total score if answer is correct
                if is_correct:
                    total_score += marks
                
                # Add to question results
                question_results.append({
                    'question_text': question_text,
                    'selected_answer': selected_answer,
                    'correct_answer': correct_answer,
                    'explanation': explanation,
                    'is_correct': is_correct,
                    'marks': marks if is_correct else 0,
                    'total_marks': marks
                })
            
            # Calculate percentage
            percentage = (total_score / test_info['total_marks']) * 100 if test_info['total_marks'] > 0 else 0
            
            # Save result
            c.execute("""
                INSERT INTO student_results 
                (student_id, test_id, marks_obtained, percentage, attempt_date, time_taken)
                VALUES (?, ?, ?, ?, datetime('now'), ?)
            """, (session['student_id'], test_id, total_score, percentage, time_taken))
            
            # Update attempt status
            c.execute("""
                UPDATE test_attempts 
                SET status = 'completed', end_time = datetime('now')
                WHERE attempt_id = ?
            """, (attempt_id,))
            
            conn.commit()
            
            # Store result data in session for the result page
            result_data = {
                'test_name': test_info['test_name'],
                'subject_name': test_info['subject_name'],
                'total_score': total_score,
                'total_marks': test_info['total_marks'],
                'percentage': percentage,
                'passing_percentage': test_info['passing_percentage'],
                'question_results': question_results,
                'test_id': test_id,
                'time_taken': time_taken,
                'attempt_date': datetime.now().strftime('%B %d, %Y %H:%M:%S')
            }
            
            logger.info(f"Test submitted successfully - Test ID: {test_id}, Student ID: {session['student_id']}, Score: {total_score}/{test_info['total_marks']}")
            session['last_test_result'] = result_data
            
            # Verify session data was stored
            if 'last_test_result' not in session:
                logger.error(f"Failed to store result in session - Test ID: {test_id}, Student ID: {session['student_id']}")
                flash('Error saving test result. Please try again.', 'danger')
                return redirect(url_for('student'))
            
            return redirect(url_for('show_test_result'))
            
    except Exception as e:
        logger.error(f"Error submitting test: {e}")
        flash('Error submitting test. Please try again.', 'danger')
        return redirect(url_for('take_test', test_id=test_id))

@app.route('/test_result')
@student_required
def show_test_result():
    try:
        result = session.get('last_test_result')
        if not result:
            logger.warning(f"No test result found in session for student {session.get('student_id')}")
            flash('No test result found. Please take a test first.', 'warning')
            return redirect(url_for('student'))
        
        logger.info(f"Displaying test result for student {session.get('student_id')} - Test: {result.get('test_name')}")
        return render_template('test_result.html', result=result)
    except Exception as e:
        logger.error(f"Error displaying test result: {e}")
        flash('Error displaying test result. Please try again.', 'danger')
        return redirect(url_for('student'))

@app.route('/view_results')
@admin_required
def view_results():
    try:
        with DatabaseConnection() as conn:
            c = conn.cursor()
            
            # Get all subjects
            c.execute("SELECT subject_id, subject_name FROM subjects ORDER BY subject_name")
            subjects = c.fetchall()
            
            # Get all results with student names, subject names, and test names
            c.execute("""
                SELECT 
                    s.student_name,
                    sub.subject_name,
                    t.test_name,
                    sr.marks_obtained,
                    t.total_marks,
                    (CAST(sr.marks_obtained AS FLOAT) / t.total_marks * 100) as percentage,
                    sr.attempt_date,
                    sub.subject_id,
                    t.test_id
                FROM student_results sr
                JOIN students s ON sr.student_id = s.student_id
                JOIN tests t ON sr.test_id = t.test_id
                JOIN subjects sub ON t.subject_id = sub.subject_id
                ORDER BY sub.subject_name, t.test_name, percentage DESC
            """)
            all_results = c.fetchall()
            
            # Organize results by subject and test
            organized_results = {}
            
            for result in all_results:
                student_name, subject_name, test_name, marks, total_marks, percentage, attempt_date, subject_id, test_id = result
                
                # Format the date
                try:
                    formatted_date = datetime.strptime(attempt_date, '%Y-%m-%d %H:%M:%S').strftime('%B %d, %Y')
                except (ValueError, TypeError):
                    formatted_date = "Unknown date"
                
                # Create subject key if it doesn't exist
                if subject_id not in organized_results:
                    organized_results[subject_id] = {
                        'name': subject_name,
                        'tests': {}
                    }
                
                # Create test key if it doesn't exist
                test_key = f"{test_id}"
                if test_key not in organized_results[subject_id]['tests']:
                    organized_results[subject_id]['tests'][test_key] = {
                        'name': test_name,
                        'total_marks': total_marks,
                        'results': [],
                        'stats': {
                            'highest': 0,
                            'lowest': total_marks,
                            'average': 0,
                            'total_attempts': 0,
                            'pass_count': 0
                        }
                    }
                
                # Add result to the test
                result_data = {
                    'student_name': student_name,
                    'marks': marks,
                    'percentage': percentage,
                    'attempt_date': formatted_date,
                    'status': 'PASS' if percentage >= 60 else 'FAIL'
                }
                organized_results[subject_id]['tests'][test_key]['results'].append(result_data)
                
                # Update test statistics
                stats = organized_results[subject_id]['tests'][test_key]['stats']
                stats['highest'] = max(stats['highest'], marks)
                stats['lowest'] = min(stats['lowest'], marks)
                stats['total_attempts'] += 1
                if percentage >= 60:
                    stats['pass_count'] += 1
                
                # Calculate average
                total_marks_sum = sum(r['marks'] for r in organized_results[subject_id]['tests'][test_key]['results'])
                stats['average'] = total_marks_sum / stats['total_attempts']
            
            # Sort results for each test by percentage in descending order
            for subject in organized_results.values():
                for test in subject['tests'].values():
                    test['results'].sort(key=lambda x: x['percentage'], reverse=True)
            
            return render_template(
                'view_results.html',
                results=organized_results,
                subjects=subjects
            )
            
    except Exception as e:
        logger.error(f"Error loading results: {e}")
        flash('Error loading results', 'danger')
        return redirect(url_for('admin'))

@app.route('/student/history')
@student_required
def student_history():
    try:
        with DatabaseConnection() as conn:
            c = conn.cursor()
            
            # Get student's details
            c.execute("SELECT student_id, student_name FROM students WHERE email = ?", (session['email'],))
            student = c.fetchone()
            
            if not student:
                flash('Student record not found', 'danger')
                return redirect(url_for('index'))
            
            # Get student's test history
            c.execute("""
                SELECT 
                    t.test_name,
                    s.subject_name,
                    sr.marks_obtained,
                    t.total_marks,
                    sr.attempt_date,
                    t.test_id
                FROM student_results sr
                JOIN tests t ON sr.test_id = t.test_id
                JOIN subjects s ON t.subject_id = s.subject_id
                WHERE sr.student_id = ?
                ORDER BY sr.attempt_date DESC
            """, (student['student_id'],))
            results = c.fetchall()
            
            # Format dates in results
            formatted_results = []
            for result in results:
                result_list = list(result)
                if result_list[4]:  # attempt_date
                    try:
                        attempt_date = datetime.strptime(result_list[4], '%Y-%m-%d %H:%M:%S')
                        result_list[4] = attempt_date.strftime('%B %d, %Y')
                    except (ValueError, TypeError):
                        result_list[4] = 'Unknown date'
                formatted_results.append(tuple(result_list))
            
            return render_template('student_history.html', 
                                 results=formatted_results, 
                                 student_name=student['student_name'])
    except Exception as e:
        logger.error(f"Error loading student history: {e}")
        flash('Error loading test history', 'danger')
        return redirect(url_for('student'))

@app.route('/download_certificate/<int:test_id>')
@student_required
def download_certificate(test_id):
    try:
        with DatabaseConnection() as conn:
            c = conn.cursor()
            
            # Get student's details and test result
            c.execute("""
                SELECT 
                    s.student_name,
                    t.test_name,
                    sub.subject_name,
                    sr.marks_obtained,
                    t.total_marks,
                    sr.percentage,
                    sr.attempt_date,
                    t.passing_percentage
                FROM student_results sr
                JOIN students s ON sr.student_id = s.student_id
                JOIN tests t ON sr.test_id = t.test_id
                JOIN subjects sub ON t.subject_id = sub.subject_id
                WHERE sr.test_id = ? AND s.email = ?
                ORDER BY sr.attempt_date DESC LIMIT 1
            """, (test_id, session['email']))
            
            result = c.fetchone()
            if not result:
                flash('Test result not found', 'danger')
                return redirect(url_for('student_history'))
            
            if result['percentage'] < result['passing_percentage']:
                flash('Certificate is only available for passing scores', 'warning')
                return redirect(url_for('student_history'))
            
            # Create PDF certificate
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter)
            styles = getSampleStyleSheet()
            
            # Create custom styles
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=28,
                spaceAfter=40,
                alignment=1,  # Center alignment
                textColor=colors.HexColor('#2C3E50')
            )
            
            content_style = ParagraphStyle(
                'CustomContent',
                parent=styles['Normal'],
                fontSize=16,
                spaceAfter=20,
                alignment=1,  # Center alignment
                textColor=colors.HexColor('#34495E')
            )
            
            # Create certificate content
            story = []
            
            # Add decorative border
            story.append(Spacer(1, 30))
            
            # Add title
            story.append(Paragraph("Certificate of Achievement", title_style))
            story.append(Spacer(1, 20))
            
            # Add decorative line
            story.append(Paragraph("<hr/>", content_style))
            story.append(Spacer(1, 30))
            
            # Add content
            story.append(Paragraph("This is to certify that", content_style))
            story.append(Paragraph(f"<b>{result['student_name']}</b>", content_style))
            story.append(Paragraph("has successfully completed the test", content_style))
            story.append(Paragraph(f"<b>{result['test_name']}</b>", content_style))
            story.append(Paragraph(f"in <b>{result['subject_name']}</b>", content_style))
            story.append(Paragraph(f"with a score of <b>{result['marks_obtained']}/{result['total_marks']}</b>", content_style))
            story.append(Paragraph(f"(<b>{result['percentage']:.1f}%</b>)", content_style))
            story.append(Paragraph(f"on {result['attempt_date']}", content_style))
            
            # Add decorative line
            story.append(Spacer(1, 30))
            story.append(Paragraph("<hr/>", content_style))
            
            # Add footer
            footer_style = ParagraphStyle(
                'CustomFooter',
                parent=styles['Normal'],
                fontSize=12,
                spaceBefore=20,
                alignment=1,
                textColor=colors.HexColor('#7F8C8D')
            )
            story.append(Paragraph("Quizora - Online Quiz Platform", footer_style))
            story.append(Paragraph("Certificate ID: " + secrets.token_urlsafe(8), footer_style))
            
            # Build PDF
            doc.build(story)
            
            # Prepare the response
            buffer.seek(0)
            return send_file(
                buffer,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=f'certificate_{result["test_name"]}_{datetime.now().strftime("%Y%m%d")}.pdf'
            )
    except Exception as e:
        logger.error(f"Error generating certificate: {e}")
        flash('Error generating certificate', 'danger')
        return redirect(url_for('student_history'))

@app.route('/admin/profile')
@admin_required
def admin_profile():
    try:
        with DatabaseConnection() as conn:
            c = conn.cursor()
            
            # Get admin details
            c.execute("""
                SELECT admin_id, admin_name, email, created_at, last_login, is_active
                FROM admins 
                WHERE admin_id = ?
            """, (session['admin_id'],))
            admin = c.fetchone()
            
            if not admin:
                flash('Admin record not found', 'danger')
                return redirect(url_for('admin'))
            
            # Get tests created by this admin with statistics
            c.execute('''
                SELECT 
                    t.test_id, 
                    t.test_name, 
                    s.subject_name, 
                    t.total_marks,
                    t.passing_percentage,
                    t.is_active,
                    t.created_at,
                    t.updated_at,
                    (SELECT COUNT(*) FROM student_results WHERE test_id = t.test_id) as attempts,
                    (SELECT AVG(percentage) FROM student_results WHERE test_id = t.test_id) as avg_score,
                    (SELECT COUNT(*) FROM student_results WHERE test_id = t.test_id AND percentage >= t.passing_percentage) as pass_count
                FROM tests t
                JOIN subjects s ON t.subject_id = s.subject_id
                WHERE t.admin_id = ?
                ORDER BY t.created_at DESC
            ''', (session['admin_id'],))
            tests = c.fetchall()
            
            # Format dates and calculate statistics
            formatted_tests = []
            for test in tests:
                test_dict = dict(test)
                for date_field in ['created_at', 'updated_at']:
                    if test_dict[date_field]:
                        try:
                            date = datetime.strptime(test_dict[date_field], '%Y-%m-%d %H:%M:%S')
                            test_dict[date_field] = date.strftime('%B %d, %Y')
                        except (ValueError, TypeError):
                            test_dict[date_field] = 'Unknown date'
                
                # Calculate pass rate
                if test_dict['attempts'] > 0:
                    test_dict['pass_rate'] = (test_dict['pass_count'] / test_dict['attempts']) * 100
                else:
                    test_dict['pass_rate'] = 0
                
                formatted_tests.append(test_dict)
            
            return render_template('admin_profile.html', 
                                 admin=admin, 
                                 tests=formatted_tests)
    except Exception as e:
        logger.error(f"Error loading admin profile: {e}")
        flash('Error loading profile', 'danger')
        return redirect(url_for('admin'))

@app.route('/admin/profile/update', methods=['POST'])
@admin_required
def update_admin_profile():
    if not validate_csrf_token(request.form.get('csrf_token')):
        return jsonify({'success': False, 'error': 'Invalid request'})
    
    try:
        admin_name = request.form.get('admin_name', '').strip()
        current_password = request.form.get('current_password', '').strip()
        new_password = request.form.get('new_password', '').strip()
        
        # Input validation
        if not admin_name:
            return jsonify({'success': False, 'error': 'Name is required'})
        
        if not current_password:
            return jsonify({'success': False, 'error': 'Current password is required'})
        
        if new_password and not validate_password(new_password):
            return jsonify({
                'success': False, 
                'error': 'New password must be at least 8 characters long and contain uppercase, lowercase, and numbers'
            })
        
        with DatabaseConnection() as conn:
            c = conn.cursor()
            
            # Verify current password
            c.execute("SELECT password FROM admins WHERE email = ?", (session.get('email'),))
            admin = c.fetchone()
            
            if not admin or not check_password_hash(admin['password'], current_password):
                return jsonify({'success': False, 'error': 'Current password is incorrect'})
            
            # Update profile
            if new_password:
                c.execute("""
                    UPDATE admins 
                    SET admin_name = ?, 
                        password = ?,
                        updated_at = datetime('now')
                    WHERE email = ?
                """, (admin_name, generate_password_hash(new_password), session.get('email')))
            else:
                c.execute("""
                    UPDATE admins 
                    SET admin_name = ?,
                        updated_at = datetime('now')
                    WHERE email = ?
                """, (admin_name, session.get('email')))
            
            conn.commit()
            
            # Update session data
            session['admin_name'] = admin_name
            
            return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error updating admin profile: {e}")
        return jsonify({'success': False, 'error': 'An error occurred while updating the profile'})

@app.route('/admin/students')
@admin_required
def manage_students():
    try:
        with DatabaseConnection() as conn:
            c = conn.cursor()
            
            # Get all students with their test statistics
            c.execute("""
                SELECT 
                    s.student_id,
                    s.student_name,
                    s.email,
                    s.created_at,
                    s.last_login,
                    s.is_active,
                    COUNT(DISTINCT sr.test_id) as tests_taken,
                    AVG(sr.percentage) as avg_score,
                    COUNT(DISTINCT CASE WHEN sr.percentage >= t.passing_percentage THEN sr.test_id END) as passed_tests,
                    COUNT(DISTINCT CASE WHEN sr.percentage < t.passing_percentage THEN sr.test_id END) as failed_tests
                FROM students s
                LEFT JOIN student_results sr ON s.student_id = sr.student_id
                LEFT JOIN tests t ON sr.test_id = t.test_id
                GROUP BY s.student_id
                ORDER BY s.student_name
            """)
            students = c.fetchall()
            
            # Format dates and calculate statistics
            formatted_students = []
            for student in students:
                student_dict = dict(student)
                for date_field in ['created_at', 'last_login']:
                    if student_dict[date_field]:
                        try:
                            date = datetime.strptime(student_dict[date_field], '%Y-%m-%d %H:%M:%S')
                            student_dict[date_field] = date.strftime('%B %d, %Y')
                        except (ValueError, TypeError):
                            student_dict[date_field] = 'Unknown date'
                
                # Calculate pass rate
                if student_dict['tests_taken'] > 0:
                    student_dict['pass_rate'] = (student_dict['passed_tests'] / student_dict['tests_taken']) * 100
                else:
                    student_dict['pass_rate'] = 0
                
                formatted_students.append(student_dict)
            
            return render_template('manage_students.html', students=formatted_students)
    except Exception as e:
        logger.error(f"Error loading students: {e}")
        flash('Error loading students', 'danger')
        return redirect(url_for('admin'))

@app.route('/admin/students/add', methods=['POST'])
@admin_required
def add_student():
    if not validate_csrf_token(request.form.get('csrf_token')):
        return jsonify({'success': False, 'error': 'Invalid request'})
    
    try:
        student_name = request.form.get('student_name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        
        # Input validation
        if not all([student_name, email, password]):
            return jsonify({'success': False, 'error': 'All fields are required'})
        
        if not validate_email(email):
            return jsonify({'success': False, 'error': 'Invalid email format'})
        
        if not validate_password(password):
            return jsonify({
                'success': False, 
                'error': 'Password must be at least 8 characters long and contain uppercase, lowercase, and numbers'
            })
        
        with DatabaseConnection() as conn:
            c = conn.cursor()
            
            # Check if email already exists
            c.execute("SELECT 1 FROM students WHERE email = ?", (email,))
            if c.fetchone():
                return jsonify({'success': False, 'error': 'Email already registered'})
            
            # Add new student
            c.execute("""
                INSERT INTO students (student_name, email, password, created_at)
                VALUES (?, ?, ?, datetime('now'))
            """, (student_name, email, generate_password_hash(password)))
            
            conn.commit()
            return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error adding student: {e}")
        return jsonify({'success': False, 'error': 'An error occurred while adding the student'})

@app.route('/admin/students/delete/<int:student_id>', methods=['POST'])
@admin_required
def delete_student(student_id):
    if not validate_csrf_token(request.form.get('csrf_token')):
        return jsonify({'success': False, 'error': 'Invalid request'})
    
    try:
        with DatabaseConnection() as conn:
            c = conn.cursor()
            
            # Check if student exists
            c.execute("SELECT student_name FROM students WHERE student_id = ?", (student_id,))
            student = c.fetchone()
            
            if not student:
                return jsonify({'success': False, 'error': 'Student not found'})
            
            # Delete student's results first
            c.execute("DELETE FROM student_results WHERE student_id = ?", (student_id,))
            
            # Delete student's test attempts
            c.execute("DELETE FROM test_attempts WHERE student_id = ?", (student_id,))
            
            # Delete student
            c.execute("DELETE FROM students WHERE student_id = ?", (student_id,))
            
            conn.commit()
            return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error deleting student: {e}")
        return jsonify({'success': False, 'error': 'An error occurred while deleting the student'})

@app.route('/admin/students/toggle_status/<int:student_id>', methods=['POST'])
@admin_required
def toggle_student_status(student_id):
    if not validate_csrf_token(request.form.get('csrf_token')):
        return jsonify({'success': False, 'error': 'Invalid request'})
    
    try:
        with DatabaseConnection() as conn:
            c = conn.cursor()
            
            # Get current status
            c.execute("SELECT is_active FROM students WHERE student_id = ?", (student_id,))
            student = c.fetchone()
            
            if not student:
                return jsonify({'success': False, 'error': 'Student not found'})
            
            # Toggle status
            new_status = not student['is_active']
            c.execute("""
                UPDATE students 
                SET is_active = ?,
                    updated_at = datetime('now')
                WHERE student_id = ?
            """, (new_status, student_id))
            
            conn.commit()
            return jsonify({
                'success': True,
                'is_active': new_status,
                'message': 'Student activated' if new_status else 'Student deactivated'
            })
    except Exception as e:
        logger.error(f"Error toggling student status: {e}")
        return jsonify({'success': False, 'error': 'An error occurred while updating student status'})

@app.route('/student/profile/update', methods=['POST'])
@student_required
def update_student_profile():
    try:
        student_name = request.form.get('student_name')
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        
        with DatabaseConnection() as conn:
            c = conn.cursor()
            
            # Verify current password
            c.execute("SELECT password FROM students WHERE email = ?", (session.get('email'),))
            student = c.fetchone()
            
            if not student or not check_password_hash(student['password'], current_password):
                return jsonify({'success': False, 'error': 'Current password is incorrect'})
            
            # Update profile
            if new_password:
                c.execute("UPDATE students SET student_name = ?, password = ? WHERE email = ?",
                         (student_name, generate_password_hash(new_password), session.get('email')))
            else:
                c.execute("UPDATE students SET student_name = ? WHERE email = ?",
                         (student_name, session.get('email')))
            
            conn.commit()
            
            # Update session data
            session['student_name'] = student_name
            
            return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error updating student profile: {e}")
        return jsonify({'success': False, 'error': 'An error occurred while updating the profile'})

if __name__ == '__main__':
    init_db()
    app.run(debug=True)