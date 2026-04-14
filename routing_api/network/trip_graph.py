"""
Trip graph and pathway metadata: build from CSV or load from pickle cache.
"""
from __future__ import annotations

import os
import pickle
from collections import defaultdict

import pandas as pd

from routing_api.config import settings


def load_trip_graph(pathways_df: pd.DataFrame, stops_df: pd.DataFrame,
                    *, force_rebuild: bool | None = None):
    """
    Build or load the trip-level transfer graph and pathway metadata.

    Returns
    -------
    tuple[defaultdict, dict]
        (trip_graph, pathway_metadata)
    """
    force = force_rebuild if force_rebuild is not None else settings.force_rebuild_trip_graph
    cache_path = str(settings.resolve(settings.trip_graph_cache_path))

    cache_meta = {
        "pathways_rows": int(len(pathways_df)),
        "stops_rows": int(len(stops_df)),
    }

    can_load = False
    cached = {}
    if (not force) and os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            cached = pickle.load(f)
        can_load = cached.get("_meta") == cache_meta

    if can_load:
        trip_graph = defaultdict(dict, cached.get("trip_graph", {}))
        pathway_metadata = cached.get("pathway_metadata", {})
        source = "pickle cache"
    else:
        trip_graph = defaultdict(dict)
        pathway_metadata = {}

        for idx, row in pathways_df.iterrows():
            pathway_id = int(idx)
            end_agency_id = row.get("end_agency_id", row["start_agency_id"])
            if pd.isna(end_agency_id):
                end_agency_id = row["start_agency_id"]

            trip_graph[row["start_trip_id"]][row["end_trip_id"]] = {
                "pathway_id": pathway_id,
                "start_stop_id": row["start_stop_id"],
                "end_stop_id": row["end_stop_id"],
                "start_stop_sequence": row["start_stop_sequence"],
                "end_stop_sequence": row["end_stop_sequence"],
                "start_agency_id": row["start_agency_id"],
                "end_agency_id": end_agency_id,
                "walking_distance_m": row["walking_distance_m"],
            }

            walking_path_coords = row.get("walking_path_coords")
            pathway_metadata[pathway_id] = {
                "end_stop_id": row["end_stop_id"],
                "start_trip_id": row["start_trip_id"],
                "end_trip_id": row["end_trip_id"],
                "walking_path_coords": None if pd.isna(walking_path_coords) else walking_path_coords,
            }

        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "wb") as f:
            pickle.dump(
                {"_meta": cache_meta, "trip_graph": dict(trip_graph),
                 "pathway_metadata": pathway_metadata},
                f, protocol=pickle.HIGHEST_PROTOCOL,
            )
        source = "fresh build"

    print(f"[trip_graph] Source: {source}")
    print(f"[trip_graph] Starting trips: {len(trip_graph)} | "
          f"Edges: {sum(len(v) for v in trip_graph.values())}")
    print(f"[trip_graph] Pathway metadata entries: {len(pathway_metadata)}")
    return trip_graph, pathway_metadata
