"""symbol_binding.py — bridge between LOGOS symbols (strings) and oscillator
indices.

Conceptually:
  Old (phase_torus):  hash table {symbol: phase_float}
                      attract(symbol, target_phase, weight) mutates the float.

  New (this module):  bidirectional map symbol ↔ oscillator index i.
                      net.theta[i], net.r[i] are the live dynamic state.
                      observe(symbol, drive) injects an external perturbation
                      into oscillator i, applied in the next integration step.

A symbol is no longer a stored phase. A symbol is an *active participant* in
the oscillator network — it has its own ω (natural frequency, decided when
the symbol is bound), and its θ(t) evolves as part of the global dynamics.

Read paths (e.g. inner_dialogue, generator) query `binding.phase(symbol)`
which returns the *current* θ from the live array. No JSON, no disk, no tick.
"""
from __future__ import annotations

import math
from typing import Optional

import numpy as np

from phi_resonance.oscillator_network import (
    KuramotoNetwork,
    StuartLandauNetwork,
    PHI,
    PHI_INV,
)

TAU = 2.0 * math.pi


class SymbolBinding:
    """Map between symbol strings and oscillator indices.

    The network capacity is fixed at construction (N oscillators). Symbols
    are bound on first observation. Once full, additional `bind()` calls
    raise — caller must decide eviction policy explicitly. No silent
    overwrite (a Canon-style discipline: data lives or dies, but never
    silently rotates underneath you).
    """

    def __init__(
        self,
        network: KuramotoNetwork | StuartLandauNetwork,
        capacity: Optional[int] = None,
    ):
        self.net = network
        self.capacity = capacity if capacity is not None else network.N
        if self.capacity > network.N:
            raise ValueError(
                f"capacity {self.capacity} exceeds network size {network.N}"
            )
        self._sym_to_idx: dict[str, int] = {}
        self._idx_to_sym: dict[int, str] = {}
        self._next_idx = 0
        # External drive accumulated between integration steps.
        # Step (in dynamical_brain.py) drains and applies this.
        self._pending_drive = np.zeros(network.N, dtype=np.float64)

    # ----- binding -----

    def bind(self, symbol: str, omega: Optional[float] = None) -> int:
        """Bind a new symbol to an oscillator slot. Returns its index.

        If the symbol is already bound, returns the existing index without
        modifying ω.
        """
        if symbol in self._sym_to_idx:
            return self._sym_to_idx[symbol]
        if self._next_idx >= self.capacity:
            raise RuntimeError(
                f"network capacity {self.capacity} exhausted — "
                f"cannot bind {symbol!r}"
            )
        idx = self._next_idx
        self._next_idx += 1
        self._sym_to_idx[symbol] = idx
        self._idx_to_sym[idx] = symbol
        if omega is not None:
            self.net.omega[idx] = float(omega)
        return idx

    def is_bound(self, symbol: str) -> bool:
        return symbol in self._sym_to_idx

    def index(self, symbol: str) -> int:
        if symbol not in self._sym_to_idx:
            raise KeyError(symbol)
        return self._sym_to_idx[symbol]

    def symbol_at(self, idx: int) -> Optional[str]:
        return self._idx_to_sym.get(idx)

    def __len__(self) -> int:
        return self._next_idx

    # ----- read live state -----

    def phase(self, symbol: str) -> float:
        """Current θ in [0, 2π) for the bound symbol's oscillator."""
        return float(self.net.theta[self.index(symbol)])

    def amplitude(self, symbol: str) -> float:
        """Current amplitude r if the network is Stuart-Landau, else 1.0."""
        if isinstance(self.net, StuartLandauNetwork):
            return float(self.net.r[self.index(symbol)])
        return 1.0

    def frequency(self, symbol: str) -> float:
        return float(self.net.omega[self.index(symbol)])

    # ----- semantic queries (replaces phase_torus / generator hops) -----

    def nearest(self, symbol: str, k: int = 8,
                exclude_self: bool = True) -> list[tuple[str, float]]:
        """k nearest symbols by phase distance on the circle.

        Replaces the greedy-walk lookup that inner_dialogue / generator do
        in current LOGOS via phase_torus. Crucial difference: distances are
        measured between *current live phases*, not stored ones, so the
        result depends on global synchronization state at this moment.
        """
        if not self._sym_to_idx:
            return []
        idx = self.index(symbol)
        live = self.net.theta[: self._next_idx]
        target = self.net.theta[idx]
        # Circular distance ∈ [0, π]
        diff = np.abs(live - target)
        diff = np.minimum(diff, TAU - diff)
        order = np.argsort(diff)
        results: list[tuple[str, float]] = []
        for j in order:
            j = int(j)
            if exclude_self and j == idx:
                continue
            sym = self._idx_to_sym.get(j)
            if sym is None:
                continue
            results.append((sym, float(diff[j])))
            if len(results) >= k:
                break
        return results

    def synchronized_cluster(self, symbol: str,
                              tolerance: float = 0.1) -> list[str]:
        """All bound symbols whose phase is within `tolerance · 2π` of
        `symbol`. The set of locally-synchronized symbols around this one —
        operational equivalent of "concept activation" without symbolic graph
        walks."""
        if not self._sym_to_idx:
            return []
        idx = self.index(symbol)
        target = self.net.theta[idx]
        live = self.net.theta[: self._next_idx]
        diff = np.abs(live - target)
        diff = np.minimum(diff, TAU - diff)
        threshold = tolerance * TAU
        in_cluster = np.where(diff <= threshold)[0]
        return [self._idx_to_sym[int(j)] for j in in_cluster
                if int(j) in self._idx_to_sym]

    # ----- external perturbation (replaces phase_torus.attract) -----

    def observe(self, symbol: str, drive: float = 1.0) -> None:
        """Inject an external phase-pulling drive into the symbol's
        oscillator. The drive is summed into a buffer that the integration
        loop applies as an additional term in dθ/dt at the next step.

        Replaces phase_torus.attract(symbol, target_phase, weight). Now you
        do not specify "where to put the phase"; you specify "how strongly
        external observation pulls". Where the phase ends up is a function
        of network dynamics, not a setpoint.
        """
        idx = self.bind(symbol) if symbol not in self._sym_to_idx \
            else self._sym_to_idx[symbol]
        self._pending_drive[idx] += float(drive)

    def consume_drive(self) -> np.ndarray:
        """Called by the integration loop. Returns the accumulated drive
        and resets the buffer."""
        drive = self._pending_drive.copy()
        self._pending_drive.fill(0.0)
        return drive

    # ----- snapshot/restore (for persistence; replaces phase_space.json) -----

    def snapshot(self) -> dict:
        return {
            "n_bound": self._next_idx,
            "capacity": self.capacity,
            "symbols": list(self._sym_to_idx.items()),
            "network": {
                "theta": self.net.theta.copy(),
                "omega": self.net.omega.copy(),
                "t": self.net.t,
                **(
                    {"r": self.net.r.copy(), "mu": self.net.mu}
                    if isinstance(self.net, StuartLandauNetwork) else {}
                ),
            },
        }

    @classmethod
    def restore(cls, snap: dict, network) -> "SymbolBinding":
        """Restore from a snapshot taken by `snapshot()`. Network must have
        been constructed with at least the same N as snap."""
        if network.N < snap["capacity"]:
            raise ValueError("network too small to restore snapshot")
        binding = cls(network, capacity=snap["capacity"])
        for sym, idx in snap["symbols"]:
            binding._sym_to_idx[sym] = int(idx)
            binding._idx_to_sym[int(idx)] = sym
            binding._next_idx = max(binding._next_idx, int(idx) + 1)
        net_state = snap["network"]
        network.theta[: len(net_state["theta"])] = net_state["theta"]
        network.omega[: len(net_state["omega"])] = net_state["omega"]
        network.t = float(net_state["t"])
        if "r" in net_state and isinstance(network, StuartLandauNetwork):
            network.r[: len(net_state["r"])] = net_state["r"]
        return binding


def initial_omega_for_symbol(symbol: str, base_freq: float = 1.0) -> float:
    """Default natural frequency assigned to a freshly-bound symbol.

    Heuristic: hash the symbol to an integer, mod 8 for harmonic class,
    use PHI^k as the frequency. This means symbols cluster into 8 frequency
    families (matching the PENTAGON/HEXAGON/SQUARE/... families in
    phi_project's attention head config), so synchronization preferentially
    happens within harmonic classes.

    This is the only place where phi appears in symbol→oscillator mapping —
    the dynamics core itself stays canonical Kuramoto.
    """
    h = abs(hash(symbol)) % 8 - 3  # -3..4
    return base_freq * (PHI ** h)
