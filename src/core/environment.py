"""Maritime patrol environment for reinforcement learning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

import numpy as np
from numpy.typing import NDArray

from src.config import (
    DEFAULT_MAX_STEPS_MULTIPLIER,
    HIGH_INFLUENCE_COUNT,
    POI_INFLUENCE_THRESHOLD,
    WEATHER_INFLUENCE_WEIGHT,
)

Position: TypeAlias = tuple[int, int]


@dataclass
class StepResult:
    """Result of an environment step."""

    next_state: Position
    hit_wall: bool
    done: bool


class MaritimePatrolEnv:
    """Maritime patrol simulation environment.

    직사각형 격자 지원 (grid_rows x grid_cols).
    """

    def __init__(
        self,
        grid_rows: int,
        grid_cols: int | None = None,
        max_steps: int | None = None,
        seed: int | None = None,
        start_position: Position | None = None,
        end_position: Position | None = None,
    ) -> None:
        """Initialize maritime patrol environment.

        Args:
            grid_rows: 격자 행 수.
            grid_cols: 격자 열 수. None이면 grid_rows와 동일(정사각형).
            max_steps: 최대 스텝. None이면 (rows*cols)^0.5 * 5.
            seed: Random seed.
            start_position: 순찰 시작 (row, col). None이면 (0, 0).
            end_position: 순찰 종료 (row, col). None이면 start_position과 동일.
        """
        if seed is not None:
            np.random.seed(seed)

        self.grid_rows = grid_rows
        self.grid_cols = grid_cols if grid_cols is not None else grid_rows
        self._start_position: Position = start_position or (0, 0)
        self._start_position = (
            max(0, min(self.grid_rows - 1, self._start_position[0])),
            max(0, min(self.grid_cols - 1, self._start_position[1])),
        )
        self._end_position: Position = end_position if end_position is not None else self._start_position
        self._end_position = (
            max(0, min(self.grid_rows - 1, self._end_position[0])),
            max(0, min(self.grid_cols - 1, self._end_position[1])),
        )
        self.state: Position = self._start_position
        base = (self.grid_rows * self.grid_cols) ** 0.5
        self.max_steps = max_steps if max_steps else int(base * DEFAULT_MAX_STEPS_MULTIPLIER)
        self.current_step = 0

        self._init_maps()
        self.visited: NDArray[np.float64] = np.zeros((self.grid_rows, self.grid_cols))
        self._poi: frozenset[Position] = self._compute_poi()

    def _init_maps(self) -> None:
        """관계성 레이어 3개 초기화 (당분간 랜덤. 포맷은 이후 AI 출력과 동일).

        - static_influence, dynamic_influence, weather_condition: 격자별 0~1 스칼라.
        - 복합영향도 = 정적 + 동적 + 환경(weather) 가중합.
        - 고영향도 셀은 HIGH_INFLUENCE_COUNT개만 랜덤 배치.
        - 추후 AI 학습으로 "데이터-순찰경로 연관성" 레이어로 교체 시, 동일 shape/타입 유지.
        """
        r, c = self.grid_rows, self.grid_cols
        total_cells = r * c
        high_count = min(HIGH_INFLUENCE_COUNT, total_cells)

        flat_indices = np.random.choice(total_cells, size=high_count, replace=False)
        high_mask = np.zeros((r, c), dtype=bool)
        high_mask.flat[flat_indices] = True

        self.static_influence = np.zeros((r, c), dtype=np.float64)
        self.static_influence[high_mask] = 0.75 + np.random.rand(high_count) * 0.2
        self.static_influence[~high_mask] = np.random.rand(total_cells - high_count) * 0.14

        self.dynamic_influence = np.random.rand(r, c) * 0.3
        self.weather_condition = np.random.rand(r, c)
        self.influence_map = (
            self.static_influence
            + self.dynamic_influence
            + WEATHER_INFLUENCE_WEIGHT * self.weather_condition
        )

    def _compute_poi(self) -> frozenset[Position]:
        """순찰 필요성 고도(POI) 셀 집합. 정규화된 0.75 이상인 셀."""
        r_min = float(np.min(self.influence_map))
        r_max = float(np.max(self.influence_map))
        r_span = max(r_max - r_min, 1e-6)
        poi: set[Position] = set()
        for row in range(self.grid_rows):
            for col in range(self.grid_cols):
                norm = (float(self.influence_map[row, col]) - r_min) / r_span
                if norm >= POI_INFLUENCE_THRESHOLD:
                    poi.add((row, col))
        return frozenset(poi)

    @property
    def unvisited_poi(self) -> set[Position]:
        """아직 방문하지 않은 POI 셀."""
        return {(r, c) for (r, c) in self._poi if self.visited[r, c] == 0}

    @property
    def grid_size(self) -> int:
        """정사각형 호환용 (rows 사용)."""
        return self.grid_rows

    def reset(self) -> Position:
        """Reset environment to initial state."""
        self.state = self._start_position
        self.current_step = 0
        self.visited = np.zeros((self.grid_rows, self.grid_cols))
        self.visited[self._start_position] = 1
        return self.state

    def step(self, action: int) -> StepResult:
        """Execute one step."""
        x, y = self.state
        old_x, old_y = x, y

        if action == 0:  # Up
            x = max(0, x - 1)
        elif action == 1:  # Down
            x = min(self.grid_rows - 1, x + 1)
        elif action == 2:  # Left
            y = max(0, y - 1)
        elif action == 3:  # Right
            y = min(self.grid_cols - 1, y + 1)

        self.state = (x, y)
        self.current_step += 1
        hit_wall = (x == old_x and y == old_y)
        reached_end = self.state == self._end_position and self.current_step > 0
        # POI(고순찰필요) 전부 방문 후 end에 도착해야 done
        all_poi_visited = all(
            self.visited[r, c] > 0 for (r, c) in self._poi
        ) if self._poi else True
        done = (
            self.current_step >= self.max_steps
            or (reached_end and all_poi_visited)
        )
        return StepResult(next_state=self.state, hit_wall=hit_wall, done=done)

    def mark_visited(self, position: Position) -> None:
        """Mark a position as visited."""
        self.visited[position] = 1

    def is_visited(self, position: Position) -> bool:
        """Check if a position has been visited."""
        return bool(self.visited[position] > 0)
