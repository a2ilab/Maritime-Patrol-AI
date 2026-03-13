"""Streamlit UI components for the patrol application."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeAlias

import numpy as np
import streamlit as st

from src.config import (
    ALPHA_RANGE,
    BETA_RANGE,
    DEFAULT_ALPHA,
    DEFAULT_BETA,
    DEFAULT_REWARD_GAMMA,
    GAMMA_RANGE,
    MAX_GRID_SIZE,
    MIN_GRID_SIZE,
)
from src.ui.strategies import STRATEGIES, get_strategy_name
from src.ui.visualization import create_patrol_figure

if TYPE_CHECKING:
    from src.core.environment import MaritimePatrolEnv

Position: TypeAlias = tuple[int, int]


def init_session_state() -> None:
    """Initialize session state with default values."""
    defaults: dict[str, Any] = {
        "map_seed": 42,
        "alpha": DEFAULT_ALPHA,
        "beta": DEFAULT_BETA,
        "gamma": DEFAULT_REWARD_GAMMA,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def render_strategy_buttons() -> None:
    """Render one-click strategy selection buttons."""
    st.sidebar.subheader("One-Click Strategy")
    col_s1, col_s2, col_s3 = st.sidebar.columns(3)

    if col_s1.button("Safety\nFirst"):
        strategy = STRATEGIES["safety"]
        st.session_state["alpha"] = strategy.alpha
        st.session_state["beta"] = strategy.beta
        st.session_state["gamma"] = strategy.gamma
        st.toast("'Safety First' strategy applied!")

    if col_s2.button("Efficiency\nFirst"):
        strategy = STRATEGIES["efficiency"]
        st.session_state["alpha"] = strategy.alpha
        st.session_state["beta"] = strategy.beta
        st.session_state["gamma"] = strategy.gamma
        st.toast("'Efficiency First' strategy applied!")

    if col_s3.button("Wide\nSurveil"):
        strategy = STRATEGIES["surveillance"]
        st.session_state["alpha"] = strategy.alpha
        st.session_state["beta"] = strategy.beta
        st.session_state["gamma"] = strategy.gamma
        st.toast("'Wide Surveillance' strategy applied!")


def render_parameter_sliders() -> tuple[float, float, float]:
    """Render parameter adjustment sliders.

    Returns:
        Tuple of (alpha, beta, gamma) values.
    """
    st.sidebar.subheader("Parameter Settings")

    alpha: float = st.sidebar.slider(
        "Influence Weight (Alpha)",
        min_value=ALPHA_RANGE[0],
        max_value=ALPHA_RANGE[1],
        key="alpha",
    )
    beta: float = st.sidebar.slider(
        "Movement Cost (Beta)",
        min_value=BETA_RANGE[0],
        max_value=BETA_RANGE[1],
        key="beta",
    )
    gamma: float = st.sidebar.slider(
        "Surveillance Effect (Gamma)",
        min_value=GAMMA_RANGE[0],
        max_value=GAMMA_RANGE[1],
        key="gamma",
    )

    return alpha, beta, gamma


def render_sidebar() -> tuple[int, float, float, float]:
    """Render complete sidebar UI.

    Returns:
        Tuple of (grid_size, alpha, beta, gamma).
    """
    st.sidebar.header("Simulation Control")

    if st.sidebar.button("Generate New Map", use_container_width=True):
        st.session_state["map_seed"] = int(np.random.randint(0, 1000))

    st.sidebar.divider()
    render_strategy_buttons()
    st.sidebar.divider()

    grid_size: int = st.sidebar.slider(
        "Grid Size",
        min_value=MIN_GRID_SIZE,
        max_value=MAX_GRID_SIZE,
        value=10,
    )
    alpha, beta, gamma = render_parameter_sliders()

    return grid_size, alpha, beta, gamma


def render_main_content(
    env: MaritimePatrolEnv,
    path: list[Position],
    alpha: float,
    beta: float,
    gamma: float,
) -> None:
    """Render main content area with map and report.

    Args:
        env: Maritime patrol environment.
        path: Generated patrol path.
        alpha: Current alpha parameter.
        beta: Current beta parameter.
        gamma: Current gamma parameter.
    """
    col1, col2 = st.columns([3, 1])

    with col1:
        st.subheader(f"Route Analysis (Map ID: {st.session_state['map_seed']})")
        fig = create_patrol_figure(env, path)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Report")
        total_influence = float(np.sum([env.influence_map[p] for p in path]))
        strategy_name = get_strategy_name(alpha, beta, gamma)

        st.info(f"Current Strategy: **{strategy_name}**")
        st.metric("Total Distance", f"{len(path)} cells")
        st.metric("Influence Score", f"{total_influence:.1f}")
        st.markdown("---")
        st.caption("Click sidebar buttons to change strategy.")
