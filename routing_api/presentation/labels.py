"""
Journey frontend labels (recommended, fastest, cheapest, etc.).
"""

JOURNEY_LABELS_AR = {
    "recommended": "موصى به",
    "fastest": "الأسرع",
    "cheapest": "الأرخص",
    "least_walking": "أقل مشي",
    "fewest_transfers": "أقل تحويلات",
}


def add_journey_labels(journeys: list[dict], selected_priority: str = "balanced") -> list[dict]:
    """Attach frontend labels to each journey based on summary metrics."""
    if not journeys:
        return journeys

    def metric(s, key):
        try:
            return float(s.get(key, float("inf")))
        except (TypeError, ValueError):
            return float("inf")

    sums = [j["summary"] for j in journeys]
    min_time = min(metric(s, "total_time_minutes") for s in sums)
    min_cost = min(metric(s, "cost") for s in sums)
    min_walk = min(metric(s, "walking_distance_meters") for s in sums)
    min_trans = min(metric(s, "transfers") for s in sums)
    eps = 1e-9

    for idx, journey in enumerate(journeys):
        s = journey["summary"]
        labels = []
        if abs(metric(s, "total_time_minutes") - min_time) <= eps:
            labels.append("fastest")
        if abs(metric(s, "cost") - min_cost) <= eps:
            labels.append("cheapest")
        if abs(metric(s, "walking_distance_meters") - min_walk) <= eps:
            labels.append("least_walking")
        if abs(metric(s, "transfers") - min_trans) <= eps:
            labels.append("fewest_transfers")
        if idx == 0:
            labels.insert(0, "recommended")
            journey["recommended_for"] = selected_priority
        journey["labels"] = list(dict.fromkeys(labels))
        journey["labels_ar"] = [JOURNEY_LABELS_AR.get(lbl, lbl) for lbl in journey["labels"]]
    return journeys
