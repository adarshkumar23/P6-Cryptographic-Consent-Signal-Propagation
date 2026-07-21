import os
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./p6_dev.db"
    satellite_kek: str = ""
    core_base_url: str = "http://localhost:8000"
    core_api_key: str = ""
    retry_backoff_seconds: str = "30,120,300"
    escalation_non_ack_hours: int = 48

    model_config = {"env_file": ".env"}

    @property
    def retry_backoff_sequence(self) -> list[int]:
        return [int(x) for x in self.retry_backoff_seconds.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()
