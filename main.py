"""Maritime Patrol AI - CLI Version.

Command-line interface for training and visualizing patrol routes.
Run with: python main.py
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

from src.config import DEFAULT_ALPHA, DEFAULT_BETA, DEFAULT_GRID_SIZE, DEFAULT_REWARD_GAMMA
from src.core.trainer import PatrolTrainer, RewardWeights


def visualize_path(trainer: PatrolTrainer, path: list[tuple[int, int]]) -> None:
    """Visualize the patrol path on an influence heatmap.

    Args:
        trainer: Trained PatrolTrainer instance.
        path: List of positions representing the patrol path.
    """
    plt.figure(figsize=(10, 8))

    sns.heatmap(
        trainer.env.influence_map,
        cmap="Reds",
        annot=True,
        fmt=".1f",
        cbar_kws={"label": "Influence Score"},
    )

    path_y = [p[0] + 0.5 for p in path]
    path_x = [p[1] + 0.5 for p in path]

    plt.plot(
        path_x,
        path_y,
        marker="o",
        color="blue",
        linewidth=3,
        markersize=8,
        label="AI Patrol Route",
    )
    plt.scatter(path_x[0], path_y[0], color="green", s=200, label="Start", zorder=5)
    plt.scatter(path_x[-1], path_y[-1], color="black", s=200, label="End", zorder=5)

    plt.title("PoC Result: Influence-based AI Patrol Route")
    plt.legend()
    plt.show()


def main() -> None:
    """Main entry point for CLI application."""
    print("Starting AI patrol route learning...")

    weights = RewardWeights(
        alpha=DEFAULT_ALPHA,
        beta=DEFAULT_BETA,
        gamma=DEFAULT_REWARD_GAMMA,
    )

    trainer = PatrolTrainer(
        grid_rows=DEFAULT_GRID_SIZE,
        weights=weights,
        seed=42,
        episodes=1000,
    )

    print("Training agent...")
    result = trainer.train_and_get_path()

    print("Training complete! Generating optimal route.")
    print(f"Route length: {len(result.path)} cells")
    print(f"Total influence score: {np.sum([result.env.influence_map[p] for p in result.path]):.1f}")

    visualize_path(trainer, result.path)


if __name__ == "__main__":
    main()
