"""
PostGIS spatial queries.
"""
from __future__ import annotations

from typing import Any

from psycopg2.extras import RealDictCursor

from db_tools.db.pool import PooledConnection


NEARBY_TRIPS_SQL = """
WITH q AS (
    SELECT ST_Transform(
        ST_SetSRID(
            ST_MakePoint(%(lon)s::double precision, %(lat)s::double precision),
            4326
        ),
        %(epsg)s
    ) AS qgeom
),
nearby_stops AS (
    SELECT
        s.stop_id,
        s.stop_name,
        s.stop_name_ar,
        s.stop_lat,
        s.stop_lon,
        ST_Distance(
            ST_Transform(
                ST_SetSRID(
                    ST_MakePoint(s.stop_lon::double precision, s.stop_lat::double precision),
                    4326
                ),
                %(epsg)s
            ),
            q.qgeom
        ) AS distance_m
    FROM gtfs_stops s
    CROSS JOIN q
    WHERE s.stop_lat IS NOT NULL
      AND s.stop_lon IS NOT NULL
      AND ST_DWithin(
            ST_Transform(
                ST_SetSRID(
                    ST_MakePoint(s.stop_lon::double precision, s.stop_lat::double precision),
                    4326
                ),
                %(epsg)s
            ),
            q.qgeom,
            %(radius_m)s::double precision
      )
),
first_stops AS (
    SELECT trip_id, MIN(stop_sequence) AS min_stop_sequence
    FROM gtfs_stop_times
    GROUP BY trip_id
)
SELECT
    q.trip_id,
    q.route_id,
    q.trip_headsign,
    q.trip_headsign_ar,
    q.direction_id,
    q.closest_stop_id,
    q.closest_stop_name,
    q.closest_stop_name_ar,
    q.closest_stop_lat,
    q.closest_stop_lon,
    q.closest_stop_sequence,
    q.route_short_name,
    q.route_short_name_ar,
    q.route_name,
    q.route_name_ar,
    q.distance_m
FROM (
    SELECT
        t.trip_id,
        t.route_id,
        t.trip_headsign,
        t.trip_headsign_ar,
        t.direction_id,
        st.stop_id AS closest_stop_id,
        ns.stop_name AS closest_stop_name,
        ns.stop_name_ar AS closest_stop_name_ar,
        ns.stop_lat AS closest_stop_lat,
        ns.stop_lon AS closest_stop_lon,
        st.stop_sequence AS closest_stop_sequence,
        r.route_short_name AS route_short_name,
        r.route_short_name_ar AS route_short_name_ar,
        r.route_long_name AS route_name,
        r.route_long_name_ar AS route_name_ar,
        ns.distance_m,
        ROW_NUMBER() OVER (
            PARTITION BY t.trip_id
            ORDER BY ns.distance_m ASC, st.stop_sequence ASC
        ) AS rn
    FROM gtfs_trips t
    JOIN gtfs_routes r ON r.route_id = t.route_id
    JOIN gtfs_stop_times st ON st.trip_id = t.trip_id
    JOIN nearby_stops ns ON ns.stop_id = st.stop_id
    LEFT JOIN first_stops fs ON fs.trip_id = t.trip_id
    WHERE (%(starts)s = FALSE OR st.stop_sequence = fs.min_stop_sequence)
) q
WHERE q.rn = 1
ORDER BY q.distance_m ASC, q.trip_id;
"""


def get_nearby_trips(
    lat: float,
    lon: float,
    radius_m: float = 1000.0,
    starts: bool = False,
    epsg: int = 32636,
) -> list[dict[str, Any]]:
    """
    Find all transit trips with at least one stop within ``radius_m`` of
    the query point.

    Returns one row per trip (the closest stop for that trip).
    """
    params = {
        "lat": lat,
        "lon": lon,
        "radius_m": radius_m,
        "starts": starts,
        "epsg": epsg,
    }
    with PooledConnection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(NEARBY_TRIPS_SQL, params)
            rows = cur.fetchall()
    return [dict(r) for r in rows]
