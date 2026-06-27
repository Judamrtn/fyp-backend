"""
One-command dev data setup.
Run after starting the server:  python setup_data.py
"""
import sys, os, requests

BASE = "http://localhost:8000/api/v1"
IDS  = {}


def post(path, data, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = requests.post(f"{BASE}{path}", json=data, headers=headers)
    return r.json()


def get_token(username, password):
    r = post("/auth/login", {"username": username, "password": password})
    if r.get("success"):
        return r["data"]["token"]["access_token"]
    print(f"  ❌ Login failed for {username}: {r.get('message')}")
    return None


def step(msg):
    print(f"\n{'='*50}\n  {msg}\n{'='*50}")


# ── Step 1: Seed Admin ────────────────────────────────────────────────────────
step("1. Creating Admin")
from app.database import SessionLocal
from app.models.user import User, UserRole
from app.utils.security import hash_password

db = SessionLocal()
try:
    existing = db.query(User).filter(User.role == UserRole.ADMIN).first()
    if existing:
        print(f"  ✅ Admin already exists: {existing.email}")
    else:
        admin = User(
            email                = "admin@fyp.com",
            password_hash        = hash_password("Admin@1234"),
            first_name           = "System",
            last_name            = "Admin",
            role                 = UserRole.ADMIN,
            is_active            = True,
            must_change_password = False,
        )
        db.add(admin)
        db.commit()
        print("  ✅ Admin created")
finally:
    db.close()

# ── Step 2: Login as Admin ────────────────────────────────────────────────────
step("2. Logging in as Admin")
admin_token = get_token("admin@fyp.com", "Admin@1234")
if not admin_token:
    sys.exit("Cannot continue without admin token.")
print("  ✅ Admin logged in")

# ── Step 3: Faculty ───────────────────────────────────────────────────────────
step("3. Creating Faculty")
r = post("/departments/faculties", {
    "name": "Faculty of Computing",
    "code": "FOC",
    "description": "Computing and Information Technology"
}, admin_token)
if r.get("success"):
    IDS["faculty_id"] = r["data"]["id"]
    print(f"  ✅ Faculty created: {IDS['faculty_id']}")
else:
    print(f"  ❌ {r.get('message')} {r.get('errors')}")

# ── Step 4: Department ────────────────────────────────────────────────────────
step("4. Creating Department")
r = post("/departments/", {
    "faculty_id":  IDS.get("faculty_id"),
    "name":        "Computer Science",
    "code":        "CS",
    "description": "Computer Science Department"
}, admin_token)
if r.get("success"):
    IDS["department_id"] = r["data"]["id"]
    print(f"  ✅ Department created: {IDS['department_id']}")
else:
    print(f"  ❌ {r.get('message')} {r.get('errors')}")

# ── Step 5: Program ───────────────────────────────────────────────────────────
step("5. Creating Program")
r = post("/departments/programs", {
    "department_id": IDS.get("department_id"),
    "name":          "Bachelor of Computer Science",
    "code":          "BCS"
}, admin_token)
if r.get("success"):
    IDS["program_id"] = r["data"]["id"]
    print(f"  ✅ Program created: {IDS['program_id']}")
else:
    print(f"  ❌ {r.get('message')} {r.get('errors')}")

# ── Step 6: Academic Year ─────────────────────────────────────────────────────
step("6. Creating Academic Year")
r = post("/academic-years/", {
    "label":      "2024/2025",
    "start_date": "2024-09-01",
    "end_date":   "2025-06-30",
    "is_active":  True
}, admin_token)
if r.get("success"):
    IDS["year_id"] = r["data"]["id"]
    print(f"  ✅ Academic Year created: {IDS['year_id']}")
else:
    print(f"  ❌ {r.get('message')} {r.get('errors')}")

# ── Step 7: HOD ───────────────────────────────────────────────────────────────
step("7. Creating HOD")
r = post("/admin/users/create-hod", {
    "email":         "hod@fyp.com",
    "password":      "Hod@1234",
    "first_name":    "Dr Sarah",
    "last_name":     "Johnson",
    "department_id": IDS.get("department_id")
}, admin_token)
if r.get("success"):
    IDS["hod_id"] = r["data"]["id"]
    print(f"  ✅ HOD created: {IDS['hod_id']}")
else:
    print(f"  ❌ {r.get('message')} {r.get('errors')}")

# ── Step 8: Login as HOD ──────────────────────────────────────────────────────
step("8. Logging in as HOD")
hod_token = get_token("hod@fyp.com", "Hod@1234")
if not hod_token:
    sys.exit("Cannot continue without HOD token.")
print("  ✅ HOD logged in")

# ── Step 9: Supervisor ────────────────────────────────────────────────────────
step("9. Creating Supervisor")
r = post("/users/create-supervisor", {
    "email":           "supervisor@fyp.com",
    "password":        "Super@1234",
    "first_name":      "Dr James",
    "last_name":       "Smith",
    "specializations": "AI, Machine Learning",
    "max_students":    5
}, hod_token)
if r.get("success"):
    IDS["supervisor_id"] = r["data"]["id"]
    print(f"  ✅ Supervisor created: {IDS['supervisor_id']}")
else:
    print(f"  ❌ {r.get('message')} {r.get('errors')}")

# ── Step 10: Students ─────────────────────────────────────────────────────────
step("10. Creating Students")
students = [
    {"regno": "CS/2024/001", "first_name": "Alice", "last_name": "Brown", "gender": "female"},
    {"regno": "CS/2024/002", "first_name": "Bob",   "last_name": "Smith", "gender": "male"},
    {"regno": "CS/2024/003", "first_name": "Carol", "last_name": "White", "gender": "female"},
]
for s in students:
    r = post("/users/create-student", {
        **s,
        "program_id":      IDS.get("program_id"),
        "enrollment_year": 2024,
    }, hod_token)
    if r.get("success"):
        print(f"  ✅ Student created: {s['regno']}")
    else:
        print(f"  ❌ {s['regno']}: {r.get('message')}")

# ── Step 11: Seed Corpus ──────────────────────────────────────────────────────
step("11. Seeding Similarity Corpus")
r = post("/admin/seed-corpus", {
    "titles": [
        "Smart Attendance System Using Face Recognition",
        "Blockchain Based Certificate Verification System",
        "IoT Based Smart Home Automation",
        "Natural Language Processing for Sentiment Analysis",
        "Deep Learning for Medical Image Classification",
        "Online Examination System with Anti-Cheating Module",
        "Student Result Management System",
        "Library Management System Using RFID",
        "E-Learning Platform with Adaptive Content",
        "Hospital Management System with Patient Tracking",
        "AI Based Fraud Detection in Banking Systems",
        "Real Time Object Detection Using YOLO",
        "Predictive Maintenance System Using Machine Learning",
        "Smart Traffic Management System Using IoT",
        "Automated Essay Grading System Using NLP",
    ]
}, admin_token)
if r.get("success"):
    print(f"  ✅ {r['data']['seeded']} titles seeded")
else:
    print(f"  ❌ {r.get('message')} {r.get('errors')}")

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"""
{'='*50}
  ✅ SETUP COMPLETE
{'='*50}

  CREDENTIALS:
  Admin      → admin@fyp.com       / Admin@1234
  HOD        → hod@fyp.com         / Hod@1234
  Supervisor → supervisor@fyp.com  / Super@1234
  Student 1  → CS/2024/001         / CS/2024/001
  Student 2  → CS/2024/002         / CS/2024/002
  Student 3  → CS/2024/003         / CS/2024/003

  IDs:
  Department : {IDS.get('department_id')}
  Program    : {IDS.get('program_id')}
  Acad. Year : {IDS.get('year_id')}
""")