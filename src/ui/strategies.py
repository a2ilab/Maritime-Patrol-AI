"""Predefined patrol strategies and strategy utilities."""

from __future__ import annotations

from typing import Final

from src.config import Strategy

STRATEGY_SAFETY: Final[Strategy] = Strategy(
    name="safety",
    alpha=40.0,
    beta=0.2,
    gamma=5.0,
    description="Safety First",
)

STRATEGY_EFFICIENCY: Final[Strategy] = Strategy(
    name="efficiency",
    alpha=5.0,
    beta=1.0,
    gamma=2.0,
    description="Efficiency First",
)

STRATEGY_SURVEILLANCE: Final[Strategy] = Strategy(
    name="surveillance",
    alpha=10.0,
    beta=0.0,
    gamma=20.0,
    description="Wide Surveillance",
)

STRATEGIES: Final[dict[str, Strategy]] = {
    "safety": STRATEGY_SAFETY,
    "efficiency": STRATEGY_EFFICIENCY,
    "surveillance": STRATEGY_SURVEILLANCE,
}


def get_strategy_name(alpha: float, beta: float, gamma: float) -> str:
    """Determine strategy name from parameters.

    Args:
        alpha: Influence weight parameter.
        beta: Movement cost parameter.
        gamma: Surveillance effect parameter.

    Returns:
        Strategy display name in Korean.
    """
    if alpha == STRATEGY_SAFETY.alpha and beta == STRATEGY_SAFETY.beta:
        return "Safety First"
    if alpha == STRATEGY_EFFICIENCY.alpha and beta == STRATEGY_EFFICIENCY.beta:
        return "Efficiency First"
    if gamma == STRATEGY_SURVEILLANCE.gamma:
        return "Wide Surveillance"
    return "Custom"
