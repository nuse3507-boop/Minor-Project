from functools import lru_cache
from pathlib import Path

from pydantic import Field, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_ROOT / ".env", extra="ignore")
    database_url: str = Field(repr=False)
    storage_path: Path = Path("private-data")
    storage_key: str = Field(default="", repr=False)
    secure_cookies: bool = False
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    environment: str = "development"
    max_upload_bytes: int = 20 * 1024 * 1024
    max_pages: int = 150
    max_document_tokens: int = 100000
    gemini_api_key: str = Field(default="", repr=False)
    gemini_model: str = ""
    groq_api_key: str = Field(default="", repr=False)
    groq_model: str = ""
    openrouter_api_key: str = Field(default="", repr=False)
    openrouter_model: str = ""
    provider_pricing: dict[str, dict[str, float]] = Field(default_factory=dict)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = Field(default="", repr=False)
    mail_from: str = ""
    public_url: str = "http://localhost:5173"

    @field_validator("database_url", mode="before")
    @classmethod
    def postgres_driver(cls, value):
        if isinstance(value, str):
            for prefix in ("postgresql://", "postgres://"):
                if value.startswith(prefix):
                    return "postgresql+psycopg://" + value[len(prefix) :]
        return value

    @field_validator("storage_path")
    @classmethod
    def private_path(cls, value):
        return value if value.is_absolute() else BACKEND_ROOT / value

    @model_validator(mode="after")
    def database_policy(self):
        if not self.database_url.startswith("postgresql+psycopg://") and not (
            self.environment == "test" and self.database_url.startswith("sqlite")
        ):
            raise ValueError("Configure PostgreSQL with psycopg; SQLite is restricted to isolated tests.")
        return self

    def providers(self):
        if self.environment == "test":
            # Do not inherit live provider credentials from .env in isolated test servers.
            return [{"name": n, "key": "", "model": ""} for n in ("gemini", "groq", "openrouter")]
        return [
            {
                "name": n,
                "key": getattr(self, n + "_api_key"),
                "model": getattr(self, n + "_model"),
                **{
                    k: v
                    for k, v in self.provider_pricing.get(n, {}).items()
                    if k in ("input_price_per_million", "output_price_per_million") and v >= 0
                },
            }
            for n in ("gemini", "groq", "openrouter")
        ]


@lru_cache
def settings():
    try:
        value = Settings()
    except ValidationError as exc:
        fields = sorted({str(e["loc"][0]) if e["loc"] else "database_policy" for e in exc.errors()})
        raise RuntimeError("Invalid application configuration: " + ", ".join(fields)) from None
    if value.environment == "production" and (
        not value.secure_cookies or not value.storage_key or not value.database_url.startswith("postgresql")
    ):
        raise RuntimeError("Production requires secure cookies, storage encryption key and PostgreSQL")
    return value
