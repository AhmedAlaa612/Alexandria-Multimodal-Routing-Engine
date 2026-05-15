from dataclasses import dataclass, field
from typing import Any


@dataclass
class TripState:
    origin: dict[str, Any] | None = None
    destination: dict[str, Any] | None = None
    mode_preference: dict[str, Any] | None = None
    last_route_snapshot: dict[str, Any] | None = None
    recent_locations: list[dict[str, Any]] = field(default_factory=list)
    last_intent: str | None = None

    def snapshot(self) -> dict:
        return {
            "origin": self.origin,
            "destination": self.destination,
            "mode_preference": self.mode_preference,
            "last_route_snapshot": self.last_route_snapshot,
            "recent_locations": list(self.recent_locations),
            "last_intent": self.last_intent,
        }

    def infer_intent(self, plan: list[dict]) -> str:
        tool_names = [step.get("tool") for step in plan if isinstance(step, dict)]
        if "get_routes" in tool_names:
            return "route"
        if "check_traffic" in tool_names:
            return "traffic"
        if "db_tools" in tool_names:
            return "nearby_trips"
        if "geocode_location" in tool_names:
            return "location_resolution"
        return "follow_up"

    def _location_key(self, location_payload: dict[str, Any]) -> tuple[Any, ...]:
        return (
            location_payload.get("role"),
            location_payload.get("source"),
            location_payload.get("place_name"),
            location_payload.get("lat"),
            location_payload.get("lon"),
        )

    def _trim_recent_locations(self) -> None:
        self.recent_locations = self.recent_locations[-8:]

    def record_location(self, location_payload: dict[str, Any]) -> None:
        if not isinstance(location_payload, dict):
            return

        if not any(self._location_key(entry) == self._location_key(location_payload) for entry in self.recent_locations):
            self.recent_locations.append(location_payload)
            self._trim_recent_locations()

    def set_origin(self, location_payload: dict[str, Any] | None) -> None:
        self.origin = location_payload
        if location_payload:
            self.record_location(location_payload)

    def set_destination(self, location_payload: dict[str, Any] | None) -> None:
        self.destination = location_payload
        if location_payload:
            self.record_location(location_payload)

    def set_mode_preference(self, preference_payload: dict[str, Any] | None) -> None:
        self.mode_preference = preference_payload

    def set_last_route_snapshot(self, snapshot_payload: dict[str, Any] | None) -> None:
        self.last_route_snapshot = snapshot_payload

    def _role_from_step(self, step_name: str | None, resolved_args: dict[str, Any]) -> str:
        tokens = " ".join(
            [
                str(step_name or ""),
                str(resolved_args.get("role") or ""),
                str(resolved_args.get("save_as") or ""),
            ]
        ).lower()

        if any(token in tokens for token in ("origin", "start", "from", "source", "pickup")):
            return "origin"
        if any(token in tokens for token in ("destination", "destination", "dest", "end", "to", "target", "dropoff")):
            return "destination"
        return "context"

    def update_from_result(self, step_name: str, tool_name: str, resolved_args: dict, result: dict) -> None:
        if tool_name == "geocode_location" and isinstance(result, dict):
            lat = result.get("lat")
            lon = result.get("lon")
            place_name = resolved_args.get("place_name")
            if lat is None or lon is None:
                return

            location_payload = {
                "role": self._role_from_step(step_name, resolved_args),
                "place_name": place_name,
                "formatted_address": result.get("formatted_address"),
                "lat": lat,
                "lon": lon,
                "source": "geocode",
                "confidence": 0.8,
            }
            self.record_location(location_payload)
            return

        if tool_name == "get_routes" and isinstance(result, dict):
            journeys = result.get("journeys", [])
            top_journey = journeys[0] if isinstance(journeys, list) and journeys else None
            self.set_last_route_snapshot(
                {
                    "selected_priority": result.get("selected_priority"),
                    "num_journeys": result.get("num_journeys"),
                    "top_journey": top_journey,
                }
            )