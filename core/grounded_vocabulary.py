"""grounded_vocabulary.py — Bridge: trade outcomes → word weights.

Closes generator grounding loop (F):
  trading daemon shadow-trade matures → record_outcome(words, pnl)
  main brain generator  → get_weights() → prefer words with positive PnL bias

Shared JSON file for cross-process state. Atomic write/read.
Path default: /root/logos_agi/state/grounded_vocabulary.json

Each entry: {
  word: {
    "pos_count": int,   # times word was in active context during winning shadow
    "neg_count": int,
    "sum_pnl": float,
    "phase": float (0..1),  # phi-phase derived from net score
    "total": int
  }
}

Weighting rule (phi-native):
  net = pos/(pos+neg)  — in [0,1]
  weight = PHI_INV_CUBE + net * (1 - PHI_INV_CUBE)  — always >= 0.236, <= 1.0
  so no word is silenced, but positive-outcome words are boosted.
"""
import os
import json
import time
import tempfile

from core.resonance_constants import PHI_INV_CUBE

DEFAULT_PATH = "/root/logos_agi/state/grounded_vocabulary.json"


def _load(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _atomic_save(path, data):
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", dir=d, delete=False, encoding="utf-8"
    ) as tf:
        json.dump(data, tf, ensure_ascii=False)
        tmp = tf.name
    os.replace(tmp, path)


def record_outcome(words, pnl, path=DEFAULT_PATH):
    """Credit/debit word weights by pnl.

    words: iterable of word strings (e.g. from epoch.name or reasoning).
    pnl: float — positive → pos_count++, negative → neg_count++.
    """
    if not words:
        return
    data = _load(path)
    for w in words:
        w = str(w).strip().lower()
        if not w or len(w) < 2:
            continue
        entry = data.setdefault(w, {
            "pos_count": 0, "neg_count": 0, "sum_pnl": 0.0, "total": 0,
            "phase": 0.5, "last_ts": 0.0,
        })
        if pnl > 0:
            entry["pos_count"] += 1
        elif pnl < 0:
            entry["neg_count"] += 1
        entry["sum_pnl"] += float(pnl)
        entry["total"] += 1
        # Phase: map net score [-1,1] → [0,1)
        total = entry["pos_count"] + entry["neg_count"]
        if total > 0:
            net = entry["pos_count"] / total  # [0,1]
            entry["phase"] = round(net, 6)
        entry["last_ts"] = time.time()
    _atomic_save(path, data)


def get_weight(word, path=DEFAULT_PATH, _cache={}, _ts=[0]):
    """Return [PHI_INV_CUBE, 1.0] weight. Cached for 1s across calls."""
    now = time.time()
    if now - _ts[0] > 1.0:
        _cache.clear()
        _cache.update(_load(path))
        _ts[0] = now
    w = str(word).strip().lower()
    entry = _cache.get(w)
    if not entry:
        return PHI_INV_CUBE  # baseline — unknown word is possible, not boosted
    total = entry.get("total", 0)
    if total <= 0:
        return PHI_INV_CUBE
    net = (entry.get("pos_count", 0) /
           (entry.get("pos_count", 0) + entry.get("neg_count", 0) + 1e-9))
    return PHI_INV_CUBE + net * (1.0 - PHI_INV_CUBE)


def top_grounded(n=21, path=DEFAULT_PATH):
    data = _load(path)
    scored = []
    for w, e in data.items():
        total = e.get("total", 0)
        if total < 2:
            continue
        net = e.get("pos_count", 0) / (total)
        scored.append((w, net, total, e.get("sum_pnl", 0.0)))
    scored.sort(key=lambda x: (-x[1], -x[2]))
    return scored[:n]
