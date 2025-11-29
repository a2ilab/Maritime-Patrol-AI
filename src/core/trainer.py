"""Training logic for patrol route optimization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

import numpy as np

from src.config import (
    BASE_REWARD_BONUS,
    DEFAULT_TRAINING_EPISODES,
    REVISIT_PENALTY,
    WALL_HIT_PENALTY,
)
from src.core.agent import QAgent
from src.core.environment import MaritimePatrolEnv

Position: TypeAlias = tuple[int, int]


@dataclass
class RewardWeights:
    """Weights for reward calculation."""

    alpha: float  # Risk weight
    beta: float   # Movement cost
    gamma: float  # Surveillance effect


@dataclass
class TrainingResult:
    """Result of training containing environment and optimal path."""

    env: MaritimePatrolEnv
    path: list[Position]


class PatrolTrainer:
    """Trainer for maritime patrol agent.

    Handles the training loop and optimal path generation.
    """

    def __init__(
        self,
        grid_size: int,
        weights: RewardWeights,
        seed: int | None = None,
        episodes: int = DEFAULT_TRAINING_EPISODES,
    ) -> None:
        """Initialize trainer.

        Args:
            grid_size: Size of the patrol grid.
            weights: Reward calculation weights.
            seed: Random seed for reproducibility.
            episodes: Number of training episodes.
        """
        self.grid_size = grid_size
        self.weights = weights
        self.seed = seed
        self.episodes = episodes

        if seed is not None:
            np.random.seed(seed)

        self.env = MaritimePatrolEnv(grid_size=grid_size)
        self.agent = QAgent(grid_size=grid_size)

    def _calculate_reward(
        self,
        position: Position,
        hit_wall: bool,
        is_revisit: bool,
    ) -> float:
        """Calculate reward for a given step.

        Args:
            position: Current position.
            hit_wall: Whether agent hit a wall.
            is_revisit: Whether position was already visited.

        Returns:
            Calculated reward value.
        """
        if hit_wall:
            return WALL_HIT_PENALTY

        if is_revisit:
            return REVISIT_PENALTY

        nx, ny = position
        r_risk = self.env.risk_map[nx, ny] * self.weights.alpha
        r_surveillance = 1.0 * self.weights.gamma
        r_cost = self.weights.beta + (self.env.weather_condition[nx, ny] * 0.5)

        return (r_risk + r_surveillance) - r_cost + BASE_REWARD_BONUS

    def train(self) -> None:
        """Execute training loop."""
        for _ in range(self.episodes):
            state = self.env.reset()
            done = False

            while not done:
                action = self.agent.get_action(state)
                result = self.env.step(action)
                next_state = result.next_state

                is_revisit = self.env.is_visited(next_state)
                reward = self._calculate_reward(
                    position=next_state,
                    hit_wall=result.hit_wall,
                    is_revisit=is_revisit,
                )

                if not result.hit_wall and not is_revisit:
                    self.env.mark_visited(next_state)

                self.agent.update(state, action, reward, next_state)
                state = next_state
                done = result.done

            self.agent.decay_epsilon()

    def generate_optimal_path(self) -> list[Position]:
        """Generate optimal path using trained agent.

        Returns:
            List of positions representing the optimal patrol path.
        """
        state = self.env.reset()
        path: list[Position] = [state]

        done = False
        max_path_length = self.env.max_steps

        while not done and len(path) <= max_path_length:
            action = self.agent.get_best_action(state)
            result = self.env.step(action)
            state = result.next_state
            path.append(state)
            done = result.done

        return path

    def train_and_get_path(self) -> TrainingResult:
        """Train agent and generate optimal path.

        Returns:
            TrainingResult containing trained environment and optimal path.
        """
        self.train()
        path = self.generate_optimal_path()
        return TrainingResult(env=self.env, path=path)
