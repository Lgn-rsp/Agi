"""shadow_trade.py — Embodied feedback loop without real risk.

Every decide() records a hypothetical trade even on silence. N bars later
the outcome is computed and fed into meta.observe_trade + concepts.confirm.
This gives the active-inference loop real data without touching capital.

Key: without outcomes her "decisions" were unobserved — she could not learn
if her predictions were right or wrong. With shadow-trade the surprise from
Predictor becomes grounded in actual market outcomes.

API:
  st = ShadowTradeLog(state_path, horizon_bars=FIBONACCI[7])
  st.load()
  st.record(bar_idx, side, size, entry_price, state_glyph, source)
  matured = st.check_outcomes(current_bar, current_price)
  # matured: list of {side, pnl, outcome, source, age}
"""
import os
import json
import tempfile
from collections import deque

from core.resonance_constants import FIBONACCI


class ShadowTradeLog:
    def __init__(self, state_path=None, horizon_bars=FIBONACCI[7],
                  max_open=FIBONACCI[10], max_closed_retained=FIBONACCI[12]):
        self.state_path = state_path
        self.horizon = horizon_bars       # how many bars until we judge outcome
        self.open = deque(maxlen=max_open)  # pending shadow trades
        self.closed = deque(maxlen=max_closed_retained)  # outcome-checked
        self.total_recorded = 0
        self.total_closed = 0
        self.sum_pnl = 0.0
        self.wins = 0
        self.losses = 0

    def record(self, bar_idx, side, size, entry_price, state_glyph,
                  source="silence"):
        """side: 'up' | 'down'. size: PHI-fraction. source: tag ('silence',
        'dialogue_refused', 'explore', 'real_trade_skipped')."""
        if side not in ("up", "down"):
            return
        if entry_price is None or entry_price <= 0:
            return
        self.open.append({
            "bar_idx": bar_idx,
            "side": side,
            "size": float(size),
            "entry_price": float(entry_price),
            "state_glyph": state_glyph,
            "source": source,
        })
        self.total_recorded += 1

    def check_outcomes(self, current_bar, current_price):
        """For any open shadow that has matured (age >= horizon), compute
        pnl = signed direction move. Returns list of matured events."""
        if current_price is None or current_price <= 0:
            return []
        matured = []
        still_open = []
        for t in self.open:
            age = current_bar - t["bar_idx"]
            if age >= self.horizon:
                ret = (current_price - t["entry_price"]) / t["entry_price"]
                if t["side"] == "down":
                    ret = -ret
                pnl = ret * t["size"]
                outcome = (
                    "up" if ret > 0.001 else
                    "down" if ret < -0.001 else
                    "flat"
                )
                event = {
                    "bar_idx": t["bar_idx"],
                    "matured_bar": current_bar,
                    "age": age,
                    "side": t["side"],
                    "size": t["size"],
                    "entry_price": t["entry_price"],
                    "exit_price": float(current_price),
                    "pnl": pnl,
                    "outcome": outcome,
                    "state_glyph": t["state_glyph"],
                    "source": t["source"],
                }
                matured.append(event)
                self.closed.append(event)
                self.total_closed += 1
                self.sum_pnl += pnl
                if pnl > 0:
                    self.wins += 1
                elif pnl < 0:
                    self.losses += 1
            else:
                still_open.append(t)
        self.open.clear()
        for t in still_open:
            self.open.append(t)
        return matured

    def stats(self):
        n = self.total_closed
        return {
            "recorded": self.total_recorded,
            "closed": n,
            "open": len(self.open),
            "wins": self.wins,
            "losses": self.losses,
            "win_rate": (self.wins / n) if n else 0.0,
            "avg_pnl": (self.sum_pnl / n) if n else 0.0,
        }

    def save(self):
        if not self.state_path:
            return
        snap = {
            "total_recorded": self.total_recorded,
            "total_closed": self.total_closed,
            "sum_pnl": self.sum_pnl,
            "wins": self.wins,
            "losses": self.losses,
            "open": list(self.open),
            "closed": list(self.closed)[-FIBONACCI[10]:],  # keep last 89
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
            self.total_recorded = int(snap.get("total_recorded", 0))
            self.total_closed = int(snap.get("total_closed", 0))
            self.sum_pnl = float(snap.get("sum_pnl", 0.0))
            self.wins = int(snap.get("wins", 0))
            self.losses = int(snap.get("losses", 0))
            for t in snap.get("open", []):
                self.open.append(t)
            for t in snap.get("closed", []):
                self.closed.append(t)
        except Exception:
            pass
