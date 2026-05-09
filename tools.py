import os
import requests
import json

ALLOWED_STREET_GROUPS = ["Abou Qir", "Coastal", "Mahmoudia", "Moustafa Kamel"]
_STREET_GROUP_LOOKUP = {name.lower(): name for name in ALLOWED_STREET_GROUPS}

# Define the tools available for the model to use (JSON Schema)
AVAILABLE_TOOLS_SCHEMA = [
    {
        "name": "geocode_location",
        "description": "Convert a place name in Alexandria to one best geographic coordinate pair (top-1 latitude/longitude). Always use this tool before searching for a multimodal transit route if you only have the place name.",
        "parameters": {
            "type": "object",
            "properties": {
                "place_name": {
                    "type": "string",
                    "description": "The name of the place (e.g., Mahatet Misr, Sidi Gaber, San Stefano)"
                }
            },
            "required": ["place_name"]
        }
    },
    {
        "name": "get_routes",
        "description": "Find multimodal transportation routes between two points using coordinates and routing preferences.",
        "parameters": {
            "type": "object",
            "properties": {
                "start_lat": {
                    "type": "number",
                    "description": "Latitude of the trip starting location"
                },
                "start_lon": {
                    "type": "number",
                    "description": "Longitude of the trip starting location"
                },
                "end_lat": {
                    "type": "number",
                    "description": "Latitude of the destination"
                },
                "end_lon": {
                    "type": "number",
                    "description": "Longitude of the destination"
                },
                "max_transfers": {
                    "type": "integer",
                    "description": "Maximum allowed transfers"
                },
                "walking_cutoff": {
                    "type": "integer",
                    "description": "Maximum walking distance in meters"
                },
                "priority": {
                    "type": "string",
                    "description": "Route optimization strategy: time, cost, or balanced"
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of top routes to return (agent enforces top 5)"
                },
                "weights": {
                    "type": "object",
                    "additionalProperties": {"type": "number"},
                    "description": "Optional weight map (e.g., time/cost/comfort)"
                },
                "filters": {
                    "type": "object",
                    "properties": {
                        "modes": {
                            "type": "object",
                            "properties": {
                                "include": {"type": "array", "items": {"type": "string"}},
                                "exclude": {"type": "array", "items": {"type": "string"}},
                                "include_match": {"type": "string", "enum": ["any", "all"]}
                            }
                        },
                        "main_streets": {
                            "type": "object",
                            "properties": {
                                "include": {"type": "array", "items": {"type": "string"}},
                                "exclude": {"type": "array", "items": {"type": "string"}},
                                "include_match": {"type": "string", "enum": ["any", "all"]}
                            }
                        }
                    }
                }
            },
            "required": ["start_lat", "start_lon", "end_lat", "end_lon"]
        }
    },
    {
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
    },
    {
        "name": "check_traffic",
        "description": "Check the current traffic status for a street group in Alexandria.",
        "parameters": {
            "type": "object",
            "properties": {
                "street_name": {
                    "type": "string",
                    "enum": ALLOWED_STREET_GROUPS,
                    "description": "Allowed street group name only: Abou Qir, Coastal, Mahmoudia, Moustafa Kamel"
                }
            },
            "required": ["street_name"]
        }
    }
]

# Real Python functions that communicate with your APIs
def execute_geocode(place_name):
    """Call the Real Geocoding API"""
    url = "http://localhost:8003/api/v1/geocode"
    params = {"address": place_name, "language": "en"}
    try:
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if not isinstance(data, dict):
                return {"error": "Unexpected geocoding response format"}

            if not data.get("success", False):
                return {"error": data.get("error", "No geocoding results found")}

            results = data.get("results", [])
            if not results:
                return {"error": "No geocoding results found"}

            top_result = results[0] if isinstance(results[0], dict) else {}
            lat = top_result.get("latitude")
            lon = top_result.get("longitude")

            if lat is None or lon is None:
                return {"error": "Top geocoding result is missing coordinates"}

            return {
                "lat": lat,
                "lon": lon,
                "formatted_address": top_result.get("formatted_address", ""),
            }
        return {"error": f"Geocoding failed: {response.status_code}"}
    except Exception as e:
        return {"error": f"Error connecting to Geocoding API: {e}"}

def execute_route(
    start_lat,
    start_lon,
    end_lat,
    end_lon,
    max_transfers=2,
    walking_cutoff=1500,
    priority="balanced",
    top_k=5,
    weights=None,
    filters=None,
):
    """Call the Real Routing API"""
    url = "http://localhost:8000/api/v1/journeys"
    safe_priority = priority if priority in {"time", "cost", "balanced"} else "balanced"
    payload = {
        "start_lat": start_lat,
        "start_lon": start_lon,
        "end_lat": end_lat,
        "end_lon": end_lon,
        "max_transfers": max_transfers,
        "walking_cutoff": walking_cutoff,
        "priority": safe_priority,
        "top_k": 5,
    }

    if isinstance(weights, dict) and weights:
        payload["weights"] = weights

    if isinstance(filters, dict) and filters:
        for key in ("modes", "main_streets"):
            block = filters.get(key)
            if isinstance(block, dict):
                include_match = block.get("include_match", "any")
                if include_match not in {"any", "all"}:
                    block["include_match"] = "any"
        payload["filters"] = filters

    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            journeys = data.get("journeys", [])[:5] if isinstance(data, dict) else []
            compact_journeys = []
            summaries = []

            for idx, journey in enumerate(journeys, start=1):
                if not isinstance(journey, dict):
                    continue

                summary = journey.get("summary") if isinstance(journey.get("summary"), dict) else {}
                text = journey.get("text_summary") or journey.get("text_summary_en")
                compact_journeys.append(
                    {
                        "route_number": idx,
                        "text_summary": text,
                        "summary": {
                            "total_time_minutes": summary.get("total_time_minutes"),
                            "walking_distance_meters": summary.get("walking_distance_meters"),
                            "transit_distance_meters": summary.get("transit_distance_meters"),
                            "total_distance_meters": summary.get("total_distance_meters"),
                            "transfers": summary.get("transfers"),
                            "cost": summary.get("cost"),
                            "modes_ar": summary.get("modes_ar", []),
                            "main_streets_ar": summary.get("main_streets_ar", []),
                        },
                    }
                )

                if text:
                    summaries.append(f"{idx}. {text}")

            return {
                "journeys": compact_journeys,
                "selected_priority": safe_priority,
                "num_journeys": len(compact_journeys),
                "raw_summary": data.get("summary") if isinstance(data, dict) else None,
            }
        return {"error": f"Routing failed: {response.status_code}"}
    except Exception as e:
        return {"error": f"Error connecting to Routing API: {e}"}

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

def execute_traffic(street_name):
    """Call the Real Traffic API"""
    if not isinstance(street_name, str) or not street_name.strip():
        return {"error": "street_name is required. Allowed values: Abou Qir, Coastal, Mahmoudia, Moustafa Kamel"}

    normalized = _STREET_GROUP_LOOKUP.get(street_name.strip().lower())
    if not normalized:
        return {
            "error": "Invalid street_name. Allowed values: Abou Qir, Coastal, Mahmoudia, Moustafa Kamel"
        }

    url = f"http://localhost:8001/api/v1/traffic/street"
    params = {"name": normalized, "language": "en"}
    try:
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, dict):
                return {"overall_status": data.get("overall_status", "")}
            return {"error": "Unexpected traffic response format"}
        return {"error": f"Traffic check failed: {response.status_code}"}
    except Exception as e:
        return {"error": f"Error connecting to Traffic API: {e}"}
