"""Settings from environment. See .env.example."""
import os
from pathlib import Path


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


class Settings:
    AI_MODE = _env("AI_MODE", "stub")
    MOCKS_URL = _env("MOCKS_URL", "")  # empty -> use fake_mocks_client
    DATABASE_URL = _env("DATABASE_URL", "postgresql+psycopg2://bharosa:bharosa@localhost:5432/bharosa")
    JWT_SECRET = _env("JWT_SECRET", "dev-only-change-me-not-for-production-0000")
    JWT_ALGORITHM = "HS256"
    UPLOAD_DIR = Path(_env("UPLOAD_DIR", str(Path(__file__).resolve().parents[1] / "uploads")))
    MAX_UPLOAD_BYTES = int(_env("MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))
    DEMO_CITIZEN_PIN = _env("DEMO_CITIZEN_PIN", "1234")  # FAKE, prototype only
    BCRYPT_ROUNDS = int(_env("BCRYPT_ROUNDS", "12"))
    JWT_EXPIRES_SECONDS = int(_env("JWT_EXPIRES_SECONDS", "3600"))
    CORS_ORIGINS = [o.strip() for o in _env("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]
    FIXTURES_DIR = Path(_env("FIXTURES_DIR", str(Path(__file__).resolve().parents[2] / "contracts" / "fixtures")))
    # Demo passwords: clearly fake, prototype only.
    DEMO_PASSWORDS = {
        "citizen": _env("DEMO_CITIZEN_PASSWORD", "citizen-demo-123"),
        "helper": _env("DEMO_HELPER_PASSWORD", "helper-demo-123"),
        "officer": _env("DEMO_OFFICER_PASSWORD", "officer-demo-123"),
        "admin": _env("DEMO_ADMIN_PASSWORD", "admin-demo-123"),
        "auditor": _env("DEMO_AUDITOR_PASSWORD", "auditor-demo-123"),
    }


settings = Settings()
