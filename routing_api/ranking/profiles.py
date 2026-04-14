"""
Priority profiles and weight normalisation.
"""
from __future__ import annotations

PRIORITY_PROFILES = {
    "balanced":         {"time": 0.25, "cost": 0.25, "walk": 0.25, "transfer": 0.25},
    "fastest":          {"time": 0.70, "cost": 0.10, "walk": 0.10, "transfer": 0.10},
    "cheapest":         {"time": 0.10, "cost": 0.70, "walk": 0.10, "transfer": 0.10},
    "least_walking":    {"time": 0.10, "cost": 0.10, "walk": 0.70, "transfer": 0.10},
    "fewest_transfers": {"time": 0.15, "cost": 0.15, "walk": 0.20, "transfer": 0.50},
}

PRIORITY_LABELS_AR = {
    "balanced": "متوازن",
    "fastest": "الأسرع",
    "cheapest": "الأرخص",
    "least_walking": "أقل مشي",
    "fewest_transfers": "أقل تحويلات",
    "custom": "مخصص",
}


def normalize_weights(weights: dict) -> dict:
    """Validate and normalize ranking weights to sum to 1."""
    keys = ("time", "cost", "walk", "transfer")
    missing = [k for k in keys if k not in weights]
    if missing:
        raise ValueError(f"weights missing required keys: {missing}")
    cleaned = {}
    for k in keys:
        try:
            cleaned[k] = max(0.0, float(weights[k]))
        except (TypeError, ValueError):
            raise ValueError(f"weights[{k}] must be numeric")
    total = sum(cleaned.values())
    if total <= 0:
        raise ValueError("sum of weights must be > 0")
    return {k: cleaned[k] / total for k in keys}


def resolve_ranking_weights(priority: str = "balanced",
                            custom_weights: dict | None = None) -> tuple[dict, str]:
    """
    Resolve final ranking weights from priority name or custom dict.

    Returns
    -------
    tuple[dict, str]
        (normalized_weights, resolved_priority_name)
    """
    if custom_weights is not None:
        return normalize_weights(custom_weights), "custom"
    priority = priority if priority in PRIORITY_PROFILES else "balanced"
    return normalize_weights(PRIORITY_PROFILES[priority]), priority
