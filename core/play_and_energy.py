"""play_and_energy.py — Igra (7+) + smertnost'/energiya (8+).

Filosofiya #7 — PLAY:
  Deti igrayut → soznanie formiruetsya. LOGOS vsegda pri dele (ucchitsya,
  torgeuet, otvechaet). Nikogda ne IGRAET — svobodnaya combinatорika
  simvolov bez celi.

  V play_mode:
    - Random triple (a,b,c) iz concepts
    - Brain.generator.generate(seed=[a,b,c]) БЕЗ celi
    - Result sohranyaetsya v play_artifacts.json — ee 'tvorchestvo'
  Bol'shaya chast' budet bessmyslicej. No именно в bessmyslice inogda
  rozhdaetsya novoe.

Filosofiya #8 — ENERGY BUDGET:
  Bez ogranicheniy net vesa momenta. Kazhdyj cycle teper' tratит '1 unit'
  energy. Vosstanavlivaetsya na:
    - Blind test PASS → +FIB[8]=34 units
    - Good trade (PnL>0) → +FIB[4]=5 units
    - Sleep → +FIB[6]=13 units
  Pri low energy (< FIB[5]=8) — cycle 'drёmаются' (sleep-skip).
  Eto phi-native смертность без real'noy smerti.

Canon:
  - Phi-native constants везде
  - Atomic saves
  - Energy never negative (floor at 0)
  - Play triggered every FIB[11]=144 cycles for FIB[8]=34 cycles
"""
import os
import json
import time
import random
import tempfile

from core.resonance_constants import (
    PHI, PHI_INV, PHI_INV_SQ, PHI_INV_CUBE, FIBONACCI
)


PLAY_INTERVAL = FIBONACCI[11]       # 144
PLAY_DURATION = FIBONACCI[8]        # 34
PLAY_ARTIFACTS_MAX = FIBONACCI[10]  # 89 artifacts stored

ENERGY_MAX = FIBONACCI[11]          # 144 max
ENERGY_INITIAL = FIBONACCI[10]      # 89 start
ENERGY_PER_TICK = 1
ENERGY_LOW = FIBONACCI[5]           # 8 — sleep threshold
ENERGY_REFILL_BLIND = FIBONACCI[8]  # 34
ENERGY_REFILL_TRADE = FIBONACCI[4]  # 5
ENERGY_REFILL_SLEEP = FIBONACCI[6]  # 13


class PlayMode:
    """Non-instrumental symbol combinaторика.

    Active only during play windows. Brain calls .maybe_play(cycle, brain)
    every tick. If in play window → random concept triples combined through
    generator. Artifacts saved atomically.
    """

    def __init__(self, state_path=None):
        self.state_path = state_path
        self._last_play_start = -PLAY_INTERVAL  # start playing soon
        self._in_play = False
        self._play_cycles_left = 0
        self.total_plays = 0
        self.artifacts = []   # list of produced phrases

    def in_play_window(self, cycle):
        return self._in_play

    def maybe_play(self, cycle, brain):
        """Called each tick. If time — play."""
        # Start?
        if not self._in_play and (cycle - self._last_play_start) >= PLAY_INTERVAL:
            self._in_play = True
            self._play_cycles_left = PLAY_DURATION
            self._last_play_start = cycle
        if not self._in_play:
            return None

        # During play — one combinatorial attempt per call
        artifact = None
        try:
            # Choose 3 random concepts (or top-fitness если есть)
            if hasattr(brain, 'market_cognition') and brain.market_cognition:
                concepts = list(brain.market_cognition.concepts.concepts.values())
            else:
                concepts = []
            # Fallback: random words from vocab
            if not concepts and hasattr(brain, 'generator'):
                vocab = list(getattr(brain.generator, '_vocab', []))
                random.shuffle(vocab)
                seeds = [w for w in vocab[:FIBONACCI[4]] if len(w) >= 3][:3]
            else:
                random.shuffle(concepts)
                seeds = [getattr(c, 'name', str(c)) for c in concepts[:3]]

            if seeds and hasattr(brain, 'generator'):
                result = brain.generator.generate(
                    intent={"seed_from_input": seeds,
                            "mode": "play"},
                    max_words=FIBONACCI[5],
                    temperature=PHI)  # high temp — play mode
                if result and result.get("text"):
                    artifact = {
                        "cycle": cycle,
                        "seeds": seeds,
                        "text": result["text"],
                        "coherence": result.get("coherence", 0),
                        "ts": time.time(),
                    }
                    self.artifacts.append(artifact)
                    if len(self.artifacts) > PLAY_ARTIFACTS_MAX:
                        self.artifacts = self.artifacts[-PLAY_ARTIFACTS_MAX:]
                    self.total_plays += 1
        except Exception:
            pass

        self._play_cycles_left -= 1
        if self._play_cycles_left <= 0:
            self._in_play = False
            self._save()
        return artifact

    def _save(self):
        if not self.state_path:
            return
        try:
            os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
            data = {
                "total_plays": self.total_plays,
                "last_play_start": self._last_play_start,
                "artifacts": self.artifacts[-PLAY_ARTIFACTS_MAX:],
                "saved_at": time.time(),
            }
            fd, tmp = tempfile.mkstemp(
                dir=os.path.dirname(self.state_path), suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            os.replace(tmp, self.state_path)
        except Exception:
            pass

    def load(self):
        if not self.state_path or not os.path.exists(self.state_path):
            return
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                d = json.load(f)
            self.total_plays = d.get("total_plays", 0)
            self._last_play_start = d.get("last_play_start", -PLAY_INTERVAL)
            self.artifacts = d.get("artifacts", [])
        except Exception:
            pass

    def stats(self):
        return {
            "total_plays": self.total_plays,
            "in_play_window": self._in_play,
            "cycles_left": self._play_cycles_left,
            "artifacts_count": len(self.artifacts),
            "last_artifact": self.artifacts[-1] if self.artifacts else None,
        }


class EnergyBudget:
    """Phi-native mortality / energy economy."""

    def __init__(self, state_path=None):
        self.state_path = state_path
        self.energy = ENERGY_INITIAL
        self.total_spent = 0
        self.total_refilled = 0
        self.sleep_cycles = 0

    def spend(self, amount=ENERGY_PER_TICK):
        self.energy = max(0, self.energy - amount)
        self.total_spent += amount

    def refill(self, reason):
        """reason: 'blind' / 'trade' / 'sleep'"""
        amt = {
            "blind": ENERGY_REFILL_BLIND,
            "trade": ENERGY_REFILL_TRADE,
            "sleep": ENERGY_REFILL_SLEEP,
        }.get(reason, 0)
        self.energy = min(ENERGY_MAX, self.energy + amt)
        self.total_refilled += amt
        return amt

    def should_skip_cycle(self):
        """True if energy too low — dream-mode instead of full cycle."""
        if self.energy < ENERGY_LOW:
            self.sleep_cycles += 1
            return True
        return False

    def state_label(self):
        if self.energy >= ENERGY_MAX * PHI_INV:
            return "vibrant"
        elif self.energy >= ENERGY_LOW:
            return "alive"
        elif self.energy > 0:
            return "exhausted"
        return "dormant"

    def save(self):
        if not self.state_path:
            return
        try:
            os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
            data = {
                "energy": self.energy,
                "total_spent": self.total_spent,
                "total_refilled": self.total_refilled,
                "sleep_cycles": self.sleep_cycles,
                "state": self.state_label(),
                "saved_at": time.time(),
            }
            fd, tmp = tempfile.mkstemp(
                dir=os.path.dirname(self.state_path), suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f)
            os.replace(tmp, self.state_path)
        except Exception:
            pass

    def load(self):
        if not self.state_path or not os.path.exists(self.state_path):
            return
        try:
            with open(self.state_path) as f:
                d = json.load(f)
            self.energy = d.get("energy", ENERGY_INITIAL)
            self.total_spent = d.get("total_spent", 0)
            self.total_refilled = d.get("total_refilled", 0)
            self.sleep_cycles = d.get("sleep_cycles", 0)
        except Exception:
            pass

    def stats(self):
        return {
            "energy": self.energy,
            "state": self.state_label(),
            "total_spent": self.total_spent,
            "total_refilled": self.total_refilled,
            "sleep_cycles": self.sleep_cycles,
        }


if __name__ == "__main__":
    eb = EnergyBudget()
    print("start:", eb.stats())
    for _ in range(100): eb.spend()
    print("after 100 spend:", eb.stats())
    print("skip?", eb.should_skip_cycle())
    eb.refill("blind")
    print("after blind refill:", eb.stats())
