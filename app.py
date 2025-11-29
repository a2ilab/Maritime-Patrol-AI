"""Maritime Patrol AI - Streamlit Web Application.

AI-based autonomous patrol route generation system.
Run with: streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

from src.core.trainer import PatrolTrainer, RewardWeights
from src.ui.components import init_session_state, render_main_content, render_sidebar

st.set_page_config(page_title="AI Maritime Patrol PoC", layout="wide")


@st.cache_resource(show_spinner="Analyzing optimal route based on strategy...")
def train_and_get_path(
    grid_size: int,
    alpha: float,
    beta: float,
    gamma: float,
    map_seed: int,
) -> tuple:
    """Train agent and generate optimal path with caching.

    Args:
        grid_size: Size of the patrol grid.
        alpha: Risk weight parameter.
        beta: Movement cost parameter.
        gamma: Surveillance effect parameter.
        map_seed: Random seed for map generation.

    Returns:
        Tuple of (environment, path).
    """
    weights = RewardWeights(alpha=alpha, beta=beta, gamma=gamma)
    trainer = PatrolTrainer(grid_size=grid_size, weights=weights, seed=map_seed)
    result = trainer.train_and_get_path()
    return result.env, result.path


def main() -> None:
    """Main application entry point."""
    init_session_state()

    st.title("AI Autonomous Patrol Route Generator")
    st.markdown("---")

    grid_size, alpha, beta, gamma = render_sidebar()

    env, path = train_and_get_path(
        grid_size=grid_size,
        alpha=alpha,
        beta=beta,
        gamma=gamma,
        map_seed=st.session_state["map_seed"],
    )

    render_main_content(env, path, alpha, beta, gamma)


if __name__ == "__main__":
    main()
