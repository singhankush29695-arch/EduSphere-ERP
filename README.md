# EduSphere ERP — MVP v1

A runnable starter implementation of the EduSphere ERP SRS. It currently includes:
- Role-based login for student, faculty, HOD, and admin
- Role-protected user creation
- Dashboards and announcements
- Assignment creation and student submissions
- E-library links
- Results entry and student result view
- Attendance entry and student attendance view
- Grievance submission and staff status management
- Maintenance ticket submission and staff status management

## Important scope note

This is an exhibition/demo MVP, not the complete enterprise-grade SRS yet. The time-limited QR attendance, QR rotation, plagiarism detection, timetable substitution, no-dues/hall-ticket workflow, detailed analytics, and production hardening are not implemented in this first version. The database uses SQLite by default so it runs immediately on a beginner's computer. The supplied SRS calls for MySQL; a MySQL adapter/schema migration should be the next step before production deployment.

## 1. Install Python

Install Python 3.10 or newer. During installation on Windows, select **Add Python to PATH**.

## 2. Open the project folder

Extract the ZIP, open the `EduSphere_ERP_MVP` folder in VS Code, then open Terminal > New Terminal.

## 3. Create a virtual environment

Windows PowerShell:
```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, use Command Prompt:
```bat
py -m venv .venv
.venv\Scripts\activate.bat
```

## 4. Install dependencies and start

```bash
python -m pip install -r requirements.txt
python app.py
```

Open the local address printed in the terminal (usually `http://127.0.0.1:5000`).

## Demo logins

| Role | Email | Password |
|---|---|---|
| Admin | admin@edusphere.local | Admin@123 |
| HOD | hod@edusphere.local | Hod@12345 |
| Faculty | faculty@edusphere.local | Faculty@123 |
| Student | student@edusphere.local | Student@123 |

These are demo credentials only. Do not deploy with them. Change the secret key and remove/reset demo accounts before any public deployment.

## Suggested demo flow

1. Sign in as faculty and create an assignment.
2. Sign out, sign in as student, and submit a response.
3. Add a library resource as faculty.
4. Add a result or attendance entry as faculty using `student@edusphere.local`.
5. Submit a grievance or maintenance ticket as student.
6. Sign in as HOD or admin to review and update statuses.
7. Sign in as admin/HOD and create an additional user.

## Project structure

```text
EduSphere_ERP_MVP/
├── app.py
├── requirements.txt
├── README.md
├── templates/
│   ├── base.html
│   ├── landing.html
│   ├── login.html
│   ├── dashboard.html
│   ├── users.html
│   ├── assignments.html
│   ├── library.html
│   ├── results.html
│   ├── attendance.html
│   ├── grievances.html
│   ├── maintenance.html
│   ├── announcements.html
│   └── error.html
└── static/
    └── style.css
```

## Notes

- The database file `edusphere.db` is created automatically at first run.
- Keep secrets in environment variables in a real deployment.
- Use HTTPS, CSRF protection, rate limiting, audit logs, backups, and a proper migration tool before production.
- The demo grievance module is not truly anonymous: it records the submitting user. The full SRS's anonymous grievance requirement needs a separate privacy-aware implementation.
