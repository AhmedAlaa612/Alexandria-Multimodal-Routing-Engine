"""
Merge GTFS trips into the OSM network graph by attaching access_map to nodes.
"""

import osmnx as ox
import pandas as pd


def merge_trips_to_network(graph, gtfs_data: dict):
    """
    Attach an ``access_map`` dict to every OSM node that serves a transit stop.

    Parameters
    ----------
    graph : networkx.MultiDiGraph
    gtfs_data : dict with keys 'stops', 'stop_times', 'trips', 'routes'

    Returns
    -------
    networkx.MultiDiGraph
        The same graph object, mutated in place.
    """
    stops_df = gtfs_data["stops"].copy()
    stop_times_df = gtfs_data["stop_times"].copy()
    trips_df = gtfs_data["trips"].copy()
    routes_df = gtfs_data["routes"].copy()

    stops_df["_sid"] = stops_df["stop_id"].astype(str).str.strip()
    stop_times_df["_sid"] = stop_times_df["stop_id"].astype(str).str.strip()
    stop_times_df["_tid"] = stop_times_df["trip_id"].astype(str).str.strip()
    trips_df["_tid"] = trips_df["trip_id"].astype(str).str.strip()
    trips_df["_rid"] = trips_df["route_id"].astype(str).str.strip()
    routes_df["_rid"] = routes_df["route_id"].astype(str).str.strip()

    stop_to_trips = stop_times_df.groupby("_sid")["_tid"].apply(list).to_dict()
    trip_to_route_local = trips_df.set_index("_tid")["_rid"].to_dict()
    route_to_agency = routes_df.set_index("_rid")["agency_id"].to_dict()

    stop_times_seq = (
        stop_times_df.sort_values("stop_sequence")
        .drop_duplicates(subset=["_tid", "_sid"], keep="first")
    )
    trip_stop_to_seq = stop_times_seq.set_index(["_tid", "_sid"])["stop_sequence"].to_dict()

    stops_for_nodes = stops_df.copy()
    stops_for_nodes["stop_lat"] = pd.to_numeric(stops_for_nodes["stop_lat"], errors="coerce")
    stops_for_nodes["stop_lon"] = pd.to_numeric(stops_for_nodes["stop_lon"], errors="coerce")
    stops_for_nodes = stops_for_nodes.dropna(subset=["stop_lat", "stop_lon"])
    if stops_for_nodes.empty:
        raise ValueError("No valid stop coordinates found in stops.txt")

    stop_nodes = ox.distance.nearest_nodes(
        graph, X=stops_for_nodes["stop_lon"].values, Y=stops_for_nodes["stop_lat"].values,
    )
    stop_to_node = pd.Series(stop_nodes, index=stops_for_nodes["_sid"]).to_dict()
    sid_to_orig = stops_for_nodes.set_index("_sid")["stop_id"].to_dict()

    nodes_updated = trip_entries = stops_no_trips = skipped = 0

    for stop_key, node_id in stop_to_node.items():
        trips_at_stop = stop_to_trips.get(stop_key, [])
        if not trips_at_stop:
            stops_no_trips += 1
            continue
        if "access_map" not in graph.nodes[node_id]:
            graph.nodes[node_id]["access_map"] = {}
            nodes_updated += 1
        orig_sid = sid_to_orig.get(stop_key, stop_key)
        for trip_key in trips_at_stop:
            route_key = trip_to_route_local.get(trip_key)
            agency_id = route_to_agency.get(route_key, "Unknown Agency") if route_key else "Unknown Agency"
            stop_seq = trip_stop_to_seq.get((trip_key, stop_key))
            if stop_seq is None:
                skipped += 1
                continue
            graph.nodes[node_id]["access_map"][trip_key] = {
                "stop_id": orig_sid,
                "stop_sequence": int(stop_seq),
                "agency_id": agency_id,
            }
            trip_entries += 1

    nodes_with_map = sum(1 for _, d in graph.nodes(data=True) if "access_map" in d)
    print("[merge] Finished mapping trips to graph nodes.")
    print(f"[merge]   Stops loaded: {len(stops_df)} | Mapped: {len(stop_to_node)} | "
          f"Nodes updated: {nodes_updated} | Access entries: {trip_entries}")
    return graph
