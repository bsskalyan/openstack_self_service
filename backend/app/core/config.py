from functools import lru_cache

from dotenv import load_dotenv
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env."""

    app_name: str = Field(
        default="OpenStack Self-Service Portal",
        validation_alias="APP_NAME",
    )
    app_version: str = Field(default="0.1.0", validation_alias="APP_VERSION")
    environment: str = Field(default="development", validation_alias="APP_ENV")
    debug: bool = Field(default=False, validation_alias="APP_DEBUG")
    api_v1_prefix: str = Field(default="/api/v1", validation_alias="API_V1_PREFIX")
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://10.161.230.18:5173",
        ],
        validation_alias="CORS_ORIGINS",
    )
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    os_auth_url: str | None = Field(default=None, validation_alias="OS_AUTH_URL")
    os_username: str | None = Field(default=None, validation_alias="OS_USERNAME")
    os_password: SecretStr | None = Field(default=None, validation_alias="OS_PASSWORD")
    os_project_name: str | None = Field(default=None, validation_alias="OS_PROJECT_NAME")
    os_user_domain_id: str = Field(default="default", validation_alias="OS_USER_DOMAIN_ID")
    os_project_domain_id: str = Field(
        default="default",
        validation_alias="OS_PROJECT_DOMAIN_ID",
    )
    os_region_name: str | None = Field(default=None, validation_alias="OS_REGION_NAME")
    ssh_private_key_path: str | None = Field(
        default=None,
        validation_alias="SSH_PRIVATE_KEY_PATH",
    )
    ssh_known_hosts_path: str | None = Field(
        default=None,
        validation_alias="SSH_KNOWN_HOSTS_PATH",
    )
    ssh_default_username: str = Field(default="ubuntu", validation_alias="SSH_DEFAULT_USERNAME")
    ssh_session_timeout_seconds: int = Field(
        default=1800,
        validation_alias="SSH_SESSION_TIMEOUT_SECONDS",
    )

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
