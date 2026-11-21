"""Settings from environment. See .env.example."""
import os
from pathlib import Path


def _env(name: str, default: str) -> str:
    """Env var, or the default when it is unset, blank, or just an inline comment (docker `env_file` can pass
    `KEY=   # comment` through as the value '# comment')."""
    value = os.environ.get(name)
    if value is None or not value.strip() or value.strip().startswith("#"):
        return default
    return value.strip()


class Settings:
    AI_MODE = _env("AI_MODE", "stub")
    MOCKS_URL = _env("MOCKS_URL", "")  # empty -> use fake_mocks_client
    DATABASE_URL = _env("DATABASE_URL", "postgresql+psycopg2://bharosa:bharosa@localhost:5432/bharosa")
    JWT_SECRET = _env("JWT_SECRET", "dev-only-change-me-not-for-production-0000")
    JWT_ALGORITHM = "HS256"
    UPLOAD_DIR = Path(_env("UPLOAD_DIR", str(Path(__file__).resolve().parents[1] / "uploads")))
    MAX_UPLOAD_BYTES = int(_env("MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))
    DEMO_CITIZEN_PIN = _env("DEMO_CITIZEN_PIN", "1234")  # FAKE, prototype only
    # --- background pipeline
    PIPELINE_MODE = _env("PIPELINE_MODE", "thread")  # thread: in-process worker | inline: run inside the request (tests)
    JOB_POLL_SECONDS = float(_env("JOB_POLL_SECONDS", "1.0"))
    JOB_STALE_SECONDS = int(_env("JOB_STALE_SECONDS", "300"))  # a 'running' job older than this is re-queued at startup
    # --- rate limiting (slowapi format "N/period")
    LOGIN_RATE_LIMIT = _env("LOGIN_RATE_LIMIT", "5/minute")
    DEFAULT_RATE_LIMIT = _env("DEFAULT_RATE_LIMIT", "120/minute")
    PUBLIC_RATE_LIMIT = _env("PUBLIC_RATE_LIMIT", "30/minute")  # per API key
    TRUST_PROXY = _env("TRUST_PROXY", "0") == "1"  # use X-Forwarded-For for the client IP (set behind Render/Railway)
    # --- monitoring / deploy
    SENTRY_DSN = _env("SENTRY_DSN", "")
    ENVIRONMENT = _env("ENVIRONMENT", "dev")
    LOG_LEVEL = _env("LOG_LEVEL", "INFO")
    EVAL_RESULTS_PATH = Path(_env("EVAL_RESULTS_PATH", str(Path(__file__).resolve().parents[2] / "ai" / "eval" / "eval_results.json")))
    APP_VERSION = "0.3.0"
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
