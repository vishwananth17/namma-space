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
    """Initialize database tables and auto-seed initial POIs if table is empty."""
    Base.metadata.create_all(bind=engine)
    try:
        with SessionLocal() as db:
            from app.models.poi import POIRecord
            import json
            if db.query(POIRecord).count() == 0:
                venues_dir = settings.VENUES_DIR
                if venues_dir.exists():
                    for venue_dir in venues_dir.iterdir():
                        if venue_dir.is_dir():
                            pois_file = venue_dir / "pois.json"
                            if pois_file.exists():
                                try:
                                    with open(pois_file, "r", encoding="utf-8") as f:
                                        data = json.load(f)
                                    for p in data:
                                        pos = p.get("position", {})
                                        record = POIRecord(
                                            id=p["id"],
                                            venue_id=p.get("venue_id", venue_dir.name),
                                            name=p["name"],
                                            category=p.get("category", "general"),
                                            description=p.get("description", ""),
                                            pos_x=pos.get("x", 0.0),
                                            pos_y=pos.get("y", 0.0),
                                            pos_z=pos.get("z", 0.0),
                                            tags=",".join(p.get("tags", [])) if isinstance(p.get("tags"), list) else str(p.get("tags", "")),
                                            floor=p.get("floor", 0),
                                        )
                                        db.add(record)
                                    db.commit()
                                except Exception:
                                    db.rollback()
    except Exception:
        pass
