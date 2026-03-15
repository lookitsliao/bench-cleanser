"""Trajectory validation subpackage for bench-cleanser.

Loads agent trajectories, classifies them for leakage patterns, and
produces per-trajectory analysis of whether solutions were genuinely
derived from the problem statement or show evidence of benchmark leakage.
"""

from bench_cleanser.trajectory.models import (
    LeakagePattern,
    TrajectoryAction,
    TrajectoryAnalysis,
    TrajectoryRecord,
)

__all__ = [
    "LeakagePattern",
    "TrajectoryAction",
    "TrajectoryAnalysis",
    "TrajectoryRecord",
]
