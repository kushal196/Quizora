-- Drop existing tables if they exist
DROP TABLE IF EXISTS student_results;
DROP TABLE IF EXISTS options;
DROP TABLE IF EXISTS questions;
DROP TABLE IF EXISTS tests;
DROP TABLE IF EXISTS students;
DROP TABLE IF EXISTS subjects;
DROP TABLE IF EXISTS admins;
DROP TABLE IF EXISTS test_attempts;

-- Drop existing indexes if they exist
DROP INDEX IF EXISTS idx_admins_email;
DROP INDEX IF EXISTS idx_students_email;
DROP INDEX IF EXISTS idx_tests_subject;
DROP INDEX IF EXISTS idx_tests_admin;
DROP INDEX IF EXISTS idx_questions_test;
DROP INDEX IF EXISTS idx_options_question;
DROP INDEX IF EXISTS idx_results_student;
DROP INDEX IF EXISTS idx_results_test;
DROP INDEX IF EXISTS idx_attempts_student;
DROP INDEX IF EXISTS idx_attempts_test;
DROP INDEX IF EXISTS idx_tests_name_subject;
DROP INDEX IF EXISTS idx_questions_text;
DROP INDEX IF EXISTS idx_options_text;

-- Create admins table
CREATE TABLE IF NOT EXISTS admins (
    admin_id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    is_active BOOLEAN DEFAULT 1,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create subjects table
CREATE TABLE IF NOT EXISTS subjects (
    subject_id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_name TEXT UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create tests table
CREATE TABLE IF NOT EXISTS tests (
    test_id INTEGER PRIMARY KEY AUTOINCREMENT,
    test_name TEXT NOT NULL,
    subject_id INTEGER NOT NULL,
    total_marks INTEGER NOT NULL CHECK (total_marks > 0),
    admin_id INTEGER NOT NULL,
    time_limit INTEGER DEFAULT 30 CHECK (time_limit > 0),
    passing_percentage INTEGER DEFAULT 60 CHECK (passing_percentage >= 0 AND passing_percentage <= 100),
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (subject_id) REFERENCES subjects(subject_id) ON DELETE RESTRICT,
    FOREIGN KEY (admin_id) REFERENCES admins(admin_id) ON DELETE RESTRICT,
    UNIQUE(test_name, subject_id)
);

-- Create questions table (MCQ only)
CREATE TABLE IF NOT EXISTS questions (
    question_id INTEGER PRIMARY KEY AUTOINCREMENT,
    test_id INTEGER NOT NULL,
    question_text TEXT NOT NULL,
    marks INTEGER NOT NULL CHECK (marks > 0),
    question_type TEXT DEFAULT 'mcq' CHECK (question_type IN ('mcq', 'true_false')),
    correct_option_id INTEGER,
    explanation TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (test_id) REFERENCES tests(test_id) ON DELETE CASCADE
);

-- Create options table for MCQ
CREATE TABLE IF NOT EXISTS options (
    option_id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id INTEGER NOT NULL,
    option_text TEXT NOT NULL,
    is_correct BOOLEAN NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (question_id) REFERENCES questions(question_id) ON DELETE CASCADE,
    UNIQUE(question_id, option_text)
);

-- Create students table
CREATE TABLE IF NOT EXISTS students (
    student_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    is_active BOOLEAN DEFAULT 1,
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create student_results table
CREATE TABLE IF NOT EXISTS student_results (
    result_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    test_id INTEGER NOT NULL,
    marks_obtained INTEGER NOT NULL CHECK (marks_obtained >= 0),
    percentage DECIMAL(5,2) NOT NULL CHECK (percentage >= 0 AND percentage <= 100),
    attempt_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    time_taken INTEGER, -- in seconds
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
    FOREIGN KEY (test_id) REFERENCES tests(test_id) ON DELETE CASCADE,
    UNIQUE(student_id, test_id)
);

-- Create test_attempts table
CREATE TABLE IF NOT EXISTS test_attempts (
    attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
    test_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP,
    status TEXT DEFAULT 'in_progress' CHECK (status IN ('in_progress', 'completed', 'abandoned')),
    FOREIGN KEY (test_id) REFERENCES tests(test_id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

-- Create indexes for better performance
CREATE INDEX idx_admins_email ON admins(email);
CREATE INDEX idx_students_email ON students(email);
CREATE INDEX idx_tests_subject ON tests(subject_id);
CREATE INDEX idx_tests_admin ON tests(admin_id);
CREATE INDEX idx_questions_test ON questions(test_id);
CREATE INDEX idx_options_question ON options(question_id);
CREATE INDEX idx_results_student ON student_results(student_id);
CREATE INDEX idx_results_test ON student_results(test_id);
CREATE INDEX idx_attempts_student ON test_attempts(student_id);
CREATE INDEX idx_attempts_test ON test_attempts(test_id);
CREATE INDEX idx_tests_name_subject ON tests(test_name, subject_id);
CREATE INDEX idx_questions_text ON questions(question_text);
CREATE INDEX idx_options_text ON options(option_text);

-- Insert sample admin with temporary password (will be updated during initialization)
INSERT OR REPLACE INTO admins (admin_name, email, password) 
VALUES ('Admin', 'admin@example.com', 'temporary_password');

-- Insert sample student with temporary password (will be updated during initialization)
INSERT OR REPLACE INTO students (student_name, email, password)
VALUES ('Test Student', 'student@example.com', 'temporary_password');

-- Insert sample subjects
INSERT OR REPLACE INTO subjects (subject_name, description) VALUES 
('Mathematics', 'Basic and advanced mathematics topics'),
('Science', 'General science and scientific concepts'),
('English', 'English language and literature'),
('History', 'World history and important events'),
('Computer Science', 'Programming and computer concepts');

-- Insert sample test with admin_id
INSERT INTO tests (test_name, subject_id, total_marks, admin_id, time_limit, passing_percentage) 
VALUES ('Basic Mathematics Quiz', 1, 100, 1, 30, 60);

-- Insert sample MCQ question
INSERT INTO questions (test_id, question_text, marks, explanation)
VALUES (1, 'What is 2 + 2?', 5, 'Basic arithmetic addition');

-- Insert options for the MCQ question
INSERT INTO options (question_id, option_text, is_correct) VALUES
(1, '3', 0),
(1, '4', 1),
(1, '5', 0),
(1, '6', 0);

-- Update correct_option_id in questions
UPDATE questions SET correct_option_id = (
    SELECT option_id FROM options 
    WHERE question_id = questions.question_id AND is_correct = 1
); 