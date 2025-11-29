"""Configuration constants and default values."""

from dataclasses import dataclass
from typing import Final


# Grid settings
DEFAULT_GRID_SIZE: Final[int] = 10
MIN_GRID_SIZE: Final[int] = 5
MAX_GRID_SIZE: Final[int] = 20

# Training settings
DEFAULT_TRAINING_EPISODES: Final[int] = 3000
DEFAULT_MAX_STEPS_MULTIPLIER: Final[int] = 5

# Agent hyperparameters
DEFAULT_EPSILON: Final[float] = 1.0
DEFAULT_EPSILON_DECAY: Final[float] = 0.998
DEFAULT_MIN_EPSILON: Final[float] = 0.01
DEFAULT_LEARNING_RATE: Final[float] = 0.1
DEFAULT_GAMMA: Final[float] = 0.99

# Reward weights
DEFAULT_ALPHA: Final[float] = 10.0  # Risk weight
DEFAULT_BETA: Final[float] = 0.2    # Movement cost
DEFAULT_REWARD_GAMMA: Final[float] = 10.0  # Surveillance effect

# Parameter ranges for UI
ALPHA_RANGE: Final[tuple[float, float]] = (0.0, 50.0)
BETA_RANGE: Final[tuple[float, float]] = (0.0, 1.0)
GAMMA_RANGE: Final[tuple[float, float]] = (0.0, 30.0)

# Penalties
WALL_HIT_PENALTY: Final[float] = -5.0
REVISIT_PENALTY: Final[float] = -2.0
BASE_REWARD_BONUS: Final[float] = 0.5


@dataclass(frozen=True)
class Strategy:
    """Predefined patrol strategy configuration."""

    name: str
    alpha: float
    beta: float
    gamma: float
    description: str
