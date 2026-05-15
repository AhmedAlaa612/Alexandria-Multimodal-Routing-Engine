import requests


TOOL_SCHEMA = {
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
}


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
