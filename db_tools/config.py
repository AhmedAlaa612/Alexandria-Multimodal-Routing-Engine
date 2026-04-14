"""
DB Tools API settings.
"""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database - load from .env SUPABASE_* variables
    db_host: str = Field(..., validation_alias="SUPABASE_HOST")
    db_port: int = Field(6543, validation_alias="SUPABASE_PORT")
    db_name: str = Field("postgres", validation_alias="SUPABASE_DB_NAME")
    db_user: str = Field(..., validation_alias="SUPABASE_DB_USER")
    db_password: str = Field(..., validation_alias="SUPABASE_DB_PASSWORD")

    # Connection pool
    db_pool_min: int = 2
    db_pool_max: int = 10

    # Server
    host: str = "0.0.0.0"
    rest_port: int = 8002
    grpc_port: int = 50053

    # Spatial defaults
    default_radius_m: float = 1000.0
    default_epsg: int = 32636  # UTM zone 36N (Alexandria)

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
