"""
Google polyline5 encoder.
"""


def encode_polyline(points, precision=5):
    """Encode a list of [lat, lon] points to a Google polyline5 string."""
    if not points:
        return ""
    factor = 10 ** precision
    encoded = []
    prev_lat = prev_lon = 0

    def _enc(val):
        val = ~(val << 1) if val < 0 else (val << 1)
        chunk = []
        while val >= 0x20:
            chunk.append(chr((0x20 | (val & 0x1F)) + 63))
            val >>= 5
        chunk.append(chr(val + 63))
        return "".join(chunk)

    for pt in points:
        if not isinstance(pt, (list, tuple)) or len(pt) < 2:
            continue
        try:
            lat, lon = float(pt[0]), float(pt[1])
        except (TypeError, ValueError):
            continue
        lat_i = int(round(lat * factor))
        lon_i = int(round(lon * factor))
        encoded += [_enc(lat_i - prev_lat), _enc(lon_i - prev_lon)]
        prev_lat, prev_lon = lat_i, lon_i
    return "".join(encoded)
