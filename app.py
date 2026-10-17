import os
import sqlite3
from datetime import datetime, date
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from werkzeug.security import generate_password_hash, check_password_hash

APP_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.environ.get("EDUSPHERE_DB", os.path.join(APP_DIR, "edusphere.db"))
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-development-key")

ROLES = ("student", "faculty", "hod", "admin")

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('student','faculty','hod','admin')),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        course TEXT NOT NULL DEFAULT '',
        due_date TEXT,
        created_by INTEGER,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(created_by) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        assignment_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        submission_text TEXT NOT NULL,
        submitted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(assignment_id, student_id),
        FOREIGN KEY(assignment_id) REFERENCES assignments(id) ON DELETE CASCADE,
        FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS library_resources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        subject TEXT NOT NULL DEFAULT '',
        resource_url TEXT NOT NULL,
        uploaded_by INTEGER,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(uploaded_by) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        subject TEXT NOT NULL,
        marks REAL NOT NULL,
        max_marks REAL NOT NULL DEFAULT 100,
        semester TEXT NOT NULL DEFAULT 'Semester 1',
        FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS grievances (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER,
        category TEXT NOT NULL,
        message TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Open',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE SET NULL
    );
    CREATE TABLE IF NOT EXISTS maintenance_tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        requester_id INTEGER,
        location TEXT NOT NULL,
        issue TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Open',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(requester_id) REFERENCES users(id) ON DELETE SET NULL
    );
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        course TEXT NOT NULL,
        attendance_date TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('Present','Absent')),
        marked_by INTEGER,
        FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY(marked_by) REFERENCES users(id) ON DELETE SET NULL
    );
    CREATE TABLE IF NOT EXISTS announcements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        body TEXT NOT NULL,
        created_by INTEGER,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(created_by) REFERENCES users(id)
    );
    """)
    count = db.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
    if count == 0:
        demo_users = [
            ("Admin Demo", "admin@edusphere.local", "Admin@123", "admin"),
            ("HOD Demo", "hod@edusphere.local", "Hod@12345", "hod"),
            ("Faculty Demo", "faculty@edusphere.local", "Faculty@123", "faculty"),
            ("Student Demo", "student@edusphere.local", "Student@123", "student"),
        ]
        for name, email, password, role in demo_users:
            db.execute(
                "INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)",
                (name, email, generate_password_hash(password), role)
            )
        db.commit()
    # Seed a few demo records only when tables are empty.
    if db.execute("SELECT COUNT(*) FROM assignments").fetchone()[0] == 0:
        faculty_id = db.execute("SELECT id FROM users WHERE role='faculty' LIMIT 1").fetchone()
        if faculty_id:
            db.execute("INSERT INTO assignments(title,description,course,due_date,created_by) VALUES(?,?,?,?,?)",
                       ("Python Basics", "Write a program using functions and lists.", "BCA-301", "2026-11-01", faculty_id["id"]))
            db.execute("INSERT INTO assignments(title,description,course,due_date,created_by) VALUES(?,?,?,?,?)",
                       ("Database Design", "Create an ER diagram for a library system.", "BCA-302", "2026-11-05", faculty_id["id"]))
    if db.execute("SELECT COUNT(*) FROM library_resources").fetchone()[0] == 0:
        db.execute("INSERT INTO library_resources(title,subject,resource_url) VALUES(?,?,?)",
                   ("Flask Documentation", "Web Development", "https://flask.palletsprojects.com/"))
        db.execute("INSERT INTO library_resources(title,subject,resource_url) VALUES(?,?,?)",
                   ("Python Tutorial", "Python", "https://docs.python.org/3/tutorial/"))
    db.commit()

@app.before_request
def setup():
    init_db()

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please sign in first.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped

def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if session.get("role") not in roles:
                flash("You do not have permission to open that page.", "danger")
                return redirect(url_for("dashboard"))
            return view(*args, **kwargs)
        return wrapped
    return decorator

def current_user():
    if not session.get("user_id"):
        return None
    return get_db().execute("SELECT id,name,email,role FROM users WHERE id=?", (session["user_id"],)).fetchone()

@app.context_processor
def inject_user():
    return {"current_user": current_user(), "today": date.today().isoformat()}

@app.route("/")
def index():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return render_template("landing.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = get_db().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["name"] = user["name"]
            session["role"] = user["role"]
            flash(f"Welcome back, {user['name']}!", "success")
            return redirect(url_for("dashboard"))
        flash("Incorrect email or password.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for("index"))

@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    role = session["role"]
    stats = {
        "assignments": db.execute("SELECT COUNT(*) FROM assignments").fetchone()[0],
        "resources": db.execute("SELECT COUNT(*) FROM library_resources").fetchone()[0],
        "grievances": db.execute("SELECT COUNT(*) FROM grievances WHERE status='Open'").fetchone()[0],
        "tickets": db.execute("SELECT COUNT(*) FROM maintenance_tickets WHERE status='Open'").fetchone()[0],
    }
    if role == "student":
        stats["my_submissions"] = db.execute("SELECT COUNT(*) FROM submissions WHERE student_id=?", (session["user_id"],)).fetchone()[0]
        stats["my_attendance"] = db.execute("SELECT COUNT(*) FROM attendance WHERE student_id=? AND status='Present'", (session["user_id"],)).fetchone()[0]
    recent_assignments = db.execute("SELECT a.*,u.name AS creator FROM assignments a LEFT JOIN users u ON u.id=a.created_by ORDER BY a.id DESC LIMIT 5").fetchall()
    announcements = db.execute("SELECT * FROM announcements ORDER BY id DESC LIMIT 5").fetchall()
    return render_template("dashboard.html", stats=stats, assignments=recent_assignments, announcements=announcements)

@app.route("/users", methods=["GET", "POST"])
@roles_required("admin", "hod")
def users():
    db = get_db()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "student")
        if not name or not email or len(password) < 8 or role not in ROLES:
            flash("Enter a name, valid email, password of at least 8 characters, and valid role.", "danger")
        else:
            try:
                db.execute("INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)",
                           (name, email, generate_password_hash(password), role))
                db.commit()
                flash("User created successfully.", "success")
                return redirect(url_for("users"))
            except sqlite3.IntegrityError:
                flash("That email address is already registered.", "danger")
    rows = db.execute("SELECT id,name,email,role,created_at FROM users ORDER BY id DESC").fetchall()
    return render_template("users.html", users=rows, roles=ROLES)

@app.route("/assignments", methods=["GET", "POST"])
@login_required
def assignments():
    db = get_db()
    if request.method == "POST":
        if session["role"] not in ("faculty", "hod", "admin"):
            flash("Only faculty, HOD, or admin can create assignments.", "danger")
            return redirect(url_for("assignments"))
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        course = request.form.get("course", "").strip()
        due_date = request.form.get("due_date") or None
        if not title or not course:
            flash("Title and course are required.", "danger")
        else:
            db.execute("INSERT INTO assignments(title,description,course,due_date,created_by) VALUES(?,?,?,?,?)",
                       (title, description, course, due_date, session["user_id"]))
            db.commit()
            flash("Assignment published.", "success")
            return redirect(url_for("assignments"))
    rows = db.execute("""SELECT a.*,u.name AS creator,
                         (SELECT COUNT(*) FROM submissions s WHERE s.assignment_id=a.id) AS submission_count
                         FROM assignments a LEFT JOIN users u ON u.id=a.created_by ORDER BY a.id DESC""").fetchall()
    return render_template("assignments.html", assignments=rows)

@app.route("/assignments/<int:assignment_id>/submit", methods=["POST"])
@roles_required("student")
def submit_assignment(assignment_id):
    db = get_db()
    exists = db.execute("SELECT id FROM assignments WHERE id=?", (assignment_id,)).fetchone()
    if not exists:
        flash("Assignment not found.", "danger")
        return redirect(url_for("assignments"))
    content = request.form.get("submission_text", "").strip()
    if len(content) < 5:
        flash("Please enter a meaningful submission (at least 5 characters).", "danger")
        return redirect(url_for("assignments"))
    db.execute("""INSERT INTO submissions(assignment_id,student_id,submission_text) VALUES(?,?,?)
                  ON CONFLICT(assignment_id,student_id) DO UPDATE SET submission_text=excluded.submission_text,
                  submitted_at=CURRENT_TIMESTAMP""", (assignment_id, session["user_id"], content))
    db.commit()
    flash("Your submission has been saved.", "success")
    return redirect(url_for("assignments"))

@app.route("/library", methods=["GET", "POST"])
@login_required
def library():
    db = get_db()
    if request.method == "POST":
        if session["role"] not in ("faculty", "hod", "admin"):
            flash("Only faculty, HOD, or admin can add resources.", "danger")
            return redirect(url_for("library"))
        title = request.form.get("title", "").strip()
        subject = request.form.get("subject", "").strip()
        resource_url = request.form.get("resource_url", "").strip()
        if not title or not resource_url.startswith(("https://", "http://")):
            flash("Enter a title and a valid http/https resource URL.", "danger")
        else:
            db.execute("INSERT INTO library_resources(title,subject,resource_url,uploaded_by) VALUES(?,?,?,?)",
                       (title, subject, resource_url, session["user_id"]))
            db.commit()
            flash("Library resource added.", "success")
            return redirect(url_for("library"))
    resources = db.execute("SELECT r.*,u.name AS uploader FROM library_resources r LEFT JOIN users u ON u.id=r.uploaded_by ORDER BY r.id DESC").fetchall()
    return render_template("library.html", resources=resources)

@app.route("/results", methods=["GET", "POST"])
@login_required
def results():
    db = get_db()
    if request.method == "POST":
        if session["role"] not in ("faculty", "hod", "admin"):
            flash("Only faculty, HOD, or admin can add results.", "danger")
            return redirect(url_for("results"))
        student_email = request.form.get("student_email", "").strip().lower()
        subject = request.form.get("subject", "").strip()
        semester = request.form.get("semester", "Semester 1").strip()
        try:
            marks = float(request.form.get("marks", ""))
            max_marks = float(request.form.get("max_marks", "100"))
        except ValueError:
            marks, max_marks = -1, 0
        student = db.execute("SELECT id FROM users WHERE email=? AND role='student'", (student_email,)).fetchone()
        if not student or not subject or max_marks <= 0 or marks < 0 or marks > max_marks:
            flash("Check student email, subject, and marks (0 to maximum marks).", "danger")
        else:
            db.execute("INSERT INTO results(student_id,subject,marks,max_marks,semester) VALUES(?,?,?,?,?)",
                       (student["id"], subject, marks, max_marks, semester))
            db.commit()
            flash("Result added.", "success")
            return redirect(url_for("results"))
    if session["role"] == "student":
        rows = db.execute("SELECT r.*,u.name AS student_name FROM results r JOIN users u ON u.id=r.student_id WHERE r.student_id=? ORDER BY r.semester,r.subject", (session["user_id"],)).fetchall()
    else:
        rows = db.execute("SELECT r.*,u.name AS student_name,u.email FROM results r JOIN users u ON u.id=r.student_id ORDER BY r.id DESC").fetchall()
    return render_template("results.html", results=rows)

@app.route("/attendance", methods=["GET", "POST"])
@login_required
def attendance():
    db = get_db()
    if request.method == "POST":
        if session["role"] not in ("faculty", "hod", "admin"):
            flash("Only faculty, HOD, or admin can mark attendance in this MVP.", "danger")
            return redirect(url_for("attendance"))
        student_email = request.form.get("student_email", "").strip().lower()
        course = request.form.get("course", "").strip()
        attendance_date = request.form.get("attendance_date") or date.today().isoformat()
        status = request.form.get("status", "Present")
        student = db.execute("SELECT id FROM users WHERE email=? AND role='student'", (student_email,)).fetchone()
        if not student or not course or status not in ("Present", "Absent"):
            flash("Check student email, course, and status.", "danger")
        else:
            db.execute("INSERT INTO attendance(student_id,course,attendance_date,status,marked_by) VALUES(?,?,?,?,?)",
                       (student["id"], course, attendance_date, status, session["user_id"]))
            db.commit()
            flash("Attendance recorded.", "success")
            return redirect(url_for("attendance"))
    if session["role"] == "student":
        rows = db.execute("SELECT a.*,u.name AS student_name FROM attendance a JOIN users u ON u.id=a.student_id WHERE a.student_id=? ORDER BY attendance_date DESC,id DESC", (session["user_id"],)).fetchall()
    else:
        rows = db.execute("SELECT a.*,u.name AS student_name FROM attendance a JOIN users u ON u.id=a.student_id ORDER BY attendance_date DESC,id DESC LIMIT 200").fetchall()
    return render_template("attendance.html", attendance=rows)

@app.route("/grievances", methods=["GET", "POST"])
@login_required
def grievances():
    db = get_db()
    if request.method == "POST":
        category = request.form.get("category", "Other").strip()
        message = request.form.get("message", "").strip()
        if len(message) < 10:
            flash("Please provide at least 10 characters so the issue can be understood.", "danger")
        else:
            db.execute("INSERT INTO grievances(student_id,category,message) VALUES(?,?,?)",
                       (session["user_id"], category, message))
            db.commit()
            flash("Grievance submitted. The MVP stores it for authorised staff to review.", "success")
            return redirect(url_for("grievances"))
    if session["role"] in ("admin", "hod"):
        rows = db.execute("SELECT g.*,u.name AS student_name FROM grievances g LEFT JOIN users u ON u.id=g.student_id ORDER BY g.id DESC").fetchall()
    else:
        rows = db.execute("SELECT g.*,u.name AS student_name FROM grievances g LEFT JOIN users u ON u.id=g.student_id WHERE g.student_id=? ORDER BY g.id DESC", (session["user_id"],)).fetchall()
    return render_template("grievances.html", grievances=rows, can_manage=session["role"] in ("admin","hod"))

@app.route("/grievances/<int:grievance_id>/status", methods=["POST"])
@roles_required("admin", "hod")
def grievance_status(grievance_id):
    status = request.form.get("status", "Open")
    if status not in ("Open", "In Review", "Resolved"):
        flash("Invalid status.", "danger")
    else:
        db = get_db()
        db.execute("UPDATE grievances SET status=? WHERE id=?", (status, grievance_id))
        db.commit()
        flash("Grievance status updated.", "success")
    return redirect(url_for("grievances"))

@app.route("/maintenance", methods=["GET", "POST"])
@login_required
def maintenance():
    db = get_db()
    if request.method == "POST":
        location = request.form.get("location", "").strip()
        issue = request.form.get("issue", "").strip()
        if not location or len(issue) < 10:
            flash("Enter a location and describe the issue in at least 10 characters.", "danger")
        else:
            db.execute("INSERT INTO maintenance_tickets(requester_id,location,issue) VALUES(?,?,?)",
                       (session["user_id"], location, issue))
            db.commit()
            flash("Maintenance ticket created.", "success")
            return redirect(url_for("maintenance"))
    if session["role"] in ("admin", "hod"):
        rows = db.execute("SELECT m.*,u.name AS requester FROM maintenance_tickets m LEFT JOIN users u ON u.id=m.requester_id ORDER BY m.id DESC").fetchall()
    else:
        rows = db.execute("SELECT m.*,u.name AS requester FROM maintenance_tickets m LEFT JOIN users u ON u.id=m.requester_id WHERE m.requester_id=? ORDER BY m.id DESC", (session["user_id"],)).fetchall()
    return render_template("maintenance.html", tickets=rows, can_manage=session["role"] in ("admin","hod"))

@app.route("/maintenance/<int:ticket_id>/status", methods=["POST"])
@roles_required("admin", "hod")
def maintenance_status(ticket_id):
    status = request.form.get("status", "Open")
    if status not in ("Open", "In Progress", "Resolved"):
        flash("Invalid status.", "danger")
    else:
        db = get_db()
        db.execute("UPDATE maintenance_tickets SET status=? WHERE id=?", (status, ticket_id))
        db.commit()
        flash("Ticket status updated.", "success")
    return redirect(url_for("maintenance"))

@app.route("/announcements", methods=["GET", "POST"])
@login_required
def announcements():
    db = get_db()
    if request.method == "POST":
        if session["role"] not in ("faculty", "hod", "admin"):
            flash("Only staff can publish announcements.", "danger")
            return redirect(url_for("announcements"))
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        if not title or not body:
            flash("Title and announcement body are required.", "danger")
        else:
            db.execute("INSERT INTO announcements(title,body,created_by) VALUES(?,?,?)",
                       (title, body, session["user_id"]))
            db.commit()
            flash("Announcement published.", "success")
            return redirect(url_for("announcements"))
    rows = db.execute("SELECT a.*,u.name AS author FROM announcements a LEFT JOIN users u ON u.id=a.created_by ORDER BY a.id DESC").fetchall()
    return render_template("announcements.html", announcements=rows)

@app.errorhandler(404)
def not_found(error):
    return render_template("error.html", code=404, message="Page not found"), 404

@app.errorhandler(500)
def server_error(error):
    return render_template("error.html", code=500, message="Something went wrong. Check the terminal for details."), 500

if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(debug=True)
