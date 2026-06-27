"""
Auth service — handles all authentication and user creation logic.

Registration rules:
  Admin      → seeded via script (no public endpoint)
  HOD        → created by Admin only
  Supervisor → created by HOD only (scoped to their department)
  Student    → created/imported by HOD only (scoped to their department's programs)

Login:
  Students   → regno + password (default password = regno, must change on first login)
  Others     → email + password
"""
import csv
import io
from datetime import datetime, timezone
from typing import List

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.user import (
    User, UserRole, Gender,
    StudentProfile, SupervisorProfile, HODProfile,
)
from app.models.department import Department, Program
from app.schemas.auth import (
    LoginRequest, ChangePasswordRequest, RefreshRequest,
    ForgotPasswordRequest, ResetPasswordRequest,
    CreateHODRequest, CreateSupervisorRequest, CreateStudentRequest,
    TokenResponse, UserOut, AuthResponse,
)
from app.utils.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token,
    create_reset_token, decode_token_strict,
)


class AuthService:

    # ── Login (regno or email) ────────────────────────────────────────────────

    def login(self, db: Session, data: LoginRequest) -> AuthResponse:
        # Try regno first (students), then email (others)
        user = (
            db.query(User).filter(User.regno == data.username, User.deleted_at.is_(None)).first()
            or
            db.query(User).filter(User.email == data.username, User.deleted_at.is_(None)).first()
        )

        if not user or not verify_password(data.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials.")

        if not user.is_active:
            raise HTTPException(status_code=403, detail="Account is inactive. Contact your HOD or Admin.")

        return self._build_auth_response(user)

    # ── Force password change ─────────────────────────────────────────────────

    def change_password(self, db: Session, data: ChangePasswordRequest, user: User) -> dict:
        if not verify_password(data.current_password, user.password_hash):
            raise HTTPException(status_code=400, detail="Current password is incorrect.")

        if data.current_password == data.new_password:
            raise HTTPException(status_code=400, detail="New password must differ from current password.")

        user.password_hash       = hash_password(data.new_password)
        user.must_change_password = False
        db.commit()
        return {"message": "Password changed successfully."}

    # ── Admin creates HOD ─────────────────────────────────────────────────────

    def create_hod(self, db: Session, data: CreateHODRequest, actor: User) -> UserOut:
        if actor.role != UserRole.ADMIN:
            raise HTTPException(403, "Only admins can create HOD accounts.")

        # Verify department exists
        dept = db.query(Department).filter(Department.id == data.department_id).first()
        if not dept:
            raise HTTPException(404, "Department not found.")

        # One HOD per department
        existing_hod = db.query(HODProfile).filter(
            HODProfile.department_id == data.department_id,
            HODProfile.deleted_at.is_(None),
        ).first()
        if existing_hod:
            raise HTTPException(400, f"Department '{dept.name}' already has an HOD.")

        self._check_email_unique(db, data.email)

        user = User(
            email         = data.email,
            password_hash = hash_password(data.password),
            first_name    = data.first_name,
            last_name     = data.last_name,
            role          = UserRole.HOD,
            phone         = data.phone,
            must_change_password = False,
        )
        db.add(user)
        db.flush()

        db.add(HODProfile(user_id=user.id, department_id=data.department_id))
        db.commit()
        db.refresh(user)
        return self._user_out(user)

    # ── HOD creates Supervisor ────────────────────────────────────────────────

    def create_supervisor(self, db: Session, data: CreateSupervisorRequest, actor: User) -> UserOut:
        if actor.role != UserRole.HOD:
            raise HTTPException(403, "Only HODs can create supervisor accounts.")

        hod_profile = db.query(HODProfile).filter(
            HODProfile.user_id == actor.id
        ).first()
        if not hod_profile:
            raise HTTPException(400, "HOD profile not found. Contact admin.")

        self._check_email_unique(db, data.email)

        user = User(
            email         = data.email,
            password_hash = hash_password(data.password),
            first_name    = data.first_name,
            last_name     = data.last_name,
            role          = UserRole.SUPERVISOR,
            phone         = data.phone,
            must_change_password = False,
        )
        db.add(user)
        db.flush()

        db.add(SupervisorProfile(
            user_id         = user.id,
            department_id   = hod_profile.department_id,
            max_students    = data.max_students,
            specializations = data.specializations,
        ))
        db.commit()
        db.refresh(user)
        return self._user_out(user)

    # ── HOD creates single Student ────────────────────────────────────────────

    def create_student(self, db: Session, data: CreateStudentRequest, actor: User) -> UserOut:
        if actor.role != UserRole.HOD:
            raise HTTPException(403, "Only HODs can create student accounts.")

        hod_profile = db.query(HODProfile).filter(HODProfile.user_id == actor.id).first()
        if not hod_profile:
            raise HTTPException(400, "HOD profile not found.")

        # Ensure program belongs to HOD's department
        program = db.query(Program).filter(Program.id == data.program_id).first()
        if not program:
            raise HTTPException(404, "Program not found.")
        if str(program.department_id) != str(hod_profile.department_id):
            raise HTTPException(403, "Program does not belong to your department.")

        # Check regno unique
        if db.query(User).filter(User.regno == data.regno).first():
            raise HTTPException(400, f"Regno '{data.regno}' already exists.")

        user = User(
            regno         = data.regno,
            email         = data.email,
            password_hash = hash_password(data.regno),  # default password = regno
            first_name    = data.first_name,
            last_name     = data.last_name,
            role          = UserRole.STUDENT,
            phone         = data.phone,
            must_change_password = True,   # force change on first login
        )
        db.add(user)
        db.flush()

        db.add(StudentProfile(
            user_id         = user.id,
            program_id      = data.program_id,
            enrollment_year = data.enrollment_year,
            gender          = data.gender,
            date_of_birth   = data.date_of_birth,
        ))
        db.commit()
        db.refresh(user)
        return self._user_out(user)

    # ── HOD bulk imports students from CSV ────────────────────────────────────

    def import_students_csv(self, db: Session, csv_content: str, actor: User) -> dict:
        if actor.role != UserRole.HOD:
            raise HTTPException(403, "Only HODs can import students.")

        hod_profile = db.query(HODProfile).filter(HODProfile.user_id == actor.id).first()
        if not hod_profile:
            raise HTTPException(400, "HOD profile not found.")

        reader = csv.DictReader(io.StringIO(csv_content))
        created, skipped, errors = 0, 0, []

        for i, row in enumerate(reader, start=2):  # start=2 (row 1 is header)
            try:
                regno = row.get("regno", "").strip()
                if not regno:
                    errors.append(f"Row {i}: regno is required.")
                    skipped += 1
                    continue

                if db.query(User).filter(User.regno == regno).first():
                    errors.append(f"Row {i}: regno '{regno}' already exists, skipped.")
                    skipped += 1
                    continue

                # Match program by code within HOD's department
                program_code = row.get("program_code", "").strip()
                program = db.query(Program).filter(
                    Program.code          == program_code,
                    Program.department_id == hod_profile.department_id,
                ).first()
                if not program:
                    errors.append(f"Row {i}: program code '{program_code}' not found in your department.")
                    skipped += 1
                    continue

                user = User(
                    regno         = regno,
                    email         = row.get("email", "").strip() or None,
                    password_hash = hash_password(regno),
                    first_name    = row.get("first_name", "").strip(),
                    last_name     = row.get("last_name", "").strip(),
                    role          = UserRole.STUDENT,
                    phone         = row.get("phone", "").strip() or None,
                    must_change_password = True,
                )
                db.add(user)
                db.flush()

                db.add(StudentProfile(
                    user_id         = user.id,
                    program_id      = program.id,
                    enrollment_year = int(row["enrollment_year"]) if row.get("enrollment_year") else None,
                ))
                created += 1

            except Exception as e:
                errors.append(f"Row {i}: {str(e)}")
                skipped += 1
                continue

        db.commit()
        return {"created": created, "skipped": skipped, "errors": errors}

    # ── Refresh token ─────────────────────────────────────────────────────────

    def refresh(self, db: Session, data: RefreshRequest) -> TokenResponse:
        payload = decode_token_strict(data.refresh_token, expected_type="refresh")
        if not payload:
            raise HTTPException(status_code=401, detail="Invalid or expired refresh token.")

        user = db.query(User).filter(
            User.id == payload["sub"],
            User.deleted_at.is_(None),
            User.is_active == True,
        ).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found or inactive.")

        return TokenResponse(
            access_token  = create_access_token(str(user.id), user.role.value),
            refresh_token = create_refresh_token(str(user.id)),
        )

    # ── Forgot / Reset password ───────────────────────────────────────────────

    def forgot_password(self, db: Session, data: ForgotPasswordRequest) -> dict:
        user = db.query(User).filter(User.email == data.email).first()
        if user:
            token = create_reset_token(str(user.id))
            user.reset_token            = token
            user.reset_token_expires_at = datetime.now(tz=timezone.utc).isoformat()
            db.commit()
        return {"message": "If that email exists, a reset link has been sent."}

    def reset_password(self, db: Session, data: ResetPasswordRequest) -> dict:
        payload = decode_token_strict(data.token, expected_type="reset")
        if not payload:
            raise HTTPException(status_code=400, detail="Invalid or expired reset token.")

        user = db.query(User).filter(User.id == payload["sub"]).first()
        if not user or user.reset_token != data.token:
            raise HTTPException(status_code=400, detail="Reset token is invalid.")

        user.password_hash          = hash_password(data.new_password)
        user.reset_token            = None
        user.reset_token_expires_at = None
        db.commit()
        return {"message": "Password reset successfully."}

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _check_email_unique(self, db: Session, email: str):
        if db.query(User).filter(User.email == email).first():
            raise HTTPException(status_code=400, detail="Email already registered.")

    def _user_out(self, user: User) -> UserOut:
        return UserOut(
            id                   = str(user.id),
            email                = user.email,
            regno                = user.regno,
            first_name           = user.first_name,
            last_name            = user.last_name,
            role                 = user.role,
            is_active            = user.is_active,
            phone                = user.phone,
            must_change_password = user.must_change_password,
        )

    def _build_auth_response(self, user: User) -> AuthResponse:
        return AuthResponse(
            user  = self._user_out(user),
            token = TokenResponse(
                access_token  = create_access_token(str(user.id), user.role.value),
                refresh_token = create_refresh_token(str(user.id)),
            ),
        )


auth_service = AuthService()