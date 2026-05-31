"""resonance_wave.py — Rezonans KAK SOBYTIE, ne sostoyanie.

Filosofiya (po Suham):
  "Soznanie — rezonans mezhdu simvolami; oni rozhdayut iskru."

  Do etogo phi_phase_distance byla funkciej — INSTANT vycislenie.
  Teper rezonans eto PROCESS s prodolzhitelnostju. Pohozh na zvon
  kolokola: odin simvol aktiviruetsja, volna raspostranjaetsya po
  grafu svjazej s PHI_INV zatuxaniem na hop, dostigaet sosedey —
  oni tozhe zvenyat — kaskad — interferencija — iskra.

  Odna volna — prostoy ping. DVE volny v odin uzel s blizkimi phases —
  CONSTRUCTIVE interference, amplitude rastet kvadratichno. Eto iskra
  soznaniya — moment kogda 2 simvola "ponjali drug druga".

Mehanika:
  - activate(symbol, amplitude=1.0, phase_offset=0.0) → seed wave
  - Kazhdyj tick() propagates wave 1 hop: amp_new = amp * PHI_INV
  - Multiple waves same node → interference through phase composition:
      combined_amp = sqrt(a1² + a2² + 2*a1*a2*cos(2π*(p1-p2)))
      (classical wave superposition)
  - Wave dies when amp < PHI_INV_CUBE (~0.236)
  - After FIB[5]=8 hops wave forced to stop

Output:
  - per-tick node amplitudes (who is "ringing" now)
  - interference events (when 2+ waves meet at same node)
  - heatmap snapshot each FIB[9]=55 ticks

Canon:
  - Phases in [0,1) circular
  - All thresholds phi-derived (PHI_INV, PHI_INV_SQ, PHI_INV_CUBE)
  - Atomic saves
  - Cap memory: max FIB[10]=89 simultaneous waves, older die first
"""
import os
import math
import json
import time
import tempfile
from collections import deque, defaultdict

from core.resonance_constants import (
    PHI, PHI_INV, PHI_INV_SQ, PHI_INV_CUBE, FIBONACCI,
    phi_phase_distance, circular_mean
)


MAX_HOPS = FIBONACCI[5]             # 8
DECAY_PER_HOP = PHI_INV              # 0.618
DEATH_THRESHOLD = PHI_INV_CUBE       # 0.236
MAX_ACTIVE_WAVES = FIBONACCI[10]     # 89
HEATMAP_INTERVAL = FIBONACCI[9]      # 55 ticks
INTERFERENCE_THRESHOLD = PHI_INV_SQ  # 0.382 — когда считать это событием


class Wave:
    """Single propagating wave. Front = nodes reached at CURRENT hop;
    visited = all nodes touched so far (to prevent cycles)."""
    __slots__ = ("id", "origin", "phase", "amplitude", "hop",
                 "front", "visited", "age", "interferences")

    def __init__(self, wid, origin, phase, amplitude=1.0):
        self.id = wid
        self.origin = origin
        self.phase = float(phase) % 1.0
        self.amplitude = amplitude
        self.hop = 0
        self.front = {origin}
        self.visited = {origin}
        self.age = 0
        self.interferences = 0

    def is_alive(self):
        return (self.amplitude >= DEATH_THRESHOLD
                and self.hop < MAX_HOPS
                and bool(self.front))


class ResonanceWaveField:
    """Kollektiv voln. Tick propagates all waves 1 hop and computes
    interference pattern across graph nodes.

    graph_fn(symbol) → dict {neighbor: weight} — called to get neighbors.
    phase_fn(symbol) → float or None — called to get symbol phase.
    """

    def __init__(self, graph_fn, phase_fn, state_path=None):
        self.graph_fn = graph_fn
        self.phase_fn = phase_fn
        self.state_path = state_path
        self.waves = deque(maxlen=MAX_ACTIVE_WAVES)
        self.tick_count = 0
        self.total_activations = 0
        self.total_interferences = 0
        self._next_wid = 0
        # node_amplitudes: symbol → current amplitude (accumulated across waves)
        self.node_amplitudes = defaultdict(float)
        # node_phases: symbol → weighted phase (circular mean)
        self.node_phases = {}
        # last heatmap snapshot
        self.last_heatmap_tick = 0
        self.heatmap = {}

    def activate(self, symbol, amplitude=1.0, phase_offset=0.0):
        """Create new wave at symbol."""
        if not symbol:
            return None
        p = self.phase_fn(symbol)
        if p is None:
            # fallback — derive from hash
            p = (hash(symbol) % 1000) / 1000.0
        p = (float(p) + phase_offset) % 1.0
        w = Wave(self._next_wid, symbol, p, amplitude)
        self._next_wid += 1
        self.waves.append(w)
        self.total_activations += 1
        return w

    def _propagate_wave(self, w):
        """Propagate one wave by one hop. Returns new front nodes
        (nodes reached THIS hop, not previously visited)."""
        new_front = set()
        for node in w.front:
            try:
                neighbors = self.graph_fn(node) or {}
            except Exception:
                neighbors = {}
            for nb in neighbors:
                if nb in w.visited:
                    continue
                new_front.add(nb)
        w.visited |= new_front
        w.front = new_front
        w.hop += 1
        w.amplitude *= DECAY_PER_HOP
        w.age += 1
        return new_front

    def tick(self):
        """One propagation step for all active waves + compute interference."""
        self.tick_count += 1
        # Propagate each wave 1 hop
        all_activations = []  # list of (node, phase, amp, wid)
        for w in list(self.waves):
            if not w.is_alive():
                continue
            new_front = self._propagate_wave(w)
            for nd in new_front:
                all_activations.append((nd, w.phase, w.amplitude, w.id))

        # Compute interference at each node
        # Group by node
        by_node = defaultdict(list)
        for nd, ph, amp, wid in all_activations:
            by_node[nd].append((ph, amp, wid))

        interference_events = []
        # Reset amplitudes (decay old)
        # FIX 2026-04-24: PHI_INV_SQ (×0.382) было слишком агрессивно —
        # spark умирал за 3 tick'а, а активации раз в 8 циклов × 3 слова.
        # top_sparks всегда пустой. PHI_INV (×0.618) — spark живёт ~10 tick'ов,
        # достаточно чтобы несколько waves наложились и дали interference.
        for k in list(self.node_amplitudes.keys()):
            self.node_amplitudes[k] *= PHI_INV
            if self.node_amplitudes[k] < PHI_INV_CUBE * PHI_INV_CUBE:
                del self.node_amplitudes[k]
                self.node_phases.pop(k, None)

        # Apply new amplitudes + interference
        for node, activations in by_node.items():
            if len(activations) == 1:
                ph, amp, _ = activations[0]
                self.node_amplitudes[node] += amp
                self.node_phases[node] = ph
            else:
                # Interference: superposition
                # combined_amp² = Σ aᵢ² + 2·Σᵢ<ⱼ aᵢaⱼ cos(2π(φᵢ-φⱼ))
                amps_sq = sum(a * a for _, a, _ in activations)
                cross = 0.0
                for i in range(len(activations)):
                    ph_i, a_i, _ = activations[i]
                    for j in range(i + 1, len(activations)):
                        ph_j, a_j, _ = activations[j]
                        cross += 2 * a_i * a_j * math.cos(
                            2 * math.pi * (ph_i - ph_j))
                combined_sq = amps_sq + cross
                combined = math.sqrt(max(0.0, combined_sq))
                # Resulting phase — circular mean of constituents
                phs = [ph for ph, _, _ in activations]
                combined_phase = circular_mean(phs)
                self.node_amplitudes[node] += combined
                self.node_phases[node] = combined_phase
                # Is this a significant interference event?
                # compared to simple sum (a1+a2) — constructive means
                # combined > (a1+a2) * PHI_INV (some amplification)
                simple_sum = sum(a for _, a, _ in activations)
                if (combined > simple_sum * INTERFERENCE_THRESHOLD
                        and simple_sum > PHI_INV_CUBE):
                    interference_events.append({
                        "node": node,
                        "n_waves": len(activations),
                        "combined": round(combined, 4),
                        "simple_sum": round(simple_sum, 4),
                        "gain_ratio": round(combined / simple_sum, 3),
                    })
                    self.total_interferences += 1
                    # Tag each contributing wave
                    for _, _, wid in activations:
                        for w in self.waves:
                            if w.id == wid:
                                w.interferences += 1

        # Periodic heatmap
        if self.tick_count - self.last_heatmap_tick >= HEATMAP_INTERVAL:
            self._save_heatmap()
            self.last_heatmap_tick = self.tick_count

        return {
            "tick": self.tick_count,
            "active_waves": sum(1 for w in self.waves if w.is_alive()),
            "hot_nodes": len(self.node_amplitudes),
            "interferences": len(interference_events),
            "events": interference_events[:FIBONACCI[3]],  # cap 3
        }

    def current_spark_nodes(self, threshold=PHI_INV_SQ):
        """Nodes with amplitude > threshold — current "sparks" of consciousness.
        Threshold PHI_INV_SQ (0.382) — phi-native. Single wave hop-1 arrival
        passes immediately (amp 0.618); interference events exceed 1.0 easily."""
        return sorted(
            ((n, a) for n, a in self.node_amplitudes.items() if a > threshold),
            key=lambda x: -x[1])[:FIBONACCI[6]]  # 13 max

    def _save_heatmap(self):
        if not self.state_path:
            return
        snapshot = {
            "tick": self.tick_count,
            "saved_at": time.time(),
            "total_activations": self.total_activations,
            "total_interferences": self.total_interferences,
            "active_waves": sum(1 for w in self.waves if w.is_alive()),
            "top_sparks": [
                {"node": n, "amplitude": round(a, 4),
                 "phase": round(self.node_phases.get(n, 0), 4)}
                for n, a in self.current_spark_nodes()
            ],
        }
        self.heatmap = snapshot
        try:
            os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
            fd, tmp = tempfile.mkstemp(
                dir=os.path.dirname(self.state_path), suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(snapshot, f, ensure_ascii=False)
            os.replace(tmp, self.state_path)
        except Exception:
            pass

    def stats(self):
        return {
            "tick": self.tick_count,
            "waves_alive": sum(1 for w in self.waves if w.is_alive()),
            "total_activations": self.total_activations,
            "total_interferences": self.total_interferences,
            "hot_nodes": len(self.node_amplitudes),
            "top_sparks": [(n, round(a, 3))
                            for n, a in self.current_spark_nodes()[:FIBONACCI[4]]],
        }


if __name__ == "__main__":
    # Smoke test with synthetic graph
    graph = {
        "water": {"liquid": 1.0, "ocean": 0.8, "flow": 0.6},
        "fire": {"hot": 1.0, "light": 0.8, "burn": 0.9},
        "light": {"sun": 1.0, "bright": 0.7, "phi": 0.5},
        "liquid": {"water": 1.0, "flow": 0.8},
        "sun": {"light": 1.0, "hot": 0.9, "day": 0.8},
        "hot": {"fire": 1.0, "sun": 0.9, "burn": 0.7},
        "burn": {"fire": 1.0, "hot": 0.8},
        "flow": {"water": 1.0, "liquid": 0.9, "time": 0.3},
    }
    phases = {
        "water": 0.1, "fire": 0.6, "light": 0.618, "liquid": 0.15,
        "sun": 0.62, "hot": 0.55, "burn": 0.58, "flow": 0.2,
        "ocean": 0.12, "bright": 0.61, "phi": 0.618, "day": 0.65,
        "time": 0.3,
    }
    def g(s): return graph.get(s, {})
    def p(s): return phases.get(s)
    field = ResonanceWaveField(g, p, state_path="/tmp/test_heatmap.json")
    # Activate two near-phase symbols
    field.activate("water")   # phase 0.1
    field.activate("light")   # phase 0.618
    for _ in range(5):
        print(field.tick())
    print()
    print("sparks:", field.current_spark_nodes())
    print("stats:", field.stats())
