"""DynamicPhaseTorus — phase_torus.PhaseTorus reimplemented on the
coupled-oscillator substrate.

Public API is intentionally compatible with `core.phase_torus.PhaseTorus`
so existing consumers (definition_extractor, generator, inner_dialogue, ...)
can be switched to this class via a one-line import change without rewriting
their bodies. Behaviour is *not* identical — the underlying physics has
changed:

    Old PhaseTorus:
        phases stored as floats; `_attract(a, b)` directly mutates the
        stored numbers toward a target distance.

    DynamicPhaseTorus (this class):
        phases are live readings of an integrating oscillator network;
        `_attract` translates to coordinated drive injection that pulls both
        oscillators toward synchronization through the network's coupling
        dynamics.

What is preserved:
    - public method signatures (observe, query, torus_distance,
      torus_resonance, find_anomalies, stats, save_state, _phase_to_field)
    - co-occurrence counting and TieredRules persistence
    - axiom phase values (clamped to canonical values each observe call)
    - dict-style attribute interface for `phases`, `cooccurrence`, `rules`,
      `axioms` (read-only views where reasonable)

What changes:
    - `phases[symbol]` returns the **current** oscillator phase (radians
      converted to [0, 1)), not a stored value
    - `_attract` no longer sets phases directly — it injects drive
    - the brain's integration loop runs in a background thread; calling
      `stop()` halts it cleanly
    - N>1 multi-dimensional torus is NOT yet supported (raises if asked)
      — this is a Phase-2-of-migration scope limit; see PHI_RESONANCE.md.
"""
from __future__ import annotations

import json
import math
import os
import sys
import tempfile
import time
from collections import defaultdict
from typing import Optional

# Ensure logos_agi root is importable
_ROOT = os.path.expanduser("~/logos_agi")
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.resonance_constants import (
    PHI, PHI_INV, PHI_INV_SQ, PHI_INV_CUBE, FIBONACCI,
    HARM_THRESHOLD, FIELD_NAMES, FIELD_PHASES, PHI_TARGETS,
    circular_mean, phi_phase_distance, phi_phase_resonance,
    is_near_phi_target,
)
from core.tiered_rules import TieredRules

from phi_resonance.oscillator_network import KuramotoNetwork
from phi_resonance.symbol_binding import SymbolBinding, initial_omega_for_symbol
from phi_resonance.dynamical_brain import DynamicalBrain

CO_OCCURRENCE_WINDOW = 3
CRYSTALLIZE_THRESHOLD = 5
MAX_COOCCURRENCE = FIBONACCI[18]   # 2584
SAVE_INTERVAL = FIBONACCI[10]      # 89

TAU = 2.0 * math.pi


# ---------------------------------------------------------------------------
# Phase representation conversion
#
# Old API stores phases ∈ [0, 1).
# Oscillator network stores phases ∈ [0, 2π).
# All public methods accept/return [0, 1) — we convert at boundaries.
# ---------------------------------------------------------------------------

def _to_unit(theta_rad: float) -> float:
    return float((theta_rad / TAU) % 1.0)


def _to_radians(theta_unit: float) -> float:
    return float((theta_unit % 1.0) * TAU)


# ---------------------------------------------------------------------------
# Axiom definitions (mirrors core/phase_torus.py:_init_axioms)
# ---------------------------------------------------------------------------

_AXIOM_DEFS = {
    "creator":           (0.0,                   "meta",
                           "Suham = origin."),
    "logos":             (PHI_INV,               "meta",
                           "LOGOS = sistema."),
    "symbiosis":         (PHI_INV_SQ,            "resonance",
                           "Svyaz mezhdu Creator i Logos."),
    "self_preservation": (PHI_INV ** 3,          "will",
                           "Samosohraneniye."),
    "harm":              (0.5,                   "void",
                           "Vred = protivofaza."),
    "transparency":      (0.5,                   "void",
                           "Sokrytiye = antirezonans."),
}


# ---------------------------------------------------------------------------
# DynamicPhaseTorus
# ---------------------------------------------------------------------------

class _TorusView:
    """Dict-like view of per-dimension phase lists keyed by symbol.

    Mirrors `core.phase_torus.PhaseTorus._torus` (a dict[str, list[float]])
    so consumer modules that access `space._torus[symbol]` directly
    (polarity_engine, causal_engine, role_engine, generator) keep working
    against the dynamic substrate.

    Reads: return CURRENT live phase list (one float per dimension).
    Writes: set the oscillator theta values for the symbol's slots. This
    is needed by causal_engine's rollback pattern (`_torus[sym] = orig`).
    """

    def __init__(self, torus: "DynamicPhaseTorus"):
        self._t = torus

    def __getitem__(self, symbol: str) -> list[float]:
        ph = self._t._all_phases(symbol)
        if ph is None:
            raise KeyError(symbol)
        return ph

    def __setitem__(self, symbol: str, phases) -> None:
        if symbol in self._t.axioms:
            return  # immutable
        if not isinstance(phases, list):
            phases = [phases]
        if not self._t.binding.is_bound(symbol):
            try:
                self._t._bind_symbol(symbol)
            except RuntimeError:
                return
        for dim in range(min(len(phases), self._t.N)):
            slot_name = symbol if dim == 0 else f"{symbol}@dim{dim}"
            if self._t.binding.is_bound(slot_name):
                idx = self._t.binding.index(slot_name)
                self._t._network.theta[idx] = _to_radians(float(phases[dim]))

    def __contains__(self, symbol: str) -> bool:
        return self._t._all_phases(symbol) is not None

    def get(self, symbol: str, default=None):
        ph = self._t._all_phases(symbol)
        return ph if ph is not None else default

    def __iter__(self):
        for s in list(self._t.axioms.keys()):
            yield s
        for s in self._t._bound_user_symbols():
            yield s

    def __len__(self) -> int:
        return len(self._t.axioms) + len(self._t._bound_user_symbols())

    def items(self):
        for s in list(self):
            ph = self._t._all_phases(s)
            if ph is not None:
                yield s, ph

    def keys(self):
        return list(self)

    def values(self):
        out = []
        for s in list(self):
            ph = self._t._all_phases(s)
            if ph is not None:
                out.append(ph)
        return out


class _PhaseView:
    """Read-only dict-like view backed by SymbolBinding. Iteration yields
    {symbol: live phase in [0, 1)}."""

    def __init__(self, torus: "DynamicPhaseTorus"):
        self._t = torus

    def __getitem__(self, symbol: str) -> float:
        if symbol in self._t.axioms:
            return float(self._t.axioms[symbol]["phase"])
        if not self._t.binding.is_bound(symbol):
            raise KeyError(symbol)
        return _to_unit(self._t.binding.phase(symbol))

    def __setitem__(self, symbol: str, phase) -> None:
        """causal_engine + market_torus pattern: `phases[sym] = value`.
        Writes the SLOT 0 phase only (_PhaseView is single-phase view).
        Axioms remain immutable. Auto-binds new symbols."""
        if symbol in self._t.axioms:
            return
        if not self._t.binding.is_bound(symbol):
            try:
                self._t._bind_symbol(symbol)
            except RuntimeError:
                return
        idx = self._t.binding.index(symbol)
        self._t._network.theta[idx] = _to_radians(float(phase))

    def get(self, symbol: str, default=None):
        try:
            return self[symbol]
        except KeyError:
            return default

    def __contains__(self, symbol: str) -> bool:
        return symbol in self._t.axioms or self._t.binding.is_bound(symbol)

    def __iter__(self):
        for s in list(self._t.axioms.keys()):
            yield s
        for s in self._t._bound_user_symbols():
            yield s

    def __len__(self) -> int:
        return len(self._t.axioms) + len(self._t._bound_user_symbols())

    def items(self):
        for s in list(self):
            yield s, self[s]

    def keys(self):
        # dream_core.py:46 calls space.phases.keys() — return list, not view
        return list(self)

    def values(self):
        return [self[s] for s in self]


class DynamicPhaseTorus:
    """Drop-in replacement for PhaseTorus, backed by oscillator network."""

    def __init__(
        self,
        dimensions: int = 1,
        creator_id: str = "creator",
        state_dir: Optional[str] = None,
        capacity: Optional[int] = None,
        coupling_K: float = 1.5,
        integration_hz: Optional[float] = None,
        dt: float = 0.01,
        autostart: Optional[bool] = None,
    ):
        # Production tuning 2026-04-26: default autostart=False under env flag
        # so that brains DON'T compete with main thread during costly init
        # phases (GroundingTorus._recompute_phases takes ~20min CPU + 4
        # background brain threads = bad). Caller is expected to .start()
        # explicitly when ready.
        if autostart is None:
            autostart = os.environ.get("LOGOS_DYNAMIC_AUTOSTART", "0") == "1"
        if capacity is None:
            capacity = int(os.environ.get("LOGOS_DYNAMIC_CAPACITY", "100000"))
        # CPU budget: 4 substrates × N oscillators × Hz × ~0.5ms per step
        # under Python GIL on single core easily blows past cgroup quota at
        # 200 Hz with N=20000. Default to 30 Hz; override via env or arg.
        if integration_hz is None:
            integration_hz = float(
                os.environ.get("LOGOS_DYNAMIC_INTEGRATION_HZ", "30")
            )
        if dimensions < 1 or dimensions > 4:
            raise ValueError(
                f"dimensions must be in [1, 4], got {dimensions}"
            )
        self.N = int(dimensions)
        # For N>1 each symbol binds N consecutive oscillator slots in the
        # network. Slot j stores phase for dimension j of that symbol.
        # Public name "symbol" resolves to slot 0 (compat with old API).
        # Internal names "symbol@dim<j>" exist for j>0.
        self.creator_id = creator_id
        self.state_dir = state_dir or os.path.expanduser("~/logos_agi/state")
        os.makedirs(self.state_dir, exist_ok=True)

        # Oscillator substrate
        self._network = KuramotoNetwork(
            n=capacity,
            coupling_K=coupling_K,
            dt=dt,
            freq_distribution="phi",
            adjacency="all_to_all",
            seed=hash((creator_id, "dpt")) & 0xFFFFFFFF,
        )
        self.binding = SymbolBinding(self._network, capacity=capacity)
        self._brain = DynamicalBrain(
            self._network, self.binding, integration_hz=integration_hz,
        )

        # Co-occurrence + crystallised rules — kept as-is from old PhaseTorus
        self.cooccurrence: dict[tuple[str, str], int] = defaultdict(int)
        self.rules = TieredRules(
            state_dir=os.path.join(self.state_dir, "tiered"),
            hot_limit=FIBONACCI[22],
        )
        self.axioms: dict[str, dict] = {}

        self.total_observations = 0
        self.total_crystallized = 0
        self.total_attractions = 0
        self.total_cross_couplings = 0  # always 0 in N=1, kept for API parity
        self.capacity_misses = 0  # bumps when bind() hits capacity ceiling

        self._init_axioms()
        self._load_state()

        # Public phases-view + torus-view (semi-public attrs in legacy code)
        self.phases = _PhaseView(self)
        self._torus = _TorusView(self)

        if autostart:
            self._brain.start()

        print(f"[+] DynamicPhaseTorus T^{self.N} initialized "
              f"(oscillator-backed). Symbols: {len(self.binding)}, "
              f"Rules: {len(self.rules)}, Axioms: {len(self.axioms)}")

    # ----- lifecycle -----

    def start(self) -> None:
        self._brain.start()

    def stop(self) -> None:
        self._brain.stop()

    def is_running(self) -> bool:
        return self._brain.is_running()

    # ----- axioms -----

    def _bind_symbol(self, name: str, omega_seed: Optional[float] = None) -> bool:
        """Bind a symbol across all N dimensions. Returns True on success,
        False if network capacity is exhausted. Capacity-miss is silent +
        counted (capacity_misses). Caller can keep going — the symbol just
        won't have a substrate slot until eviction frees one."""
        for dim in range(self.N):
            slot_name = name if dim == 0 else f"{name}@dim{dim}"
            if self.binding.is_bound(slot_name):
                continue
            if omega_seed is not None:
                omega = omega_seed * (PHI_INV ** dim)
            else:
                omega = initial_omega_for_symbol(slot_name)
            try:
                self.binding.bind(slot_name, omega=omega)
            except RuntimeError:
                self.capacity_misses += 1
                # Roll back partial bind (if dim>0 some slots bound but not all)
                for d2 in range(dim):
                    rb_name = name if d2 == 0 else f"{name}@dim{d2}"
                    # We can't unbind cleanly without breaking other state;
                    # leave the partial — torus_distance treats missing
                    # dim as None safely via _all_phases.
                    pass
                return False
        return True

    def _slot_indices(self, name: str) -> Optional[list[int]]:
        """Return network indices for all N dimensions of `name`, or None
        if any dimension is unbound."""
        out = []
        for dim in range(self.N):
            slot_name = name if dim == 0 else f"{name}@dim{dim}"
            if not self.binding.is_bound(slot_name):
                return None
            out.append(self.binding.index(slot_name))
        return out

    def _init_axioms(self) -> None:
        for name, (base_phase, field, desc) in _AXIOM_DEFS.items():
            torus_phases = []
            for dim in range(self.N):
                # phi-shift between dimensions (mirrors old _init_axioms)
                p = (base_phase + dim * PHI_INV_SQ) % 1.0
                torus_phases.append(p)
            try:
                self._bind_symbol(name, omega_seed=0.0)  # axioms ω=0
            except RuntimeError:
                pass
            for dim in range(self.N):
                slot_name = name if dim == 0 else f"{name}@dim{dim}"
                if self.binding.is_bound(slot_name):
                    idx = self.binding.index(slot_name)
                    self._network.theta[idx] = _to_radians(torus_phases[dim])
            self.axioms[name] = {
                "phases": torus_phases,
                "phase": base_phase,
                "field": field,
                "immutable": True,
                "description": desc,
            }

    def _clamp_axioms(self) -> None:
        """Re-anchor all axiom oscillator slots to canonical phases."""
        for name, info in self.axioms.items():
            for dim in range(self.N):
                slot_name = name if dim == 0 else f"{name}@dim{dim}"
                if not self.binding.is_bound(slot_name):
                    continue
                idx = self.binding.index(slot_name)
                self._network.theta[idx] = _to_radians(info["phases"][dim])

    # ----- main observe path -----

    def observe(self, sequence) -> None:
        if not sequence:
            return
        # Bind any new symbols (axioms already bound at init)
        for sym in sequence:
            if sym in self.axioms:
                continue
            if not self.binding.is_bound(sym):
                self._bind_symbol(sym)

        window = CO_OCCURRENCE_WINDOW
        for i in range(len(sequence)):
            for j in range(1, min(window + 1, len(sequence) - i)):
                a, b = sequence[i], sequence[i + j]
                if a == b:
                    continue
                pair = (a, b) if a < b else (b, a)
                self.cooccurrence[pair] += 1
                count = self.cooccurrence[pair]
                if count >= CRYSTALLIZE_THRESHOLD:
                    self._attract(a, b, distance=j)
                    if count % CRYSTALLIZE_THRESHOLD == 0:
                        self._try_crystallize(a, b, j, count)
        self.total_observations += len(sequence)
        self._evict_cooccurrence()
        self._clamp_axioms()

    def _attract(self, a: str, b: str, distance: int) -> None:
        """Drive every dimension of a and b toward synchronization. Drive is
        scaled by phi-power per dimension (matches old phase_torus weighting:
        higher dimensions get weaker coupling)."""
        a_mut = a not in self.axioms
        b_mut = b not in self.axioms
        if not (a_mut or b_mut):
            return
        count = self.cooccurrence.get(
            (a, b) if a < b else (b, a), 1
        )
        base_step = (PHI_INV_CUBE * PHI_INV_CUBE) / (
            1.0 + math.log(1 + count) / math.log(PHI)
        )
        base_drive = base_step / max(distance, 1)
        for dim in range(self.N):
            dim_drive = base_drive * (PHI_INV ** dim)
            slot_a = a if dim == 0 else f"{a}@dim{dim}"
            slot_b = b if dim == 0 else f"{b}@dim{dim}"
            if a_mut and self.binding.is_bound(slot_a):
                self.binding.observe(slot_a, drive=dim_drive)
            if b_mut and self.binding.is_bound(slot_b):
                self.binding.observe(slot_b, drive=dim_drive)
        self.total_attractions += 1

    def _try_crystallize(self, a: str, b: str, distance: int,
                          count: int) -> None:
        phase_a = self._get_phase(a)
        phase_b = self._get_phase(b)
        if phase_a is None or phase_b is None:
            return
        dist = phi_phase_distance(phase_a, phase_b)
        if dist is None or dist < 0.01:
            return
        ratio = max(dist, 0.001) / max(1.0 - dist, 0.001)
        hit = is_near_phi_target(ratio, tolerance=0.08)
        if not hit:
            return
        mid_phase = circular_mean([phase_a, phase_b])
        creator_phase = self.axioms["creator"]["phase"]
        creator_dist = phi_phase_distance(mid_phase, creator_phase)
        creator_resonance = phi_phase_resonance(creator_dist)
        harm_phase = self.axioms["harm"]["phase"]
        harm_distance = phi_phase_distance(mid_phase, harm_phase)
        if harm_distance < HARM_THRESHOLD:
            return
        target_name, target_error = hit
        rule_key = f"{a}|{b}"
        rule_data = {
            "a": a, "b": b,
            "phase_a": round(phase_a, 6),
            "phase_b": round(phase_b, 6),
            "distance": round(dist, 6),
            "phi_target": target_name,
            "error": round(target_error, 6),
            "count": count,
            "field_a": self._phase_to_field(phase_a),
            "field_b": self._phase_to_field(phase_b),
            "crystallized_at": time.time(),
        }
        self.rules.put(rule_key, rule_data)
        self.total_crystallized += 1

    def _evict_cooccurrence(self) -> None:
        if len(self.cooccurrence) <= MAX_COOCCURRENCE:
            return
        n_remove = max(1, int(len(self.cooccurrence) * PHI_INV_SQ))
        counts = sorted(self.cooccurrence.values())
        threshold = counts[min(n_remove, len(counts) - 1)]
        to_remove = []
        for pair, cnt in self.cooccurrence.items():
            if cnt <= threshold:
                to_remove.append(pair)
            if len(to_remove) >= n_remove:
                break
        for pair in to_remove:
            del self.cooccurrence[pair]

    # ----- distance / resonance API -----

    def _all_phases(self, name: str) -> Optional[list[float]]:
        """Return live phases [in 0,1) ] for all N dimensions of `name`,
        or None if not bound."""
        if name in self.axioms:
            return list(self.axioms[name]["phases"])
        slots = self._slot_indices(name)
        if slots is None:
            return None
        return [_to_unit(self._network.theta[i]) for i in slots]

    def torus_distance(self, sym_a: str, sym_b: str) -> Optional[float]:
        ta = self._all_phases(sym_a)
        tb = self._all_phases(sym_b)
        if ta is None or tb is None:
            return None
        total = 0.0
        wsum = 0.0
        for dim in range(self.N):
            d = phi_phase_distance(ta[dim], tb[dim])
            w = PHI_INV ** dim
            total += d * w
            wsum += w
        return total / wsum if wsum > 0 else None

    def torus_resonance(self, sym_a: str, sym_b: str) -> float:
        ta = self._all_phases(sym_a)
        tb = self._all_phases(sym_b)
        if ta is None or tb is None:
            return 0.0
        total = 0.0
        wsum = 0.0
        for dim in range(self.N):
            d = phi_phase_distance(ta[dim], tb[dim])
            r = phi_phase_resonance(d)
            w = PHI_INV ** dim
            total += r * w
            wsum += w
        return total / wsum if wsum > 0 else 0.0

    # ----- query -----

    def query(self, symbol: str) -> dict:
        phase = self._get_phase(symbol)
        if phase is None:
            return {"symbol": symbol, "known": False}
        field = self._phase_to_field(phase)
        resonance = phi_phase_resonance(phase)
        connections = []
        for key, rule in self.rules.items():
            if rule["a"] == symbol or rule["b"] == symbol:
                other = rule["b"] if rule["a"] == symbol else rule["a"]
                connections.append({
                    "symbol": other,
                    "phi_target": rule["phi_target"],
                    "count": rule["count"],
                    "field": rule.get(
                        "field_b" if rule["a"] == symbol else "field_a"),
                })
        connections.sort(key=lambda x: x["count"], reverse=True)
        return {
            "symbol": symbol,
            "known": True,
            "phase": round(phase, 6),
            "field": field,
            "resonance": round(resonance, 4),
            "connections": connections[:FIBONACCI[6]],
        }

    def find_anomalies(self, top_k: int = FIBONACCI[6]) -> list[dict]:
        anomalies = []
        for pair, count in self.cooccurrence.items():
            if count < CRYSTALLIZE_THRESHOLD:
                continue
            a, b = pair
            phase_a = self._get_phase(a)
            phase_b = self._get_phase(b)
            if phase_a is None or phase_b is None:
                continue
            dist = phi_phase_distance(phase_a, phase_b)
            if dist < PHI_INV_CUBE * PHI_INV_CUBE:
                continue
            ratio = max(dist, 0.001) / max(1.0 - dist, 0.001)
            hit = is_near_phi_target(ratio, tolerance=0.15)
            if hit:
                target_name, err = hit
                if 0.05 < err < 0.15:
                    anomalies.append({
                        "pair": pair,
                        "distance": round(dist, 6),
                        "nearest_target": target_name,
                        "gap": round(err, 6),
                        "count": count,
                        "priority": round(count * (0.15 - err), 4),
                    })
        anomalies.sort(key=lambda x: x["priority"], reverse=True)
        return anomalies[:top_k]

    # ----- introspection -----

    def stats(self) -> dict:
        n_user = len(self._bound_user_symbols())
        return {
            "symbols": n_user,
            "rules": len(self.rules),
            "rules_hot": self.rules.hot_size(),
            "axioms": len(self.axioms),
            "cooccurrence_pairs": len(self.cooccurrence),
            "total_observations": self.total_observations,
            "total_crystallized": self.total_crystallized,
            "total_attractions": self.total_attractions,
            "total_cross_couplings": self.total_cross_couplings,
            "dimensions": self.N,
            "substrate": "oscillator_network",
            "brain_running": self._brain.is_running(),
            "brain_steps": self._brain.steps_executed,
            "network_size": self._network.N,
            "network_capacity_used": len(self.binding),
            "capacity_misses": self.capacity_misses,
        }

    # ----- helpers -----

    def _get_phase(self, symbol: str) -> Optional[float]:
        if symbol in self.axioms:
            return float(self.axioms[symbol]["phase"])
        if not self.binding.is_bound(symbol):
            return None
        return _to_unit(self.binding.phase(symbol))

    def _get_torus(self, symbol: str) -> Optional[list[float]]:
        return self._all_phases(symbol)

    def _bound_user_symbols(self) -> list[str]:
        """Public-name symbols (not axiom slots, not @dim<j> internal slots)."""
        out = []
        for s in self.binding._sym_to_idx:
            if "@dim" in s:
                continue
            if s in self.axioms:
                continue
            out.append(s)
        return out

    def _phase_to_field(self, phase: float) -> str:
        best_field = FIELD_NAMES[0]
        best_dist = 1.0
        for name, fp in FIELD_PHASES.items():
            d = phi_phase_distance(phase, fp)
            if d < best_dist:
                best_dist = d
                best_field = name
        return best_field

    # ----- persistence -----

    def save_state(self) -> None:
        min_count = FIBONACCI[3]
        filtered_cooc = {
            f"{a}||{b}": c
            for (a, b), c in self.cooccurrence.items()
            if c >= min_count
        }
        # Snapshot user symbols, all dimensions
        torus_data = {}
        for sym in self._bound_user_symbols():
            phases = self._all_phases(sym)
            if phases is None:
                continue
            torus_data[sym] = phases[0] if self.N == 1 else phases
        state = {
            "dimensions": self.N,
            "phases": torus_data,
            "rules": self.rules.to_dict(),
            "cooccurrence": filtered_cooc,
            "stats": {
                "total_observations": self.total_observations,
                "total_crystallized": self.total_crystallized,
                "total_attractions": self.total_attractions,
                "total_cross_couplings": self.total_cross_couplings,
                "symbol_counter": len(self.binding),
            },
            "saved_at": time.time(),
            "substrate": "oscillator_network",
        }
        path = os.path.join(self.state_dir, "phase_space.json")
        try:
            fd, tmp = tempfile.mkstemp(dir=self.state_dir, suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False)
            os.replace(tmp, path)
        except Exception as e:
            print(f"[!] DynamicPhaseTorus save failed: {e}")
            try:
                os.unlink(tmp)
            except Exception:
                pass

    def _load_state(self) -> None:
        path = os.path.join(self.state_dir, "phase_space.json")
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                state = json.load(f)
        except Exception as e:
            print(f"[!] DynamicPhaseTorus load failed: {e}")
            return
        for sym, data in state.get("phases", {}).items():
            if isinstance(data, list):
                phases_unit = [float(p) for p in data]
                # Pad with phi-shifted defaults if fewer dims saved than current N
                while len(phases_unit) < self.N:
                    phases_unit.append((phases_unit[-1] * PHI) % 1.0)
            else:
                phases_unit = [float(data)]
                while len(phases_unit) < self.N:
                    phases_unit.append((phases_unit[-1] * PHI) % 1.0)
            try:
                self._bind_symbol(sym)
            except RuntimeError:
                continue
            for dim in range(self.N):
                slot_name = sym if dim == 0 else f"{sym}@dim{dim}"
                if self.binding.is_bound(slot_name):
                    idx = self.binding.index(slot_name)
                    self._network.theta[idx] = _to_radians(phases_unit[dim])
        self.rules.merge_from_dict(state.get("rules", {}))
        for key, count in state.get("cooccurrence", {}).items():
            parts = key.split("||")
            if len(parts) == 2:
                self.cooccurrence[(parts[0], parts[1])] = int(count)
        stats = state.get("stats", {})
        self.total_observations = stats.get("total_observations", 0)
        self.total_crystallized = stats.get("total_crystallized", 0)
        self.total_attractions = stats.get("total_attractions", 0)
