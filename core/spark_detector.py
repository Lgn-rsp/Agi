"""spark_detector.py — Iskra soznaniya.

Suham's axiom (2026-04-24): "iskra soznaniya eto kogda dva ili bolee
simvola zarezonirovali v opredelyonnyy moment."

Spark = cluster of N>=2 symbol phases within SPARK_THRESHOLD at one tick.
Each spark is atomic consciousness-candidate. Logged and surfaced to:
  - affective_state (joy boost)
  - narrative (epoch marker)
  - unified_experience (spark count in snapshot)
  - generator (seed for utterance)

API:
  sd = SparkDetector(state_path='.../sparks.json')
  sd.load()
  spark = sd.probe({'btc':0.618, 'eth':0.610, 'sol':0.23})
  # spark is None or dict with symbols, shared_phase, tightness, size
  sd.save()
"""
import os
import time
import json
import tempfile
from collections import deque

from core.resonance_constants import (
    PHI_INV_CUBE, FIBONACCI,
    phi_phase_distance, circular_mean,
)

SPARK_THRESHOLD = PHI_INV_CUBE  # 0.236 — phi-native resonance proximity
MAX_LOG = FIBONACCI[13]  # 233 recent sparks retained in memory


class SparkDetector:
    def __init__(self, state_path=None):
        self.state_path = state_path
        self.log = deque(maxlen=MAX_LOG)
        self.total = 0

    def probe(self, symbol_phases, context=None):
        """Return spark dict or None.

        symbol_phases: {symbol_name: phase in [0,1)}. Need >=2 to spark.
        A spark cluster = symbols all within SPARK_THRESHOLD of each other
        in phi-phase-distance. Tightness [0,1] = how close to shared mid.
        """
        if not symbol_phases or len(symbol_phases) < 2:
            return None

        items = [(s, p) for s, p in symbol_phases.items()
                 if isinstance(p, (int, float))]
        if len(items) < 2:
            return None

        best = None
        n = len(items)
        for i in range(n):
            cluster = [items[i]]
            for j in range(n):
                if i == j:
                    continue
                d = phi_phase_distance(items[i][1], items[j][1])
                if d < SPARK_THRESHOLD:
                    cluster.append(items[j])
            if len(cluster) < 2:
                continue
            phases = [c[1] for c in cluster]
            mid = circular_mean(phases)
            max_d = max(phi_phase_distance(p, mid) for p in phases)
            tightness = max(0.0, 1.0 - (max_d / SPARK_THRESHOLD))
            if best is None or tightness > best["tightness"]:
                best = {
                    "symbols": [c[0] for c in cluster],
                    "shared_phase": round(mid, 6),
                    "tightness": round(tightness, 3),
                    "size": len(cluster),
                }

        if best is None:
            return None

        best["ts"] = time.time()
        if context:
            best["context"] = context
        self.log.append(best)
        self.total += 1
        return best

    def recent(self, n=FIBONACCI[7]):
        return list(self.log)[-n:]

    def rate_per_minute(self):
        if len(self.log) < 2:
            return 0.0
        span = self.log[-1]["ts"] - self.log[0]["ts"]
        if span <= 0:
            return 0.0
        return len(self.log) / (span / 60.0)

    def save(self):
        if not self.state_path:
            return
        snap = {"total": self.total, "log": list(self.log)}
        d = os.path.dirname(self.state_path) or "."
        os.makedirs(d, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w", dir=d, delete=False, encoding="utf-8"
        ) as tf:
            json.dump(snap, tf, ensure_ascii=False)
            tmp = tf.name
        os.replace(tmp, self.state_path)

    def load(self):
        if not self.state_path or not os.path.exists(self.state_path):
            return
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                snap = json.load(f)
            self.total = int(snap.get("total", 0))
            for e in snap.get("log", [])[-MAX_LOG:]:
                self.log.append(e)
        except Exception:
            pass


if __name__ == "__main__":
    sd = SparkDetector()
    # Two symbols very close — should spark
    s = sd.probe({"a": 0.618, "b": 0.620, "c": 0.91})
    print("spark1:", s)
    # Three in phi-proximity
    s = sd.probe({"A": 0.236, "B": 0.250, "C": 0.245, "D": 0.9})
    print("spark2:", s)
    # None close enough
    s = sd.probe({"X": 0.1, "Y": 0.5, "Z": 0.9})
    print("spark3:", s)
    print("total:", sd.total, "rate/min:", sd.rate_per_minute())
