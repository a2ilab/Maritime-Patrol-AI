"""Q-Learning 기반 세그먼트 경로 계획.

influence_map + polygon mask 위에서 start → end 경로를
Q-Learning으로 학습하여 반환한다.
"""

from __future__ import annotations

from collections import deque

import numpy as np
from numpy.typing import NDArray

# --- 하이퍼파라미터 (세그먼트 단위이므로 가볍게) -----
_EPISODES: int = 250
_EPSILON_START: float = 1.0
_EPSILON_DECAY: float = 0.985
_EPSILON_MIN: float = 0.01
_LR: float = 0.2
_GAMMA: float = 0.95
_MAX_STEPS_MULT: int = 5
_EARLY_STOP_STREAK: int = 15

# 보상·패널티
_WALL_PENALTY: float = -5.0
_REVISIT_PENALTY: float = -2.0
_HIGH_INFLUENCE_BONUS: float = 3.0
_ARRIVAL_BONUS: float = 20.0
_STEP_COST: float = -0.1
# 이동 방향과 목적지 방향 사이 각도별 보상 (구간: 각도 상한, 보상값)
_DIRECTION_BANDS: list[tuple[float, float]] = [
    (40.0, 1.0),
    (80.0, 0.5),
    (120.0, 0.0),
    (180.1, -2.0),
]

# 4방향: 상, 하, 좌, 우
_ACTIONS = [(-1, 0), (1, 0), (0, -1), (0, 1)]


def _bfs_fallback(
    start: tuple[int, int],
    goal: tuple[int, int],
    rows: int,
    cols: int,
    walkable: NDArray[np.bool_] | None,
) -> list[tuple[int, int]]:
    """Q-Learning 실패 시 BFS 최단 경로 폴백."""
    if start == goal:
        return [start]
    visited: set[tuple[int, int]] = {start}
    queue: deque[list[tuple[int, int]]] = deque([[start]])
    while queue:
        path = queue.popleft()
        r, c = path[-1]
        for dr, dc in _ACTIONS:
            nr, nc = r + dr, c + dc
            if nr < 0 or nr >= rows or nc < 0 or nc >= cols:
                continue
            if (nr, nc) in visited:
                continue
            if walkable is not None and not walkable[nr, nc]:
                continue
            new_path = path + [(nr, nc)]
            if (nr, nc) == goal:
                return new_path
            visited.add((nr, nc))
            queue.append(new_path)
    return [start, goal]


def plan_segment(
    influence_map: NDArray[np.float64],
    start: tuple[int, int],
    end: tuple[int, int],
    poly_mask: NDArray[np.bool_] | None = None,
    episodes: int = _EPISODES,
) -> list[tuple[int, int]]:
    """start → end 세그먼트를 Q-Learning으로 계획.

    Args:
        influence_map: (rows, cols) 형태의 순찰 필요성 맵 (0~1 정규화 권장).
        start: 출발 격자 (row, col).
        end: 도착 격자 (row, col).
        poly_mask: (rows, cols) bool 배열. True=이동 가능, False=벽.
        episodes: 학습 에피소드 수.

    Returns:
        (row, col) 리스트. start와 end를 포함한다.
    """
    rows, cols = influence_map.shape
    if start == end:
        return [start]

    walkable: NDArray[np.bool_] | None = poly_mask
    if walkable is not None:
        walkable[start[0], start[1]] = True
        walkable[end[0], end[1]] = True

    max_steps = int((rows * cols) ** 0.5 * _MAX_STEPS_MULT)
    q_table = np.zeros((rows, cols, 4), dtype=np.float64)
    epsilon = _EPSILON_START

    r_min = float(np.min(influence_map))
    r_max = float(np.max(influence_map))
    r_span = max(r_max - r_min, 1e-6)
    norm_map = (influence_map - r_min) / r_span

    end_r, end_c = end
    arrival_streak = 0

    for _ep in range(episodes):
        state = start
        reached_goal = False
        visited_set: set[tuple[int, int]] = {state}
        for _step in range(max_steps):
            sr, sc = state
            if np.random.rand() < epsilon:
                action = int(np.random.randint(4))
            else:
                action = int(np.argmax(q_table[sr, sc]))

            dr, dc = _ACTIONS[action]
            nr, nc = sr + dr, sc + dc

            hit_wall = False
            if nr < 0 or nr >= rows or nc < 0 or nc >= cols:
                hit_wall = True
            elif walkable is not None and not walkable[nr, nc]:
                hit_wall = True

            if hit_wall:
                reward = _WALL_PENALTY
                next_state = state
            else:
                next_state = (nr, nc)
                inf_val = float(norm_map[nr, nc])
                if next_state in visited_set:
                    reward = _REVISIT_PENALTY
                else:
                    reward = inf_val * _HIGH_INFLUENCE_BONUS + _STEP_COST
                    visited_set.add(next_state)

                goal_dr = end_r - sr
                goal_dc = end_c - sc
                if goal_dr != 0 or goal_dc != 0:
                    dot = dr * goal_dr + dc * goal_dc
                    mag_move = (dr * dr + dc * dc) ** 0.5
                    mag_goal = (goal_dr * goal_dr + goal_dc * goal_dc) ** 0.5
                    cos_val = dot / (mag_move * mag_goal + 1e-9)
                    cos_val = max(-1.0, min(1.0, cos_val))
                    angle_deg = np.degrees(np.arccos(cos_val))
                    for band_limit, band_reward in _DIRECTION_BANDS:
                        if angle_deg <= band_limit:
                            reward += band_reward
                            break

            if next_state == end:
                reward += _ARRIVAL_BONUS

            old_q = q_table[sr, sc, action]
            nsr, nsc = next_state
            next_max = float(np.max(q_table[nsr, nsc]))
            q_table[sr, sc, action] = old_q + _LR * (
                reward + _GAMMA * next_max - old_q
            )

            state = next_state
            if state == end:
                reached_goal = True
                break

        if reached_goal:
            arrival_streak += 1
            if arrival_streak >= _EARLY_STOP_STREAK:
                break
        else:
            arrival_streak = 0
        epsilon = max(_EPSILON_MIN, epsilon * _EPSILON_DECAY)

    state = start
    path: list[tuple[int, int]] = [state]
    visited_gen: set[tuple[int, int]] = {state}
    for _ in range(max_steps):
        sr, sc = state
        action = int(np.argmax(q_table[sr, sc]))
        dr, dc = _ACTIONS[action]
        nr, nc = sr + dr, sc + dc
        oob = nr < 0 or nr >= rows or nc < 0 or nc >= cols
        blocked = (walkable is not None and not oob and not walkable[nr, nc])
        if oob or blocked:
            break
        state = (nr, nc)
        path.append(state)
        if state == end:
            break
        if state in visited_gen:
            break
        visited_gen.add(state)

    if path[-1] != end:
        bfs = _bfs_fallback(path[-1], end, rows, cols, walkable)
        if len(bfs) > 1:
            path.extend(bfs[1:])

    return path


def plan_full_route(
    influence_maps: list[NDArray[np.float64]],
    ordered_waypoints: list[tuple[int, int]],
    waypoint_slot_indices: list[int],
    poly_mask: NDArray[np.bool_] | None = None,
    episodes: int = _EPISODES,
) -> list[tuple[int, int]]:
    """여러 웨이포인트를 순서대로 순회하는 전체 경로를 Q-Learning으로 생성.

    Args:
        influence_maps: 시간대별 influence_map 리스트 (index 0 = slot 1).
        ordered_waypoints: 순서대로 방문할 격자 좌표 리스트 (start, wp1, wp2, ..., end).
        waypoint_slot_indices: 각 웨이포인트가 속한 시간대 인덱스 (0-based).
            두 웨이포인트 사이 세그먼트에서는 **도착 쪽**의 시간대 맵을 사용한다.
        poly_mask: (rows, cols) bool 배열. True=이동 가능.
        episodes: 세그먼트당 학습 에피소드 수.

    Returns:
        (row, col) 리스트. 첫 웨이포인트부터 마지막까지 연결된 전체 경로.
    """
    if len(ordered_waypoints) < 2:
        return list(ordered_waypoints)

    full_path: list[tuple[int, int]] = []
    for i in range(len(ordered_waypoints) - 1):
        seg_start = ordered_waypoints[i]
        seg_end = ordered_waypoints[i + 1]
        slot_idx = waypoint_slot_indices[min(i + 1, len(waypoint_slot_indices) - 1)]
        slot_idx = max(0, min(slot_idx, len(influence_maps) - 1))
        inf_map = influence_maps[slot_idx]

        mask_copy = poly_mask.copy() if poly_mask is not None else None
        seg_path = plan_segment(inf_map, seg_start, seg_end, mask_copy, episodes)

        if i == 0:
            full_path.extend(seg_path)
        else:
            full_path.extend(seg_path[1:])

    return full_path
