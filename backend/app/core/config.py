from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 127.0.0.1, not localhost: the container binds IPv4 loopback only, and
    # localhost may resolve to a blackholed ::1 first on this machine.
    database_url: str = "postgresql+psycopg://awc:awc_local_dev@127.0.0.1:5432/ai_writing_coach"
    database_connect_timeout: int = 5
    # Port 3000 sits inside a Windows Hyper-V/WinNAT excluded port range on the
    # dev machine, so the local frontend runs on 3500.
    cors_origins: list[str] = ["http://localhost:3500"]

    # --- Authentication (Stage 2 Slice 1) ---
    # Dev-only default; override JWT_SECRET with a long random value in any
    # real deployment. Never commit real secrets.
    jwt_secret: str = "dev-only-insecure-jwt-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "ai-writing-coach"
    jwt_audience: str = "ai-writing-coach-api"
    access_token_ttl_seconds: int = 900
    refresh_token_ttl_days: int = 30
    refresh_cookie_name: str = "awc_refresh_token"
    refresh_cookie_path: str = "/api/v1/auth"
    # In-process rate-limit reservation for register/login (per client IP).
    # Single-worker dev store; replace with a shared store when scaling out.
    auth_rate_limit_max_requests: int = 20
    auth_rate_limit_window_seconds: int = 300

    # --- Grammar checking (Stage 2 Slice 3) ---
    language_tool_url: str = "http://127.0.0.1:8010"
    language_tool_timeout_seconds: float = 15.0
    language_tool_language: str = "en-US"

    # --- LLM provider abstraction (Stage 2 Slice 3) ---
    # mock: deterministic dev/test provider, zero cost, never for production.
    # openai_compat: any OpenAI-compatible chat completions endpoint.
    llm_provider: str = "mock"
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_timeout_seconds: float = 60.0
    llm_max_retries: int = 1
    # Optional pricing for cost estimates (USD per 1K tokens).
    llm_input_cost_per_1k: float = 0.0
    llm_output_cost_per_1k: float = 0.0

    # --- Embeddings / RAG (Stage 2 Slice 5) ---
    # mock: deterministic pseudo-vectors for tests (NOT semantic).
    # openai_compat: any OpenAI-compatible embeddings endpoint.
    embedding_provider: str = "mock"
    embedding_base_url: str = ""
    embedding_api_key: str = ""
    embedding_model: str = ""
    # Must match the VECTOR(n) column (migration 0010 uses 1536).
    embedding_dimensions: int = 1536
    embedding_timeout_seconds: float = 30.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
