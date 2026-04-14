"""
Walking-only journey builder.
"""

import math

import networkx as nx

from routing_api.presentation.polyline import encode_polyline


def build_walking_journey(G, start_node, end_node, walking_cutoff):
    """
    Build a direct walking journey if within cutoff, else return None.
    Single Dijkstra pass.
    """
    try:
        walk_path_nodes = nx.shortest_path(G, start_node, end_node, weight="length")
        walk_length = sum(
            G[u][v][0].get("length", 0)
            for u, v in zip(walk_path_nodes, walk_path_nodes[1:])
        )
        if walk_length > walking_cutoff:
            return None
        walk_coords = [
            [G.nodes[n]["y"], G.nodes[n]["x"]]
            for n in walk_path_nodes if n in G.nodes
        ]
        walk_time_min = max(1, math.ceil(walk_length / 83.33))
        return {
            "id": 1,
            "text_summary": "امشي لغايه وجهتك",
            "text_summary_en": "Walk to your destination",
            "summary": {
                "total_time_minutes": walk_time_min,
                "walking_distance_meters": round(walk_length),
                "transit_distance_meters": 0,
                "total_distance_meters": round(walk_length),
                "transfers": 0,
                "cost": 0,
                "modes_en": ["walking"],
                "modes_ar": ["مشي"],
                "main_streets_en": [],
                "main_streets_ar": [],
            },
            "legs": [{
                "type": "walk",
                "distance_meters": round(walk_length),
                "duration_minutes": walk_time_min,
                "polyline": encode_polyline(walk_coords),
            }],
        }
    except nx.NetworkXNoPath:
        return None
