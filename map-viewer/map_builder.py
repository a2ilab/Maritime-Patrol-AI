"""API 응답을 Folium 지도로 변환."""

from __future__ import annotations

from typing import Any

import folium
from folium import Circle, Marker, PolyLine
from folium.plugins import Fullscreen, MeasureControl

# 부산 해역 중심 (기본 줌)
DEFAULT_CENTER: tuple[float, float] = (35.15, 129.05)
DEFAULT_ZOOM: int = 12


def build_base_map() -> str:
    """경로 없이 기본 지도만 생성 (초기 표시용)."""
    m = folium.Map(
        location=DEFAULT_CENTER,
        zoom_start=DEFAULT_ZOOM,
        tiles="OpenStreetMap",
        control_scale=True,
        width="100%",
        height=500,
    )
    Fullscreen().add_to(m)
    MeasureControl().add_to(m)
    return m._repr_html_()


def build_map_from_response(data: dict[str, Any]) -> str:
    """API 응답 JSON → Folium 지도 HTML 문자열.

    Args:
        data: InferenceResponse JSON (dict).

    Returns:
        지도 HTML 문자열.
    """
    m = folium.Map(
        location=DEFAULT_CENTER,
        zoom_start=DEFAULT_ZOOM,
        tiles="OpenStreetMap",
        control_scale=True,
        width="100%",
        height=500,
    )
    Fullscreen().add_to(m)
    MeasureControl().add_to(m)

    routes = data.get("routes", [])
    zones = data.get("patrolZones", data.get("accidents", []))
    labels = data.get("labels", [])

    # 경로 (Polyline)
    for route in routes:
        path = [(p["lat"], p["lng"]) for p in route.get("path", [])]
        if path:
            PolyLine(
                path,
                color="blue",
                weight=5,
                opacity=0.8,
                popup=route.get("name", "Route"),
            ).add_to(m)
            # 출발/도착 마커
            Marker(
                path[0],
                popup="출발",
                icon=folium.Icon(color="green", icon="play"),
            ).add_to(m)
            Marker(
                path[-1],
                popup="도착",
                icon=folium.Icon(color="black", icon="stop"),
            ).add_to(m)

    # 순찰 지역 (Circle)
    for acc in zones:
        center = acc.get("center", {})
        lat, lng = center.get("lat"), center.get("lng")
        if lat is None or lng is None:
            continue
        radius = acc.get("radius", 500)
        label = acc.get("label", "위험 구역")
        Circle(
            location=(lat, lng),
            radius=radius,
            color="red",
            fill=True,
            fill_color="red",
            fill_opacity=0.3,
            popup=f"{label} (반경 {radius:.0f}m)",
        ).add_to(m)

    # 라벨 (Marker)
    for lb in labels:
        lat, lng = lb.get("lat"), lb.get("lng")
        text = lb.get("text", "")
        if lat is None or lng is None:
            continue
        Marker(
            (lat, lng),
            popup=text,
            tooltip=text,
            icon=folium.Icon(color="orange", icon="info-sign"),
        ).add_to(m)

    # bounds 자동 조정
    if routes or zones or labels:
        bounds = []
        for r in routes:
            bounds.extend([(p["lat"], p["lng"]) for p in r.get("path", [])])
        for a in zones:
            c = a.get("center", {})
            if "lat" in c and "lng" in c:
                bounds.append((c["lat"], c["lng"]))
        for lb in labels:
            bounds.append((lb["lat"], lb["lng"]))
        if bounds:
            m.fit_bounds(bounds, padding=50)

    return m._repr_html_()
