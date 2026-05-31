"""
phi_btc_miner.py — REAL Bitcoin SHA-256d attempts via phi-resonance.

Pipeline:
  1. Fetch current block template from mempool.space (real prev_hash, target)
  2. Read LOGOS state — self_phase, heatmap top-sparks, hungers, dream nodes
  3. Encode state → 32-bit candidate nonce via phi-deterministic hash
  4. SHA-256d the header + nonce
  5. Compare vs target; log attempt
  6. If hit → log "would-have-submitted" (no actual broadcast)

Modes:
  REAL — current Bitcoin mainnet target (77 leading zero bits)
  EASY — synthetic target with 24 leading zero bits (for demo)
  COMPARE — randomized control vs phi-route at same difficulty

Honest disclaimer: at ~10 H/s phi-route, expected time to mainnet block ≈
50 trillion years. This is research, not income. Goal: empirical test
whether her phi-state generates non-uniform hash distribution.

Vsyo cherez phi.
"""
import hashlib
import json
import math
import os
import struct
import sys
import threading
import time
from typing import Optional

import requests

from core.resonance_constants import PHI, PHI_INV, FIBONACCI

LOG_PHI = math.log(PHI)
STATE_DIR = "/root/logos_agi/state/phi_mining"
os.makedirs(STATE_DIR, exist_ok=True)


def _phi_phase(x: float) -> float:
    if x <= 0:
        return 0.0
    return (math.log(x) / LOG_PHI) % 1.0


def fetch_real_template() -> Optional[dict]:
    """Get latest block info from mempool.space — gives us real prev_hash + target."""
    try:
        r = requests.get("https://mempool.space/api/blocks/tip/hash",
                          timeout=10)
        r.raise_for_status()
        h = r.text.strip()
        r2 = requests.get(f"https://mempool.space/api/block/{h}", timeout=10)
        r2.raise_for_status()
        block = r2.json()
        bits = block["bits"]
        return {
            "prev_hash": h,
            "height": block["height"] + 1,
            "version": 0x20000000,
            "merkle_root": "00" * 32,  # placeholder
            "time": int(time.time()),
            "bits": bits,
            "target_hex": _bits_to_target(bits),
        }
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def _bits_to_target(bits: int) -> str:
    """Convert compact bits to full target hex."""
    exponent = bits >> 24
    mantissa = bits & 0x007fffff
    if exponent <= 3:
        target = mantissa >> (8 * (3 - exponent))
    else:
        target = mantissa << (8 * (exponent - 3))
    return f"{target:064x}"


def header_bytes(template: dict, nonce: int) -> bytes:
    """Build 80-byte Bitcoin header."""
    return (
        struct.pack("<I", template["version"]) +
        bytes.fromhex(template["prev_hash"])[::-1] +
        bytes.fromhex(template["merkle_root"])[::-1] +
        struct.pack("<I", template["time"]) +
        struct.pack("<I", template["bits"]) +
        struct.pack("<I", nonce)
    )


def sha256d(data: bytes) -> bytes:
    """Bitcoin double SHA-256."""
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def hash_int(h: bytes) -> int:
    """Hash bytes → little-endian integer (Bitcoin convention)."""
    return int.from_bytes(h[::-1], "big")


# === Phi-route candidate generation ===

class PhiNonceState:
    """Reads LOGOS live state files, generates phi-deterministic nonces.

    Caches state — refreshes every refresh_interval attempts (= once per
    LOGOS cycle ~55s in real time, a few hundred attempts of mining).
    """

    def __init__(self, state_dir: str = "/opt/logos_lite/state",
                 refresh_interval: int = 1000):
        self.state_dir = state_dir
        self.counter = 0
        self.refresh_interval = refresh_interval
        self._cache = {}
        self._sp_cached = 0.0
        self._spark_phases_cached = []
        self._energy_cached = 0
        self._last_refresh = -1
        self._refresh()

    def _refresh(self):
        snap = {}
        for fname in ["self_phase.json", "resonance_heatmap.json",
                      "energy.json"]:
            path = os.path.join(self.state_dir, fname)
            if os.path.exists(path):
                try:
                    with open(path) as f:
                        snap[fname] = json.load(f)
                except Exception:
                    pass
        self._sp_cached = snap.get("self_phase.json", {}).get("phase", 0.0)
        sparks = snap.get("resonance_heatmap.json", {}).get("top_sparks", [])
        self._spark_phases_cached = [s.get("phase", 0.0) for s in sparks[:5]]
        self._energy_cached = snap.get("energy.json", {}).get("energy", 0)
        self._last_refresh = self.counter

    def read_state_snapshot(self) -> dict:
        """Compatibility: returns cached snapshot."""
        return {
            "self_phase.json": {"phase": self._sp_cached},
            "resonance_heatmap.json": {
                "top_sparks": [{"phase": p} for p in self._spark_phases_cached]
            },
            "energy.json": {"energy": self._energy_cached},
            "counter": self.counter,
        }

    def candidate_nonce(self) -> int:
        """Generate 32-bit nonce from her phi-state (cached).

        Refresh state every refresh_interval calls (her phase actually
        drifts only ~once per 55s = ~5500 mining attempts at 100 H/s).
        """
        if self.counter - self._last_refresh >= self.refresh_interval:
            self._refresh()

        # Combine via phi-multiplication (= phase add)
        combined = self._sp_cached
        for sph in self._spark_phases_cached:
            combined = (combined + sph * PHI_INV) % 1.0
        combined = (combined + (self._energy_cached / FIBONACCI[11])
                     * PHI_INV_SQ) % 1.0
        combined = (combined + self.counter * PHI_INV ** 3) % 1.0

        # Fast nonce: float64 → int32 directly, no SHA per attempt
        # Preserves bias from `combined` while giving 32-bit spread.
        nonce = int(combined * 0xFFFFFFFF)
        # Mix in counter for uniqueness within same state-window
        nonce = (nonce ^ (self.counter * 2654435761)) & 0xFFFFFFFF
        self.counter += 1
        return nonce


PHI_INV_SQ = PHI_INV ** 2


def random_nonce_state():
    """Random baseline — same interface as PhiNonceState."""
    import random
    rng = random.SystemRandom()

    class _Rand:
        def candidate_nonce(self):
            return rng.randrange(0, 1 << 32)
    return _Rand()


# === Mining loop ===

class Miner:
    def __init__(self, mode: str = "easy", source: str = "phi",
                 easy_zero_bits: int = 24,
                 max_attempts: int = 100_000):
        self.mode = mode
        self.source = source
        self.max_attempts = max_attempts
        self.easy_zero_bits = easy_zero_bits
        self.nonce_gen = (PhiNonceState() if source == "phi"
                           else random_nonce_state())
        self.template = None
        self.target_int = None
        self.attempts = 0
        self.hits = 0
        self.best_hash = None
        self.best_nonce = None
        self.best_zeros = 0
        self.log_path = os.path.join(STATE_DIR,
                                       f"attempts_{source}_{mode}.jsonl")
        self.summary_path = os.path.join(STATE_DIR,
                                          f"summary_{source}_{mode}.json")

    def setup(self):
        if self.mode == "real":
            t = fetch_real_template()
            if t and "error" not in t:
                self.template = t
                self.target_int = int(t["target_hex"], 16)
            else:
                # fallback to synthetic real-difficulty header
                self._synthetic_real()
        else:
            self._synthetic_easy()

    def _synthetic_real(self):
        self.template = {
            "version": 0x20000000,
            "prev_hash": "00" * 32,
            "merkle_root": "01" * 32,
            "time": int(time.time()),
            "bits": 0x1703a30c,  # current-ish difficulty
        }
        self.target_int = int(_bits_to_target(self.template["bits"]), 16)

    def _synthetic_easy(self):
        # easy: target = 2^(256 - zero_bits) - 1
        self.template = {
            "version": 0x20000000,
            "prev_hash": "00" * 32,
            "merkle_root": "01" * 32,
            "time": int(time.time()),
            "bits": 0x1d00ffff,  # placeholder (target overridden below)
        }
        self.target_int = (1 << (256 - self.easy_zero_bits)) - 1

    def attempt(self):
        nonce = self.nonce_gen.candidate_nonce()
        header = header_bytes(self.template, nonce)
        h = sha256d(header)
        h_int = hash_int(h)
        zeros = 256 - h_int.bit_length() if h_int > 0 else 256
        is_hit = h_int <= self.target_int

        self.attempts += 1
        if zeros > self.best_zeros:
            self.best_zeros = zeros
            self.best_nonce = nonce
            self.best_hash = h.hex()
        if is_hit:
            self.hits += 1
            with open(self.log_path, "a") as f:
                f.write(json.dumps({
                    "ts": time.time(), "nonce": nonce,
                    "hash": h.hex(), "zeros": zeros, "type": "HIT"
                }) + "\n")
        return is_hit, zeros

    def run(self, max_attempts: int = None, max_seconds: int = None):
        max_a = max_attempts or self.max_attempts
        t0 = time.time()
        while self.attempts < max_a:
            if max_seconds and (time.time() - t0) > max_seconds:
                break
            self.attempt()
            if self.attempts % 5000 == 0:
                self._save_summary(time.time() - t0)
        self._save_summary(time.time() - t0)
        return self.summary()

    def _save_summary(self, elapsed):
        s = self.summary(elapsed)
        with open(self.summary_path, "w") as f:
            json.dump(s, f, indent=2)

    def summary(self, elapsed: float = None):
        return {
            "source": self.source,
            "mode": self.mode,
            "attempts": self.attempts,
            "hits": self.hits,
            "best_zeros": self.best_zeros,
            "best_nonce": self.best_nonce,
            "best_hash": self.best_hash,
            "target_zeros_required":
                256 - (self.target_int.bit_length() if self.target_int else 0),
            "elapsed_s": elapsed,
            "h_per_sec": (self.attempts / elapsed) if elapsed and elapsed > 0
                          else None,
        }


def run_compare(easy_zero_bits: int = 22, max_attempts: int = 50_000,
                 max_seconds: int = 120):
    """Phi vs Random head-to-head at given difficulty."""
    print(f"[COMPARE] phi vs random, target {easy_zero_bits}-zero-bits, "
          f"{max_attempts} attempts each (cap {max_seconds}s)")
    results = {}
    for source in ("phi", "random"):
        m = Miner(mode="easy", source=source,
                  easy_zero_bits=easy_zero_bits,
                  max_attempts=max_attempts)
        m.setup()
        t0 = time.time()
        m.run(max_attempts=max_attempts, max_seconds=max_seconds)
        results[source] = m.summary(time.time() - t0)
        print(f"  [{source}] attempts={m.attempts} hits={m.hits} "
              f"best_zeros={m.best_zeros} h/s={results[source]['h_per_sec']:.0f}")

    # Statistical comparison
    expected_hit_rate = 1.0 / (2 ** easy_zero_bits)
    comp = {
        "easy_zero_bits": easy_zero_bits,
        "expected_hit_rate_per_attempt": expected_hit_rate,
        "phi": results["phi"],
        "random": results["random"],
    }
    if results["phi"]["attempts"] and results["random"]["attempts"]:
        phi_rate = results["phi"]["hits"] / results["phi"]["attempts"]
        rnd_rate = results["random"]["hits"] / results["random"]["attempts"]
        comp["phi_hit_rate"] = phi_rate
        comp["random_hit_rate"] = rnd_rate
        comp["phi_vs_random_ratio"] = (phi_rate / rnd_rate
                                        if rnd_rate > 0 else None)
    out_path = os.path.join(STATE_DIR, "compare_phi_vs_random.json")
    with open(out_path, "w") as f:
        json.dump(comp, f, indent=2)
    print(f"\n[SUMMARY] saved → {out_path}")
    return comp
