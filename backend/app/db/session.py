from pathlib import Path
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.config import settings

# Create parent data folder if needed
try:
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass

connect_args = {}
if "sqlite" in settings.effective_db_url:
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.effective_db_url,
    connect_args=connect_args,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Dependency that yields a managed SQLAlchemy database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)
