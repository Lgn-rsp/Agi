"""Continuous daemon: phi-mining at real Bitcoin difficulty + random baseline.

Runs forever:
  - Refreshes block template every ~5 min (real Bitcoin tip)
  - Mines via phi-route (reading LOGOS live state)
  - Mines via random baseline in parallel batches
  - Logs all attempts + best_zeros peaks
  - Saves rolling summary every batch

Resource:
  ~1 CPU thread, ~100K H/s, low memory. Doesn't impact lite-peer
  (different process, separate state cache).

Stop: pkill -f phi_btc_daemon
"""
import json
import os
import sys
import time
import signal

sys.path.insert(0, "/opt/logos_lite")

from core.phi_btc_miner import Miner, fetch_real_template, _bits_to_target

DAEMON_LOG = "/root/logos_agi/state/phi_mining/daemon.log"
DAEMON_SUMMARY = "/root/logos_agi/state/phi_mining/daemon_summary.json"
PEAKS_LOG = "/root/logos_agi/state/phi_mining/peaks.jsonl"
BATCH_ATTEMPTS = 500_000
BATCH_SECONDS = 60
TEMPLATE_REFRESH_EVERY_N_BATCHES = 5  # refresh real header every ~5 min


_state = {
    "started_at": time.time(),
    "total_attempts": {"phi": 0, "random": 0},
    "total_hits": {"phi": 0, "random": 0},
    "best_zeros": {"phi": 0, "random": 0},
    "best_nonce": {"phi": None, "random": None},
    "best_hash": {"phi": None, "random": None},
    "batches_done": 0,
    "last_template": None,
    "last_template_time": 0,
}


def log(msg: str):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(DAEMON_LOG, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def save_summary():
    s = dict(_state)
    s["elapsed_h"] = (time.time() - s["started_at"]) / 3600
    if s["elapsed_h"] > 0:
        s["phi_h_per_sec"] = s["total_attempts"]["phi"] / (s["elapsed_h"] * 3600)
        s["random_h_per_sec"] = s["total_attempts"]["random"] / (s["elapsed_h"] * 3600)
    with open(DAEMON_SUMMARY, "w") as f:
        json.dump(s, f, indent=2)


def log_peak(source: str, zeros: int, nonce: int, hash_hex: str, template: dict):
    rec = {
        "ts": time.time(), "source": source, "zeros": zeros,
        "nonce": nonce, "hash": hash_hex,
        "template_height": template.get("height"),
        "template_time": template.get("time"),
    }
    with open(PEAKS_LOG, "a") as f:
        f.write(json.dumps(rec) + "\n")


def get_template(force_refresh: bool = False) -> dict:
    """Get block template — cached for refresh interval."""
    if (not force_refresh and _state["last_template"]
            and time.time() - _state["last_template_time"] < 300):
        return _state["last_template"]
    t = fetch_real_template()
    if t and "error" not in t:
        _state["last_template"] = t
        _state["last_template_time"] = time.time()
        log(f"template refreshed: height={t.get('height')} "
            f"target_zeros={256 - int(t['target_hex'], 16).bit_length()}")
        return t
    elif _state["last_template"]:
        log(f"template fetch failed ({t}), using cached")
        return _state["last_template"]
    else:
        log(f"template fetch failed ({t}), using synthetic")
        return None


def run_one_batch(source: str, template: dict):
    """Run one batch of mining for given source."""
    m = Miner(mode="real", source=source)
    m.template = template
    m.target_int = int(template["target_hex"], 16)
    m.run(max_attempts=BATCH_ATTEMPTS, max_seconds=BATCH_SECONDS)
    s = m.summary()
    _state["total_attempts"][source] += s["attempts"]
    _state["total_hits"][source] += s["hits"]
    if s["best_zeros"] > _state["best_zeros"][source]:
        _state["best_zeros"][source] = s["best_zeros"]
        _state["best_nonce"][source] = s["best_nonce"]
        _state["best_hash"][source] = s["best_hash"]
        log_peak(source, s["best_zeros"], s["best_nonce"],
                 s["best_hash"], template)
        log(f"  [{source}] NEW PEAK: {s['best_zeros']} zero bits  "
            f"hash={s['best_hash'][:24]}... nonce={s['best_nonce']}")
    return s


def main_loop():
    log(f"=== phi_btc_daemon STARTED ===")
    log(f"  Batch: {BATCH_ATTEMPTS} attempts × max {BATCH_SECONDS}s")
    log(f"  Refresh real template every {TEMPLATE_REFRESH_EVERY_N_BATCHES} batches")

    stop_flag = {"stop": False}

    def handle_stop(signum, frame):
        stop_flag["stop"] = True
        log("SIGTERM/INT received — saving and exiting")

    signal.signal(signal.SIGTERM, handle_stop)
    signal.signal(signal.SIGINT, handle_stop)

    while not stop_flag["stop"]:
        force = (_state["batches_done"] % TEMPLATE_REFRESH_EVERY_N_BATCHES == 0)
        template = get_template(force_refresh=force)
        if not template:
            log("no template available, sleeping 30s")
            time.sleep(30)
            continue

        for source in ("phi", "random"):
            if stop_flag["stop"]:
                break
            s = run_one_batch(source, template)
            hps = s.get("h_per_sec")
            hps_str = f"{hps:.0f}" if hps else "?"
            log(f"  [{source}] batch: attempts={s['attempts']} "
                f"hits={s['hits']} best={s['best_zeros']} "
                f"H/s={hps_str}")

        _state["batches_done"] += 1
        save_summary()

        # rolling status every 10 batches
        if _state["batches_done"] % 10 == 0:
            phi_a = _state["total_attempts"]["phi"]
            rnd_a = _state["total_attempts"]["random"]
            log(f"=== ROLLING SUMMARY (batch {_state['batches_done']}) ===")
            log(f"  phi:    {phi_a:>14,} attempts  "
                f"hits={_state['total_hits']['phi']}  "
                f"best={_state['best_zeros']['phi']}")
            log(f"  random: {rnd_a:>14,} attempts  "
                f"hits={_state['total_hits']['random']}  "
                f"best={_state['best_zeros']['random']}")

    save_summary()
    log("daemon exited cleanly")


if __name__ == "__main__":
    main_loop()
