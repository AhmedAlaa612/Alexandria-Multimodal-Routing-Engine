"""
Application settings loaded from environment variables / .env file.
"""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All paths are relative to the project root (V1/)."""

    # ── Data paths ────────────────────────────────────────────────────────────
    osm_xml_path: str = "data/utils/alex.osm"
    graph_cache_path: str = "data/utils/alex_cached.pkl"
    trip_graph_cache_path: str = "data/utils/trip_graph_cache.pkl"
    gtfs_lookup_cache_path: str = "data/utils/gtfs_lookup_cache.pkl"
    gtfs_path: str = "data/gtfsAlex"
    pathways_path: str = "data/utils/trip_pathways.csv"
    prefix_distances_path: str = "data/utils/prefixdistances.json"
    prefix_times_path: str = "data/utils/prefixtimes.json"
    fare_model_path: str = "data/utils/model.pkl"

    # ── Rebuild flags ─────────────────────────────────────────────────────────
    force_rebuild_graph: bool = False
    force_rebuild_trip_graph: bool = False
    force_rebuild_lookups: bool = False

    # ── Server ────────────────────────────────────────────────────────────────
    host: str = "0.0.0.0"
    rest_port: int = 8000
    grpc_port: int = 50051
    admin_key: str = "Alaa"

    # ── Project root (resolved once) ─────────────────────────────────────────
    @property
    def project_root(self) -> Path:
        """V1/ directory — all relative paths are resolved against this."""
        return Path(__file__).resolve().parent.parent
 
    def resolve(self, relative: str) -> Path:
        """Resolve a settings path relative to
         the project root."""
        return self.project_root / relative

    model_config = {"env_prefix": "ROUTING_", "env_file": ".env", "extra": "ignore"}


settings = Settings()
