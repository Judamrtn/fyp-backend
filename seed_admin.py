"""
Run once to create the first superadmin account.
Usage: python seed_admin.py
"""
import sys
import os
sys.path.append(os.path.dirname(__file__))

from app.database import SessionLocal
from app.models.user import User, UserRole
from app.utils.security import hash_password


def seed_admin():
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.role == UserRole.ADMIN).first()
        if existing:
            print(f"Admin already exists: {existing.email}")
            return

        admin = User(
            email         = "admin@fyp.com",
            password_hash = hash_password("Admin@1234"),
            first_name    = "System",
            last_name     = "Admin",
            role          = UserRole.ADMIN,
            is_active     = True,
            must_change_password = False,
        )
        db.add(admin)
        db.commit()
        print("✅ Admin created successfully!")
        print("   Email:    admin@fyp.com")
        print("   Password: Admin@1234")
        print("   ⚠️  Change this password after first login!")

    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_admin()