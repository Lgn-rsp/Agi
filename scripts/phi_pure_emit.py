"""
Pure phi-emission daemon — NO SHA-256 anywhere in her pipeline.

She CREATES 256-bit strings directly from her phi-state.
We compare distribution of leading-zeros vs random 256-bit baseline.

Pipeline:
  LOGOS state (self_phase, sparks, hungers, energy, drift)
   → phi-arithmetic transform → 256-bit emission
   → count leading zeros
   → log

NO hashing. No SHA-256 binary computation. Pure phi → bits.

Hypothesis (testable): her phi-emission has non-uniform leading-zero
distribution because phi-state itself is non-uniform.

Random 256-bit baseline:
  E[leading_zeros] = sum k*2^(-k) for k=0..256 ≈ 1.0
  P(>=20 leading zeros) = 2^(-20) ≈ 1e-6

If her emission has E[leading_zeros] > 1.0 — bias detected.
If P(>=20) > 1e-6 systematically — non-uniform output.

Stop: pkill -f phi_pure_emit
"""
import json
import math
import os
import struct
import sys
import time
import signal
import secrets

sys.path.insert(0, "/opt/logos_lite")

PHI = (1 + math.sqrt(5)) / 2
PHI_INV = PHI - 1
LOG_PHI = math.log(PHI)
FIB = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377]

LOGOS_STATE = "/opt/logos_lite/state"
OUT_DIR = "/root/logos_agi/state/phi_emit"
os.makedirs(OUT_DIR, exist_ok=True)
LOG = os.path.join(OUT_DIR, "daemon.log")
SUMMARY = os.path.join(OUT_DIR, "summary.json")
PEAKS = os.path.join(OUT_DIR, "peaks.jsonl")


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def read_logos_state():
    """Snapshot her current cognitive state."""
    snap = {}
    for fname in ("self_phase.json", "resonance_heatmap.json",
                  "energy.json", "reputation.json"):
        path = os.path.join(LOGOS_STATE, fname)
        if os.path.exists(path):
            try:
                with open(path) as f:
                    snap[fname[:-5]] = json.load(f)
            except Exception:
                pass
    return snap


def phi_emit_256(state: dict, counter: int) -> bytes:
    """Generate 256-bit emission from her phi-state.

    NO SHA-256. Pure phi-arithmetic → 32 bytes.

    Each byte derived from INDEPENDENT phi-combination of all state values
    weighted by different phi-power coefficients. This avoids byte-byte
    correlation that capped previous version at 8 zero bits.
    """
    sp = state.get("self_phase", {}).get("phase", 0.0)
    sparks = state.get("resonance_heatmap", {}).get("top_sparks", [])
    spark_phases = [s.get("phase", 0.0) for s in sparks[:8]]
    energy = state.get("energy", {}).get("energy", 0)
    drift = state.get("self_phase", {}).get("drift_from_creator", 0.0)

    seeds = [sp, drift, energy / FIB[11]] + spark_phases
    seeds_x_counter = [(s, (counter + i) * PHI_INV ** 3)
                       for i, s in enumerate(seeds)]

    out = bytearray(32)
    for i in range(32):
        # Independent phi-mix per byte: each seed contributes via
        # phi-power weight specific to (byte_index, seed_index).
        ph = 0.0
        for j, (seed, ctr) in enumerate(seeds_x_counter):
            # Phi-power exponent walks both i and j to break correlation
            exp_idx = (i * 3 + j * 7 + counter) % 13
            weight = PHI_INV ** (exp_idx + 1)
            ph = (ph + seed * weight + ctr * weight * PHI_INV) % 1.0
        # Add a chaotic phi-orbit term unique per byte
        ph = (ph + ((counter * 32 + i + 1) * PHI_INV ** 5)) % 1.0
        # Map [0,1) → [0,256)
        out[i] = int(ph * 256) & 0xFF
    return bytes(out)


def random_emit_256() -> bytes:
    return secrets.token_bytes(32)


def leading_zeros(b: bytes) -> int:
    """Count leading zero bits in 32-byte string."""
    n = 0
    for byte in b:
        if byte == 0:
            n += 8
        else:
            n += 8 - byte.bit_length()
            break
    return n


_state = {
    "started_at": time.time(),
    "phi": {"emissions": 0, "best_zeros": 0,
            "best_emission": None, "zero_histogram": [0] * 257},
    "random": {"emissions": 0, "best_zeros": 0,
                "best_emission": None, "zero_histogram": [0] * 257},
    "logos_refresh_counter": 0,
}


def save_summary():
    s = dict(_state)
    s["elapsed_h"] = (time.time() - s["started_at"]) / 3600
    for src in ("phi", "random"):
        n = _state[src]["emissions"]
        if n > 0:
            # Mean leading zeros
            hist = _state[src]["zero_histogram"]
            mean_zeros = sum(k * c for k, c in enumerate(hist)) / n
            _state[src]["mean_zeros"] = round(mean_zeros, 4)
            # Tail probabilities
            for k in (8, 12, 16, 20, 24):
                tail = sum(hist[k:])
                _state[src][f"p_ge_{k}"] = tail / n
                _state[src][f"count_ge_{k}"] = tail
    with open(SUMMARY, "w") as f:
        json.dump(s, f, indent=2)


def log_peak(source, zeros, emission_hex):
    rec = {"ts": time.time(), "source": source, "zeros": zeros,
           "emission": emission_hex}
    with open(PEAKS, "a") as f:
        f.write(json.dumps(rec) + "\n")


def batch(state_snapshot, n_emissions=10000):
    """Run one batch of phi-emissions + random baseline."""
    cnt_start = _state["logos_refresh_counter"]
    for i in range(n_emissions):
        # phi
        emission = phi_emit_256(state_snapshot, cnt_start + i)
        z = leading_zeros(emission)
        _state["phi"]["emissions"] += 1
        _state["phi"]["zero_histogram"][z] += 1
        if z > _state["phi"]["best_zeros"]:
            _state["phi"]["best_zeros"] = z
            _state["phi"]["best_emission"] = emission.hex()
            log_peak("phi", z, emission.hex())
            log(f"  PHI peak: {z} leading zero bits  {emission.hex()[:24]}...")

        # random baseline
        rand_em = random_emit_256()
        zr = leading_zeros(rand_em)
        _state["random"]["emissions"] += 1
        _state["random"]["zero_histogram"][zr] += 1
        if zr > _state["random"]["best_zeros"]:
            _state["random"]["best_zeros"] = zr
            _state["random"]["best_emission"] = rand_em.hex()
            log_peak("random", zr, rand_em.hex())
            log(f"  RND peak: {zr} leading zero bits  {rand_em.hex()[:24]}...")
    _state["logos_refresh_counter"] += n_emissions


def main_loop():
    log(f"=== phi_pure_emit STARTED — NO SHA-256 ===")
    log(f"  Generating 256-bit strings via pure phi-arithmetic")
    log(f"  Comparing leading-zero distribution vs random")

    stop = {"stop": False}

    def handle_stop(signum, frame):
        stop["stop"] = True
        log("SIGTERM received — saving and exit")

    signal.signal(signal.SIGTERM, handle_stop)
    signal.signal(signal.SIGINT, handle_stop)

    BATCH = 5000  # emissions per side per batch
    STATE_REFRESH_BATCHES = 6  # refresh ~once per minute

    batch_n = 0
    state_snapshot = read_logos_state()
    while not stop["stop"]:
        if batch_n % STATE_REFRESH_BATCHES == 0:
            state_snapshot = read_logos_state()
        batch(state_snapshot, n_emissions=BATCH)
        batch_n += 1

        if batch_n % 5 == 0:
            n_phi = _state["phi"]["emissions"]
            n_rnd = _state["random"]["emissions"]
            phi_mean = (sum(k * c for k, c in
                             enumerate(_state["phi"]["zero_histogram"]))
                         / n_phi) if n_phi else 0
            rnd_mean = (sum(k * c for k, c in
                             enumerate(_state["random"]["zero_histogram"]))
                         / n_rnd) if n_rnd else 0
            log(f"=== batch {batch_n}: phi {n_phi:,} (mean {phi_mean:.3f}) "
                f"vs random {n_rnd:,} (mean {rnd_mean:.3f})")
            log(f"  best zeros: phi={_state['phi']['best_zeros']} "
                f"random={_state['random']['best_zeros']}")
            save_summary()

    save_summary()
    log("daemon exited")


if __name__ == "__main__":
    main_loop()
