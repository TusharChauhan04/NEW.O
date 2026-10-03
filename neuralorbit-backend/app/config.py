"""
config.py — NeuralOrbit Backend Settings
All config comes from .env (or environment variables on AWS).
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── App ──────────────────────────────────────────────
    APP_ENV: str = "development"
    AUTH_REQUIRED: bool = False  # Set True in production
    APP_CORS_ORIGINS: str = (
        "http://localhost:5173,http://localhost:3000,"
        "http://127.0.0.1:5500,http://localhost:8080"
    )

    # ── Supabase ─────────────────────────────────────────
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_JWT_SECRET: str = ""

    # ── LLM ──────────────────────────────────────────────
    LLM_PROVIDER: str = "mock"  # "mock" | "openai" | "gemini" | "claude"
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    CLAUDE_API_KEY: str = ""   # Anthropic Claude — set LLM_PROVIDER=claude to activate

    # ── Redis / Celery ────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── OAuth — CRM (L2) ─────────────────────────────────
    ZOHO_CLIENT_ID: str = ""
    ZOHO_CLIENT_SECRET: str = ""
    HUBSPOT_CLIENT_ID: str = ""
    HUBSPOT_CLIENT_SECRET: str = ""
    OAUTH_REDIRECT_URI: str = "http://localhost:8000/api/v1/integrations/oauth/callback"

    # ── OAuth — Marketing (L3) ───────────────────────────
    META_APP_ID: str = ""
    META_APP_SECRET: str = ""
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # ── n8n Executor (L5) ────────────────────────────────
    N8N_BASE_URL: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.APP_CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    class Config:
        env_file = ".env"
        extra = "ignore"


class InsecureConfigError(RuntimeError):
    """Raised when a config combination would silently run insecurely."""


def validate_production_config(s: "Settings") -> None:
    """
    Refuse to boot if APP_ENV=production is set without AUTH_REQUIRED=true.
    AUTH_REQUIRED defaults to False for local dev convenience (see
    README_ADMIN.md's documented dev-mode workflow) — that default is
    intentional and must not change. What must never happen is a
    *production* deployment silently inheriting it.
    """
    if s.is_production and not s.AUTH_REQUIRED:
        raise InsecureConfigError(
            "Refusing to start: APP_ENV=production requires AUTH_REQUIRED=true. "
            "Set AUTH_REQUIRED=true in this environment's .env / secrets, or "
            "unset APP_ENV=production if this is genuinely a dev deployment."
        )


@lru_cache()
def get_settings() -> Settings:
    return Settings()


# Single importable instance
settings = get_settings()
