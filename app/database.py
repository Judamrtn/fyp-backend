from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
from typing import Generator
from app.config import settings

# ── Sync engine (used by Alembic + sync endpoints) ──────────────────────────
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,          # auto-reconnect on stale connections
    pool_size=10,
    max_overflow=20,
    echo=settings.debug,         # log SQL in development
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# ── Base class for all ORM models ────────────────────────────────────────────
Base = declarative_base()


# ── Dependency: yields a DB session per request ──────────────────────────────
def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency. Yields a SQLAlchemy session and guarantees cleanup.

    Usage:
        @router.get("/example")
        def example(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ── Utility: create all tables (used in tests / dev bootstrap) ───────────────
def create_tables() -> None:
    """Creates all tables registered on Base. Only for dev — use Alembic in prod."""
    Base.metadata.create_all(bind=engine)


def drop_tables() -> None:
    """Drops all tables. Destructive — dev/test only."""
    Base.metadata.drop_all(bind=engine)
