"""Paired bootstrap used by the frozen ablation.

The interval is the 2.5 and 97.5 percentiles of the resampled mean difference.
NumPy 1.26.4, method "linear". Seed 0 and 10,000 resamples are the protocol
defaults. A contrast clears only when the lower bound is strictly above 0.
"""

from __future__ import annotations

import numpy as np


def paired_bootstrap(
    left: list[int] | np.ndarray,
    right: list[int] | np.ndarray,
    n_resamples: int = 10_000,
    seed: int = 0,
) -> dict:
    a = np.asarray(left, dtype=np.float64)
    b = np.asarray(right, dtype=np.float64)
    if a.shape != b.shape or a.ndim != 1 or a.size == 0:
        raise ValueError("paired outcomes must be equal-length and non-empty")
    diff = a - b
    point = float(diff.mean())
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, diff.size, size=(n_resamples, diff.size))
    means = diff[draws].mean(axis=1)
    lo, hi = np.quantile(means, [0.025, 0.975], method="linear")
    left_only = int(np.sum((a == 1) & (b == 0)))
    right_only = int(np.sum((a == 0) & (b == 1)))
    return {
        "n": int(diff.size),
        "left_rate": float(a.mean()),
        "right_rate": float(b.mean()),
        "diff": point,
        "ci_low": float(lo),
        "ci_high": float(hi),
        "clears": bool(lo > 0),
        "left_only": left_only,
        "right_only": right_only,
    }


def unpaired_diff_bootstrap(
    left: list[int] | np.ndarray,
    right: list[int] | np.ndarray,
    n_resamples: int = 10_000,
    seed: int = 0,
) -> dict:
    """Difference of two independent rates. Each side is resampled on its own."""
    a = np.asarray(left, dtype=np.float64)
    b = np.asarray(right, dtype=np.float64)
    if a.ndim != 1 or b.ndim != 1 or a.size == 0 or b.size == 0:
        raise ValueError("rates must be non-empty vectors")
    point = float(a.mean() - b.mean())
    rng = np.random.default_rng(seed)
    a_means = a[rng.integers(0, a.size, size=(n_resamples, a.size))].mean(axis=1)
    b_means = b[rng.integers(0, b.size, size=(n_resamples, b.size))].mean(axis=1)
    diffs = a_means - b_means
    lo, hi = np.quantile(diffs, [0.025, 0.975], method="linear")
    return {
        "n_left": int(a.size),
        "n_right": int(b.size),
        "left_rate": float(a.mean()),
        "right_rate": float(b.mean()),
        "diff": point,
        "ci_low": float(lo),
        "ci_high": float(hi),
        "clears": bool(lo > 0),
    }


def bootstrap_versus_best(
    society: list[int] | np.ndarray,
    subjects: dict[str, list[int]],
    n_resamples: int = 10_000,
    seed: int = 0,
) -> dict:
    """Society minus the best single subject.

    The best subject is chosen on the full sample for the point estimate, and
    chosen again inside every resample so the interval includes that selection.
    """
    names = list(subjects)
    matrix = np.vstack([np.asarray(subjects[name], dtype=np.float64) for name in names])
    group = np.asarray(society, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[1] != group.size or group.size == 0:
        raise ValueError("society and subject vectors must share a task axis")
    totals = matrix.sum(axis=1)
    point_index = int(np.argmax(totals))
    point = float(group.mean() - matrix[point_index].mean())
    rng = np.random.default_rng(seed)
    n = group.size
    idx = rng.integers(0, n, size=(n_resamples, n))
    group_means = group[idx].mean(axis=1)
    sampled = matrix[:, idx]
    resample_totals = sampled.sum(axis=2)
    best = resample_totals.argmax(axis=0)
    chosen = sampled[best, np.arange(n_resamples), :]
    diffs = group_means - chosen.mean(axis=1)
    lo, hi = np.quantile(diffs, [0.025, 0.975], method="linear")
    return {
        "n": int(n),
        "best_name": names[point_index],
        "best_solved": int(totals[point_index]),
        "society_solved": int(group.sum()),
        "diff": point,
        "ci_low": float(lo),
        "ci_high": float(hi),
        "clears": bool(lo > 0),
    }


def cycle_labels(target: np.ndarray) -> np.ndarray:
    """Move each positive label onto the next operation. No fixed point."""
    shifted = np.roll(target, 1)
    if target.shape != shifted.shape:
        raise ValueError("label width changed")
    return shifted
