"""
Traffic updater settings.
"""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Data paths (relative to project root V1/)
    gtfs_path: str = "data/gtfsAlex"
    prefix_times_path: str = "data/utils/prefixtimes.json"
    prefix_distances_path: str = "data/utils/prefixdistances.json"

    # Routing API (to notify after update)
    routing_api_url: str = "http://localhost:8000"
    routing_admin_key: str = "Alaa"

    # Google Maps
    gmaps_language: str = "en"
    gmaps_country: str = "eg"
    gmaps_request_delay: float = 1.0  # seconds between requests to avoid rate-limiting

    # Server
    host: str = "0.0.0.0"
    rest_port: int = 8001
    grpc_port: int = 50052

    @property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parent.parent

    def resolve(self, relative: str) -> Path:
        return self.project_root / relative

    model_config = {"env_prefix": "TRAFFIC_", "env_file": ".env", "extra": "ignore"}


settings = Settings()
