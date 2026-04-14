"""
Utility constants and helpers for geocoding.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass

ALEXANDRIA_BOUNDS = {
    "min_lat": 30.85,
    "max_lat": 31.42,
    "min_lng": 29.52,
    "max_lng": 30.25,
}


def is_in_alexandria(lat: float, lon: float) -> bool:
    """Check if coordinates fall within the Alexandria bounding box."""
    return (
        ALEXANDRIA_BOUNDS["min_lat"] <= lat <= ALEXANDRIA_BOUNDS["max_lat"]
        and ALEXANDRIA_BOUNDS["min_lng"] <= lon <= ALEXANDRIA_BOUNDS["max_lng"]
    )


def decode_html_entities(text: str) -> str:
    """Decode HTML numeric character references like &#945; and named entities."""
    return html.unescape(text)
