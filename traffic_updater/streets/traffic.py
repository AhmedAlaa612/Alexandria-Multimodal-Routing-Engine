"""
Street traffic module: load GeoJSON road segments, sample waypoints,
and query Google Maps for live traffic on main streets.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Optional

from traffic_updater.config import settings
from traffic_updater.gmaps.client import get_directions

# ── Street group definitions ─────────────────────────────────────────────────

GEOJSON_FILES = {
    "primary": "data/utils/export1.geojson",
    "trunk": "data/utils/export2.geojson",
    "secondary": "data/utils/export3.geojson",
}

STREET_GROUPS = {
    "Abou Qir": [
        "Gamal Abd Al Naser Street",
    ],
    "Coastal": [
        "Al Geish Road",
    ],
    "Mahmoudia": [
        "Qanal Al Mahmodiah Street",
        "Qanal Al Mahmodiah Al Bahry Street",
        "Qana Al Mahmodiah Street",
    ],
    "Moustafa Kamel": [
        "Moustafa Kamel Street",
    ],
}

STREET_GROUPS_AR = {
    "Abou Qir": "شارع ابوقير",
    "Coastal": "بحر",
    "Mahmoudia": "محمودية",
    "Moustafa Kamel": "مصطفى كامل",
}

# ── GeoJSON loading and waypoint extraction ──────────────────────────────────

_geojson_cache: dict[str, list] = {}


def _load_geojson(highway_class: str) -> list[dict]:
    """Load and cache a GeoJSON FeatureCollection."""
    if highway_class not in _geojson_cache:
        rel_path = GEOJSON_FILES.get(highway_class)
        if not rel_path:
            return []
        full_path = settings.resolve(rel_path)
        if not full_path.exists():
            print(f"[streets] Warning: GeoJSON not found: {full_path}")
            return []
        with open(full_path, encoding="utf-8") as f:
            data = json.load(f)
        _geojson_cache[highway_class] = data.get("features", [])
    return _geojson_cache[highway_class]


def _features_for_street(street_name: str) -> list[dict]:
    """
    Find all GeoJSON features whose name:en (or name) matches any of
    the aliases in the street group.
    """
    aliases = STREET_GROUPS.get(street_name)
    if not aliases:
        return []

    alias_set = set(a.lower() for a in aliases)
    features = []
    for hw_class in GEOJSON_FILES:
        for feat in _load_geojson(hw_class):
            props = feat.get("properties", {})
            name_en = (props.get("name:en") or props.get("name") or "").strip()
            if name_en.lower() in alias_set:
                features.append(feat)
    return features


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in meters."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _extract_ordered_coords(features: list[dict]) -> list[tuple[float, float]]:
    """
    Extract all coordinates from LineString features and chain them in order.
    Returns list of (lat, lon) tuples.
    
    GeoJSON stores coords as [lon, lat], so we swap.
    """
    all_coords = []
    for feat in features:
        geom = feat.get("geometry", {})
        if geom.get("type") != "LineString":
            continue
        coords = geom.get("coordinates", [])
        # coords are [lon, lat] pairs
        segment = [(c[1], c[0]) for c in coords]
        all_coords.extend(segment)
    return all_coords


def _sample_waypoints(
    coords: list[tuple[float, float]],
    max_waypoints: int = 20,
    min_spacing_m: float = 200,
) -> list[tuple[float, float]]:
    """
    Sample waypoints from a potentially dense coordinate list.
    
    Google Maps directions API supports at most ~25 waypoints.
    We sample evenly along the polyline, respecting a minimum spacing.
    """
    if len(coords) <= max_waypoints:
        return coords

    # Compute cumulative distances
    cum_dist = [0.0]
    for i in range(1, len(coords)):
        d = _haversine_m(coords[i - 1][0], coords[i - 1][1],
                         coords[i][0], coords[i][1])
        cum_dist.append(cum_dist[-1] + d)

    total_length = cum_dist[-1]
    if total_length < 100:
        return [coords[0], coords[-1]]

    # Target spacing
    step = max(total_length / (max_waypoints - 1), min_spacing_m)
    sampled = [coords[0]]
    next_target = step
    for i in range(1, len(coords)):
        if cum_dist[i] >= next_target:
            sampled.append(coords[i])
            next_target += step

    # Always include the last point
    if sampled[-1] != coords[-1]:
        sampled.append(coords[-1])

    return sampled


# ── Public API ───────────────────────────────────────────────────────────────

def get_available_streets() -> list[dict]:
    """List all available street groups with metadata."""
    streets = []
    for name, aliases in STREET_GROUPS.items():
        features = _features_for_street(name)
        coords = _extract_ordered_coords(features)
        total_len_m = 0
        for i in range(1, len(coords)):
            total_len_m += _haversine_m(
                coords[i - 1][0], coords[i - 1][1],
                coords[i][0], coords[i][1],
            )
        streets.append({
            "name": name,
            "name_ar": STREET_GROUPS_AR.get(name, ""),
            "aliases": aliases,
            "segments": len(features),
            "total_length_km": round(total_len_m / 1000, 1),
        })
    return streets


def _calculate_status(congestion_ratio: float) -> str:
    """Determine traffic status based on congestion ratio.
    
    Thresholds:
    - Clear: ratio < 1.5 (actual time < 1.5x normal)
    - Moderate: 1.5 <= ratio < 3.0
    - Heavy: ratio >= 3.0
    """
    if congestion_ratio < 1.5:
        return "clear"
    elif congestion_ratio < 3.0:
        return "moderate"
    else:
        return "heavy"


def get_street_traffic(
    street_name: str,
    language: str = "en",
    max_waypoints: int = 20,
    normal_speed_kph: float = 40,
) -> dict:
    """
    Get live traffic info for a named street from Google Maps.

    1. Loads GeoJSON segments for the street group
    2. Extracts and chains all coordinates
    3. Samples waypoints (max ~20 to stay within Google limits)
    4. Calls Google Maps directions to get traffic-aware times
    5. Returns summary + per-leg breakdown with traffic status

    Parameters
    ----------
    street_name : str
        One of the keys in STREET_GROUPS (e.g. "Abou Qir", "Coastal")
    language : str
        Google Maps language code
    max_waypoints : int
        Max waypoints to send to Google (default 20)
    normal_speed_kph : float
        Normal free-flow speed in km/h (default 40)

    Returns
    -------
    dict with keys:
        street, street_ar, segments, waypoints_used,
        total_distance_km, total_duration_min, total_duration_normal_s,
        overall_status,
        legs (list of per-segment distance/duration with status),
        error (if any)
    """
    if street_name not in STREET_GROUPS:
        available = list(STREET_GROUPS.keys())
        return {
            "street": street_name,
            "error": f"Unknown street. Available: {available}",
        }

    features = _features_for_street(street_name)
    if not features:
        return {
            "street": street_name,
            "error": "No GeoJSON features found for this street.",
        }

    coords = _extract_ordered_coords(features)
    if len(coords) < 2:
        return {
            "street": street_name,
            "error": "Not enough coordinates to query traffic.",
        }

    waypoints = _sample_waypoints(coords, max_waypoints=max_waypoints)

    try:
        gmaps_result = get_directions(
            stops=waypoints,
            language=language,
            country=settings.gmaps_country,
        )
    except Exception as e:
        return {
            "street": street_name,
            "error": f"Google Maps request failed: {e}",
        }

    # ── Calculate status for each leg ──────────────────────────────────────────
    total_distance_m = gmaps_result.get("total_distance_km", 0) * 1000
    total_duration_s = gmaps_result.get("total_duration_min", 0) * 60
    
    # Expected duration at normal speed: distance / speed * 3600
    normal_duration_s = int((total_distance_m / 1000) / normal_speed_kph * 3600)
    
    # Calculate status for each leg
    legs_with_status = []
    for leg in gmaps_result.get("legs", []):
        leg_distance_m = leg.get("distance_m", 0)
        leg_duration_s = leg.get("duration_seconds", 0)
        
        # Calculate normal duration for this leg
        leg_normal_s = (leg_distance_m / 1000) / normal_speed_kph * 3600 if leg_distance_m > 0 else 0
        
        # Calculate congestion ratio
        if leg_normal_s > 0:
            congestion_ratio = leg_duration_s / leg_normal_s
        else:
            congestion_ratio = 1.0
        
        status = _calculate_status(congestion_ratio)
        
        leg_with_status = dict(leg)
        leg_with_status["status"] = status
        legs_with_status.append(leg_with_status)
    
    # ── Calculate overall status ──────────────────────────────────────────────
    if normal_duration_s > 0:
        overall_congestion = total_duration_s / normal_duration_s
    else:
        overall_congestion = 1.0
    
    overall_status = _calculate_status(overall_congestion)

    return {
        "street": street_name,
        "street_ar": STREET_GROUPS_AR.get(street_name, ""),
        "segments": len(features),
        "waypoints_used": len(waypoints),
        "total_distance_km": gmaps_result.get("total_distance_km", 0),
        "total_duration_min": gmaps_result.get("total_duration_min", 0),
        "total_duration_normal_s": normal_duration_s,
        "overall_status": overall_status,
        "legs": legs_with_status,
        "routes": gmaps_result.get("routes", []),
    }
