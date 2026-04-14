"""
Fare model: sklearn regression model for trip segment fares.
"""
from __future__ import annotations

import math

from joblib import load as joblib_load

from routing_api.config import settings
from routing_api.cost.distance import get_distance_km

# Module-level state (loaded once at startup)
_intercept: float = 0.0
_beta_distance: float = 0.0
_beta_passengers: float = 0.0


def load_fare_model() -> None:
    """Load the sklearn fare model and extract coefficients."""
    global _intercept, _beta_distance, _beta_passengers
    path = str(settings.resolve(settings.fare_model_path))
    model = joblib_load(path)
    _intercept = model.intercept_
    _beta_distance, _beta_passengers = model.coef_
    print(f"[fare] Model loaded - intercept: {_intercept:.4f}, "
          f"beta_distance: {_beta_distance:.4f}, beta_passengers: {_beta_passengers:.4f}")


def get_fare(
    trip_id: str,
    start_stop: str,
    end_stop: str,
    agency: str = "P_O_14",
    distance_km: float | None = None,
) -> int:
    """
    Fare for a trip segment.

    Pass pre-computed ``distance_km`` to avoid a redundant distance lookup.
    """
    if distance_km is None:
        distance_km = get_distance_km(trip_id, start_stop, end_stop)
    passengers = 8 if agency == "P_B_8" else 14
    return math.ceil(_intercept + _beta_distance * distance_km + _beta_passengers * passengers)
