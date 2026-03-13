"""Training logic for patrol route optimization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

import numpy as np

from src.config import (
    BASE_REWARD_BONUS,
    DEFAULT_TRAINING_EPISODES,
    END_ARRIVAL_BONUS,
    LOW_INFLUENCE_PENALTY,
    POI_INFLUENCE_THRESHOLD,
    POI_VISIT_BONUS,
    REVISIT_PENALTY,
    REVISIT_SURVEILLANCE_BONUS,
    WALL_HIT_PENALTY,
)
from src.core.agent import QAgent
from src.core.environment import MaritimePatrolEnv

Position: TypeAlias = tuple[int, int]


@dataclass
class RewardWeights:
    """Weights for reward calculation."""

    alpha: float  # Influence weight
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
        grid_rows: int,
        grid_cols: int | None = None,
        weights: RewardWeights | None = None,
        seed: int | None = None,
        episodes: int = DEFAULT_TRAINING_EPISODES,
        start_position: Position | None = None,
        end_position: Position | None = None,
    ) -> None:
        """Initialize trainer.

        Args:
            grid_rows: 격자 행 수.
            grid_cols: 격자 열 수. None이면 grid_rows와 동일.
            weights: Reward calculation weights.
            seed: Random seed for reproducibility.
            episodes: Number of training episodes.
            start_position: 순찰 시작 (row, col). None이면 (0, 0).
            end_position: 순찰 종료 (row, col). None이면 start_position과 동일.
        """
        self.grid_rows = grid_rows
        self.grid_cols = grid_cols if grid_cols is not None else grid_rows
        self.weights = weights or RewardWeights(alpha=10.0, beta=0.2, gamma=10.0)
        self.seed = seed
        self.episodes = episodes

        if seed is not None:
            np.random.seed(seed)

        self.env = MaritimePatrolEnv(
            grid_rows=grid_rows,
            grid_cols=self.grid_cols,
            start_position=start_position,
            end_position=end_position,
        )
        self.agent = QAgent(grid_rows=grid_rows, grid_cols=self.grid_cols)

    def _calculate_reward(
        self,
        position: Position,
        hit_wall: bool,
        is_revisit: bool,
        done: bool,
    ) -> float:
        """Calculate reward for a given step.

        순찰 필요성 높은 곳 우선 탐색. 재방문 시 고영향도는 감시 보상, 저영향도는 패널티.
        모든 POI 방문 후 도착지 도달 시 큰 보너스.
        """
        if hit_wall:
            return WALL_HIT_PENALTY

        nx, ny = position
        influence = float(self.env.influence_map[nx, ny])

        if is_revisit:
            if influence >= POI_INFLUENCE_THRESHOLD:
                return REVISIT_SURVEILLANCE_BONUS
            return REVISIT_PENALTY

        r_influence = influence * self.weights.alpha
        r_surveillance = 1.0 * self.weights.gamma
        r_cost = self.weights.beta + (self.env.weather_condition[nx, ny] * 0.5)
        reward = (r_influence + r_surveillance) - r_cost + BASE_REWARD_BONUS
        if (nx, ny) in getattr(self.env, "_poi", frozenset()):
            reward += POI_VISIT_BONUS
        if influence < 0.3:
            reward += LOW_INFLUENCE_PENALTY
        # 모든 POI 방문 후 도착지 도달 → 큰 보너스
        if done and not self.env.unvisited_poi:
            reward += END_ARRIVAL_BONUS
        return reward

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

                if not result.hit_wall and not is_revisit:
                    self.env.mark_visited(next_state)

                reward = self._calculate_reward(
                    position=next_state,
                    hit_wall=result.hit_wall,
                    is_revisit=is_revisit,
                    done=result.done,
                )

                influence = float(self.env.influence_map[next_state[0], next_state[1]])
                boost = is_revisit and influence >= POI_INFLUENCE_THRESHOLD
                self.agent.update(state, action, reward, next_state, boost_lr=boost)
                state = next_state
                done = result.done

            self.agent.decay_epsilon()

    def generate_optimal_path(self) -> list[Position]:
        """Generate optimal path using trained agent.

        Q-Learning으로 경로 생성 후, 미방문 POI가 있으면
        BFS 보완 경로로 연결하고 도착지로 복귀.
        """
        state = self.env.reset()
        path: list[Position] = [state]

        done = False
        max_path_length = self.env.max_steps

        while not done and len(path) <= max_path_length:
            action = self.agent.get_best_action(state)
            result = self.env.step(action)
            state = result.next_state
            if not result.hit_wall:
                self.env.mark_visited(state)
            path.append(state)
            done = result.done

        # 미방문 POI 보완: BFS로 최단 경로 연결
        unvisited = self.env.unvisited_poi
        if unvisited:
            current = path[-1]
            for poi in sorted(unvisited, key=lambda p: abs(p[0]-current[0]) + abs(p[1]-current[1])):
                sub = self._bfs(current, poi)
                if sub:
                    path.extend(sub[1:])
                    for p in sub:
                        self.env.mark_visited(p)
                    current = poi
            # 도착지 복귀
            if current != self.env._end_position:
                sub = self._bfs(current, self.env._end_position)
                if sub:
                    path.extend(sub[1:])

        # 마지막이 도착지가 아니면 BFS로 복귀
        if path[-1] != self.env._end_position:
            sub = self._bfs(path[-1], self.env._end_position)
            if sub:
                path.extend(sub[1:])

        return path

    def _bfs(self, start: Position, goal: Position) -> list[Position]:
        """BFS 최단 경로 (격자 내)."""
        from collections import deque
        if start == goal:
            return [start]
        rows, cols = self.env.grid_rows, self.env.grid_cols
        visited: set[Position] = {start}
        queue: deque[list[Position]] = deque([[start]])
        while queue:
            current_path = queue.popleft()
            cx, cy = current_path[-1]
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < rows and 0 <= ny < cols and (nx, ny) not in visited:
                    new_path = current_path + [(nx, ny)]
                    if (nx, ny) == goal:
                        return new_path
                    visited.add((nx, ny))
                    queue.append(new_path)
        return []

    def train_and_get_path(self) -> TrainingResult:
        """Train agent and generate optimal path.

        Returns:
            TrainingResult containing trained environment and optimal path.
        """
        self.train()
        path = self.generate_optimal_path()
        return TrainingResult(env=self.env, path=path)
