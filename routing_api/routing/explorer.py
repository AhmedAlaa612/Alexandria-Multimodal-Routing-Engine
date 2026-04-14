"""
Trip explorer: Dijkstra walk from an OSM node to discover reachable transit trips.
"""

import heapq


def explore_trips(G, source: int, cutoff: float = 1500.0) -> dict:
    """
    Dijkstra from *source* node; return all reachable transit trips within
    *cutoff* meters.

    Returns
    -------
    dict
        trip_id → {stop_id, agency, stop_sequence, osm_node_id, walk, path}
    """
    dist = {source: 0.0}
    prev = {}
    pq = [(0.0, source)]
    visited = set()
    trips = {}

    def path_coords(node):
        cur, nodes = node, []
        while cur in prev:
            nodes.append(cur)
            cur = prev[cur]
        nodes.append(source)
        return [[G.nodes[n]["y"], G.nodes[n]["x"]] for n in reversed(nodes) if n in G.nodes]

    while pq:
        d, node = heapq.heappop(pq)
        if d > cutoff:
            break
        if node in visited:
            continue
        visited.add(node)

        for trip_id, info in (G.nodes[node].get("access_map") or {}).items():
            if trips.get(trip_id, {}).get("walk", float("inf")) > d:
                trips[trip_id] = {
                    "stop_id": info["stop_id"],
                    "agency": info["agency_id"],
                    "stop_sequence": info["stop_sequence"],
                    "osm_node_id": node,
                    "walk": d,
                    "path": path_coords(node),
                }

        for nbr, edge_data in G[node].items():
            for _, attr in edge_data.items():
                new_dist = d + float(attr.get("length", 1.0))
                if new_dist <= cutoff and new_dist < dist.get(nbr, float("inf")):
                    dist[nbr] = new_dist
                    prev[nbr] = node
                    heapq.heappush(pq, (new_dist, nbr))

    return trips
