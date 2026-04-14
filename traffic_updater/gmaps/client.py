"""
Google Maps directions client — adapted from gmaps_directions.py.

Wraps the existing ``get_directions`` function for use by the updater service.
"""

import re
import urllib.parse
import urllib.request

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.google.com/maps/",
    "Accept": "*/*",
}


def _build_pb(stops: list[tuple[float, float]]) -> str:
    stops_pb = "".join(
        f"!1m4!3m2!3d{lat}!4d{lng}!6e2" for lat, lng in stops
    )
    center_lat = sum(s[0] for s in stops) / len(stops)
    center_lng = sum(s[1] for s in stops) / len(stops)
    multi = len(stops) > 2

    return (
        f"{stops_pb}"
        f"!3m8!1m3!1d27295.9!2d{center_lng}!3d{center_lat}"
        f"!3m2!1i1024!2i768!4f13.1!4i1"
        f"!6m52!1m5!18b1!30b1!31m1!1b1!34e1"
        f"!2m4!5m1!6e2!20e3!39b1"
        f"!6m23!49b1!63m0!66b1!74i150000!85b1!91b1"
        f"!114b1!149b1!206b1!209b1!212b1!223b1!232b1"
        f"!234b1!235b1!244b1!246b1!250b1!253b1!258b1"
        f"!260b1!266b1!268b1"
        f"!10b1!12b1!13b1!14b1!16b1"
        f"!17m1!3e1"
        f"!20m5!{'1e0' if multi else '1e6'}!2e{'3' if multi else '1'}!5e2!6b1!14b1"
        f"!46m1!1b0!96b1!99b1"
    )


def _fetch_raw(stops: list[tuple[float, float]], language: str, country: str) -> str:
    pb = _build_pb(stops)
    url = (
        "https://www.google.com/maps/preview/directions"
        f"?authuser=0&hl={language}&gl={country}"
        f"&pb={urllib.parse.quote(pb)}"
    )
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req) as resp:
        return resp.read().decode("utf-8")


def _parse(raw: str, num_stops: int) -> dict:
    num_legs = num_stops - 1

    route_pat = re.compile(r'\[0,"([^"]*)",\[(\d+),"([^"]+)",0\],\[(\d+),"([^"]+)"')
    leg_pat = re.compile(r'\[null,null,\[(\d+),"([^"]+)",0\],\[(\d+),"([^"]+)"')

    routes, seen_dist = [], set()
    for m in route_pat.finditer(raw):
        label, dist_m, dist_text, dur_s, dur_text = m.groups()
        label = label.strip()
        dist_m = int(dist_m)
        if "\\u003c" in label or "maneuver" in label:
            continue
        if label and dist_m not in seen_dist:
            seen_dist.add(dist_m)
            routes.append({
                "label": label,
                "distance_m": dist_m,
                "distance_text": dist_text.strip(),
                "duration_seconds": int(dur_s),
                "duration_text": dur_text.strip(),
            })

    if num_legs == 1:
        legs = [{
            "distance_m": routes[0]["distance_m"],
            "distance_text": routes[0]["distance_text"],
            "duration_seconds": routes[0]["duration_seconds"],
            "duration_text": routes[0]["duration_text"],
        }] if routes else []
    else:
        legs, seen_legs = [], set()
        for m in leg_pat.finditer(raw):
            dist_m, dist_text, dur_s, dur_text = m.groups()
            dist_m, dur_s = int(dist_m), int(dur_s)
            if dist_m < 50:
                continue
            key = (dist_m, dur_s)
            if key not in seen_legs:
                seen_legs.add(key)
                legs.append({
                    "distance_m": dist_m,
                    "distance_text": dist_text.strip(),
                    "duration_seconds": dur_s,
                    "duration_text": dur_text.strip(),
                })
            if len(legs) == num_legs:
                break

    total_dist = sum(leg["distance_m"] for leg in legs)
    total_time = sum(leg["duration_seconds"] for leg in legs)

    return {
        "routes": routes,
        "legs": legs,
        "total_distance_km": round(total_dist / 1000, 1),
        "total_duration_min": round(total_time / 60, 1),
    }


def get_directions(
    stops: list[tuple[float, float]],
    language: str = "en",
    country: str = "eg",
) -> dict:
    """
    Get traffic-aware driving directions between 2+ stops.

    Returns dict with routes, legs, total_distance_km, total_duration_min.
    """
    if len(stops) < 2:
        raise ValueError("Need at least 2 stops")
    raw = _fetch_raw(stops, language, country)
    return _parse(raw, num_stops=len(stops))
