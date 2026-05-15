import os

import requests


TOOL_SCHEMA = {
    "name": "db_tools",
    "description": "Find nearby transit trips around a coordinate using the DB Tools API.",
    "parameters": {
        "type": "object",
        "properties": {
            "lat": {"type": "number", "description": "Latitude of the search center"},
            "lon": {"type": "number", "description": "Longitude of the search center"},
            "radius_m": {
                "type": "number",
                "description": "Search radius in meters (optional, default 1000)"
            },
            "starts": {
                "type": "boolean",
                "description": "If true, only trips whose start stop is within radius"
            }
        },
        "required": ["lat", "lon"]
    }
}


def execute_db_tools(lat, lon, radius_m=1000, starts=False):
    """Call DB Tools API for nearby trips"""
    base_url = os.getenv("DB_TOOLS_BASE_URL", "http://localhost:8086")
    url = f"{base_url.rstrip('/')}" + "/api/v1/nearby-trips"
    params = {
        "lat": lat,
        "lon": lon,
        "radius_m": radius_m,
        "starts": starts,
    }
    try:
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            trips = data.get("trips", [])[:5] if isinstance(data, dict) else []
            filtered_trips = []
            for trip in trips:
                if isinstance(trip, dict):
                    filtered_trips.append({"route_name_ar": trip.get("route_name_ar", "")})

            return {
                "trips": filtered_trips,
            }
        return {"error": f"DB Tools failed: {response.status_code}"}
    except Exception as e:
        return {"error": f"Error connecting to DB Tools API: {e}"}
