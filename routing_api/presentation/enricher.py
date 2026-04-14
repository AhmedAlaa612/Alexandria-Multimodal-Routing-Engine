"""
Enrich raw routing results into frontend-ready journey JSON.
"""

import ast
import math
import re

from routing_api.network.gtfs_lookups import GTFSLookups
from routing_api.presentation.polyline import encode_polyline
from routing_api.presentation.text_summary import build_text_summaries


def _ordered_unique(values):
    seen, out = set(), []
    for v in values:
        t = str(v).strip()
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _extract_mode_labels(route_short_en, route_short_ar):
    def norm(text):
        return " ".join(re.sub(r"\d+", "", str(text or "")).split()).strip()
    mode_en = norm(route_short_en).lower() or "unknown"
    mode_ar = norm(route_short_ar) or mode_en
    return mode_en, mode_ar


def _get_trip_street_lists(trip_id, lookups: GTFSLookups):
    en = [str(s).strip() for s in lookups.trip_to_main_streets.get(trip_id, []) if str(s).strip()]
    ar = [str(s).strip() for s in lookups.trip_to_main_streets_ar.get(trip_id, []) if str(s).strip()]
    if en and not ar:
        ar = list(en)
    if ar and not en:
        en = list(ar)
    return _ordered_unique(en), _ordered_unique(ar)


def _get_trip_shape_path(trip_id, from_stop_id, to_stop_id, lookups: GTFSLookups):
    """Shape sub-path between two stops for a trip."""
    shape_id = lookups.trip_to_shape.get(trip_id)
    pts = lookups.shape_points.get(shape_id) if shape_id else None
    if not pts:
        return []
    from_c = lookups.stop_to_coords.get(from_stop_id)
    to_c = lookups.stop_to_coords.get(to_stop_id)
    if not from_c or not to_c:
        return []

    def nearest(lat, lon):
        return min(range(len(pts)), key=lambda i: (pts[i][0] - lat) ** 2 + (pts[i][1] - lon) ** 2)

    s = nearest(from_c["stop_lat"], from_c["stop_lon"])
    e = nearest(to_c["stop_lat"], to_c["stop_lon"])
    if s > e:
        s, e = e, s
    return pts[s : e + 1]


def enrich_journey_results(routing_results, start_trips, target_trips,
                           lookups: GTFSLookups, pathway_metadata: dict,
                           top_k: int = 5):
    """
    Transform routing results into frontend-ready JSON.

    Builds legs, computes all distance metrics, text summaries, and labels.
    """
    journeys = []
    for trip_path, total_costs, cost_details in routing_results:
        transfers, total_fare, total_time, total_walk = total_costs
        legs = []
        modes_en, modes_ar = [], []
        streets_en, streets_ar = [], []
        walking_m = transit_m = 0.0

        start_data = start_trips[trip_path[0]]
        if start_data["walk"] > 0:
            walking_m += start_data["walk"]
            legs.append({
                "type": "walk",
                "distance_meters": round(start_data["walk"]),
                "duration_minutes": max(1, math.ceil(start_data["walk"] / 83.33)),
                "polyline": encode_polyline(start_data["path"]),
            })

        for detail in cost_details:
            if detail["type"] == "trip":
                route_id = lookups.trip_to_route.get(detail["trip_id"])
                route_short = lookups.route_to_short_name.get(route_id, "")
                route_short_ar = lookups.route_to_short_name_ar.get(route_id, route_short)
                mode_en, mode_ar = _extract_mode_labels(route_short, route_short_ar)
                if mode_en not in modes_en:
                    modes_en.append(mode_en)
                if mode_ar not in modes_ar:
                    modes_ar.append(mode_ar)

                trip_ids = _ordered_unique(
                    [detail["trip_id"]] + (detail.get("trip_ids") or [])
                )
                shape_path = _get_trip_shape_path(
                    detail["trip_id"], detail["from_stop_id"],
                    detail["to_stop_id"], lookups,
                )
                dist_m = detail.get("distance_km", 0.0) * 1000
                transit_m += dist_m

                for tid in trip_ids:
                    ten, tar = _get_trip_street_lists(tid, lookups)
                    for s in ten:
                        if s not in streets_en:
                            streets_en.append(s)
                    for s in tar:
                        if s not in streets_ar:
                            streets_ar.append(s)

                from_c = lookups.stop_to_coords.get(detail["from_stop_id"], {})
                to_c = lookups.stop_to_coords.get(detail["to_stop_id"], {})
                legs.append({
                    "type": "trip",
                    "trip_id": detail["trip_id"],
                    "trip_ids": trip_ids,
                    "mode_en": mode_en,
                    "mode_ar": mode_ar,
                    "route_short_name": route_short,
                    "route_short_name_ar": route_short_ar,
                    "headsign": lookups.trip_to_headsign.get(detail["trip_id"], "Unknown"),
                    "headsign_ar": lookups.trip_to_headsign_ar.get(
                        detail["trip_id"],
                        lookups.trip_to_headsign.get(detail["trip_id"], "Unknown"),
                    ),
                    "fare": round(detail["fare"], 2),
                    "distance_meters": int(round(dist_m)),
                    "duration_minutes": max(1, math.ceil(detail["time"] / 60)),
                    "from": {
                        "stop_id": detail["from_stop_id"],
                        "name": lookups.stop_to_name.get(detail["from_stop_id"], "Unknown Stop"),
                        "name_ar": lookups.stop_to_name_ar.get(
                            detail["from_stop_id"],
                            lookups.stop_to_name.get(detail["from_stop_id"], "Unknown Stop"),
                        ),
                        "coord": [from_c.get("stop_lat", 0), from_c.get("stop_lon", 0)],
                    },
                    "to": {
                        "stop_id": detail["to_stop_id"],
                        "name": lookups.stop_to_name.get(detail["to_stop_id"], "Unknown Stop"),
                        "name_ar": lookups.stop_to_name_ar.get(
                            detail["to_stop_id"],
                            lookups.stop_to_name.get(detail["to_stop_id"], "Unknown Stop"),
                        ),
                        "coord": [to_c.get("stop_lat", 0), to_c.get("stop_lon", 0)],
                    },
                    "polyline": encode_polyline(shape_path),
                })

            elif detail["type"] == "transfer":
                pw = detail.get("pathway", {})
                pw_meta = pathway_metadata.get(pw.get("pathway_id"), {})
                raw = pw_meta.get("walking_path_coords")
                try:
                    walk_coords = ast.literal_eval(raw) if isinstance(raw, str) else (raw or [])
                except (ValueError, SyntaxError, TypeError):
                    walk_coords = []
                from_tid = pw_meta.get("start_trip_id", detail.get("from_trip_id", ""))
                to_tid = pw_meta.get("end_trip_id", detail.get("to_trip_id", ""))
                from_name_en = lookups.trip_to_headsign.get(from_tid, "Unknown")
                from_name_ar = lookups.trip_to_headsign_ar.get(from_tid, from_name_en)
                to_name_en = lookups.trip_to_headsign.get(to_tid, "Unknown")
                to_name_ar = lookups.trip_to_headsign_ar.get(to_tid, to_name_en)
                walking_m += detail["walking_distance_m"]
                legs.append({
                    "type": "transfer",
                    "from_trip_id": detail["from_trip_id"],
                    "to_trip_id": detail["to_trip_id"],
                    "from_trip_name": from_name_en,
                    "from_trip_name_ar": from_name_ar,
                    "to_trip_name": to_name_en,
                    "to_trip_name_ar": to_name_ar,
                    "end_stop_id": pw_meta.get("end_stop_id", pw.get("end_stop_id", "")),
                    "walking_distance_meters": round(detail["walking_distance_m"]),
                    "duration_minutes": max(1, int(detail["walking_distance_m"] / 83.33)),
                    "polyline": encode_polyline(walk_coords),
                })

        final_walk = target_trips[trip_path[-1]]["walk"]
        if final_walk > 0:
            walking_m += final_walk
            legs.append({
                "type": "walk",
                "distance_meters": round(final_walk),
                "duration_minutes": max(1, math.ceil(final_walk / 83.33)),
                "polyline": encode_polyline(target_trips[trip_path[-1]]["path"]),
            })

        journeys.append({
            "summary": {
                "total_time_minutes": math.ceil(total_time / 60),
                "walking_distance_meters": int(round(walking_m)),
                "transit_distance_meters": int(round(transit_m)),
                "total_distance_meters": int(round(walking_m + transit_m)),
                "transfers": transfers,
                "cost": round(total_fare, 2),
                "modes_en": _ordered_unique(modes_en),
                "modes_ar": _ordered_unique(modes_ar),
                "main_streets_en": _ordered_unique(streets_en),
                "main_streets_ar": _ordered_unique(streets_ar),
            },
            "legs": legs,
        })

    # Text summaries
    for idx, journey in enumerate(journeys):
        build_text_summaries(journey, lookups)
        journey["id"] = idx + 1

    return {
        "geometry_encoding": "polyline5",
        "num_journeys": len(journeys),
        "journeys": journeys[:top_k],
    }
