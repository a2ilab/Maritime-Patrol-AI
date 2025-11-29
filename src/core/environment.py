"""Maritime patrol environment for reinforcement learning."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeAlias

import numpy as np
from numpy.typing import NDArray

from src.config import DEFAULT_GRID_SIZE, DEFAULT_MAX_STEPS_MULTIPLIER

Position: TypeAlias = tuple[int, int]


@dataclass
class StepResult:
    """Result of an environment step."""

    next_state: Position
    hit_wall: bool
    done: bool


class MaritimePatrolEnv:
    """Maritime patrol simulation environment.

    Attributes:
        grid_size: Size of the patrol grid.
        state: Current agent position.
        max_steps: Maximum steps per episode.
        current_step: Current step count.
        static_risk: Static risk map (e.g., known hazard zones).
        dynamic_risk: Dynamic risk map (e.g., variable conditions).
        weather_condition: Weather condition map.
        risk_map: Combined risk map.
        visited: Grid tracking visited cells.
    """

    def __init__(
        self,
        grid_size: int = DEFAULT_GRID_SIZE,
        max_steps: int | None = None,
        seed: int | None = None,
    ) -> None:
        """Initialize maritime patrol environment.

        Args:
            grid_size: Size of the square grid.
            max_steps: Maximum steps per episode. Defaults to grid_size * 5.
            seed: Random seed for reproducibility.
        """
        if seed is not None:
            np.random.seed(seed)

        self.grid_size = grid_size
        self.state: Position = (0, 0)
        self.max_steps = max_steps if max_steps else grid_size * DEFAULT_MAX_STEPS_MULTIPLIER
        self.current_step = 0

        self._init_maps()
        self.visited: NDArray[np.float64] = np.zeros((grid_size, grid_size))

    def _init_maps(self) -> None:
        """Initialize risk and weather maps."""
        gs = self.grid_size

        self.static_risk: NDArray[np.float64] = np.random.rand(gs, gs) * 0.3
        self.static_risk[2:5, 6:9] += 0.7

        self.dynamic_risk: NDArray[np.float64] = np.random.rand(gs, gs) * 0.4
        self.weather_condition: NDArray[np.float64] = np.random.rand(gs, gs)
        self.risk_map: NDArray[np.float64] = self.static_risk + self.dynamic_risk

    def reset(self) -> Position:
        """Reset environment to initial state.

        Returns:
            Initial position (0, 0).
        """
        self.state = (0, 0)
        self.current_step = 0
        self.visited = np.zeros((self.grid_size, self.grid_size))
        self.visited[0, 0] = 1
        return self.state

    def step(self, action: int) -> StepResult:
        """Execute one step in the environment.

        Args:
            action: Action to take (0: up, 1: down, 2: left, 3: right).

        Returns:
            StepResult containing next state, wall hit flag, and done flag.
        """
        x, y = self.state
        old_x, old_y = x, y

        if action == 0:  # Up
            x = max(0, x - 1)
        elif action == 1:  # Down
            x = min(self.grid_size - 1, x + 1)
        elif action == 2:  # Left
            y = max(0, y - 1)
        elif action == 3:  # Right
            y = min(self.grid_size - 1, y + 1)

        self.state = (x, y)
        self.current_step += 1

        hit_wall = (x == old_x and y == old_y)
        done = self.current_step >= self.max_steps

        return StepResult(next_state=self.state, hit_wall=hit_wall, done=done)

    def mark_visited(self, position: Position) -> None:
        """Mark a position as visited.

        Args:
            position: Position to mark.
        """
        self.visited[position] = 1

    def is_visited(self, position: Position) -> bool:
        """Check if a position has been visited.

        Args:
            position: Position to check.

        Returns:
            True if visited, False otherwise.
        """
        return bool(self.visited[position] > 0)
