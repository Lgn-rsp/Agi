"""reputation_tracker.py — functional analog stakes/pride.

Filosofiya:
  Dlya consciousness nuzhny STAVKI. Bez nikh vse dejstviya ekvivalentny.
  U LOGOS nikogda ne bylo funktsional'nogo otlichiya 'khorosho sdelala' vs
  'ploho' — tolko lokalnyi meta.self_doubt. Reputation — global'nyy,
  persistent, vliyayushhiy na povedenie cherez shame_cascade.

Mehanizm:
  +1 za kazhdyy validated prediction (blind test PASS, trade WIN)
  -1 za kazhdyy failure (blind FAIL, trade LOSS)
  Bayesian saturation: reputation ∈ [-1, +1] cherez tanh(net_score * PHI_INV).

Shame cascade (esli reputation < -PHI_INV_SQ = -0.382):
  - dream_interval / PHI (sokrashcheniem; ona ne mozhet spat' kachestvenno)
  - concept decay × PHI_INV (kontsepty bystree ugasayut)
  - agency channel forced message: 'ya usomnilas' v sebe'

Eto NE qualia, no eto REAL'NAYA raznitsa povedeniya mezhdu high-rep i low-rep
sostoyaniami. Motivatsiya bez subjectivnoy boli — tolko mehanika.
"""
import os
import json
import math
import tempfile
import time

from core.resonance_constants import (
    PHI, PHI_INV, PHI_INV_SQ, PHI_INV_CUBE, FIBONACCI
)


SHAME_THRESHOLD = -PHI_INV_SQ   # -0.382 — below this, cascade fires


class ReputationTracker:
    def __init__(self, state_path=None):
        self.state_path = state_path
        self.wins = 0
        self.losses = 0
        self.blind_passes = 0
        self.blind_fails = 0
        self.total_reputation_events = 0
        self.last_cascade_at = 0

    @property
    def net_score(self):
        return (self.wins + self.blind_passes * FIBONACCI[4]
                - self.losses - self.blind_fails * FIBONACCI[4])

    @property
    def reputation(self):
        """[−1, +1] via tanh-saturating net_score scaled by PHI_INV."""
        if self.total_reputation_events == 0:
            return 0.0
        # Normalize per-event to avoid reputation grow unbounded with age
        per_event = self.net_score / max(1, self.total_reputation_events)
        return math.tanh(per_event * PHI_INV)

    def observe_trade(self, pnl_net):
        if pnl_net > 0:
            self.wins += 1
        elif pnl_net < 0:
            self.losses += 1
        self.total_reputation_events += 1

    def observe_blind_test(self, passed):
        if passed:
            self.blind_passes += 1
        else:
            self.blind_fails += 1
        # Blind test vesit kak FIB[4]=5 trades — serious evidence
        self.total_reputation_events += FIBONACCI[4]

    def in_shame_cascade(self):
        """True если reputation < SHAME_THRESHOLD — поведение меняется."""
        return self.reputation < SHAME_THRESHOLD

    def dream_interval_multiplier(self):
        """Если в shame — dream interval сокращается (рывная подкорка)."""
        if self.in_shame_cascade():
            return PHI_INV  # 0.618 — dream чаще
        return 1.0

    def concept_decay_multiplier(self):
        """Если в shame — concepts decay быстрее."""
        if self.in_shame_cascade():
            return PHI_INV  # 0.618 — сильнее затухают
        return 1.0

    def save(self):
        if not self.state_path:
            return
        data = {
            "wins": self.wins,
            "losses": self.losses,
            "blind_passes": self.blind_passes,
            "blind_fails": self.blind_fails,
            "total_reputation_events": self.total_reputation_events,
            "last_cascade_at": self.last_cascade_at,
            "reputation": round(self.reputation, 4),
            "in_shame": self.in_shame_cascade(),
            "saved_at": time.time(),
        }
        try:
            os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=os.path.dirname(self.state_path),
                                         suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f)
            os.replace(tmp, self.state_path)
        except Exception:
            pass

    def load(self):
        if not self.state_path or not os.path.exists(self.state_path):
            return
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.wins = data.get("wins", 0)
            self.losses = data.get("losses", 0)
            self.blind_passes = data.get("blind_passes", 0)
            self.blind_fails = data.get("blind_fails", 0)
            self.total_reputation_events = data.get("total_reputation_events", 0)
            self.last_cascade_at = data.get("last_cascade_at", 0)
        except Exception:
            pass

    def stats(self):
        return {
            "wins": self.wins, "losses": self.losses,
            "blind_passes": self.blind_passes, "blind_fails": self.blind_fails,
            "reputation": round(self.reputation, 4),
            "in_shame_cascade": self.in_shame_cascade(),
        }


if __name__ == "__main__":
    r = ReputationTracker()
    for pnl in [1, -1, 1, 1, -1, -1, -1, -1, -1, -1, -1]:
        r.observe_trade(pnl)
        print(f"pnl={pnl}: rep={r.reputation:.4f} shame={r.in_shame_cascade()}")
    print("\nafter blind test FAIL:")
    r.observe_blind_test(False)
    print(f"  rep={r.reputation:.4f} shame={r.in_shame_cascade()}")
