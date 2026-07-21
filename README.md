# FYP Topic Repository — Backend API

A FastAPI backend for university Final Year Project topic management.

## Tech Stack
- **Framework**: FastAPI (Python)
- **Database**: PostgreSQL + SQLAlchemy ORM
- **Auth**: JWT (access 15min + refresh 7 days)
- **Similarity**: TF-IDF + HuggingFace semantic embeddings (hybrid)
- **Storage**: Local (dev) / MinIO / AWS S3

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env with your database credentials and API keys
```

### 3. Start server
```bash
uvicorn app.main:app --reload --port 8000
```

### 4. Seed initial data
```bash
python setup_data.py
```

### 5. Initialize migrations
```bash
python migrate.py init
```

Open **http://localhost:8000/docs** for interactive API documentation.

---

## User Roles & Credentials (Dev)

| Role       | Username           | Password    |
|------------|--------------------|-------------|
| Admin      | admin@fyp.com      | Admin@1234  |
| HOD        | hod@fyp.com        | Hod@1234    |
| Supervisor | supervisor@fyp.com | Super@1234  |
| Student 1  | CS/2024/001        | CS/2024/001 |
| Student 2  | CS/2024/002        | CS/2024/002 |
| Student 3  | CS/2024/003        | CS/2024/003 |

> Students must change their password on first login.

---

## Workflow


---

## API Endpoints Summary

| Group               | Base URL                          |
|---------------------|-----------------------------------|
| Auth                | /api/v1/auth                      |
| Users               | /api/v1/users                     |
| Departments         | /api/v1/departments               |
| Academic Years      | /api/v1/academic-years            |
| Proposals           | /api/v1/proposals                 |
| Similarity          | /api/v1/proposals/{id}/similarity |
| Allocations         | /api/v1/allocations               |
| Project Supervision | /api/v1/projects                  |
| Repository          | /api/v1/repository                |
| Notifications       | /api/v1/notifications             |
| Reports             | /api/v1/reports                   |
| Deadlines           | /api/v1/deadlines                 |
| Config              | /api/v1/config                    |
| Admin               | /api/v1/admin                     |
| Health              | /api/v1/health                    |

---

## Database Migrations

```bash
# After changing a model:
python migrate.py generate describe_your_change
python migrate.py upgrade

# View history
python migrate.py history

# Check current revision
python migrate.py current
```

---

## Similarity Engine

The system uses a **hybrid approach**:
- **TF-IDF** (40% weight) — fast, offline, word-level matching
- **HuggingFace** (60% weight) — semantic meaning matching

Field weights:
- Title: 30%
- Abstract: 30%
- Objectives: 25%
- Keywords: 15%

Set `USE_AI_SIMILARITY=false` in `.env` to use TF-IDF only.