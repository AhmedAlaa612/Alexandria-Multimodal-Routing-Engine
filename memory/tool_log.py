from typing import Any, Optional

from .models import ToolCall


class ToolLog:
    def __init__(self, max_tool_calls: int = 20):
        self.tool_call_log: list[ToolCall] = []
        self.max_tool_calls = max_tool_calls

    def _compact_route_summary(self, summary: dict[str, Any] | None) -> dict[str, Any] | None:
        if not isinstance(summary, dict):
            return None

        compact_summary = {
            "total_time_minutes": summary.get("total_time_minutes"),
            "walking_distance_meters": summary.get("walking_distance_meters"),
            "transit_distance_meters": summary.get("transit_distance_meters"),
            "total_distance_meters": summary.get("total_distance_meters"),
            "transfers": summary.get("transfers"),
            "cost": summary.get("cost"),
            "modes_ar": summary.get("modes_ar", []),
            "main_streets_ar": summary.get("main_streets_ar", []),
        }
        return compact_summary

    def _summarize_result(self, tool_name: str, result: Any):
        if not isinstance(result, dict):
            return result

        if "error" in result:
            return {"error": result.get("error")}

        if tool_name == "geocode_location":
            return {
                "lat": result.get("lat"),
                "lon": result.get("lon"),
                "formatted_address": result.get("formatted_address"),
            }

        if tool_name == "check_traffic":
            return {"overall_status": result.get("overall_status")}

        if tool_name == "db_tools":
            trips = result.get("trips", [])
            top_routes = []
            if isinstance(trips, list):
                for trip in trips[:3]:
                    if isinstance(trip, dict):
                        top_routes.append(
                            trip.get("route_name_ar")
                            or trip.get("route_name")
                            or trip.get("route_short_name_ar")
                            or trip.get("route_short_name")
                            or trip.get("trip_id")
                        )
            return {
                "count": len(trips) if isinstance(trips, list) else 0,
                "top_routes": [route for route in top_routes if route],
            }

        if tool_name == "get_routes":
            journeys = result.get("journeys", [])
            top_journey = journeys[0] if isinstance(journeys, list) and journeys else None
            top_summary = None
            if isinstance(top_journey, dict):
                top_summary = {
                    "route_number": top_journey.get("route_number"),
                    "text_summary": top_journey.get("text_summary"),
                    "summary": self._compact_route_summary(top_journey.get("summary")),
                }
            return {
                "selected_priority": result.get("selected_priority"),
                "num_journeys": result.get("num_journeys"),
                "top_journey": top_summary,
            }

        compact_result = {}
        for key, value in result.items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                compact_result[key] = value
            elif isinstance(value, list):
                compact_result[key] = value[:3]
            elif isinstance(value, dict):
                compact_result[key] = {
                    nested_key: nested_value
                    for nested_key, nested_value in value.items()
                    if isinstance(nested_value, (str, int, float, bool)) or nested_value is None
                }
        return compact_result or {"result_type": type(result).__name__}

    def log_tool_call(self, turn: Optional[int], tool_name: str, params: dict, result: Any):
        call = ToolCall(
            tool_name=tool_name,
            params=params,
            result=self._summarize_result(tool_name, result),
            turn=turn,
        )
        self.tool_call_log.append(call)
        if len(self.tool_call_log) > self.max_tool_calls:
            self.tool_call_log = self.tool_call_log[-self.max_tool_calls:]

    def get_recent_tool_calls(self) -> list[dict]:
        return [
            {
                "tool": t.tool_name,
                "params": t.params,
                "result": t.result,
                "turn": t.turn,
            }
            for t in self.tool_call_log
        ]

    def was_tool_called_with(self, tool_name: str, params: dict) -> Optional[dict]:
        for call in reversed(self.tool_call_log):
            if call.tool_name == tool_name and call.params == params:
                return call.result
        return None