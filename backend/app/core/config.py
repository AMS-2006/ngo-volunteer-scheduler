from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    # App
    app_name: str = "NGO Volunteer Scheduler"
    app_version: str = "1.0.0"
    debug: bool = True

    # Database
    database_url: str = "postgresql+psycopg2://postgres:password@localhost:5432/ngo_volunteer_db"

    # JWT
    secret_key: str = "fallback-dev-secret-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # CORS
    allowed_origins: str = "http://localhost:3000,http://localhost:5173"

    # Module 4: how often (seconds) overdue invitations are expired in the background; 0 = off
    invitation_expiry_interval_seconds: int = 60

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]


@lru_cache()
def get_settings() -> Settings:
    return Settings()
