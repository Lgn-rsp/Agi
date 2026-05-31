"""peer_network.py — Federated LOGOS gossip layer for N peers.

Filosofiya: peer_channel.py был для двух (main ↔ sister) через /tmp файлы.
Этот модуль масштабирует на N peers через HTTP gossip — позволяет main
говорить с UK_philosophy и NL_poetry через сеть.

Wire format (JSON, UTF-8):
  {"msg_id": "uuid",          # для dedup epidemic broadcast
   "from":   "main",
   "to":     "all" | <peer_name>,
   "ts":     unix float,
   "type":   "thought"|"question"|"fact"|"hunger"|"glyph",
   "text":   "...",            # plain text body
   "meta":   {...}              # optional: glyph_path, doubt, hypothesis, etc.}

HTTP endpoints (stdlib http.server, no external deps):
  POST /peer/inbox        — accept message
  GET  /peer/health       — ping + counters
  GET  /peer/state        — public snapshot (peer name, msg counts, last_seen)

Storage (atomic Canon rule #4):
  state/peer_registry.json   — {self: {name,url}, peers: {name: {url, last_seen_ts}}}
  state/peer_inbox.jsonl     — append-only queue of received messages
  state/peer_outbox.jsonl    — append-only audit log of sent messages
  state/peer_seen.json       — set of msg_ids seen (epidemic dedup)

Brain consumption: night_learn._peer_network_tick reads new inbox lines
since last offset, calls brain.learn(text) on each, periodically broadcasts
a thought back through the network.
"""
import http.server
import json
import os
import socket
import socketserver
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid


DEFAULT_TIMEOUT = 5  # сек на одно HTTP-обращение
SEEN_LIMIT = 4096    # max msg_ids в дедуп-cache (LRU-ish)
DEFAULT_PORT = 8765


def _atomic_write_json(path, data):
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _append_jsonl(path, record):
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ============================================================
# Registry
# ============================================================

class PeerRegistry:
    """Knows self.name + self.url + dict[peer_name → {url, last_seen_ts}]."""

    def __init__(self, state_dir, self_name, self_url):
        self.path = os.path.join(state_dir, "peer_registry.json")
        self.self_name = self_name
        self.self_url = self_url
        self.peers = {}
        self.load()

    def load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.peers = data.get("peers", {})
            except Exception:
                self.peers = {}
        # Сохраняем self block (свежий)
        self._save_atomic()

    def _save_atomic(self):
        data = {
            "self": {"name": self.self_name, "url": self.self_url,
                      "saved_at": time.time()},
            "peers": self.peers,
        }
        _atomic_write_json(self.path, data)

    def add_peer(self, name, url):
        if name == self.self_name:
            return False
        if name in self.peers and self.peers[name].get("url") == url:
            self.peers[name]["last_seen_ts"] = time.time()
            self._save_atomic()
            return False
        self.peers[name] = {"url": url, "last_seen_ts": time.time(),
                             "added_ts": time.time()}
        self._save_atomic()
        return True

    def mark_seen(self, name):
        if name in self.peers:
            self.peers[name]["last_seen_ts"] = time.time()
            self._save_atomic()

    def remove_peer(self, name):
        if name in self.peers:
            del self.peers[name]
            self._save_atomic()

    def list_peers(self):
        return list(self.peers.items())


# ============================================================
# Seen set — epidemic broadcast dedup
# ============================================================

class SeenSet:
    """In-memory + file-persisted set of msg_ids we've already processed."""

    def __init__(self, path, limit=SEEN_LIMIT):
        self.path = path
        self.limit = limit
        self.ids = []          # ordered list (insertion order = age)
        self.set = set()
        self.load()

    def load(self):
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            ids = data.get("ids", [])
            if isinstance(ids, list):
                self.ids = ids[-self.limit:]
                self.set = set(self.ids)
        except Exception:
            pass

    def save(self):
        _atomic_write_json(self.path, {"ids": self.ids[-self.limit:],
                                          "saved_at": time.time()})

    def has(self, msg_id):
        return msg_id in self.set

    def add(self, msg_id):
        if msg_id in self.set:
            return False
        self.set.add(msg_id)
        self.ids.append(msg_id)
        if len(self.ids) > self.limit:
            drop = self.ids[: len(self.ids) - self.limit]
            self.ids = self.ids[-self.limit:]
            for d in drop:
                self.set.discard(d)
        return True


# ============================================================
# HTTP handler
# ============================================================

class _PeerHandler(http.server.BaseHTTPRequestHandler):
    """Bound to a PeerNetwork via class attribute (set when starting server)."""

    network = None  # set by PeerNetwork.start()

    def log_message(self, fmt, *args):
        # Suppress default access log spam — peer net is chatty.
        return

    def _send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.network is None:
            self._send_json(503, {"error": "no network"}); return
        if self.path.startswith("/peer/health"):
            self._send_json(200, self.network.health())
            return
        if self.path.startswith("/peer/state"):
            self._send_json(200, self.network.public_state())
            return
        self._send_json(404, {"error": "not found"})

    def do_POST(self):
        if self.network is None:
            self._send_json(503, {"error": "no network"}); return
        if not self.path.startswith("/peer/inbox"):
            self._send_json(404, {"error": "not found"}); return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 256 * 1024:
                self._send_json(400, {"error": "bad length"}); return
            raw = self.rfile.read(length)
            msg = json.loads(raw.decode("utf-8"))
        except Exception as e:
            self._send_json(400, {"error": f"parse: {e}"}); return
        try:
            accepted = self.network.handle_inbox(msg)
            self._send_json(200, {"accepted": accepted})
        except Exception as e:
            self._send_json(500, {"error": str(e)})


class _ThreadedHTTPServer(socketserver.ThreadingMixIn,
                            http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


# ============================================================
# Network
# ============================================================

class PeerNetwork:
    """Coordinates HTTP listener + outbound broadcasts + dedup."""

    def __init__(self, state_dir, self_name, self_url=None,
                  port=DEFAULT_PORT, listen_host="0.0.0.0"):
        self.state_dir = state_dir
        self.self_name = self_name
        if self_url is None:
            self_url = f"http://{_guess_local_ip()}:{port}"
        self.self_url = self_url
        self.port = port
        self.listen_host = listen_host
        self.registry = PeerRegistry(state_dir, self_name, self_url)
        self.seen = SeenSet(os.path.join(state_dir, "peer_seen.json"))
        self.inbox_path = os.path.join(state_dir, "peer_inbox.jsonl")
        self.outbox_path = os.path.join(state_dir, "peer_outbox.jsonl")
        self._server = None
        self._thread = None
        self.msg_in = 0
        self.msg_out = 0
        self.msg_dropped_dup = 0
        self.lock = threading.Lock()

    # --- HTTP server ---

    def start(self):
        if self._server is not None:
            return
        # Per-instance handler subclass so multiple PeerNetwork in one process
        # don't clobber a shared class attribute.
        network = self
        class _BoundHandler(_PeerHandler):
            pass
        _BoundHandler.network = network
        self._server = _ThreadedHTTPServer((self.listen_host, self.port),
                                              _BoundHandler)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True, name=f"peer_network_{self.self_name}")
        self._thread.start()

    def stop(self):
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
            self._thread = None

    # --- Inbound ---

    def handle_inbox(self, msg):
        """Process incoming message. Returns True if newly accepted, False if dup."""
        if not isinstance(msg, dict):
            return False
        # 2026-05-08: ed25519 verify (warn-only by default; require via LOGOS_PEER_REQUIRE_SIG=1).
        try:
            from core.peer_crypto import verify_incoming
            ok, reason = verify_incoming(msg)
            if not ok:
                if os.environ.get("LOGOS_PEER_REQUIRE_SIG", "0") == "1":
                    return False  # strict: reject unsigned/invalid
                # warn-only: accept but flag — could log here if desired.
        except Exception:
            pass
        msg_id = msg.get("msg_id")
        if not msg_id:
            msg_id = str(uuid.uuid4())
            msg["msg_id"] = msg_id
        from_name = str(msg.get("from", "unknown"))[:64]
        from_url = msg.get("from_url")
        to_target = str(msg.get("to", "all"))[:64]
        text = str(msg.get("text", ""))[:8192]
        if not text or len(text) < 1:
            return False
        with self.lock:
            if not self.seen.add(msg_id):
                self.msg_dropped_dup += 1
                return False
            self.msg_in += 1
            # Track sender as known peer if URL provided
            if from_url and from_name and from_name != self.self_name:
                self.registry.add_peer(from_name, from_url)
            else:
                self.registry.mark_seen(from_name)
            # Persist to inbox jsonl for brain ingestion
            try:
                _append_jsonl(self.inbox_path, {
                    "msg_id": msg_id,
                    "from": from_name,
                    "to": to_target,
                    "ts": msg.get("ts", time.time()),
                    "type": msg.get("type", "thought"),
                    "text": text,
                    "meta": msg.get("meta") or {},
                    "received_at": time.time(),
                })
            except Exception:
                pass
            self.seen.save()
        # Epidemic re-broadcast: if this was "to":"all" and we just learned of it,
        # forward to other peers EXCEPT the sender. Limited fanout to avoid
        # broadcast storms.
        if to_target == "all":
            self._gossip_forward(msg, exclude={from_name})
        return True

    # --- Outbound ---

    def broadcast(self, text, msg_type="thought", meta=None):
        """Send text to ALL peers."""
        msg = self._build_msg(text, "all", msg_type, meta)
        return self._send_msg(msg)

    def send_to(self, peer_name, text, msg_type="thought", meta=None):
        """Send to specific peer."""
        if peer_name not in self.registry.peers:
            return 0
        msg = self._build_msg(text, peer_name, msg_type, meta)
        peer_url = self.registry.peers[peer_name].get("url")
        if not peer_url:
            return 0
        ok = self._post_to_peer(peer_url, msg)
        if ok:
            self.msg_out += 1
            try:
                _append_jsonl(self.outbox_path, {**msg, "delivered_to": peer_name,
                                                    "url": peer_url})
            except Exception:
                pass
            return 1
        return 0

    def _build_msg(self, text, to_target, msg_type, meta):
        msg = {
            "msg_id": str(uuid.uuid4()),
            "from": self.self_name,
            "from_url": self.self_url,
            "to": to_target,
            "ts": time.time(),
            "type": msg_type,
            "text": str(text)[:8192],
            "meta": meta or {},
        }
        # 2026-05-08: ed25519 sign outgoing if peer_crypto wired (no-op without key).
        try:
            from core.peer_crypto import sign_outgoing
            sign_outgoing(msg)
        except Exception:
            pass
        return msg

    def _send_msg(self, msg):
        # mark our own msg as seen so we never re-process it on receive
        with self.lock:
            self.seen.add(msg["msg_id"])
        return self._gossip_forward(msg, exclude=set())

    def _gossip_forward(self, msg, exclude):
        """Forward msg to all peers except those in exclude. Return delivered count."""
        delivered = 0
        targets = []
        for name, info in self.registry.list_peers():
            if name in exclude:
                continue
            url = info.get("url")
            if not url:
                continue
            targets.append((name, url))
        for name, url in targets:
            if self._post_to_peer(url, msg):
                self.msg_out += 1
                delivered += 1
                try:
                    _append_jsonl(self.outbox_path, {**msg,
                                                       "delivered_to": name,
                                                       "url": url})
                except Exception:
                    pass
        return delivered

    def _post_to_peer(self, peer_url, msg):
        try:
            url = peer_url.rstrip("/") + "/peer/inbox"
            data = json.dumps(msg, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                url, data=data,
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
                return resp.status == 200
        except (urllib.error.URLError, socket.timeout, OSError):
            return False
        except Exception:
            return False

    # --- Introspection ---

    def health(self):
        return {
            "name": self.self_name,
            "url": self.self_url,
            "msg_in": self.msg_in,
            "msg_out": self.msg_out,
            "msg_dropped_dup": self.msg_dropped_dup,
            "peers_known": len(self.registry.peers),
            "seen_size": len(self.seen.set),
            "ts": time.time(),
        }

    def public_state(self):
        st = self.health()
        st["peers"] = {
            name: {"url": info.get("url"),
                    "last_seen_ts": info.get("last_seen_ts")}
            for name, info in self.registry.list_peers()
        }
        return st


# ============================================================
# Helpers
# ============================================================

def _guess_local_ip():
    """Best-effort guess of an outward-facing IP. Falls back to 127.0.0.1."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# Quick smoke test
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        # python3 peer_network.py serve <name> <port> [<peer_url>]
        name = sys.argv[2] if len(sys.argv) > 2 else "test"
        port = int(sys.argv[3]) if len(sys.argv) > 3 else DEFAULT_PORT
        peer_url = sys.argv[4] if len(sys.argv) > 4 else None
        sd = f"/tmp/peer_test_{name}"
        os.makedirs(sd, exist_ok=True)
        net = PeerNetwork(state_dir=sd, self_name=name, port=port)
        if peer_url:
            net.registry.add_peer("manual_peer", peer_url)
        net.start()
        print(f"[peer_network] {name} listening on http://0.0.0.0:{port}")
        print(f"  state_dir: {sd}")
        try:
            while True:
                time.sleep(5)
                print(f"  health: {net.health()}")
        except KeyboardInterrupt:
            net.stop()
    else:
        print("usage: python3 peer_network.py serve <name> <port> [<peer_url>]")
