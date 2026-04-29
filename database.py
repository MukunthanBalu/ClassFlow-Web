import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'classroom.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        roll_number TEXT UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        status TEXT DEFAULT 'absent',
        checked_in_at TIMESTAMP,
        FOREIGN KEY(student_id) REFERENCES students(id),
        UNIQUE(student_id, date)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        topic TEXT,
        code_filename TEXT,
        code_path TEXT,
        pdf_filename TEXT,
        pdf_path TEXT,
        submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(student_id) REFERENCES students(id)
    )''')
    conn.commit()
    conn.close()


# ── Students ──────────────────────────────────────────────────────────────────

def get_all_students():
    conn = get_db()
    rows = conn.execute('SELECT * FROM students ORDER BY name').fetchall()
    conn.close()
    return rows


def get_student_by_id(student_id):
    conn = get_db()
    row = conn.execute('SELECT * FROM students WHERE id=?', (student_id,)).fetchone()
    conn.close()
    return row


def add_student(name, roll_number):
    conn = get_db()
    try:
        cur = conn.execute('INSERT INTO students (name, roll_number) VALUES (?,?)', (name, roll_number))
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def delete_student(student_id):
    conn = get_db()
    conn.execute('DELETE FROM students WHERE id=?', (student_id,))
    conn.commit()
    conn.close()


# ── Attendance ────────────────────────────────────────────────────────────────

def get_attendance_for_date(date):
    conn = get_db()
    rows = conn.execute('''
        SELECT a.*, s.name, s.roll_number FROM attendance a
        JOIN students s ON s.id = a.student_id
        WHERE a.date=? ORDER BY s.name
    ''', (date,)).fetchall()
    conn.close()
    return rows


def mark_attendance(student_id, date, status):
    conn = get_db()
    conn.execute('''INSERT INTO attendance (student_id, date, status)
        VALUES (?,?,?) ON CONFLICT(student_id, date) DO UPDATE SET status=excluded.status
    ''', (student_id, date, status))
    conn.commit()
    conn.close()


def checkin_student(student_id, date):
    conn = get_db()
    conn.execute('''INSERT INTO attendance (student_id, date, status, checked_in_at)
        VALUES (?,?,'present',CURRENT_TIMESTAMP)
        ON CONFLICT(student_id, date) DO UPDATE SET status='present', checked_in_at=CURRENT_TIMESTAMP
    ''', (student_id, date))
    conn.commit()
    conn.close()
    return 'ok'


def get_all_attendance_dates():
    conn = get_db()
    rows = conn.execute('SELECT DISTINCT date FROM attendance ORDER BY date DESC').fetchall()
    conn.close()
    return [r['date'] for r in rows]


# ── Submissions ───────────────────────────────────────────────────────────────

def add_submission(student_id, date, topic, code_filename, code_path, pdf_filename, pdf_path):
    conn = get_db()
    cur = conn.execute('''INSERT INTO submissions
        (student_id, date, topic, code_filename, code_path, pdf_filename, pdf_path)
        VALUES (?,?,?,?,?,?,?)
    ''', (student_id, date, topic, code_filename, code_path, pdf_filename, pdf_path))
    conn.commit()
    sid = cur.lastrowid
    conn.close()
    return sid


def get_submission_by_id(submission_id):
    conn = get_db()
    row = conn.execute('SELECT * FROM submissions WHERE id=?', (submission_id,)).fetchone()
    conn.close()
    return row


def get_submissions_by_date(date):
    conn = get_db()
    rows = conn.execute('''
        SELECT sub.*, s.name, s.roll_number FROM submissions sub
        JOIN students s ON s.id = sub.student_id
        WHERE sub.date=? ORDER BY sub.submitted_at DESC
    ''', (date,)).fetchall()
    conn.close()
    return rows


def get_submissions_by_student(student_id):
    conn = get_db()
    rows = conn.execute('''
        SELECT sub.*, s.name, s.roll_number FROM submissions sub
        JOIN students s ON s.id = sub.student_id
        WHERE sub.student_id=? ORDER BY sub.date DESC, sub.submitted_at DESC
    ''', (student_id,)).fetchall()
    conn.close()
    return rows


def get_recent_submissions(limit=10):
    conn = get_db()
    rows = conn.execute('''
        SELECT sub.*, s.name, s.roll_number FROM submissions sub
        JOIN students s ON s.id = sub.student_id
        ORDER BY sub.submitted_at DESC LIMIT ?
    ''', (limit,)).fetchall()
    conn.close()
    return rows


def get_submission_dates():
    conn = get_db()
    rows = conn.execute('SELECT DISTINCT date FROM submissions ORDER BY date DESC').fetchall()
    conn.close()
    return [r['date'] for r in rows]


def get_stats(today):
    conn = get_db()
    total_students = conn.execute('SELECT COUNT(*) FROM students').fetchone()[0]
    today_present = conn.execute(
        "SELECT COUNT(*) FROM attendance WHERE date=? AND status='present'", (today,)).fetchone()[0]
    total_submissions = conn.execute('SELECT COUNT(*) FROM submissions').fetchone()[0]
    today_submissions = conn.execute(
        'SELECT COUNT(*) FROM submissions WHERE date=?', (today,)).fetchone()[0]
    conn.close()
    return {
        'total_students': total_students,
        'today_present': today_present,
        'total_submissions': total_submissions,
        'today_submissions': today_submissions,
    }
