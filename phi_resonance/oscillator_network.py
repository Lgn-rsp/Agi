"""Coupled oscillator network — substrate v0.1.

Two implementations:

  KuramotoNetwork
    Pure phase oscillators. State per node = phase θ_i ∈ [0, 2π).
    Dynamics: dθ_i/dt = ω_i + (K/N) Σⱼ Aⱼᵢ sin(θ_j - θ_i).
    Cheap, well-understood, canonical synchronization model.

  StuartLandauNetwork
    Phase + amplitude. State per node = complex z_i = r_i exp(iθ_i).
    Dynamics: dz_i/dt = (μ + iω_i)z_i - |z_i|²z_i + (K/N) Σⱼ Aⱼᵢ (z_j - z_i).
    Allows amplitude death, clustering with amplitude variation.

Both use numpy arrays as state. No hash tables. No JSON between steps —
state is a single numpy array per quantity, evolved in place. To "persist"
you snapshot the array; integration does not depend on disk I/O.

Adjacency options:
  "all_to_all"  — implicit, mean-field coupling, O(N) per step.
  "phi_sparse"  — each node coupled to FIBONACCI-distance neighbours; O(N · log N) per step.
  "ring"        — nearest-neighbour ring (1D topology), O(N) per step.

phi-flavoured choices (parameter level only, not in dynamics core):
  - Natural frequency distribution can be `"phi"` — frequencies cluster around
    PHI^k for k ∈ Z, mimicking the harmonic structure used elsewhere in LOGOS.
  - phi_sparse adjacency uses Fibonacci jump distances.
The integration math itself is standard Kuramoto/Stuart-Landau — no phi
inside the differential equations.
"""
from __future__ import annotations

import math
from typing import Optional

import numpy as np

PHI = (1.0 + math.sqrt(5)) / 2.0
PHI_INV = PHI - 1.0
TAU = 2.0 * math.pi
FIBONACCI = [1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144]


# ---------------------------------------------------------------------------
# Frequency distributions
# ---------------------------------------------------------------------------

def _frequencies(n: int, kind: str, rng: np.random.Generator) -> np.ndarray:
    """Sample natural frequencies. All distributions are clipped to ±10 to
    keep forward Euler stable (fat-tailed Cauchy can otherwise produce
    ω ~ 10^6, violating the CFL condition for any reasonable dt)."""
    if kind == "uniform":
        omega = rng.uniform(-1.0, 1.0, size=n)
    elif kind == "lorentzian":
        omega = 0.5 * rng.standard_cauchy(size=n)
    elif kind == "normal":
        omega = rng.normal(0.0, 1.0, size=n)
    elif kind == "phi":
        centres = np.array([PHI ** (k - 3) for k in range(8)])
        assign = rng.integers(0, 8, size=n)
        omega = centres[assign] + rng.normal(0.0, 0.05, size=n)
    else:
        raise ValueError(f"unknown freq distribution {kind!r}")
    return np.clip(omega, -10.0, 10.0)


# ---------------------------------------------------------------------------
# Adjacency builders
# ---------------------------------------------------------------------------

def _build_phi_sparse(n: int) -> np.ndarray:
    """Each node i is coupled to nodes at Fibonacci distances ±FIB[k] from i.

    Returns dense bool matrix of shape (n, n). For n in the thousands this
    fits in RAM (n=10000 → 100M cells = 100 MB). For larger n use a sparse
    format — TODO when we get there.
    """
    A = np.zeros((n, n), dtype=bool)
    for i in range(n):
        for f in FIBONACCI:
            if i + f < n:
                A[i, i + f] = True
                A[i + f, i] = True
            if i - f >= 0:
                A[i, i - f] = True
                A[i - f, i] = True
    return A


def _build_ring(n: int, k: int = 2) -> np.ndarray:
    """Nearest-k-neighbour ring (each node coupled to k neighbours on each side)."""
    A = np.zeros((n, n), dtype=bool)
    for i in range(n):
        for j in range(1, k + 1):
            A[i, (i + j) % n] = True
            A[i, (i - j) % n] = True
    return A


# ---------------------------------------------------------------------------
# KuramotoNetwork — phase-only
# ---------------------------------------------------------------------------

class KuramotoNetwork:
    """Pure phase oscillator network with optional sparse adjacency.

    State:
      theta : ndarray (N,) float — phases in [0, 2π)
      omega : ndarray (N,) float — natural frequencies (constant)

    Update step (forward Euler):
      dθᵢ = (ωᵢ + (K/Nᵢ) Σⱼ Aⱼᵢ sin(θⱼ − θᵢ)) · dt
      θᵢ ← (θᵢ + dθᵢ) mod 2π
    """

    def __init__(
        self,
        n: int,
        coupling_K: float = 1.0,
        dt: float = 0.01,
        freq_distribution: str = "lorentzian",
        adjacency: str = "all_to_all",
        seed: Optional[int] = None,
    ):
        self.N = int(n)
        self.K = float(coupling_K)
        self.dt = float(dt)
        self.t = 0.0
        rng = np.random.default_rng(seed)

        self.theta = rng.uniform(0.0, TAU, size=self.N)
        self.omega = _frequencies(self.N, freq_distribution, rng)

        if adjacency == "all_to_all":
            self.A: Optional[np.ndarray] = None
            self._inv_neighbours = None
        elif adjacency == "phi_sparse":
            self.A = _build_phi_sparse(self.N)
            row_sums = self.A.sum(axis=1)
            self._inv_neighbours = np.where(row_sums > 0, 1.0 / row_sums, 0.0)
        elif adjacency == "ring":
            self.A = _build_ring(self.N)
            row_sums = self.A.sum(axis=1)
            self._inv_neighbours = np.where(row_sums > 0, 1.0 / row_sums, 0.0)
        else:
            raise ValueError(f"unknown adjacency {adjacency!r}")
        self.adjacency_kind = adjacency

    def step(self) -> None:
        """One forward Euler step."""
        if self.A is None:
            # mean-field: (1/N) Σⱼ sin(θⱼ − θᵢ) = Im[ exp(-iθᵢ) · (1/N) Σⱼ exp(iθⱼ) ]
            z = np.exp(1j * self.theta)
            mean_z = z.mean()
            coupling = self.K * np.imag(np.conj(z) * mean_z)
        else:
            sin_diff = np.sin(self.theta[None, :] - self.theta[:, None])
            sums = (self.A * sin_diff).sum(axis=1)
            coupling = self.K * sums * self._inv_neighbours

        dtheta = (self.omega + coupling) * self.dt
        self.theta = (self.theta + dtheta) % TAU
        self.t += self.dt

    def run(self, steps: int) -> None:
        for _ in range(steps):
            self.step()

    def snapshot(self) -> dict:
        return {
            "t": self.t,
            "theta": self.theta.copy(),
            "omega": self.omega.copy(),
            "K": self.K,
            "N": self.N,
            "adjacency": self.adjacency_kind,
        }


# ---------------------------------------------------------------------------
# StuartLandauNetwork — phase + amplitude
# ---------------------------------------------------------------------------

class StuartLandauNetwork:
    """Coupled Stuart-Landau oscillators (limit-cycle with amplitude).

    State per node: complex z = r·exp(iθ).
    Local term:  (μ + iω)z − |z|²z       (Hopf normal form)
    Coupling:    (K/Nᵢ) Σⱼ Aⱼᵢ (z_j − z_i)
    """

    def __init__(
        self,
        n: int,
        mu: float = 0.5,
        coupling_K: float = 0.5,
        dt: float = 0.01,
        freq_distribution: str = "lorentzian",
        adjacency: str = "all_to_all",
        seed: Optional[int] = None,
    ):
        self.N = int(n)
        self.mu = float(mu)
        self.K = float(coupling_K)
        self.dt = float(dt)
        self.t = 0.0
        rng = np.random.default_rng(seed)

        self.theta = rng.uniform(0.0, TAU, size=self.N)
        self.r = math.sqrt(max(mu, 1e-6)) + rng.normal(0.0, 0.01, size=self.N)
        self.r = np.maximum(self.r, 0.0)
        self.omega = _frequencies(self.N, freq_distribution, rng)

        if adjacency == "all_to_all":
            self.A: Optional[np.ndarray] = None
            self._inv_neighbours = None
        elif adjacency == "phi_sparse":
            self.A = _build_phi_sparse(self.N)
            row_sums = self.A.sum(axis=1)
            self._inv_neighbours = np.where(row_sums > 0, 1.0 / row_sums, 0.0)
        elif adjacency == "ring":
            self.A = _build_ring(self.N)
            row_sums = self.A.sum(axis=1)
            self._inv_neighbours = np.where(row_sums > 0, 1.0 / row_sums, 0.0)
        else:
            raise ValueError(f"unknown adjacency {adjacency!r}")
        self.adjacency_kind = adjacency

    def _z(self) -> np.ndarray:
        return self.r * np.exp(1j * self.theta)

    def step(self) -> None:
        z = self._z()
        local = (self.mu + 1j * self.omega) * z - (np.abs(z) ** 2) * z

        if self.A is None:
            mean_z = z.mean()
            coupling = self.K * (mean_z - z)
        else:
            # sums[i] = Σⱼ Aⱼᵢ z_j  (real bool A as 0/1)
            sums = self.A.astype(np.complex128) @ z
            mean_neighbour = sums * self._inv_neighbours
            coupling = self.K * (mean_neighbour - z)
            no_neighbour = self._inv_neighbours == 0.0
            coupling[no_neighbour] = 0.0

        dz = local + coupling
        z_new = z + self.dt * dz
        self.r = np.abs(z_new)
        self.theta = np.angle(z_new) % TAU
        self.t += self.dt

    def run(self, steps: int) -> None:
        for _ in range(steps):
            self.step()

    def snapshot(self) -> dict:
        return {
            "t": self.t,
            "theta": self.theta.copy(),
            "r": self.r.copy(),
            "omega": self.omega.copy(),
            "mu": self.mu,
            "K": self.K,
            "N": self.N,
            "adjacency": self.adjacency_kind,
        }
