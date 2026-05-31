"""Measurable invariants of an oscillator network.

These are the things you actually look at to decide whether the substrate
is doing something — synchronization, clustering, intermittent coherence
("chimera" states), spectral properties of the mean field.

All functions take phases (radians) and/or amplitudes as numpy arrays.
None of them mutate state.
"""
from __future__ import annotations

import numpy as np

TAU = 2.0 * np.pi


def order_parameter(theta: np.ndarray) -> tuple[float, float]:
    """Kuramoto order parameter R, ψ.

    R ∈ [0, 1]: 1.0 = full sync, 0.0 = no sync.
    ψ: mean phase angle, ∈ [0, 2π).
    """
    z = np.exp(1j * theta)
    mean = z.mean()
    return float(np.abs(mean)), float(np.angle(mean) % TAU)


def cluster_phases(theta: np.ndarray, gap_fraction: float = 0.1) -> list[np.ndarray]:
    """Group oscillators by phase proximity. Returns list of index arrays.

    Sort phases on the circle, find gaps larger than gap_fraction * 2π,
    cut into clusters at those gaps.
    """
    n = theta.size
    if n == 0:
        return []
    sorted_idx = np.argsort(theta)
    sorted_phases = theta[sorted_idx]
    diffs = np.empty(n)
    diffs[:-1] = np.diff(sorted_phases)
    diffs[-1] = (sorted_phases[0] + TAU) - sorted_phases[-1]

    threshold = gap_fraction * TAU
    cuts = np.where(diffs > threshold)[0]
    if cuts.size == 0:
        return [sorted_idx]
    clusters: list[np.ndarray] = []
    start = (cuts[-1] + 1) % n  # wrap so first cluster starts after the last cut
    rolled = np.roll(sorted_idx, -start)
    rolled_diffs = np.roll(diffs, -start)
    cur_start = 0
    for i in range(n):
        if rolled_diffs[i] > threshold:
            clusters.append(rolled[cur_start:i + 1])
            cur_start = i + 1
    if cur_start < n:
        clusters.append(rolled[cur_start:])
    return clusters


def chimera_index(theta: np.ndarray, n_groups: int = 8) -> float:
    """Heuristic "chimera-ness": variance of local synchronization across groups.

    Split oscillators into n_groups equal-sized chunks (by index), compute
    local order parameter per chunk, return std-dev of those values. Maxes
    when some chunks are sync (R≈1) and others async (R≈0) — i.e. chimera
    states. Zero when all chunks are equally (a)synchronized.
    """
    n = theta.size
    if n_groups <= 0 or n < n_groups:
        return 0.0
    group_size = n // n_groups
    local_R = np.empty(n_groups)
    for g in range(n_groups):
        chunk = theta[g * group_size:(g + 1) * group_size]
        local_R[g] = np.abs(np.exp(1j * chunk).mean())
    return float(local_R.std())


def mean_field(theta: np.ndarray, r: np.ndarray | None = None) -> complex:
    """Complex mean field <r exp(iθ)>. If r is None, treat amplitudes as 1."""
    if r is None:
        return complex(np.exp(1j * theta).mean())
    return complex((r * np.exp(1j * theta)).mean())


def power_spectrum(time_series: np.ndarray, dt: float) -> tuple[np.ndarray, np.ndarray]:
    """One-sided power spectrum of a real-valued time series.

    Returns (frequencies in Hz, |X(f)|²).
    """
    n = time_series.size
    if n < 4:
        return np.array([]), np.array([])
    series = time_series - time_series.mean()
    spectrum = np.fft.rfft(series)
    freqs = np.fft.rfftfreq(n, d=dt)
    return freqs, np.abs(spectrum) ** 2


def synchronization_entropy(theta: np.ndarray, n_bins: int = 32) -> float:
    """Shannon entropy of phase distribution. 0 = perfectly synced (single bin),
    log2(n_bins) ≈ uniformly spread.

    Rough complement to order_parameter — entropy captures multimodal
    distributions that R alone cannot distinguish from uniform.
    """
    if theta.size == 0:
        return 0.0
    hist, _ = np.histogram(theta, bins=n_bins, range=(0.0, TAU))
    p = hist.astype(np.float64) / hist.sum() if hist.sum() > 0 else hist
    p = p[p > 0]
    return float(-(p * np.log2(p)).sum())
