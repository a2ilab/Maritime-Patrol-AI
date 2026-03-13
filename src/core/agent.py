"""Q-Learning agent for maritime patrol optimization."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from src.config import (
    DEFAULT_EPSILON,
    DEFAULT_EPSILON_DECAY,
    DEFAULT_GAMMA,
    DEFAULT_LEARNING_RATE,
    DEFAULT_MIN_EPSILON,
    REVISIT_LEARNING_RATE_BOOST,
)


class QAgent:
    """Q-Learning based patrol agent.

    Attributes:
        q_table: Q-value table for state-action pairs.
        epsilon: Current exploration rate.
        epsilon_decay: Rate at which epsilon decays.
        min_epsilon: Minimum exploration rate.
        lr: Learning rate.
        gamma: Discount factor for future rewards.
    """

    def __init__(
        self,
        grid_rows: int,
        grid_cols: int | None = None,
        action_size: int = 4,
        epsilon: float = DEFAULT_EPSILON,
        epsilon_decay: float = DEFAULT_EPSILON_DECAY,
        min_epsilon: float = DEFAULT_MIN_EPSILON,
        learning_rate: float = DEFAULT_LEARNING_RATE,
        gamma: float = DEFAULT_GAMMA,
    ) -> None:
        """Initialize Q-Learning agent.

        Args:
            grid_rows: 격자 행 수.
            grid_cols: 격자 열 수. None이면 grid_rows와 동일.
            action_size: Number of possible actions (default 4: up, down, left, right).
            epsilon: Initial exploration rate.
            epsilon_decay: Decay rate for epsilon.
            min_epsilon: Minimum value for epsilon.
            learning_rate: Learning rate for Q-value updates.
            gamma: Discount factor for future rewards.
        """
        cols = grid_cols if grid_cols is not None else grid_rows
        self.q_table: NDArray[np.float64] = np.random.uniform(
            low=0.0, high=0.1, size=(grid_rows, cols, action_size)
        )
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        self.min_epsilon = min_epsilon
        self.lr = learning_rate
        self.gamma = gamma

    def get_action(self, state: tuple[int, int]) -> int:
        """Select action using epsilon-greedy policy.

        Args:
            state: Current position (x, y).

        Returns:
            Selected action index (0: up, 1: down, 2: left, 3: right).
        """
        if np.random.rand() < self.epsilon:
            return int(np.random.randint(4))
        return int(np.argmax(self.q_table[state]))

    def get_best_action(self, state: tuple[int, int]) -> int:
        """Get the best action without exploration.

        Args:
            state: Current position (x, y).

        Returns:
            Best action index based on Q-values.
        """
        return int(np.argmax(self.q_table[state]))

    def update(
        self,
        state: tuple[int, int],
        action: int,
        reward: float,
        next_state: tuple[int, int],
        boost_lr: bool = False,
    ) -> None:
        """Update Q-value using Q-Learning formula.

        boost_lr: True면 재방문 등 중요 전이에 학습률 가중 적용.
        """
        lr = self.lr * REVISIT_LEARNING_RATE_BOOST if boost_lr else self.lr
        old_value = self.q_table[state][action]
        next_max = np.max(self.q_table[next_state])
        new_value = (1 - lr) * old_value + lr * (
            reward + self.gamma * next_max
        )
        self.q_table[state][action] = new_value

    def decay_epsilon(self) -> None:
        """Decay exploration rate."""
        self.epsilon = max(self.min_epsilon, self.epsilon * self.epsilon_decay)
