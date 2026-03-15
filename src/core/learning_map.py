"""학습 맵 모델: 데이터별 그래프 + 그래프별 가중치.

algorithm.md §3·§4에 따른 추론용 모델. 실제 학습은 미구현이며,
동일 포맷으로 랜덤 그래프·가중치를 채워 '학습된 것처럼' 동작한다.
랜덤으로 생성한 모델은 models/ 에 저장해 재활용한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

import numpy as np
from numpy.typing import NDArray

# 학습 맵 저장 경로 (프로젝트 루트 기준 models/)
_MODELS_DIR: Path = Path(__file__).resolve().parent.parent.parent / "models"
LEARNING_MAP_FILENAME: str = "patrol_learning_map.npz"


class IndicatorDef(NamedTuple):
    """지표 정의: 이름, 값 범위 (min, max)."""

    name: str
    min_val: float
    max_val: float


# 기본 지표 3종 (정적/동적/환경 레이어와 1:1 대응 가능)
DEFAULT_INDICATORS: tuple[IndicatorDef, ...] = (
    IndicatorDef("surface_current_kn", 0.0, 8.0),   # 표층 해류 (노트)
    IndicatorDef("wind_speed_kn", 0.0, 30.0),        # 풍속 (노트)
    IndicatorDef("visibility_km", 0.0, 20.0),       # 시정 (km)
)


def _piecewise_linear(x: NDArray[np.float64], breakpoints: list[tuple[float, float]]) -> NDArray[np.float64]:
    """구간별 선형 함수. breakpoints는 (x, y) 리스트, x 오름차순."""
    out = np.zeros_like(x, dtype=np.float64)
    for i in range(len(breakpoints) - 1):
        x0, y0 = breakpoints[i]
        x1, y1 = breakpoints[i + 1]
        mask = (x >= x0) & (x < x1)
        if x1 > x0:
            out[mask] = y0 + (x[mask] - x0) * (y1 - y0) / (x1 - x0)
        else:
            out[mask] = y1
    # 마지막 구간: x >= last_x
    if breakpoints:
        x_last, y_last = breakpoints[-1]
        out[x >= x_last] = y_last
    return np.clip(out, 0.0, 1.0)


@dataclass
class IndicatorGraph:
    """지표값 → 순찰 영향도(0~1) 그래프. 구간별 선형(학습 결과 시뮬레이션)."""

    breakpoints: list[tuple[float, float]] = field(default_factory=list)

    def apply(self, values: NDArray[np.float64]) -> NDArray[np.float64]:
        """값 배열에 그래프 적용 → 영향도 배열."""
        if not self.breakpoints:
            return np.zeros_like(values)
        return _piecewise_linear(values, self.breakpoints)


def _random_breakpoints(rng: np.random.Generator, ind: IndicatorDef, n: int = 5) -> list[tuple[float, float]]:
    """지표 범위 내에서 랜덤 구간점 생성 (학습된 그래프 시뮬레이션)."""
    lo, hi = ind.min_val, ind.max_val
    x = np.sort(rng.uniform(lo, hi, size=n))
    x = np.unique(np.clip(x, lo, hi))
    if len(x) < 2:
        x = np.array([lo, hi])
    # 0~1 구간에서 낮은 값은 낮은 영향, 높은 값은 높은 영향 경향
    y = np.sort(rng.uniform(0.0, 1.0, size=len(x)))
    return [(float(xi), float(yi)) for xi, yi in zip(x, y)]


@dataclass
class InferenceModel:
    """학습 맵 모델: 지표별 그래프 + 지표별 가중치."""

    indicators: tuple[IndicatorDef, ...] = DEFAULT_INDICATORS
    graphs: list[IndicatorGraph] = field(default_factory=list)
    weights: NDArray[np.float64] = field(default_factory=lambda: np.array([]))

    def __post_init__(self) -> None:
        n = len(self.indicators)
        if len(self.graphs) != n:
            self.graphs = [IndicatorGraph(breakpoints=[]) for _ in range(n)]
        if len(self.weights) != n:
            self.weights = np.ones(n, dtype=np.float64) / n

    @classmethod
    def random_from_seed(cls, seed: int, indicators: tuple[IndicatorDef, ...] = DEFAULT_INDICATORS) -> InferenceModel:
        """시드로 랜덤 그래프·가중치 생성 (학습 결과를 랜덤으로 채운 것과 동일)."""
        rng = np.random.default_rng(seed)
        graphs = [
            IndicatorGraph(breakpoints=_random_breakpoints(rng, ind))
            for ind in indicators
        ]
        w = rng.uniform(0.2, 1.0, size=len(indicators))
        w = w / w.sum()
        return cls(indicators=indicators, graphs=graphs, weights=w)

    def save(self, path: Path | None = None) -> Path:
        """모델을 npz로 저장. path 미지정 시 models/patrol_learning_map.npz."""
        path = path or (_MODELS_DIR / LEARNING_MAP_FILENAME)
        path.parent.mkdir(parents=True, exist_ok=True)
        # 그래프별 breakpoints: (x배열, y배열) 리스트 → 가변 길이이므로 패딩하여 저장
        max_bp = max(len(g.breakpoints) for g in self.graphs) if self.graphs else 0
        n = len(self.graphs)
        bp_x = np.full((n, max_bp), np.nan, dtype=np.float64)
        bp_y = np.full((n, max_bp), np.nan, dtype=np.float64)
        for i, g in enumerate(self.graphs):
            for j, (x, y) in enumerate(g.breakpoints):
                bp_x[i, j] = x
                bp_y[i, j] = y
        np.savez_compressed(
            path,
            weights=self.weights,
            bp_x=bp_x,
            bp_y=bp_y,
            n_indicators=np.int32(n),
        )
        return path

    @classmethod
    def load(cls, path: Path | None = None, indicators: tuple[IndicatorDef, ...] = DEFAULT_INDICATORS) -> InferenceModel | None:
        """저장된 모델 로드. 실패 시 None."""
        path = path or (_MODELS_DIR / LEARNING_MAP_FILENAME)
        if not path.exists():
            return None
        try:
            data = np.load(path, allow_pickle=False)
            n = int(data["n_indicators"])
            if n != len(indicators):
                return None
            weights = np.asarray(data["weights"], dtype=np.float64)
            bp_x = np.asarray(data["bp_x"], dtype=np.float64)
            bp_y = np.asarray(data["bp_y"], dtype=np.float64)
            graphs = []
            for i in range(n):
                xs = bp_x[i, :]
                ys = bp_y[i, :]
                valid = ~np.isnan(xs)
                bp = [(float(xs[j]), float(ys[j])) for j in range(len(xs)) if valid[j]]
                graphs.append(IndicatorGraph(breakpoints=bp))
            return cls(indicators=indicators, graphs=graphs, weights=weights)
        except Exception:
            return None

    def apply(
        self,
        data_grid: NDArray[np.float64],
    ) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
        """data_grid: (rows, cols, n_indicators). 반환: influence_map, static, dynamic, environment."""
        r, c, k = data_grid.shape
        influence_layers = np.zeros((r, c, k), dtype=np.float64)
        for i in range(k):
            influence_layers[:, :, i] = self.graphs[i].apply(data_grid[:, :, i])
        # 가중 합 → 최종 순찰 필요성
        influence_map = np.zeros((r, c), dtype=np.float64)
        for i in range(k):
            influence_map += self.weights[i] * influence_layers[:, :, i]
        # 정규화 0~1 (선택). 이미 0~1 구간이면 스케일만 맞춤
        imin, imax = float(np.min(influence_map)), float(np.max(influence_map))
        span = max(imax - imin, 1e-6)
        influence_map = np.clip((influence_map - imin) / span, 0.0, 1.0)
        # 3레이어 호환: static = 0번, dynamic = 1번, environment = 2번
        static = influence_layers[:, :, 0] if k >= 1 else np.zeros((r, c))
        dynamic = influence_layers[:, :, 1] if k >= 2 else np.zeros((r, c))
        environment = influence_layers[:, :, 2] if k >= 3 else np.zeros((r, c))
        return influence_map, static, dynamic, environment


def generate_random_data(
    rows: int,
    cols: int,
    indicators: tuple[IndicatorDef, ...],
    seed: int,
) -> NDArray[np.float64]:
    """격자 셀별 지표값 랜덤 생성. 반환 shape: (rows, cols, n_indicators)."""
    rng = np.random.default_rng(seed)
    k = len(indicators)
    out = np.zeros((rows, cols, k), dtype=np.float64)
    for i, ind in enumerate(indicators):
        out[:, :, i] = rng.uniform(ind.min_val, ind.max_val, size=(rows, cols))
    return out
