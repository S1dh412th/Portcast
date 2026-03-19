from __future__ import annotations

from pydantic import BaseModel, Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseModel):
    url: str = Field(default="sqlite+pysqlite:///./app.db", description="Database connection URL")
    echo: bool = Field(default=False, description="Enable SQLAlchemy echo logging")


class RedisSettings(BaseModel):
    url: str = Field(default="redis://localhost:6379", description="Redis connection URL")
    ttl: int = Field(default=86400, gt=0, description="Cache TTL in seconds (24 hours)")
    enabled: bool = Field(default=True, description="Enable Redis caching")


class ExternalAPISettings(BaseModel):
    metaphorpsum_url: str = Field(default="http://metaphorpsum.com/paragraphs/1/50", description="Metaphorpsum API URL")
    metaphorpsum_timeout: float = Field(default=15.0, gt=0, description="Timeout for metaphorpsum API calls")
    dictionary_base_url: str = Field(default="https://api.dictionaryapi.dev/api/v2/entries/en", description="Dictionary API base URL")
    dictionary_timeout: float = Field(default=15.0, gt=0, description="Timeout for dictionary API calls")


class APISettings(BaseModel):
    title: str = Field(default="Portcast API", description="API title")
    version: str = Field(default="0.1.0", description="API version")
    description: str = Field(default="Paragraph fetch/search/dictionary API", description="API description")


class Settings(BaseSettings):
    database: DatabaseSettings = DatabaseSettings()
    redis: RedisSettings = RedisSettings()
    external_api: ExternalAPISettings = ExternalAPISettings()
    api: APISettings = APISettings()

    model_config = SettingsConfigDict(
        env_prefix="PORTCAST_",
        env_nested_delimiter="__",
        env_file=".env",
    )


try:
    settings = Settings()
except ValidationError as e:
    raise RuntimeError(f"Configuration validation error: {e}") from e
except Exception as e:
    raise RuntimeError(f"Configuration loading error: {e}") from e