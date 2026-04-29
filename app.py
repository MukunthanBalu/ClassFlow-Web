import os
import io
import csv
import socket
from datetime import date
from functools import wraps

from flask import (Flask, render_template, request, redirect,
                   url_for, session, jsonify, send_file, abort)
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename

import database as db

app = Flask(__name__)
app.secret_key = 'classroom_hub_s3cr3t_2024'
socketio = SocketIO(app, cors_allowed_origins='*', max_http_buffer_size=8 * 1024 * 1024)

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
ADMIN_PASSWORD = 'prof123'
ALLOWED_CODE = {'py', 'ipynb', 'txt'}
ALLOWED_PDF  = {'pdf'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def today():
    return date.today().strftime('%Y-%m-%d')

def ext_ok(filename, allowed):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated


# ── Student Routes ────────────────────────────────────────────────────────────

@app.route('/')
def index():
    students = db.get_all_students()
    return render_template('student.html', students=students, today=today())


@app.route('/api/submit', methods=['POST'])
def submit_assignment():
    student_name = request.form.get('student_name', '').strip()
    topic = request.form.get('topic', '').strip()
    code_file = request.files.get('code_file')
    pdf_file  = request.files.get('pdf_file')

    if not student_name:
        return jsonify({'success': False, 'error': 'Please enter your name.'}), 400

    # find or create student
    students = db.get_all_students()
    student = next((s for s in students if s['name'].lower() == student_name.lower()), None)
    if not student:
        student_id = db.add_student(student_name, None)
        student = db.get_student_by_id(student_id)
    else:
        student_id = student['id']

    roll = (student['roll_number'] or str(student['id'])).replace(' ', '_')
    name = student['name'].replace(' ', '_')
    student_dir = os.path.join(UPLOAD_FOLDER, today(), f"{roll}_{name}")
    os.makedirs(student_dir, exist_ok=True)

    code_path = pdf_path = code_filename = pdf_filename = None

    if code_file and code_file.filename:
        if not ext_ok(code_file.filename, ALLOWED_CODE):
            return jsonify({'success': False, 'error': 'Code must be .py / .ipynb / .txt'}), 400
        code_filename = secure_filename(code_file.filename)
        code_path = os.path.join(student_dir, f"code_{code_filename}")
        code_file.save(code_path)

    if pdf_file and pdf_file.filename:
        if not ext_ok(pdf_file.filename, ALLOWED_PDF):
            return jsonify({'success': False, 'error': 'Output must be a PDF.'}), 400
        pdf_filename = secure_filename(pdf_file.filename)
        pdf_path = os.path.join(student_dir, f"output_{pdf_filename}")
        pdf_file.save(pdf_path)

    if not code_path and not pdf_path:
        return jsonify({'success': False, 'error': 'Upload at least one file.'}), 400

    sid = db.add_submission(student_id=int(student_id), date=today(), topic=topic,
                            code_filename=code_filename, code_path=code_path,
                            pdf_filename=pdf_filename, pdf_path=pdf_path)
    return jsonify({'success': True, 'submission_id': sid})


@app.route('/api/checkin', methods=['POST'])
def checkin():
    data = request.get_json()
    student_name = data.get('student_name', '').strip()
    if not student_name:
        return jsonify({'success': False, 'error': 'No name provided'}), 400
        
    students = db.get_all_students()
    student = next((s for s in students if s['name'].lower() == student_name.lower()), None)
    if not student:
        student_id = db.add_student(student_name, None)
    else:
        student_id = student['id']
        
    db.checkin_student(student_id, today())
    return jsonify({'success': True})


@app.route('/api/students')
def get_students():
    return jsonify([dict(s) for s in db.get_all_students()])


# ── Admin Auth ────────────────────────────────────────────────────────────────

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['admin'] = True
            return redirect(url_for('admin_dashboard'))
        error = 'Incorrect password. Try again.'
    return render_template('admin_login.html', error=error)


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('admin_login'))


# ── Admin Dashboard ───────────────────────────────────────────────────────────

@app.route('/admin')
@admin_required
def admin_dashboard():
    stats   = db.get_stats(today())
    recent  = db.get_recent_submissions(10)
    att     = db.get_attendance_for_date(today())
    students = db.get_all_students()
    return render_template('admin_dashboard.html',
                           stats=stats, recent=recent,
                           today_att=att, today=today(),
                           students=students)


# ── Admin Attendance ──────────────────────────────────────────────────────────

@app.route('/admin/attendance')
@admin_required
def admin_attendance():
    sel_date  = request.args.get('date', today())
    students  = db.get_all_students()
    att       = db.get_attendance_for_date(sel_date)
    att_dict  = {a['student_id']: dict(a) for a in att}
    all_dates = db.get_all_attendance_dates()
    return render_template('admin_attendance.html',
                           students=students, att_dict=att_dict,
                           sel_date=sel_date, all_dates=all_dates)


@app.route('/api/attendance/mark', methods=['POST'])
@admin_required
def mark_attendance():
    data = request.get_json()
    student_id = data.get('student_id')
    date_str   = data.get('date', today())
    status     = data.get('status')
    if not student_id or status not in ('present', 'absent', 'late'):
        return jsonify({'success': False, 'error': 'Invalid data'}), 400
    db.mark_attendance(int(student_id), date_str, status)
    return jsonify({'success': True})


@app.route('/admin/attendance/export/<date_str>')
@admin_required
def export_attendance(date_str):
    students = db.get_all_students()
    att      = db.get_attendance_for_date(date_str)
    att_map  = {a['student_id']: a['status'] for a in att}
    buf = io.StringIO()
    w   = csv.writer(buf)
    w.writerow(['Roll Number', 'Name', 'Status', 'Date'])
    for s in students:
        w.writerow([s['roll_number'], s['name'], att_map.get(s['id'], 'absent'), date_str])
    buf.seek(0)
    return send_file(io.BytesIO(buf.getvalue().encode()),
                     mimetype='text/csv', as_attachment=True,
                     download_name=f'attendance_{date_str}.csv')


# ── Admin Submissions ─────────────────────────────────────────────────────────

@app.route('/admin/submissions')
@admin_required
def admin_submissions():
    view      = request.args.get('view', 'date')
    selected  = request.args.get('selected', today())
    students  = db.get_all_students()
    all_dates = db.get_submission_dates()
    if view == 'student':
        subs = db.get_submissions_by_student(int(selected)) if selected else []
    else:
        subs = db.get_submissions_by_date(selected)
    return render_template('admin_submissions.html',
                           view=view, selected=selected,
                           students=students, all_dates=all_dates, subs=subs)


@app.route('/api/download/<int:sub_id>/<ftype>')
@admin_required
def download_file(sub_id, ftype):
    sub = db.get_submission_by_id(sub_id)
    if not sub:
        abort(404)
    if ftype == 'code' and sub['code_path'] and os.path.exists(sub['code_path']):
        return send_file(sub['code_path'], as_attachment=True,
                         download_name=sub['code_filename'] or 'code.py')
    if ftype == 'pdf' and sub['pdf_path'] and os.path.exists(sub['pdf_path']):
        return send_file(sub['pdf_path'], as_attachment=True,
                         download_name=sub['pdf_filename'] or 'output.pdf')
    abort(404)


# ── Admin Students ────────────────────────────────────────────────────────────

@app.route('/admin/students')
@admin_required
def admin_students():
    return render_template('admin_students.html', students=db.get_all_students())


@app.route('/api/students/add', methods=['POST'])
@admin_required
def add_student():
    data = request.get_json()
    name = data.get('name', '').strip()
    roll = data.get('roll_number', '').strip()
    if not name:
        return jsonify({'success': False, 'error': 'Name is required'}), 400
    sid = db.add_student(name, roll)
    if sid:
        return jsonify({'success': True, 'id': sid})
    return jsonify({'success': False, 'error': 'Roll number already exists'}), 400


@app.route('/api/students/delete/<int:sid>', methods=['POST'])
@admin_required
def delete_student(sid):
    db.delete_student(sid)
    return jsonify({'success': True})


# ── Socket.IO ─────────────────────────────────────────────────────────────────

@socketio.on('screen_frame')
def relay_frame(data):
    emit('screen_frame', data, broadcast=True, include_self=False)

@socketio.on('sharing_started')
def sharing_started():
    emit('sharing_started', broadcast=True, include_self=False)

@socketio.on('sharing_stopped')
def sharing_stopped():
    emit('sharing_stopped', broadcast=True, include_self=False)


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    db.init_db()
    try:
        local_ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        local_ip = '127.0.0.1'
    print(f"\n{'='*52}")
    print(f"  🎓  ClassFlow is running!")
    print(f"{'='*52}")
    print(f"  Student URL  →  http://{local_ip}:5001")
    print(f"  Admin URL    →  http://{local_ip}:5001/admin")
    print(f"  Admin Pass   →  {ADMIN_PASSWORD}")
    print(f"{'='*52}\n")
    socketio.run(app, host='0.0.0.0', port=5001, debug=False,
                 allow_unsafe_werkzeug=True)
