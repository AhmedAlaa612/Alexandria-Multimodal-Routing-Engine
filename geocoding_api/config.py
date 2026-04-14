"""
Geocoding API settings.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Server
    host: str = "0.0.0.0"
    rest_port: int = 8003
    grpc_port: int = 50054

    # Defaults
    default_language: str = "en"
    bias_to_alexandria: bool = True

    model_config = {
        "env_prefix": "GEOCODING_",
        "env_file": ".env",
        "extra": "ignore",
    }


settings = Settings()
