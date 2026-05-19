"""
Adaptive Allocator — Self-Healing Resource Allocation
======================================================
WHEN TO USE: You have N channels/agents/features competing for a fixed
budget (money, time, attention, compute). You want the system to
automatically shift resources toward what's working and away from what
isn't — daily, without human intervention.

EXAMPLES:
- Marketing spend across 4 channels
- Compute allocation across intelligence features
- Staff time across client accounts
- Content cadence across platforms

INPUTS:
- Dictionary of {channel_name: list_of_daily_returns}
- Current weights (or None for equal)
- Config thresholds

OUTPUTS:
- New weight dictionary (sums to 1.0)
- Assessment per channel (kill/boost/hold)

Provenance: Nexus V2 kaizen_l1_reweight.py (320 lines) → generalised.
Devon-b3d8 | 2026-05-15
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np


@dataclass
class AllocatorConfig:
    """Tuneable parameters for the adaptive allocator."""

    # Performance window
    sharpe_window: int = 63             # Days of history for Sharpe calculation
    return_window: int = 21             # Days for trailing return

    # Kill switch: when to reduce allocation
    kill_sharpe: float = -0.50          # If risk-adjusted return < this, cut
    kill_drawdown: float = -0.10        # If max loss > this, cut
    kill_reduction: float = 0.50        # Cut weight by this fraction (50%)

    # Boost: when to increase allocation
    boost_sharpe: float = 1.0           # If risk-adjusted return > this, boost
    boost_increase: float = 0.25        # Increase weight by this fraction (25%)

    # Constraints
    min_weight: float = 0.05            # Floor (never zero — keeps optionality)
    max_weight: float = 0.50            # Ceiling (no single channel dominates)
    max_change_per_cycle: float = 0.05  # Max weight shift per rebalance (5%)
    min_cycles_between: int = 5         # Minimum cycles between rebalances

    # Mean reversion
    mean_reversion_rate: float = 0.10   # Drift 10% back to baseline per cycle

    # Annualisation factor (252 for daily trading, 365 for daily marketing,
    # 52 for weekly, 12 for monthly)
    annualisation: int = 252


def trailing_sharpe(returns: List[float], window: int, annualisation: int = 252) -> float:
    """
    Risk-adjusted performance metric.
    Formula: (mean_return / std_deviation) × √annualisation

    Interpretation:
    - > 1.0: excellent (return significantly exceeds volatility)
    - 0 to 1.0: acceptable
    - < 0: losing money on risk-adjusted basis
    - < -0.5: actively harmful
    """
    if len(returns) < 20:
        return 0.0
    recent = returns[-window:]
    mean = np.mean(recent)
    std = np.std(recent) or 1e-8
    return float((mean / std) * np.sqrt(annualisation))


def trailing_return(returns: List[float], window: int, annualisation: int = 252) -> float:
    """Annualised trailing return over the window."""
    if len(returns) < 5:
        return 0.0
    recent = returns[-window:]
    cum = float(np.prod([1 + r for r in recent]) - 1)
    ann = (1 + cum) ** (annualisation / len(recent)) - 1
    return ann


def max_drawdown(returns: List[float]) -> float:
    """
    Maximum peak-to-trough decline.
    Returns negative number (e.g., -0.15 = 15% max loss from peak).
    """
    if len(returns) < 2:
        return 0.0
    equity = np.cumprod([1 + r for r in returns])
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / (peak + 1e-8)
    return float(np.min(dd))


def assess_channel(
    returns: List[float],
    cfg: AllocatorConfig,
) -> Dict:
    """
    Assess a single channel's health.

    Returns dict with:
    - sharpe: risk-adjusted performance
    - trailing_return: annualised return
    - max_drawdown: worst loss from peak
    - action: 'kill' | 'boost' | 'hold'
    - reason: human-readable explanation
    """
    sharpe = trailing_sharpe(returns, cfg.sharpe_window, cfg.annualisation)
    ret = trailing_return(returns, cfg.return_window, cfg.annualisation)
    dd = max_drawdown(returns)

    assessment = {
        "sharpe": round(sharpe, 3),
        "trailing_return": round(ret, 4),
        "max_drawdown": round(dd, 4),
        "action": "hold",
        "reason": "",
    }

    if sharpe < cfg.kill_sharpe:
        assessment["action"] = "kill"
        assessment["reason"] = f"Sharpe {sharpe:.2f} < kill threshold {cfg.kill_sharpe}"
    elif dd < cfg.kill_drawdown:
        assessment["action"] = "kill"
        assessment["reason"] = f"Drawdown {dd:.1%} < kill threshold {cfg.kill_drawdown:.1%}"
    elif sharpe > cfg.boost_sharpe:
        assessment["action"] = "boost"
        assessment["reason"] = f"Sharpe {sharpe:.2f} > boost threshold {cfg.boost_sharpe}"

    return assessment


def rebalance(
    channel_returns: Dict[str, List[float]],
    current_weights: Optional[Dict[str, float]] = None,
    base_weights: Optional[Dict[str, float]] = None,
    cfg: Optional[AllocatorConfig] = None,
) -> Tuple[Dict[str, float], Dict[str, Dict]]:
    """
    Core rebalancing function.

    Args:
        channel_returns: {channel_name: [daily_return_1, daily_return_2, ...]}
        current_weights: Current allocation (None = use base_weights)
        base_weights: Starting/target weights (None = equal weight)
        cfg: Configuration (None = defaults)

    Returns:
        (new_weights, assessments) where:
        - new_weights sums to 1.0
        - assessments contains per-channel health data
    """
    if cfg is None:
        cfg = AllocatorConfig()

    channels = list(channel_returns.keys())
    n = len(channels)

    if n == 0:
        return {}, {}

    # Default to equal weights
    if base_weights is None:
        base_weights = {ch: 1.0 / n for ch in channels}
    if current_weights is None:
        current_weights = dict(base_weights)

    # 1. Assess each channel
    assessments = {}
    for ch in channels:
        assessments[ch] = assess_channel(channel_returns[ch], cfg)

    # 2. Calculate new weights based on assessments
    new_weights = {}
    for ch in channels:
        base_w = base_weights.get(ch, 1.0 / n)
        action = assessments[ch]["action"]

        if action == "kill":
            new_w = max(base_w * (1 - cfg.kill_reduction), cfg.min_weight)
        elif action == "boost":
            new_w = min(base_w * (1 + cfg.boost_increase), cfg.max_weight)
        else:
            # Mean-revert toward base
            current_w = current_weights.get(ch, base_w)
            new_w = current_w + (base_w - current_w) * cfg.mean_reversion_rate

        new_weights[ch] = new_w

    # 3. Normalise to sum to 1.0
    total = sum(new_weights.values()) or 1.0
    new_weights = {k: v / total for k, v in new_weights.items()}

    # 4. Constrain maximum change per cycle
    for ch in channels:
        old_w = current_weights.get(ch, base_weights.get(ch, 1.0 / n))
        change = new_weights[ch] - old_w
        if abs(change) > cfg.max_change_per_cycle:
            capped = np.sign(change) * cfg.max_change_per_cycle
            new_weights[ch] = old_w + capped

    # 5. Re-normalise after capping
    total = sum(new_weights.values()) or 1.0
    new_weights = {k: v / total for k, v in new_weights.items()}

    return new_weights, assessments
