"""
Forward geocoding: address -> list of (lat, lon, formatted_address).

Ported from geocoding-main/lib/nodejs-geocoding/src/index.ts encode()
and geocoding-main/src/geocode.ts geocodeWithBias().
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Optional

from geocoding_api.geocoder.utils import (
    ALEXANDRIA_BOUNDS,
    decode_html_entities,
    is_in_alexandria,
)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}

# The protobuf parameter blob for Google Maps search.
# Default center is Alexandria; user coords can override.
_DEFAULT_PB = (
    "!2i4!4m12!1m3!1d47768.67838190306!2d29.902868658279324!3d31.21938689710795"
    "!2m3!1f0!2f0!3f0!3m2!1i1707!2i336!4f13.1!7i20!10b1!12m25!1m5!18b1!30b1"
    "!31m1!1b1!34e1!2m4!5m1!6e2!20e3!39b1!10b1!12b1!13b1!16b1!17m1!3e1"
    "!20m3!5e2!6b1!14b1!46m1!1b0!96b1!99b1!19m4!2m3!1i360!2i120!4i8"
    "!20m57!2m2!1i203!2i100!3m2!2i4!5b1!6m6!1m2!1i86!2i86!1m2!1i408!2i240"
    "!7m33!1m3!1e1!2b0!3e3!1m3!1e2!2b1!3e2!1m3!1e2!2b0!3e3!1m3!1e8!2b0!3e3"
    "!1m3!1e10!2b0!3e3!1m3!1e10!2b1!3e2!1m3!1e10!2b0!3e4!1m3!1e9!2b1!3e2!2b1"
    "!9b0!15m8!1m7!1m2!1m1!1e2!2m2!1i195!2i195!3i20!22m3"
    "!1skeK5aaa6MMmqkdUP1ueEgA8!7e81!17skeK5aaa6MMmqkdUP1ueEgA8:540"
    "!23m2!4b1!10b1!24m109!1m27!13m9!2b1!3b1!4b1!6i1!8b1!9b1!14b1!20b1!25b1"
    "!18m16!3b1!4b1!5b1!6b1!9b1!13b1!14b1!17b1!20b1!21b1!22b1!32b1!33m1!1b1!34b1"
    "!36e2!10m1!8e3!11m1!3e1!17b1!20m2!1e3!1e6!24b1!25b1!26b1!27b1!29b1!30m1!2b1"
    "!36b1!37b1!39m3!2m2!2i1!3i1!43b1!52b1!54m1!1b1!55b1!56m1!1b1!61m2!1m1!1e1"
    "!65m5!3m4!1m3!1m2!1i224!2i298!72m22!1m8!2b1!5b1!7b1!12m4!1b1!2b1!4m1!1e1"
    "!4b1!8m10!1m6!4m1!1e1!4m1!1e3!4m1!1e4"
    "!3sother_user_google_review_posts__and__hotel_and_vr_partner_review_posts!6m1!1e1"
    "!9b1!89b1!90m2!1m1!1e2!98m3!1b1!2b1!3b1!103b1!113b1!114m3!1b1!2m1!1b1!117b1"
    "!122m1!1b1!126b1!127b1!128m1!1b0!26m4!2m3!1i80!2i92!4i8!34m19!2b1!3b1!4b1"
    "!6b1!8m6!1b1!3b1!4b1!5b1!6b1!7b1!9b1!12b1!14b1!20b1!23b1!25b1!26b1!31b1"
    "!37m1!1e81!47m0!49m10!3b1!6m2!1b1!2b1!7m2!1e3!2b1!8b1!9b1!10e2!61b1"
    "!67m5!7b1!10b1!14b1!15m1!1b0!69i771!77b1"
)


def _try_parse_json(text: str):
    """Try to parse a JSON string, return None on failure."""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None


def _build_url(query: str, language: str, pb: str) -> str:
    return (
        f"https://www.google.com/s?gs_ri=maps&authuser=0"
        f"&hl={language}&pb={urllib.parse.quote(pb)}"
        f"&q={urllib.parse.quote(query)}"
    )


def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.read().decode("utf-8")


def _parse_results(raw: str) -> list[dict]:
    """
    Parse the multi-line JSON response from Google Maps search.
    Extracts (lat, lon, formatted_address) for each result.
    """
    lines = [_try_parse_json(line.strip()) for line in raw.split("\n")]
    parsed = [j for j in lines if j is not None]

    if not parsed:
        return []

    first = parsed[0]
    if not isinstance(first, list):
        return []
    if len(first) < 1 or not isinstance(first[0], list):
        return []
    if len(first[0]) < 2 or not isinstance(first[0][1], list):
        return []

    items = first[0][1]
    results = []
    for item in items:
        try:
            detailed = item[22]
            if not detailed:
                continue
            if not detailed[0] or not detailed[0][0]:
                continue
            if not detailed[11] or not detailed[11][2] or not detailed[11][3]:
                continue

            lat = float(str(detailed[11][2]).strip())
            lon = float(str(detailed[11][3]).strip())
            address = decode_html_entities(str(detailed[0][0]).strip())

            results.append({
                "latitude": lat,
                "longitude": lon,
                "formatted_address": address,
            })
        except (IndexError, TypeError, ValueError):
            continue

    return results


def geocode(
    address: str,
    language: str = "en",
    bias: bool = True,
    user_lat: Optional[float] = None,
    user_lng: Optional[float] = None,
) -> list[dict]:
    """
    Forward geocode an address string using Google Maps scraping.

    Parameters
    ----------
    address : str
    language : str
    bias : bool
        If True, append "Alexandria, Egypt" hint and filter to bounding box.
    user_lat, user_lng : float, optional
        If provided, re-center the Google Maps search around these coords.

    Returns
    -------
    list[dict]
        Each dict has keys: latitude, longitude, formatted_address.
    """
    if not address or not address.strip():
        return []

    # Build the search query
    query = f"{address.strip()} Alexandria, Egypt" if bias else address.strip()

    # Build the pb parameter
    pb = _DEFAULT_PB
    if user_lat is not None and user_lng is not None:
        pb = pb.replace("!2d29.902868658279324", f"!2d{user_lng}")
        pb = pb.replace("!3d31.21938689710795", f"!3d{user_lat}")

    url = _build_url(query, language, pb)
    raw = _fetch(url)
    results = _parse_results(raw)

    # Filter to Alexandria bounding box if bias is on
    if bias:
        results = [
            r for r in results
            if is_in_alexandria(r["latitude"], r["longitude"])
        ]

    return results
