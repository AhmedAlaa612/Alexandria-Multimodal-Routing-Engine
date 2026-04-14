"""
Core routing: Pareto-optimal BFS across the trip graph.
"""

from collections import deque

from routing_api.cost.distance import get_distance_km
from routing_api.cost.fare import get_fare
from routing_api.cost.time import get_transport_time


def find_journeys_pareto(graph, start_trips, goal_trips, max_transfers,
                         excluded_trips=None):
    """
    BFS with Pareto pruning across (transfers, fare, total_time, walk).

    Parameters
    ----------
    graph : dict
        Trip-level transfer graph.
    start_trips / goal_trips : dict
        Output of ``explore_trips``.
    max_transfers : int
    excluded_trips : set, optional
        Trip IDs pre-resolved from filters.

    Returns
    -------
    list[tuple]
        [(trip_path, cost_vector, cost_details), ...]
    """
    excluded_trips = excluded_trips or set()
    results = []
    queue = deque()
    best = {}  # trip_id -> [cost_vector, ...]

    def dominates(v1, v2):
        return all(v1[i] <= v2[i] for i in range(4)) and any(v1[i] < v2[i] for i in range(4))

    def update_frontier(frontier, c):
        frontier = [v for v in frontier if not dominates(c, v)]
        if not any(dominates(v, c) for v in frontier):
            frontier.append(c)
        return frontier

    def walk_time(meters):
        return meters / 83.33 * 60  # seconds at 5 km/h

    def _record_goal(trip_id, board_stop, board_seq, path, c, cost_details):
        if trip_id not in goal_trips:
            return
        goal = goal_trips[trip_id]
        if board_seq >= goal["stop_sequence"]:
            return
        dist_km = get_distance_km(trip_id, board_stop, goal["stop_id"])
        fare = get_fare(trip_id, board_stop, goal["stop_id"], goal["agency"], distance_km=dist_km)
        time_s = get_transport_time(trip_id, board_stop, goal["stop_id"])
        c_final = (
            c[0],
            c[1] + fare,
            c[2] + time_s + walk_time(goal["walk"]),
            c[3] + goal["walk"],
        )
        results.append((path, c_final, cost_details + [{
            "type": "trip", "trip_id": trip_id,
            "from_stop_id": board_stop, "to_stop_id": goal["stop_id"],
            "fare": fare, "distance_km": dist_km, "time": time_s,
            "agency_id": goal["agency"],
        }]))

    # 1. Seed queue with start trips
    for trip_id, data in start_trips.items():
        if trip_id in excluded_trips:
            continue
        c0 = (0, 0, walk_time(data["walk"]), data["walk"])
        queue.append((trip_id, data["stop_id"], data["stop_sequence"], [trip_id], c0, []))
        best[trip_id] = [c0]
        _record_goal(trip_id, data["stop_id"], data["stop_sequence"], [trip_id], c0, [])

    # 2. BFS
    while queue:
        current_trip, board_stop, board_seq, path, c, cost_details = queue.popleft()
        if len(path) - 1 >= max_transfers:
            continue

        for next_trip, pw in graph.get(current_trip, {}).items():
            if next_trip in path:
                continue
            if next_trip in excluded_trips:
                continue
            if board_seq >= pw["start_stop_sequence"]:
                continue

            dist_km = get_distance_km(current_trip, board_stop, pw["start_stop_id"])
            fare = get_fare(current_trip, board_stop, pw["start_stop_id"],
                            pw["start_agency_id"], distance_km=dist_km)
            time_s = get_transport_time(current_trip, board_stop, pw["start_stop_id"])
            c_new = (
                c[0] + 1,
                c[1] + fare,
                c[2] + time_s + walk_time(pw["walking_distance_m"]),
                c[3] + pw["walking_distance_m"],
            )

            if next_trip in best and any(dominates(v, c_new) for v in best[next_trip]):
                continue
            best[next_trip] = update_frontier(best.get(next_trip, []), c_new)

            new_details = cost_details + [
                {"type": "trip", "trip_id": current_trip,
                 "from_stop_id": board_stop, "to_stop_id": pw["start_stop_id"],
                 "fare": fare, "distance_km": dist_km, "time": time_s,
                 "agency_id": pw["start_agency_id"]},
                {"type": "transfer", "from_trip_id": current_trip, "to_trip_id": next_trip,
                 "walking_distance_m": pw["walking_distance_m"], "pathway": pw},
            ]
            new_path = path + [next_trip]
            queue.append((next_trip, pw["end_stop_id"], pw["end_stop_sequence"],
                          new_path, c_new, new_details))
            _record_goal(next_trip, pw["end_stop_id"], pw["end_stop_sequence"],
                         new_path, c_new, new_details)

    return results
