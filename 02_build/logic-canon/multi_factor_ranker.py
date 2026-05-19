"""
Multi-Factor Ranker — Cross-Sectional Ranking by Multiple Criteria
===================================================================
WHEN TO USE: You have N items to rank against each other using multiple
scoring dimensions simultaneously. You want a single composite score
that respects the relative importance of each factor.

EXAMPLES:
- Lead scoring: rank prospects by recency × engagement × company size × fit
- Content prioritisation: rank ideas by trending × gap × brand-fit × effort
- Task prioritisation: rank tickets by urgency × impact × effort-inverse
- Vendor selection: rank suppliers by price × reliability × capacity × terms
- Feature prioritisation: rank product features by demand × feasibility × revenue

HOW IT WORKS:
1. Score each item on N factors (raw scores, any scale)
2. Rank all items percentile-wise on each factor (0 to 1)
3. Center ranks at 0 (-0.5 to +0.5) so positive = above median
4. Weight and sum into composite score
5. Top X% = strong signal, bottom X% = weak signal

INPUTS:
- Dictionary of {item: {factor: raw_score}}
- Factor weights (which dimensions matter more)
- Threshold for signal generation

OUTPUTS:
- Ranked items with composite scores
- Signal dictionary: {item: signal_strength} (-1 to +1)

Provenance: Nexus V2 engines.py MultiFactorEngine (lines 275-389) → generalised.
Devon-b3d8 | 2026-05-15
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


@dataclass
class RankerConfig:
    """Multi-factor ranker configuration."""

    # Factor weights (must sum to 1.0 — normalised internally if not)
    weights: Dict[str, float] = field(default_factory=lambda: {
        "momentum": 0.40,
        "mean_reversion": 0.30,
        "quality": 0.30,
    })

    # Signal thresholds
    long_threshold: float = 0.15        # Composite > this = positive signal
    short_threshold: float = -0.15      # Composite < this = negative signal
    signal_scale: float = 2.0           # Multiply composite for signal strength
    max_signal: float = 1.0             # Cap signal at ±1.0


def rank_items(
    scores: Dict[str, Dict[str, float]],
    cfg: Optional[RankerConfig] = None,
) -> Tuple[Dict[str, float], Dict[str, float]]:
    """
    Rank items by weighted multi-factor composite.

    Args:
        scores: {item_name: {factor_name: raw_score}}
                e.g., {"lead_A": {"recency": 0.8, "engagement": 0.3, "size": 50000}}
        cfg: Configuration with weights and thresholds

    Returns:
        (composites, signals) where:
        - composites: {item: composite_score} (centered around 0)
        - signals: {item: signal_strength} (only items above threshold, -1 to +1)

    Example:
        scores = {
            "Lead A": {"recency": 5, "engagement": 0.8, "company_size": 50},
            "Lead B": {"recency": 2, "engagement": 0.3, "company_size": 200},
            "Lead C": {"recency": 8, "engagement": 0.6, "company_size": 100},
        }
        cfg = RankerConfig(weights={"recency": 0.3, "engagement": 0.4, "company_size": 0.3})
        composites, signals = rank_items(scores, cfg)
    """
    if cfg is None:
        cfg = RankerConfig()

    if not scores:
        return {}, {}

    # Build DataFrame
    df = pd.DataFrame(scores).T

    # Get factor names from config weights (only use factors that exist in data)
    factors = [f for f in cfg.weights if f in df.columns]
    if not factors:
        # Fall back to all columns in data
        factors = list(df.columns)

    # Normalise weights
    raw_weights = {f: cfg.weights.get(f, 1.0 / len(factors)) for f in factors}
    weight_sum = sum(raw_weights.values()) or 1.0
    weights = {f: w / weight_sum for f, w in raw_weights.items()}

    # Rank each factor: percentile rank centered at 0
    for factor in factors:
        col = df[factor].astype(float)
        df[f"{factor}_ranked"] = col.rank(pct=True) - 0.5  # Range: [-0.5, +0.5]

    # Composite score (weighted sum of ranked factors)
    df["composite"] = sum(
        df[f"{factor}_ranked"] * weights[factor]
        for factor in factors
    )

    # Extract composites
    composites = df["composite"].to_dict()

    # Generate signals (only for items above threshold)
    signals = {}
    for item, comp in composites.items():
        if not np.isfinite(comp):
            continue
        if comp > cfg.long_threshold:
            signal = min(comp * cfg.signal_scale, cfg.max_signal)
            signals[item] = signal
        elif comp < cfg.short_threshold:
            signal = max(comp * cfg.signal_scale, -cfg.max_signal)
            signals[item] = signal

    return composites, signals


def rank_simple(
    items: Dict[str, Dict[str, float]],
    weights: Dict[str, float],
) -> List[Tuple[str, float]]:
    """
    Simplified ranking — returns sorted list of (item, composite_score).

    Convenience wrapper when you just want a sorted list.

    Example:
        ranked = rank_simple(
            {"Task A": {"urgency": 9, "impact": 7, "effort_inv": 3},
             "Task B": {"urgency": 3, "impact": 9, "effort_inv": 8}},
            weights={"urgency": 0.4, "impact": 0.4, "effort_inv": 0.2}
        )
        # Returns: [("Task B", 0.12), ("Task A", -0.12)] or similar
    """
    cfg = RankerConfig(weights=weights)
    composites, _ = rank_items(items, cfg)
    return sorted(composites.items(), key=lambda x: x[1], reverse=True)
