from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings(BaseSettings):
    GROQ_API_KEY: str = ""
    ENV: str = "dev"
    PORT: int = 8000
    CORS_ALLOWED_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_allowed_origins(self) -> list[str]:
        return _parse_csv(self.CORS_ALLOWED_ORIGINS)

    @property
    def session_cookie_secure(self) -> bool:
        return self.ENV.strip().lower() == "prod"


settings = Settings()
