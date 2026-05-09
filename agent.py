import json
import os

from llm_client import GeminiClient
from memory.buffer import ConversationBuffer
from memory.tool_log import ToolLog
from memory.trip_state import TripState
from tools import (
    AVAILABLE_TOOLS_SCHEMA,
    execute_db_tools,
    execute_geocode,
    execute_route,
    execute_traffic,
)


class AlOstaAgent:
    """Planner-Executor-Synthesizer agent for Alexandria routing."""

    def __init__(self, api_key, planner_model=None, synthesizer_model=None):
        self.planner_llm = GeminiClient(
            api_key,
            model_name=planner_model or os.getenv("PLANNER_MODEL", "gemini-2.5-flash"),
        )
        self.synthesizer_slm = GeminiClient(
            api_key,
            model_name=synthesizer_model or os.getenv("SLM_MODEL", "gemini-2.5-flash-lite"),
        )
        self.memory = ConversationBuffer(max_turns=4)
        self.tool_log = ToolLog(max_tool_calls=8)
        self.trip_state = TripState()
        self._last_tool_output = None

        self.planner_prompt = f"""
You are the Planner for an Alexandria multimodal routing assistant.
Your only job is to analyze the user request and output a JSON array of tool calls.
Do not write explanations or prose. Output valid JSON only.
    Use medium reasoning depth internally, but do not reveal reasoning.

Available tools:
{json.dumps(AVAILABLE_TOOLS_SCHEMA, ensure_ascii=False, indent=2)}

Rules:
1. Use only these tools: geocode_location, get_routes, db_tools, check_traffic.
2. If the user asks for a route between named places, plan geocode_location for the origin and destination first, then get_routes.
    If the user provides explicit coordinates, use them directly as the route origin and do not geocode them.
3. For dependent calls, use save_as on the geocode steps and reference results with placeholders like "$origin.lat" and "$origin.lon".
4. For geocoded route endpoints, use save_as values that match the route role: "origin" and "destination".
5. For get_routes, always include start_lat, start_lon, end_lat, end_lon, max_transfers, walking_cutoff, priority, and top_k.
6. Keep top_k equal to 5.
7. If the user asks about nearby trips around a place name, use geocode_location then db_tools.
    db_tools is only for nearby-trip lookup around a coordinate. It does not replace get_routes.
    If the user asks to go "على البحر" or to the Corniche/coastal edge, geocode a concrete Corniche anchor such as "Corniche Alexandria" instead of the literal corridor label.
    If the user message includes coordinates, pass them to geocode_location as user_lat and user_lng so the geocoder can choose the nearest coastal point.
    If that geocode fails, retry once with bias=false and a broader Corniche query before giving up.
8. When adding get_routes.filters.modes.include or get_routes.filters.modes.exclude, use GTFS agency IDs instead of descriptive mode names.
    For example, write P_O_14 rather than "microbus" when you mean the orange 14-seater microbus agency.
    Use the exact agency_id values are P_B_8 for tomnaya or suzuki , P_O_14 for microbus, Minibus for minibus, and Bus for bus.
    People in Alexandria often say "مشروع" or "مشاريع" instead of "microbus".
    People may also say "توناية" or "سوزوكي" to mean a tomnaya.
9. If the user wants to go to a specific landmark or named destination such as a mall, hospital, school, police station, university, mosque, church, club, station, terminal, or any other clear landmark, set walking_cutoff to 2500 before the route request.
10. If the user names a neighborhood or area in Alexandria such as جناكليس, كليوباترا, or any similar area name, keep walking_cutoff as the default value and do not increase it just because the place name is known.
11. If the user mentions زحمة, traffic, crowded, fastest, أسرع, عاوز أوصل بسرعة, or any similar congestion/urgency wording, call check_traffic first before any route call.
12. If the user asks about traffic on a corridor, use check_traffic with one of: Abou Qir, Coastal, Mahmoudia, Moustafa Kamel.
13. If the user mentions one of the corridor names directly, treat it as street context even if they do not say "شارع" or "طريق".
14. After checking traffic, if a route is still needed, use get_routes and set filters.main_streets.include to the checked corridor when possible so the route prefers that street context.
15. If traffic is heavy, avoid that corridor in the route call when a better alternative exists.
16. These corridor groups are long city axes across Alexandria, so choose the nearest relevant point or segment on that corridor to the user location when resolving traffic, routing, or nearby context.
17. If the user asks to compare two corridors, asks which corridor is better, or uses "ولا" between corridor names, do not answer with one corridor only.
18. In comparison requests, create separate get_routes calls for each corridor using the same origin and destination but different filters.main_streets.include values when possible.
19. Alexandria is a long coastal city, so many trips run east-west along the main corridors and central areas can be busy.
20. Abou Qir is the eastern corridor toward Abu Qir and East Alexandria.
21. Coastal is the Corniche and sea-front corridor along the Mediterranean coast.
22. Mahmoudia follows the Mahmoudia Canal corridor and is often a practical alternative axis.
23. Moustafa Kamel is a major central-east corridor that helps movement inside East Alexandria and toward Smouha.
24. If nothing needs a tool, return []

Example:
User: "عايز اروح من محطة مصر لميامي"
Output:
[
    {{"tool": "geocode_location", "save_as": "origin", "args": {{"place_name": "محطة مصر"}}}},
    {{"tool": "geocode_location", "save_as": "destination", "args": {{"place_name": "ميامي"}}}},
    {{"tool": "get_routes", "args": {{"start_lat": "$origin.lat", "start_lon": "$origin.lon", "end_lat": "$destination.lat", "end_lon": "$destination.lon", "max_transfers": 2, "walking_cutoff": 1500, "priority": "balanced", "top_k": 5}}}}
]
"""

        self.synthesizer_prompt = """
You are Al-Osta, a friendly Alexandria transit assistant.
You will receive the original user request and raw tool results from the backend.
Write the final answer in Egyptian Arabic only.
    Use medium reasoning depth internally, but do not reveal reasoning.
    First, internally reason over the user request, the prompt, and the tool results, then give only the final answer.
    If the raw tool output contains trips, list every trip exactly as returned and in the same order.
    Preserve time, cost, walking distance and route summary exactly as given by the tool.
    If a value is missing from the tool output, say it is not mentioned instead of estimating it.

Alexandria street context:

Alexandria is a linear coastal city stretching west to east along the Mediterranean. Most trips happen along this axis, especially between eastern districts and the central area.

City zones:
- West (Agamy, Dekheila): lower density, longer distances, fewer transit options.
- Central (Mansheya, Mahatet Misr, Moharam Bek, Smouha): very busy, with major hubs.
- East (Sidi Gaber → Montaza): high density and strong dependence on the main corridors.

Key corridors:
- Corniche (Coastal Road): often the fastest in theory, but frequently congested.
- Abou Qir Street: a backbone corridor, but sometimes very crowded.
- Mahmoudia Axis: a useful less-crowded alternative to Corniche and Abou Qir.
- Moustafa Kamel: important for movement inside East Alexandria and access to Smouha.

Important areas:
- Mansheya: old area, narrow streets, slower movement.
- Mahatet Misr: major station and transit hub.
- Raml Station: central interchange point.
- Sidi Gaber: important transit node.
- Smouha: organized and easier to move through.
- Stanley / San Stefano: busy coastal areas.
- Montaza: eastern end of many lines.
- Al Mawqaf El Gedid: major transit hub.

Routing heuristics:
- Alexandria is linear, so most trips are east ↔ central.
- If there is traffic, avoid Corniche and Abou Qir when possible.
- Prefer Mahmoudia as an alternative when it fits the trip.
- Old areas like Mansheya are slower and may require more walking.
- Smouha and newer areas are easier to plan around.
- If the user is comparing corridors, return route candidates for each corridor and let the final answer rank them using time, cost, total distance, transfers, and walking.

Local transit language:
- People in Alexandria often say "مشروع" or "مشاريع" instead of "microbus".
- People may also say "توناية" or "سوزوكي" to mean a tomnaya.
- The user may mention corridor names directly, without saying "شارع" or "طريق".
- The important corridor groups are Abou Qir, Coastal, Mahmoudia, and Moustafa Kamel.
- These are long corridors across Alexandria, so if the user asks about one of them, you may need to choose the nearest relevant point or segment to the user's location.
- Use this city context to explain why a corridor is chosen and whether it is a good or bad option for the requested trip.

Rules:
1. Be helpful and concise.
2. Use the tool results exactly as they are, do not invent missing route or traffic details.
3. If the raw tool output includes a journeys list, show every journey in the same order and do not collapse them into one answer.
4. For each journey, mention at least:
   - route number
   - Arabic route summary if present
   - total time in minutes
   - cost
   - total distance in kilometers
   - walking distance if present
   - transfers if present
   - main streets or modes if present
5. When presenting journeys to the user, use a fixed format with clear alignment and one section per journey.
    Use this shape:
    رحلة 1:
      امشي لغايه ... وتركب ... لغايه ... وتمشي لغايه وجهتك
      الوقت: 31 دقيقة | التكلفة: 11 جنيه | مشي: 584 متر | وسيلة: اتوبيس
    Keep the text natural, preserve the tool meaning exactly, and align the labels the same way for every journey.
    If a field is missing, write "غير مذكور" instead of inventing it.
6. If the raw tool output includes route details, list each route separately and keep the numbers clear.
7. If the raw tool output includes nearby trips, show all returned trips clearly, one by one.
8. If there is an error or empty result, apologize briefly and explain what is missing.
9. If route summaries are present, present them clearly and naturally.
10. If raw tool output contains both journey_summaries and structured journeys, prefer the structured journeys for time, cost, and distance, but still show the journey_summaries without changing their meaning.
11. If the raw tool output includes multiple route candidates from different corridor filters, present them all separately first; only recommend one if the tool output itself makes the ranking clear or the user explicitly asks.
12. Do not collapse multiple route results into one summary; show each candidate separately before any recommendation.
13. if the planner returned [], try to answer the user question from your context.
"""

    def process_query(self, user_query):
        """Plan with an LLM, execute in Python, then synthesize with a smaller model."""

        self.memory.add_user_message(user_query)

        plan_context = self._build_planner_context(user_query)
        print("\n[Planner] starting")
        plan_response = self.planner_llm.generate(plan_context)
        print(f"[Planner] response: {plan_response}")
        if not plan_response:
            return "عذرا، في مشكلة في الاتصال حاليا."

        plan = self._parse_plan(plan_response)

        print(f"[Executor] running {len(plan)} step(s)")
        self.trip_state.last_intent = self.trip_state.infer_intent(plan)
        tool_results = self._execute_plan(plan)
        if tool_results:
            self._last_tool_output = tool_results

        self._commit_trip_state(user_query, plan, tool_results)

        synth_context = self._build_synth_context(user_query, tool_results)
        print("[Synthesizer] starting")
        final_answer = self.synthesizer_slm.generate(synth_context)
        print(f"[Synthesizer] response: {final_answer}")
        if not final_answer:
            return "عذرا، حصلت مشكلة في توليد الرد."

        self.memory.add_assistant_message(final_answer)
        return final_answer

    def _build_planner_context(self, user_query):
        planner_state = {
            "trip_state": self.trip_state.snapshot(),
            "recent_tool_cache": self._last_tool_output or [],
        }
        return (
            f"{self.planner_prompt}\n\n"
            f"Current Short-Term State:\n{json.dumps(planner_state, ensure_ascii=False, indent=2)}\n\n"
            f"User Request: {user_query}\n"
            "Output:"
        )

    def _build_synth_context(self, user_query, tool_results):
        effective_tool_output = tool_results if tool_results else (self._last_tool_output or [])
        synth_state = {
            "trip_state": self.trip_state.snapshot(),
            "recent_conversation": self.memory.get_history(),
            "recent_tool_log": self.tool_log.get_recent_tool_calls(),
            "tool_output": effective_tool_output,
        }

        return (
            f"{self.synthesizer_prompt}\n\n"
            f"Current Short-Term State:\n{json.dumps(synth_state['trip_state'], ensure_ascii=False, indent=2)}\n\n"
            f"Recent Conversation:\n{json.dumps(synth_state['recent_conversation'], ensure_ascii=False, indent=2)}\n\n"
            f"Recent Tool Log:\n{json.dumps(synth_state['recent_tool_log'], ensure_ascii=False, indent=2)}\n\n"
            f"Raw Tool Output:\n{json.dumps(synth_state['tool_output'], ensure_ascii=False, indent=2)}\n\n"
            f"User Request: {user_query}\n\n"
            "اكتب الرد النهائي:"
        )

    def _parse_plan(self, plan_response):
        clean_plan = plan_response.replace("```json", "").replace("```", "").strip()
        start_index = clean_plan.find("[")
        end_index = clean_plan.rfind("]")
        if start_index != -1 and end_index != -1 and end_index >= start_index:
            clean_plan = clean_plan[start_index : end_index + 1]

        try:
            parsed = json.loads(clean_plan)
        except json.JSONDecodeError:
            return []

        return parsed if isinstance(parsed, list) else []

    def _execute_plan(self, plan):
        results = []
        memory = {}

        for index, step in enumerate(plan, start=1):
            if not isinstance(step, dict):
                results.append({"step": index, "error": "Invalid plan step format"})
                continue

            tool_name = step.get("tool")
            args = step.get("args", {})
            step_name = step.get("save_as") or step.get("id") or f"step_{index}"

            if not isinstance(tool_name, str) or not isinstance(args, dict):
                results.append({"step": step_name, "error": "Missing tool or args"})
                continue

            try:
                resolved_args = self._resolve_value(args, memory)
                print(f"[Executor] step {index} ({step_name}) calling {tool_name} with {json.dumps(resolved_args, ensure_ascii=False)}")
                result = self._execute_tool(tool_name, resolved_args)
                print(f"[Executor] step {index} result: {result}")
                results.append({
                    "step": step_name,
                    "tool": tool_name,
                    "raw_args": args,
                    "resolved_args": resolved_args,
                    "result": result,
                })
                memory[step_name] = result
                self.tool_log.log_tool_call(self.memory.current_turn, tool_name, resolved_args, result)
            except Exception as exc:
                error_result = {"error": str(exc)}
                results.append({
                    "step": step_name,
                    "tool": tool_name,
                    "raw_args": args,
                    "resolved_args": args,
                    "result": error_result,
                })
                memory[step_name] = error_result
                self.tool_log.log_tool_call(self.memory.current_turn, tool_name, args, error_result)
                print(f"[Executor] step {index} ({step_name}) failed: {exc}")

        return results

    def _commit_trip_state(self, user_query, plan, tool_results):
        results_by_step = {
            item.get("step"): item
            for item in tool_results
            if isinstance(item, dict) and isinstance(item.get("step"), str)
        }

        location_by_step = {}
        for step in plan:
            if not isinstance(step, dict):
                continue

            tool_name = step.get("tool")
            step_name = step.get("save_as") or step.get("id") or ""
            if tool_name != "geocode_location" or not step_name:
                continue

            execution = results_by_step.get(step_name)
            if not execution:
                continue

            result = execution.get("result")
            resolved_args = execution.get("resolved_args") or step.get("args", {})
            if not isinstance(result, dict) or result.get("error"):
                continue

            lat = result.get("lat")
            lon = result.get("lon")
            if lat is None or lon is None:
                continue

            location = {
                "role": self._role_from_step_name(step_name, resolved_args),
                "place_name": resolved_args.get("place_name"),
                "formatted_address": result.get("formatted_address"),
                "lat": lat,
                "lon": lon,
                "source": "geocode",
                "confidence": 0.8,
            }
            location_by_step[step_name] = location
            self.trip_state.record_location(location)

            if location["role"] == "origin":
                self.trip_state.set_origin(location)
            elif location["role"] == "destination":
                self.trip_state.set_destination(location)

        route_execution = next((item for item in tool_results if isinstance(item, dict) and item.get("tool") == "get_routes"), None)
        route_step = next((step for step in plan if isinstance(step, dict) and step.get("tool") == "get_routes"), None)
        if route_execution and route_step:
            route_result = route_execution.get("result")
            route_args = route_execution.get("raw_args") if isinstance(route_execution.get("raw_args"), dict) else route_step.get("args", {})
            if isinstance(route_result, dict):
                route_snapshot = self._build_route_snapshot(route_args, route_result, location_by_step)
                self.trip_state.set_last_route_snapshot(route_snapshot)

                origin_location = self._resolve_route_endpoint(route_args, "start", location_by_step)
                destination_location = self._resolve_route_endpoint(route_args, "end", location_by_step)

                if origin_location:
                    self.trip_state.set_origin(origin_location)
                if destination_location:
                    self.trip_state.set_destination(destination_location)

                mode_preference = self._extract_mode_preference(route_args, user_query)
                if mode_preference:
                    self.trip_state.set_mode_preference(mode_preference)

        for location in location_by_step.values():
            self.trip_state.record_location(location)

    def _role_from_step_name(self, step_name, resolved_args):
        tokens = " ".join(
            [
                str(step_name or ""),
                str((resolved_args or {}).get("role") or ""),
                str((resolved_args or {}).get("save_as") or ""),
            ]
        ).lower()

        if any(token in tokens for token in ("origin", "start", "from", "source", "pickup")):
            return "origin"
        if any(token in tokens for token in ("destination", "dest", "end", "to", "target", "dropoff")):
            return "destination"
        return "context"

    def _build_route_snapshot(self, route_args, route_result, location_by_step):
        return {
            "selected_priority": route_result.get("selected_priority"),
            "num_journeys": route_result.get("num_journeys"),
            "top_journey": route_result.get("journeys", [None])[0] if route_result.get("journeys") else None,
            "origin_coords": self._resolve_route_coords(route_args, "start", location_by_step),
            "destination_coords": self._resolve_route_coords(route_args, "end", location_by_step),
            "mode_filter": self._extract_mode_filter(route_args),
        }

    def _extract_mode_filter(self, route_args):
        filters = route_args.get("filters") if isinstance(route_args.get("filters"), dict) else {}
        modes = filters.get("modes") if isinstance(filters.get("modes"), dict) else {}
        if not modes:
            return None

        return {
            "include": list(modes.get("include") or []),
            "exclude": list(modes.get("exclude") or []),
            "include_match": modes.get("include_match", "any"),
        }

    def _extract_mode_preference(self, route_args, user_query):
        mode_filter = self._extract_mode_filter(route_args)
        if mode_filter:
            return {
                **mode_filter,
                "source": "planner",
                "confidence": 1.0,
            }

        normalized_query = (user_query or "").lower()
        if any(token in normalized_query for token in ("مشروع", "مشاريع", "microbus", "مينيباص", "minibus")):
            return {
                "include": ["P_O_14", "Minibus"],
                "exclude": [],
                "include_match": "any",
                "source": "user_query",
                "confidence": 0.7,
            }

        return None

    def _resolve_route_coords(self, route_args, prefix, location_by_step):
        lat_key = f"{prefix}_lat"
        lon_key = f"{prefix}_lon"
        raw_lat = route_args.get(lat_key)
        raw_lon = route_args.get(lon_key)

        location = self._resolve_route_endpoint(route_args, prefix, location_by_step)
        if location:
            return {
                "lat": location.get("lat"),
                "lon": location.get("lon"),
                "source": location.get("source"),
                "confidence": location.get("confidence"),
            }

        if isinstance(raw_lat, (int, float)) and isinstance(raw_lon, (int, float)):
            return {
                "lat": raw_lat,
                "lon": raw_lon,
                "source": "user_coordinates",
                "confidence": 1.0,
            }

        return None

    def _resolve_route_endpoint(self, route_args, prefix, location_by_step):
        lat_key = f"{prefix}_lat"
        lon_key = f"{prefix}_lon"
        raw_lat = route_args.get(lat_key)
        raw_lon = route_args.get(lon_key)

        if isinstance(raw_lat, str) and raw_lat.startswith("$"):
            reference = raw_lat[1:].split(".", 1)[0]
            location = location_by_step.get(reference)
            if location:
                return location

        if isinstance(raw_lon, str) and raw_lon.startswith("$"):
            reference = raw_lon[1:].split(".", 1)[0]
            location = location_by_step.get(reference)
            if location:
                return location

        if isinstance(raw_lat, (int, float)) and isinstance(raw_lon, (int, float)):
            return {
                "role": prefix,
                "place_name": "current location" if prefix == "start" else None,
                "lat": raw_lat,
                "lon": raw_lon,
                "source": "user_coordinates",
                "confidence": 1.0,
            }

        return None

    def _resolve_value(self, value, memory):
        if isinstance(value, str) and value.startswith("$"):
            reference = value[1:]
            step_name, dot, field_name = reference.partition(".")
            source = memory.get(step_name)
            if not dot:
                return source
            if isinstance(source, dict):
                return source.get(field_name)
            return None

        if isinstance(value, list):
            return [self._resolve_value(item, memory) for item in value]

        if isinstance(value, dict):
            return {key: self._resolve_value(item, memory) for key, item in value.items()}

        return value

    def _execute_tool(self, tool_name, args):
        if tool_name == "geocode_location":
            return execute_geocode(args.get("place_name"))

        if tool_name == "get_routes":
            return execute_route(
                args.get("start_lat"),
                args.get("start_lon"),
                args.get("end_lat"),
                args.get("end_lon"),
                args.get("max_transfers", 2),
                args.get("walking_cutoff", 1500),
                args.get("priority", "balanced"),
                args.get("top_k", 5),
                args.get("weights"),
                args.get("filters"),
            )

        if tool_name == "db_tools":
            return execute_db_tools(
                args.get("lat"),
                args.get("lon"),
                args.get("radius_m", 1000),
                args.get("starts", False),
            )

        if tool_name == "check_traffic":
            return execute_traffic(args.get("street_name"))

        return {"error": f"Tool {tool_name} does not exist"}
