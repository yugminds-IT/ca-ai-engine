from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "CAA AI Service"
    app_version: str = "1.0.0"
    debug: bool = False

    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    upload_dir: str = "/tmp/caa-ai/uploads"
    output_dir: str = "/tmp/caa-ai/outputs"
    max_file_size: int = 10 * 1024 * 1024  # 10 MB

    # HuggingFace model path/ID for SmolVLM (override to use a local cache)
    vlm_model_path: str = "HuggingFaceTB/SmolVLM-256M-Instruct"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


@lru_cache
def get_settings() -> Settings:
    return Settings()
