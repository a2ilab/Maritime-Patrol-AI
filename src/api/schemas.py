"""Pydantic schemas for REST API (opinion.pptx JSON 스펙 기반)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# --- Request ---


class LatLngPointInput(BaseModel):
    """위도·경도 좌표 (입력용)."""

    lat: float
    lng: float


class FilterRequest(BaseModel):
    """요청 필터."""

    startTime: str = Field(..., description="시작 시간 (ISO 8601)")
    endTime: str = Field(..., description="종료 시간 (ISO 8601)")
    shipId: str = Field(default="ALL", description="선박 ID")

    accidentType: str = Field(default="ALL", description="사고 유형")


class OptionsRequest(BaseModel):
    """출력 옵션."""

    includeRoute: bool = Field(default=True, description="경로 포함 여부")
    includeAccidentZone: bool = Field(
        default=True,
        description="순찰 지역 포함 여부 (하위 호환: includeAccidentZone)",
    )
    includeLabels: bool = Field(default=True, description="라벨 포함 여부")
    includeGrid: bool = Field(default=True, description="격자 표시 여부")


class InferenceRequest(BaseModel):
    """추론 API 요청 (입력 JSON)."""

    requestId: str = Field(..., description="요청 ID")
    filter: FilterRequest = Field(..., description="필터 조건")
    options: OptionsRequest = Field(default_factory=OptionsRequest, description="출력 옵션")

    # 전략 파라미터 (선택)
    strategy: Literal["safety", "efficiency", "surveillance"] | None = Field(
        default="safety",
        description="순찰 전략",
    )
    map_seed: int | None = Field(
        default=None,
        description="맵 시드 (재현성). 미지정 시 requestId에서 유도",
    )
    # 순찰/경비 지역 Polygon (WGS84). 최소 2점 이상. 2점이면 대각 꼭짓점으로 bbox 생성.
    polygon: list[LatLngPointInput] | None = Field(
        default=None,
        description="순찰 지역 Polygon [lat,lng] 배열. None이면 기본 영역 사용",
    )
    # 순찰 시작 위치. port="gunsan"이면 (35.97530, 126.5657) 사용.
    port: Literal["gunsan"] | None = Field(
        default="gunsan",
        description="출발 항구. gunsan=군산항(35.97530, 126.5657)",
    )
    start_position: LatLngPointInput | None = Field(
        default=None,
        description="순찰 시작 좌표. port 지정 시 무시됨",
    )
    end_position: LatLngPointInput | None = Field(
        default=None,
        description="순찰 종료 좌표. 미지정 시 시작지점과 동일",
    )


# --- Response ---


class LatLngPoint(BaseModel):
    """위도·경도 좌표."""

    lat: float
    lng: float


class Route(BaseModel):
    """순찰 경로."""

    routeId: str
    name: str
    path: list[LatLngPoint]


class PatrolZone(BaseModel):
    """순찰 지역 (복합영향도 기반). 감시·경고·대형사고 예방 등."""

    id: str
    type: str = Field(..., description="예: 고위험, 위험")
    label: str = Field(..., description="예: 순찰필요 고도, 순찰필요")
    center: LatLngPoint
    radius: float = Field(..., description="반경 (미터). 75→최대의 50%, 100→최대")
    count: int = Field(default=0, description="참고용")
    patrolNecessity: float = Field(default=0.0, description="순찰 필요성 0~1 (75 이상만 원 표시)")
    # 복합영향도 계산 3요소 (0~1, 퍼센트로 표시)
    staticScore: float = Field(default=0.0, description="정적위험 점수")
    dynamicScore: float = Field(default=0.0, description="동적위험 점수")
    environmentScore: float = Field(default=0.0, description="환경제약 점수")


class Label(BaseModel):
    """지도 표시용 라벨."""

    text: str
    lat: float
    lng: float


class Summary(BaseModel):
    """요약 정보."""

    routeCount: int
    patrolZoneCount: int = Field(
        default=0,
        description="순찰필요 영역 수 (감시·경고·대형사고 예방 등)",
    )
    accidentCount: int = Field(
        default=0,
        description="patrolZoneCount와 동일 (하위 호환)",
    )


class GridBbox(BaseModel):
    """격자 경계 상자."""

    latMin: float
    latMax: float
    lngMin: float
    lngMax: float


class GridLine(BaseModel):
    """격자선 1개 (시작~끝)."""

    start: LatLngPoint
    end: LatLngPoint


class GridInfo(BaseModel):
    """격자 정보 (웹 뷰어 표시용)."""

    bbox: GridBbox
    rows: int
    cols: int
    lines: list[GridLine] = Field(default_factory=list, description="격자선 좌표 (수평+수직)")
    influence: list[float] = Field(
        default_factory=list,
        description="셀별 복합영향도 0~1 (행우선). 색상 그라데이션용",
    )
    staticInfluence: list[float] = Field(
        default_factory=list,
        description="셀별 정적위험 0~1 (행우선)",
    )
    dynamicInfluence: list[float] = Field(
        default_factory=list,
        description="셀별 동적위험 0~1 (행우선)",
    )
    environmentInfluence: list[float] = Field(
        default_factory=list,
        description="셀별 환경제약 0~1 (행우선)",
    )


class InferenceResponse(BaseModel):
    """추론 API 응답 (출력 JSON)."""

    success: bool = Field(
        default=True,
        description="서비스 동작 여부. 시작 지점 미지정 시 false",
    )
    requestId: str
    summary: Summary
    routes: list[Route] = Field(default_factory=list)
    patrolZones: list[PatrolZone] = Field(
        default_factory=list,
        description="순찰 지역 목록",
    )
    labels: list[Label] = Field(default_factory=list)
    grid: GridInfo | None = Field(default=None, description="격자 정보. includeGrid 시 포함")
