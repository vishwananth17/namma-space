import os
import shutil
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application runtime settings and environment configuration."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "NammaSpace 3D Digital Twin Backend"
    APP_VERSION: str = "0.1.0"
    ENV: str = "development"
    DEBUG: bool = True

    # Server settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Cross-Origin Resource Sharing (CORS) for Naresh's frontend
    # Allows localhost Vite (5173), Next.js (3000), Three.js dev servers, and Vercel domains
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "*",  # Permissive during hackathon local dev and staging
    ]

    # File paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    VENUES_DIR: Path = DATA_DIR / "venues"

    # Static URL prefix for model and asset serving
    STATIC_URL_PREFIX: str = "/static"

    # Database configuration (SQLite default)
    DATABASE_URL: str = ""

    @property
    def sqlite_db_path(self) -> Path:
        if os.environ.get("VERCEL"):
            # On Vercel serverless, root is read-only; copy persistent DB to /tmp
            tmp_db = Path("/tmp/nammaspace.db")
            if not tmp_db.exists():
                src_db = self.DATA_DIR / "nammaspace.db"
                if src_db.exists():
                    shutil.copy2(src_db, tmp_db)
            return tmp_db
        return self.DATA_DIR / "nammaspace.db"

    @property
    def effective_db_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        # On Windows or Linux/Vercel, format clean sqlite URL
        return f"sqlite:///{self.sqlite_db_path.as_posix()}"


settings = Settings()
