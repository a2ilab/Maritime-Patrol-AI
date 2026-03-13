"""Configuration constants and default values."""

from dataclasses import dataclass
from typing import Final


# Seed range for RandomGenerator (min, max inclusive)
SEED_RANGE: Final[tuple[int, int]] = (0, 999_999)

# Grid settings
DEFAULT_GRID_SIZE: Final[int] = 10
MIN_GRID_SIZE: Final[int] = 5
MAX_GRID_SIZE: Final[int] = 20

# Training settings
DEFAULT_TRAINING_EPISODES: Final[int] = 3000
DEFAULT_MAX_STEPS_MULTIPLIER: Final[int] = 15  # POI 전부 방문 후 복귀에 충분한 스텝
END_ARRIVAL_BONUS: Final[float] = 10.0  # 모든 POI 방문 후 도착지 도달 시 보너스

# Agent hyperparameters
DEFAULT_EPSILON: Final[float] = 1.0
DEFAULT_EPSILON_DECAY: Final[float] = 0.998
DEFAULT_MIN_EPSILON: Final[float] = 0.01
DEFAULT_LEARNING_RATE: Final[float] = 0.1
REVISIT_LEARNING_RATE_BOOST: Final[float] = 1.5  # 재방문 시 Q 업데이트 가중치
DEFAULT_GAMMA: Final[float] = 0.99

# Reward weights
DEFAULT_ALPHA: Final[float] = 10.0  # Influence weight
DEFAULT_BETA: Final[float] = 0.2    # Movement cost
DEFAULT_REWARD_GAMMA: Final[float] = 10.0  # Surveillance effect

# Parameter ranges for UI
ALPHA_RANGE: Final[tuple[float, float]] = (0.0, 50.0)
BETA_RANGE: Final[tuple[float, float]] = (0.0, 1.0)
GAMMA_RANGE: Final[tuple[float, float]] = (0.0, 30.0)

# Composite influence: 환경제약(weather) 가중치
WEATHER_INFLUENCE_WEIGHT: Final[float] = 0.3

# POI(순찰필요 고도) 임계값 - 0.75 이상이면 고위험군
POI_INFLUENCE_THRESHOLD: Final[float] = 0.75
# 고영향도(0.75 이상) 셀 개수 (순찰 필요 지역 목표 수)
HIGH_INFLUENCE_COUNT: Final[int] = 10
POI_VISIT_BONUS: Final[float] = 5.0  # POI(순찰필요 고도) 최초 방문 시 추가 보상
REVISIT_SURVEILLANCE_BONUS: Final[float] = 2.0  # 고영향도 재방문 시 감시 보상

# Penalties
WALL_HIT_PENALTY: Final[float] = -5.0
REVISIT_PENALTY: Final[float] = -3.0  # 저영향도 재방문 시 (낭비)
LOW_INFLUENCE_PENALTY: Final[float] = -1.0  # 순찰필요성 낮은 구역(0.3 미만) 방문 시
BASE_REWARD_BONUS: Final[float] = 0.5


@dataclass(frozen=True)
class Strategy:
    """Predefined patrol strategy configuration."""

    name: str
    alpha: float
    beta: float
    gamma: float
    description: str
