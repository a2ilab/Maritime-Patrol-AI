"""Visualization utilities for patrol routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeAlias

import plotly.graph_objects as go

if TYPE_CHECKING:
    from src.core.environment import MaritimePatrolEnv

Position: TypeAlias = tuple[int, int]


def create_hover_text(env: MaritimePatrolEnv) -> list[list[str]]:
    """Create hover text for heatmap cells.

    Args:
        env: Maritime patrol environment.

    Returns:
        2D list of hover text strings.
    """
    gs = env.grid_size
    return [
        [f"({r},{c})\nRisk: {env.risk_map[r][c]:.2f}" for c in range(gs)]
        for r in range(gs)
    ]


def create_patrol_figure(
    env: MaritimePatrolEnv,
    path: list[Position],
) -> go.Figure:
    """Create Plotly figure for patrol visualization.

    Args:
        env: Maritime patrol environment with risk maps.
        path: List of positions representing the patrol path.

    Returns:
        Plotly Figure object.
    """
    hover_text = create_hover_text(env)

    fig = go.Figure()

    fig.add_trace(
        go.Heatmap(
            z=env.risk_map,
            text=hover_text,
            hoverinfo="text",
            texttemplate="%{z:.1f}",
            textfont={"size": 12},
            colorscale="Reds",
            name="Risk",
        )
    )

    path_x = [p[1] for p in path]
    path_y = [p[0] for p in path]

    fig.add_trace(
        go.Scatter(
            x=path_x,
            y=path_y,
            mode="lines+markers",
            line={"color": "blue", "width": 4},
            name="Path",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=[path_x[0]],
            y=[path_y[0]],
            mode="markers",
            marker={"size": 12, "color": "green"},
            name="Start",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=[path_x[-1]],
            y=[path_y[-1]],
            mode="markers",
            marker={"size": 12, "color": "black"},
            name="End",
        )
    )

    fig.update_layout(
        height=600,
        yaxis={"autorange": "reversed"},
        margin={"l": 10, "r": 10, "t": 10, "b": 10},
    )

    return fig
