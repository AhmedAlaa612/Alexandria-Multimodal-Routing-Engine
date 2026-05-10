import requests


TOOL_SCHEMA = {
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
}


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
        normalized_filters = dict(filters)
        for key in ("modes", "main_streets"):
            block = normalized_filters.get(key)
            if isinstance(block, dict):
                normalized_block = dict(block)
                include_match = normalized_block.get("include_match", "any")
                if include_match not in {"any", "all"}:
                    normalized_block["include_match"] = "any"
                normalized_filters[key] = normalized_block
        payload["filters"] = normalized_filters

    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            journeys = data.get("journeys", [])[:5] if isinstance(data, dict) else []
            compact_journeys = []

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

            return {
                "journeys": compact_journeys,
                "selected_priority": safe_priority,
                "num_journeys": len(compact_journeys),
                "raw_summary": data.get("summary") if isinstance(data, dict) else None,
            }
        return {"error": f"Routing failed: {response.status_code}"}
    except Exception as e:
        return {"error": f"Error connecting to Routing API: {e}"}
