from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    database_url: str = "postgresql+psycopg://dialectio:dialectio@localhost:5432/dialectio"
    cors_origins: list[str] = ["http://localhost:3000"]
    # Shared secret for the word editor; editing is disabled when empty.
    editor_token: str = ""


settings = Settings()
