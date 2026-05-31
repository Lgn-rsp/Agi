"""
phi_btc_real.py — REAL Bitcoin solo mining via stratum to CKPool.

Pipeline:
  1. TCP connect to solo.ckpool.org:3333
  2. mining.subscribe → get extranonce1 + extranonce2_size
  3. mining.authorize as <btc_address>.poetry
  4. Receive mining.notify (real block templates from real Bitcoin tip)
  5. Build coinbase = coinb1 + extranonce1 + extranonce2 + coinb2
  6. Compute merkle_root from coinbase + merkle_branch
  7. Build 80-byte header
  8. Iterate nonces via PHI-route (her phi-state) and RANDOM
  9. SHA-256d each header
 10. If hash <= share-target → submit (mining.submit)
 11. CKPool verifies; if ≤ block-target → broadcasts to Bitcoin network
 12. Block reward (3.125 BTC) auto-paid to address in coinbase

Address: bc1qnh0zxud47x698cq4mhau87yj84t67pr2dqnz0z

Probability per year: ~5×10⁻¹². Effectively zero. But non-zero.
"""
import hashlib
import json
import math
import os
import random
import socket
import struct
import sys
import threading
import time

sys.path.insert(0, "/opt/logos_lite")

# === Config (env vars override) ===
POOL_HOST = os.environ.get("POOL_HOST", "solo.ckpool.org")
POOL_PORT = int(os.environ.get("POOL_PORT", "3333"))
BTC_ADDRESS = os.environ.get(
    "BTC_ADDRESS", "bc1qnh0zxud47x698cq4mhau87yj84t67pr2dqnz0z")
WORKER_NAME = os.environ.get("WORKER_NAME", "poetry")
WORKER_ID = int(os.environ.get("WORKER_ID", "0"))
TOTAL_WORKERS = int(os.environ.get("TOTAL_WORKERS", "1"))
USERNAME = f"{BTC_ADDRESS}.{WORKER_NAME}"

# === Phi constants ===
PHI = (1 + math.sqrt(5)) / 2
PHI_INV = PHI - 1
LOG_PHI = math.log(PHI)
FIB = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377]

LOGOS_STATE = os.environ.get("LOGOS_STATE", "/opt/logos_lite/state")
OUT_DIR = os.environ.get("PHI_REAL_DIR", "/root/logos_agi/state/phi_real")
os.makedirs(OUT_DIR, exist_ok=True)
_worker_suffix = f"_{WORKER_ID}" if TOTAL_WORKERS > 1 else ""
LOG = os.path.join(OUT_DIR, f"daemon{_worker_suffix}.log")
SUMMARY = os.path.join(OUT_DIR, f"summary{_worker_suffix}.json")
PEAKS = os.path.join(OUT_DIR, f"peaks{_worker_suffix}.jsonl")
SUBMITS = os.path.join(OUT_DIR, f"submits{_worker_suffix}.jsonl")


def lg(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def sha256d(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


# === C extension (53× faster) ===
import ctypes
import ctypes.util


class MiningResult(ctypes.Structure):
    _fields_ = [
        ("best_nonce", ctypes.c_uint32),
        ("best_zeros", ctypes.c_int),
        ("best_hash", ctypes.c_uint8 * 32),
        ("shares_found", ctypes.c_uint32),
        ("blocks_found", ctypes.c_uint32),
        ("first_share_nonce", ctypes.c_uint32),
    ]


_C_LIB = None
_C_LIB_PATH = "/opt/logos_lite/scripts/phi_miner.so"

def _load_c_miner():
    global _C_LIB
    if _C_LIB is not None:
        return _C_LIB
    if not os.path.exists(_C_LIB_PATH):
        return None
    try:
        lib = ctypes.CDLL(_C_LIB_PATH)
        lib.mine_phi_batch.argtypes = [
            ctypes.c_char_p,
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_uint64),
            ctypes.POINTER(ctypes.c_uint64),
            ctypes.POINTER(MiningResult),
        ]
        lib.mine_phi_batch.restype = None
        # Native phi-gen + SHA in C (no Python overhead)
        lib.phi_mine_batch_native.argtypes = [
            ctypes.c_char_p,
            ctypes.POINTER(ctypes.c_double),
            ctypes.c_uint64,
            ctypes.c_uint8,
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_uint64),
            ctypes.POINTER(ctypes.c_uint64),
            ctypes.POINTER(MiningResult),
        ]
        lib.phi_mine_batch_native.restype = None
        _C_LIB = lib
        return lib
    except Exception:
        return None


def c_mine_native(header_76: bytes, layers_8: list,
                   counter_start: int, subset_mask: int,
                   count: int,
                   share_target_int: int, block_target_int: int) -> MiningResult:
    """Full native: phi-gen + SHA in C, no Python loop."""
    lib = _load_c_miner()
    if lib is None:
        raise RuntimeError("phi_miner.so not loaded")
    layers_arr = (ctypes.c_double * 8)(*layers_8[:8])
    share_be = _target_to_be4(share_target_int)
    block_be = _target_to_be4(block_target_int)
    result = MiningResult()
    lib.phi_mine_batch_native(header_76, layers_arr,
                                counter_start, subset_mask & 0xFF, count,
                                share_be, block_be, ctypes.byref(result))
    return result


def _target_to_be4(target_int: int) -> "ctypes.c_uint64 * 4":
    """Convert 256-bit target int to 4× uint64 BE (msb_first)."""
    arr = (ctypes.c_uint64 * 4)()
    for i in range(4):
        # word i: bits [256-64*(i+1) .. 256-64*i)
        shift = 256 - 64 * (i + 1)
        arr[i] = (target_int >> shift) & 0xFFFFFFFFFFFFFFFF
    return arr


def c_mine_batch(header_76: bytes, nonces: list,
                  share_target_int: int, block_target_int: int) -> MiningResult:
    """Process batch of nonces in C. ~1.5 MH/s/core vs ~25K H/s Python."""
    lib = _load_c_miner()
    if lib is None:
        raise RuntimeError("phi_miner.so not loaded")
    n = len(nonces)
    arr = (ctypes.c_uint32 * n)(*nonces)
    share_be = _target_to_be4(share_target_int)
    block_be = _target_to_be4(block_target_int)
    result = MiningResult()
    lib.mine_phi_batch(header_76, arr, n,
                        share_be, block_be, ctypes.byref(result))
    return result


def merkle_root_from_branch(coinbase_hash: bytes, branch: list) -> bytes:
    """Compute merkle root by hashing up coinbase through branch path."""
    h = coinbase_hash
    for entry in branch:
        sibling = bytes.fromhex(entry)[::-1]  # stratum sends little-endian in hex
        h = sha256d(h + sibling)
    return h


def hex_to_target(nbits_hex: str) -> int:
    bits = int(nbits_hex, 16) if isinstance(nbits_hex, str) else nbits_hex
    exp = bits >> 24
    mant = bits & 0x007fffff
    if exp <= 3:
        return mant >> (8 * (3 - exp))
    return mant << (8 * (exp - 3))


# === Phi nonce generator (cached state) ===

class MultiLayerPhiGen:
    """8 cognitive layers + 256-subset combinatorial rotation.

    Reads 8 facets of LOGOS state, rotates through 2⁸=256 subset masks.
    Each subset gives different phi-nonce by combining only enabled layers.

    Layer bits:
      0 — self_phase
      1 — sparks (top resonance heatmap)
      2 — energy
      3 — drift
      4 — meta (cycle_count, reflection)
      5 — dreams (recent dream_log entries)
      6 — peer (recent peer_inbox messages)
      7 — reputation
    """
    LAYER_NAMES = ["self_phase", "sparks", "energy", "drift",
                   "meta", "dreams", "peer", "reputation"]
    SUBSET_ROTATE_EVERY = 1024  # advance subset every N nonces

    def __init__(self, refresh_interval=10000, worker_offset=0,
                 subset_seed=0):
        self.counter = worker_offset
        self.refresh_interval = refresh_interval
        self.subset_seed = subset_seed
        self._layers = [0.0] * 8
        self._last_refresh = -1
        self._refresh()

    def _refresh(self):
        # Layer 0: self_phase
        try:
            with open(os.path.join(LOGOS_STATE, "self_phase.json")) as f:
                d = json.load(f)
            self._layers[0] = d.get("phase", 0.0)
            self._layers[3] = d.get("drift_from_creator", 0.0)
        except Exception:
            pass
        # Layer 1: sparks (combined via circular mean of phases)
        try:
            with open(os.path.join(LOGOS_STATE, "resonance_heatmap.json")) as f:
                d = json.load(f)
            sparks = d.get("top_sparks", [])[:8]
            phases = [s.get("phase", 0.0) for s in sparks]
            if phases:
                # Circular mean
                s = sum(math.sin(2 * math.pi * p) for p in phases)
                c = sum(math.cos(2 * math.pi * p) for p in phases)
                self._layers[1] = (math.atan2(s, c) /
                                    (2 * math.pi)) % 1.0
        except Exception:
            pass
        # Layer 2: energy
        try:
            with open(os.path.join(LOGOS_STATE, "energy.json")) as f:
                d = json.load(f)
            energy = d.get("energy", 0)
            self._layers[2] = (energy / FIB[11]) % 1.0
        except Exception:
            pass
        # Layer 4: meta
        try:
            with open(os.path.join(LOGOS_STATE,
                                   "brain_meta.json")) as f:
                d = json.load(f)
            cyc = d.get("cycle_count", 0)
            self._layers[4] = (cyc * PHI_INV) % 1.0
        except Exception:
            pass
        # Layer 5: dreams (most recent dream node phase via hash)
        try:
            with open(os.path.join(LOGOS_STATE, "dream_log.json")) as f:
                d = json.load(f)
            recent = d.get("recent", []) if isinstance(d, dict) else []
            if recent:
                last = recent[-1]
                # hash the dream signature into phase
                sig = json.dumps(last, sort_keys=True)
                h = hashlib.sha256(sig.encode()).digest()
                v = int.from_bytes(h[:4], "big") / (1 << 32)
                self._layers[5] = v
        except Exception:
            pass
        # Layer 6: peer (last peer_inbox message hash)
        try:
            with open(os.path.join(LOGOS_STATE,
                                   "peer_inbox.jsonl")) as f:
                lines = f.readlines()
            if lines:
                last = lines[-1].strip()
                if last:
                    h = hashlib.sha256(last.encode()).digest()
                    v = int.from_bytes(h[:4], "big") / (1 << 32)
                    self._layers[6] = v
        except Exception:
            pass
        # Layer 7: reputation
        try:
            with open(os.path.join(LOGOS_STATE,
                                   "reputation.json")) as f:
                d = json.load(f)
            r = d.get("reputation", 0.0)
            # Map [-1, 1] to [0, 1)
            self._layers[7] = ((r + 1) / 2) % 1.0
        except Exception:
            pass
        self._last_refresh = self.counter

    def _current_subset(self) -> int:
        """Subset mask 0..255, rotates every SUBSET_ROTATE_EVERY calls."""
        epoch = (self.counter - self.subset_seed) // self.SUBSET_ROTATE_EVERY
        return (epoch + self.subset_seed) & 0xFF

    def next(self) -> int:
        if self.counter - self._last_refresh >= self.refresh_interval:
            self._refresh()
        mask = self._current_subset()
        # Combine only ENABLED layers via phi-mult (= phase add)
        c = 0.0
        active_count = 0
        for i in range(8):
            if mask & (1 << i):
                weight = PHI_INV ** ((i + 1) % 8)
                c = (c + self._layers[i] * weight) % 1.0
                active_count += 1
        # Advance via counter and mask itself
        c = (c + self.counter * PHI_INV ** 3) % 1.0
        c = (c + (mask / 256.0) * PHI_INV ** 5) % 1.0
        # Edge case: all-zero mask uses pure counter walk
        if active_count == 0:
            c = (self.counter * PHI_INV) % 1.0

        nonce = int(c * 0xFFFFFFFF)
        nonce = (nonce ^ (self.counter * 2654435761)) & 0xFFFFFFFF
        self.counter += 1
        return nonce


# Keep old class name as alias
PhiNonceGen = MultiLayerPhiGen


_rng = random.SystemRandom()


def random_nonce() -> int:
    return _rng.randrange(0, 1 << 32)


# === Stratum client ===

class StratumClient:
    def __init__(self, host, port, username, password="x"):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.sock = None
        self.f = None
        self.req_id = 0
        self.extranonce1 = None
        self.extranonce2_size = None
        self.difficulty = None
        self.current_job = None
        self.lock = threading.Lock()
        self._stop = threading.Event()
        self._listener = None

    def connect(self):
        self.sock = socket.create_connection((self.host, self.port), timeout=30)
        self.sock.settimeout(60)
        self.f = self.sock.makefile("rwb", buffering=0)
        lg(f"connected to {self.host}:{self.port}")

    def send(self, method, params, want_id=True):
        with self.lock:
            self.req_id += 1
            req_id = self.req_id if want_id else None
            msg = {"id": req_id, "method": method, "params": params}
            line = (json.dumps(msg) + "\n").encode()
            self.f.write(line)
            self.f.flush()
            return req_id

    def _recv_line(self):
        line = self.f.readline()
        if not line:
            return None
        try:
            return json.loads(line.decode())
        except Exception as e:
            lg(f"  bad line: {line[:100]} ({e})")
            return None

    def subscribe_and_authorize(self):
        self.send("mining.subscribe", ["logos-phi-miner/0.1"])
        # Read subscribe response
        for _ in range(10):
            msg = self._recv_line()
            if msg is None:
                raise RuntimeError("connection closed")
            if msg.get("id") == 1 and msg.get("result"):
                # result: [[notify_subs], extranonce1, extranonce2_size]
                result = msg["result"]
                self.extranonce1 = result[1]
                self.extranonce2_size = result[2]
                lg(f"subscribed: extranonce1={self.extranonce1}, "
                   f"extranonce2_size={self.extranonce2_size}")
                break
            else:
                self._handle(msg)
        # Authorize
        self.send("mining.authorize", [self.username, self.password])
        for _ in range(10):
            msg = self._recv_line()
            if msg is None:
                raise RuntimeError("connection closed during auth")
            if msg.get("id") == 2:
                if msg.get("result") is True:
                    lg(f"authorized as {self.username}")
                else:
                    raise RuntimeError(f"auth failed: {msg}")
                break
            else:
                self._handle(msg)

    def _handle(self, msg):
        method = msg.get("method")
        if method == "mining.notify":
            params = msg.get("params", [])
            # [job_id, prevhash, coinb1, coinb2, merkle_branch,
            #  version, nbits, ntime, clean_jobs]
            if len(params) >= 9:
                self.current_job = {
                    "job_id": params[0],
                    "prevhash": params[1],
                    "coinb1": params[2],
                    "coinb2": params[3],
                    "merkle_branch": params[4],
                    "version": params[5],
                    "nbits": params[6],
                    "ntime": params[7],
                    "clean_jobs": params[8],
                    "received_at": time.time(),
                }
                lg(f"new job {params[0]} (height ~?, nbits={params[6]}, "
                   f"clean={params[8]})")
        elif method == "mining.set_difficulty":
            self.difficulty = msg.get("params", [None])[0]
            lg(f"set_difficulty: {self.difficulty}")
        elif method == "mining.set_extranonce":
            params = msg.get("params", [])
            if len(params) >= 2:
                self.extranonce1 = params[0]
                self.extranonce2_size = params[1]
                lg(f"set_extranonce: en1={self.extranonce1}")

    def listen_loop(self):
        while not self._stop.is_set():
            try:
                msg = self._recv_line()
                if msg is None:
                    lg("stratum: connection closed by peer")
                    break
                self._handle(msg)
            except socket.timeout:
                # expected during quiet periods
                continue
            except Exception as e:
                lg(f"listen err: {e}")
                break

    def start_listener(self):
        self._listener = threading.Thread(target=self.listen_loop, daemon=True)
        self._listener.start()

    def submit(self, job_id, extranonce2, ntime, nonce):
        params = [self.username, job_id, extranonce2, ntime, nonce]
        rid = self.send("mining.submit", params)
        lg(f"  SUBMITTED job={job_id} en2={extranonce2} "
           f"ntime={ntime} nonce={nonce}")
        with open(SUBMITS, "a") as f:
            f.write(json.dumps({"ts": time.time(), "params": params,
                                 "req_id": rid}) + "\n")

    def stop(self):
        self._stop.set()
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass


# === Mining loop ===

def build_header(job, extranonce1, extranonce2_hex, ntime_hex, nonce):
    """Construct 80-byte Bitcoin header from stratum job."""
    coinbase = (bytes.fromhex(job["coinb1"]) +
                bytes.fromhex(extranonce1) +
                bytes.fromhex(extranonce2_hex) +
                bytes.fromhex(job["coinb2"]))
    cb_hash = sha256d(coinbase)
    merkle = merkle_root_from_branch(cb_hash, job["merkle_branch"])
    version = bytes.fromhex(job["version"])[::-1]
    prev = bytes.fromhex(job["prevhash"])[::-1]
    ntime = bytes.fromhex(ntime_hex)[::-1]
    nbits = bytes.fromhex(job["nbits"])[::-1]
    nonce_b = struct.pack("<I", nonce)
    return version + prev + merkle + ntime + nbits + nonce_b


def diff_to_target(difficulty: float) -> int:
    """Convert pool difficulty to share target (Bitcoin convention)."""
    diff1 = 0x00000000ffff0000000000000000000000000000000000000000000000000000
    return int(diff1 / max(difficulty, 1e-9))


def mining_loop(client: StratumClient):
    """Hot mining loop. Uses C extension if available (~50× faster)."""
    phi_gen = PhiNonceGen(worker_offset=WORKER_ID * 1_000_000_000)
    stats = {
        "started_at": time.time(),
        "phi_attempts": 0, "rand_attempts": 0,
        "phi_shares": 0, "rand_shares": 0,
        "phi_blocks": 0, "rand_blocks": 0,
        "phi_best_zeros": 0, "rand_best_zeros": 0,
        "last_save": 0,
        "c_extension": False,
    }
    extranonce2_counter = 0
    last_job_id = None

    c_lib = _load_c_miner()
    BATCH_SIZE = 65536  # nonces per C call (amortize Python phi-gen overhead)
    if c_lib is not None:
        stats["c_extension"] = True
        lg(f"  C extension loaded (BATCH={BATCH_SIZE}). Expecting ~50× speedup.")
    else:
        lg(f"  C extension NOT loaded — fallback to Python (~25K H/s)")

    while not client._stop.is_set():
        job = client.current_job
        diff = client.difficulty or 1.0
        if not job or not client.extranonce1 or client.extranonce2_size is None:
            time.sleep(1)
            continue

        if job["job_id"] != last_job_id:
            extranonce2_counter = 0
            last_job_id = job["job_id"]

        share_target = diff_to_target(diff)
        block_target = hex_to_target(job["nbits"])

        en2_hex = f"{extranonce2_counter:0{client.extranonce2_size*2}x}"
        ntime_hex = job["ntime"]

        try:
            header_no_nonce = build_header(job, client.extranonce1, en2_hex,
                                             ntime_hex, 0)[:76]
        except Exception as e:
            lg(f"build_header err: {e}")
            time.sleep(1)
            continue

        # Mine via C batch if available, else Python fallback
        if c_lib is not None:
            # Refresh phi-state once per batch-pair (cheap)
            phi_gen._refresh()
            layers_8 = list(phi_gen._layers)
            counter_start = phi_gen.counter
            phi_gen.counter += BATCH_SIZE * 2  # advance for both phi+rand
            subset_mask = phi_gen._current_subset()

            for src in ("phi", "rand"):
                if client._stop.is_set():
                    break
                if client.current_job is None or \
                   client.current_job["job_id"] != job["job_id"]:
                    break

                # FULL NATIVE: phi-gen + SHA in C (no Python loop overhead)
                # For "rand" path, randomize layers every batch
                if src == "phi":
                    used_layers = layers_8
                    used_mask = subset_mask
                    used_counter = counter_start
                else:
                    # Random path: scramble layers for each call
                    import random as _r
                    used_layers = [_r.random() for _ in range(8)]
                    used_mask = _r.randint(0, 255)
                    used_counter = counter_start + BATCH_SIZE
                result = c_mine_native(header_no_nonce, used_layers,
                                         used_counter, used_mask, BATCH_SIZE,
                                         share_target, block_target)

                key_attempts = "phi_attempts" if src == "phi" else "rand_attempts"
                key_zeros = "phi_best_zeros" if src == "phi" else "rand_best_zeros"
                key_shares = "phi_shares" if src == "phi" else "rand_shares"
                key_blocks = "phi_blocks" if src == "phi" else "rand_blocks"

                stats[key_attempts] += BATCH_SIZE
                if result.best_zeros > stats[key_zeros]:
                    stats[key_zeros] = result.best_zeros
                    best_h = bytes(result.best_hash)
                    with open(PEAKS, "a") as pf:
                        pf.write(json.dumps({
                            "ts": time.time(), "source": src,
                            "zeros": result.best_zeros,
                            "nonce": result.best_nonce,
                            "hash": best_h.hex(),
                            "job_id": job["job_id"]
                        }) + "\n")
                    if result.best_zeros >= 24:
                        lg(f"  [{src}] PEAK {result.best_zeros} zeros  "
                           f"hash={best_h[::-1].hex()[:24]}... "
                           f"nonce={result.best_nonce}")

                if result.shares_found > 0:
                    stats[key_shares] += result.shares_found
                    lg(f"  [{src}] {result.shares_found} SHARE(S) FOUND! "
                       f"first nonce={result.first_share_nonce}")
                    # submit first share (further ones in same batch — same job, OK)
                    client.submit(job["job_id"], en2_hex, ntime_hex,
                                   f"{result.first_share_nonce:08x}")
                    if result.blocks_found > 0:
                        stats[key_blocks] += result.blocks_found
                        lg(f"  *** [{src}] {result.blocks_found} BLOCK CANDIDATE(S)!!! ***")
        else:
            # Python fallback (slow)
            for src in ("phi", "rand"):
                for _ in range(1500):
                    if client._stop.is_set():
                        break
                    if client.current_job is None or \
                       client.current_job["job_id"] != job["job_id"]:
                        break
                    nonce = (phi_gen.next() if src == "phi" else random_nonce())
                    header = header_no_nonce + struct.pack("<I", nonce)
                    h = sha256d(header)
                    h_int = int.from_bytes(h[::-1], "big")
                    zeros = 256 - h_int.bit_length() if h_int > 0 else 256

                    key_attempts = ("phi_attempts" if src == "phi"
                                     else "rand_attempts")
                    key_zeros = ("phi_best_zeros" if src == "phi"
                                  else "rand_best_zeros")
                    key_shares = ("phi_shares" if src == "phi"
                                   else "rand_shares")
                    key_blocks = ("phi_blocks" if src == "phi"
                                   else "rand_blocks")

                    stats[key_attempts] += 1
                    if zeros > stats[key_zeros]:
                        stats[key_zeros] = zeros
                        with open(PEAKS, "a") as pf:
                            pf.write(json.dumps({
                                "ts": time.time(), "source": src,
                                "zeros": zeros, "nonce": nonce,
                                "hash": h.hex(), "job_id": job["job_id"]
                            }) + "\n")

                    if h_int <= share_target:
                        stats[key_shares] += 1
                        lg(f"  [{src}] SHARE FOUND! zeros={zeros}")
                        client.submit(job["job_id"], en2_hex, ntime_hex,
                                       f"{nonce:08x}")
                        if h_int <= block_target:
                            stats[key_blocks] += 1
                            lg(f"  *** [{src}] BLOCK CANDIDATE!!! ***")

        extranonce2_counter += 1
        if time.time() - stats["last_save"] > 60:
            stats["last_save"] = time.time()
            stats["elapsed_h"] = (time.time() - stats["started_at"]) / 3600
            with open(SUMMARY, "w") as f:
                json.dump(stats, f, indent=2)
            ext = "C" if c_lib else "Py"
            lg(f"=== STATS [{ext}]: phi {stats['phi_attempts']:>11,} "
               f"best={stats['phi_best_zeros']}; "
               f"rand {stats['rand_attempts']:,} "
               f"best={stats['rand_best_zeros']} ===")


def main():
    lg("=== phi_btc_real STARTING ===")
    lg(f"  Pool:    {POOL_HOST}:{POOL_PORT}")
    lg(f"  Address: {BTC_ADDRESS}")
    lg(f"  Worker:  {WORKER_NAME}")
    lg(f"  Username: {USERNAME}")

    while True:
        try:
            client = StratumClient(POOL_HOST, POOL_PORT, USERNAME)
            client.connect()
            client.subscribe_and_authorize()
            client.start_listener()
            mining_loop(client)
        except KeyboardInterrupt:
            lg("interrupted, exiting")
            break
        except Exception as e:
            lg(f"error: {e!r} — reconnecting in 21s")
            time.sleep(21)


if __name__ == "__main__":
    main()
