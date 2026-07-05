from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    database_url: str = "postgresql+asyncpg://specula:specula@localhost:55432/specula"
    service_jwt_secret: str = ""
    service_jwt_issuer: str = "specula-web"
    service_jwt_audience: str = "specula-api"


settings = Settings()
