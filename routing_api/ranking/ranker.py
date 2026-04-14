"""
Weighted normalised ranking of routing results.
"""


def rank_routing_results(routing_results, weights, top_n=5):
    """
    Rank routing results by weighted normalised costs.

    Expects pre-normalised weights from ``resolve_ranking_weights``.
    """
    if not routing_results or top_n <= 0:
        return []
    if len(routing_results) == 1:
        return routing_results[:top_n]

    transfers = [c[0] for _, c, _ in routing_results]
    fares = [c[1] for _, c, _ in routing_results]
    times = [c[2] / 60 for _, c, _ in routing_results]
    walks = [c[3] for _, c, _ in routing_results]

    ranges = {
        "transfer": (min(transfers), max(transfers)),
        "fare": (min(fares), max(fares)),
        "time": (min(times), max(times)),
        "walk": (min(walks), max(walks)),
    }

    def norm(val, key):
        lo, hi = ranges[key]
        return (val - lo) / (hi - lo) if hi > lo else 0.0

    scored = []
    for trip_path, c, details in routing_results:
        score = (
            weights["transfer"] * norm(c[0], "transfer")
            + weights["cost"] * norm(c[1], "fare")
            + weights["time"] * norm(c[2] / 60, "time")
            + weights["walk"] * norm(c[3], "walk")
        )
        tie = (c[0], c[2] / 60, c[1], c[3])
        scored.append((trip_path, c, details, score, tie))

    ranked = sorted(scored, key=lambda x: (x[3], x[4]))[:top_n]
    return [(tp, c, cd) for tp, c, cd, _, _ in ranked]
