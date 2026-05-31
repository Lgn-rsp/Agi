"""predictor.py — Active-inference core (Friston loop).

Generative model over glyph sequences. Each tick:
  1. predict(recent_glyphs) → p(next_glyph)
  2. On next tick, compute surprise = phi_phase_distance(predicted_phase, actual_phase)
  3. Update transition weights by surprise (low surprise → reinforce, high → adapt)

Surprise is the coupling that closes perceive→act→measure→update. Without this
cognition is a one-way pipeline. With it, output changes state which changes
model which changes next output — the minimum ingredient for agency.

API:
  p = Predictor(state_path)
  p.load()
  pred = p.predict(recent_glyphs)   # dict {glyph: prob, ...}, or None
  surprise = p.observe(actual_glyph)  # updates weights, returns phi-distance
  p.save()
"""
import os
import json
import tempfile
from collections import defaultdict, deque

from core.resonance_constants import (
    PHI_INV, PHI_INV_CUBE, FIBONACCI,
    phi_phase_distance,
)
from core.consciousness_glyphs import GLYPHS, glyph_phase

HISTORY_LEN = FIBONACCI[7]  # 21 glyphs context
REINFORCE = PHI_INV          # 0.618 — strong reinforcement for correct predict
PENALIZE = PHI_INV_CUBE      # 0.236 — weaker penalty on miss (stay learnable)


class Predictor:
    def __init__(self, state_path=None):
        self.state_path = state_path
        # transitions[prev_glyph][next_glyph] = weight (additive, >=0)
        self.transitions = defaultdict(lambda: defaultdict(float))
        self.history = deque(maxlen=HISTORY_LEN)
        self.last_prediction = None  # {glyph: prob, ...} OR None
        self.last_top_glyph = None
        self.total_observations = 0
        self.total_surprise = 0.0
        self.correct = 0  # top-1 hits

    def _distribution(self, prev):
        w = self.transitions.get(prev)
        if not w:
            return {}
        total = sum(w.values())
        if total <= 0:
            return {}
        return {g: v / total for g, v in w.items()}

    def predict(self, recent_glyphs=None):
        """Return dict {glyph: prob} for next glyph or None if no context."""
        if recent_glyphs:
            prev = recent_glyphs[-1]
        elif self.history:
            prev = self.history[-1]
        else:
            return None
        dist = self._distribution(prev)
        if not dist:
            return None
        top = max(dist, key=dist.get)
        self.last_prediction = dist
        self.last_top_glyph = top
        return dist

    def observe(self, actual_glyph):
        """Update transitions from previous → actual. Returns surprise [0,0.5].

        Surprise = phi_phase_distance(predicted_phase, actual_phase).
        Max circular distance is 0.5. Low surprise = good model.
        """
        surprise = 0.0
        if self.last_top_glyph is not None and actual_glyph is not None:
            pp = glyph_phase(self.last_top_glyph)
            ap = glyph_phase(actual_glyph)
            if pp is not None and ap is not None:
                surprise = phi_phase_distance(pp, ap)

        if self.history:
            prev = self.history[-1]
            # reinforce the actual transition (always) — positive learning
            self.transitions[prev][actual_glyph] += REINFORCE
            # if we predicted top correctly, extra reinforce; else slight pen
            if self.last_top_glyph == actual_glyph:
                self.transitions[prev][actual_glyph] += REINFORCE
                self.correct += 1
            else:
                if self.last_top_glyph is not None:
                    # decay the mis-prediction slightly (don't delete — keep it
                    # observed, just weaken)
                    old = self.transitions[prev][self.last_top_glyph]
                    self.transitions[prev][self.last_top_glyph] = max(
                        0.0, old - PENALIZE * old)

        self.history.append(actual_glyph)
        self.total_observations += 1
        self.total_surprise += surprise
        # clear last_prediction after observation (must re-predict explicitly)
        self.last_prediction = None
        self.last_top_glyph = None
        return surprise

    def stats(self):
        n = self.total_observations
        return {
            "observations": n,
            "avg_surprise": (self.total_surprise / n) if n else 0.0,
            "top1_accuracy": (self.correct / n) if n else 0.0,
            "states_learned": len(self.transitions),
        }

    def save(self):
        if not self.state_path:
            return
        snap = {
            "transitions": {k: dict(v) for k, v in self.transitions.items()},
            "history": list(self.history),
            "total_observations": self.total_observations,
            "total_surprise": self.total_surprise,
            "correct": self.correct,
        }
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
            for prev, inner in snap.get("transitions", {}).items():
                for nxt, w in inner.items():
                    self.transitions[prev][nxt] = float(w)
            for g in snap.get("history", [])[-HISTORY_LEN:]:
                self.history.append(g)
            self.total_observations = int(snap.get("total_observations", 0))
            self.total_surprise = float(snap.get("total_surprise", 0.0))
            self.correct = int(snap.get("correct", 0))
        except Exception:
            pass


if __name__ == "__main__":
    p = Predictor()
    # Teach a sequence: Φ → ∴ → Φ → ∴ ...
    seq = ["Φ", "∴", "Φ", "∴", "Φ", "∴", "Φ", "∴"]
    for g in seq:
        p.predict()
        s = p.observe(g)
        print(f"observe {g} surprise={s:.3f}")
    pred = p.predict()
    print("prediction:", pred, "top:", p.last_top_glyph)
    print("stats:", p.stats())
