import requests

from .constants import ALLOWED_STREET_GROUPS, STREET_GROUP_LOOKUP


TOOL_SCHEMA = {
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


def execute_traffic(street_name):
    """Call the Real Traffic API"""
    if not isinstance(street_name, str) or not street_name.strip():
        return {"error": "street_name is required. Allowed values: Abou Qir, Coastal, Mahmoudia, Moustafa Kamel"}

    normalized = STREET_GROUP_LOOKUP.get(street_name.strip().lower())
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
