"""난수 생성 전용 클래스. 시드 범위 내에서 변동 가능한 시드/난수 제공."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from numpy.random import Generator


# 기본 시드 범위 (0 ~ 999,999)
DEFAULT_SEED_RANGE: tuple[int, int] = (0, 999_999)


class RandomGenerator:
    """시드 범위 내에서 난수를 생성하는 전용 클래스.

    requestId 등 고정값만으로 시드가 결정되지 않도록,
    시간·시스템 난수 등을 활용해 매번 변동되는 시드를 제공.
    """

    def __init__(
        self,
        seed_range: tuple[int, int] = DEFAULT_SEED_RANGE,
        base: int | None = None,
    ) -> None:
        """초기화.

        Args:
            seed_range: 시드 후보 범위 (min, max) 포함.
            base: 재현성이 필요할 때 사용할 기준값. None이면 완전 변동.
        """
        self.seed_min, self.seed_max = seed_range
        self.base = base
        self._rng: Generator | None = None

    def get_seed(self) -> int:
        """시드 범위 내에서 변동되는 시드 반환.

        base가 있으면 base + 변동분, 없으면 시간·난수 기반.
        """
        span = self.seed_max - self.seed_min + 1
        # 시간 + 시스템 난수로 변동분 생성
        ns = int(time.time_ns()) % (2**32)
        try:
            import secrets
            extra = secrets.randbelow(span)
        except ImportError:
            extra = hash(str(time.perf_counter())) % span
        offset = (ns + extra) % span
        seed = self.seed_min + offset
        if self.base is not None:
            seed = (self.base + offset) % span + self.seed_min
        return seed

    def get_rng(self) -> Generator:
        """현재 시드로 생성된 numpy Generator 반환."""
        if self._rng is None:
            self._rng = np.random.default_rng(self.get_seed())
        return self._rng

    def reset(self) -> None:
        """새 시드로 Generator 재생성 (다음 get_rng 호출 시)."""
        self._rng = None
