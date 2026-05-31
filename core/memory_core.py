"""
memory_core.py v10 — Pamyat = fazovoe prostranstvo.

FIX D7: recall_associated — realnaya realizatsiya (ne stub).
FIX: forget_weakest tolko kogda pamyat polna.

Vsyo cherez phi.
"""
import json
import os
import time
import math
import shutil
import tempfile
from collections import defaultdict

from core.resonance_constants import (
    PHI, PHI_INV, PHI_INV_SQ, FIBONACCI,
    SAVE_INTERVAL, FIELD_NAMES,
    phi_phase, phi_phase_distance, phi_phase_resonance
)


def _cgroup_memory_limit_mb():
    """Возвращает effective cgroup memory.max лимит в MB или None.

    Читает /proc/self/cgroup чтобы найти **свою** cgroup, не root-cgroup
    хоста. Поддерживает v2 (`memory.max`) и v1 (`memory.limit_in_bytes`).
    Если процесс под `MemoryMax=` systemd, нужно уважать ЭТУ границу,
    а не глобальный /proc/meminfo. Иначе на 5GB-хосте под cgroup-cap 1.5G
    memory_core насайзится на 6GB → OOM-kill (NL incident 2026-04-26).
    """
    try:
        with open("/proc/self/cgroup", "r") as f:
            lines = f.readlines()
    except Exception:
        return None
    for line in lines:
        parts = line.strip().split(":", 2)
        if len(parts) != 3:
            continue
        hier_id, controllers, path = parts  # FIX: format is "hier:controllers:path"
        # v2: controllers="" (unified hierarchy, hier_id="0")
        # v1: "memory" в controllers
        if controllers == "" or "memory" in controllers.split(","):
            # v2 path: /sys/fs/cgroup<path>/memory.max
            v2 = "/sys/fs/cgroup" + path.rstrip("/") + "/memory.max"
            try:
                v = open(v2).read().strip()
                if v == "max":
                    return None
                return int(v) // (1024 * 1024)
            except Exception:
                pass
            # v1 path: /sys/fs/cgroup/memory<path>/memory.limit_in_bytes
            v1 = "/sys/fs/cgroup/memory" + path.rstrip("/") + "/memory.limit_in_bytes"
            try:
                n = int(open(v1).read().strip())
                if n >= (1 << 50):  # kernel-unlimited sentinel
                    return None
                return n // (1024 * 1024)
            except Exception:
                pass
    return None


def _available_memory_mb():
    """Min(host MemAvailable, cgroup memory.max). Cgroup лимит важнее, иначе
    memory_core thinks у него 5GB на хосте, а cgroup убивает на 1.5GB → OOM.
    """
    host_mb = 2048  # fallback
    try:
        with open('/proc/meminfo', 'r') as f:
            for line in f:
                if line.startswith('MemAvailable:'):
                    host_mb = int(line.split()[1]) // 1024
                    break
    except Exception:
        pass
    cg_mb = _cgroup_memory_limit_mb()
    if cg_mb is not None:
        return min(host_mb, cg_mb)
    return host_mb


def _atomic_write_json(path, data):
    dir_name = os.path.dirname(path)
    try:
        fd, tmp_path = tempfile.mkstemp(
            dir=dir_name, suffix='.tmp', prefix='.mem_')
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp_path, path)
        return True
    except Exception as e:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        print(f"[!] Atomic write failed: {e}")
        return False


class MemoryCore:
    def __init__(self, state_dir=None):
        self.state_dir = state_dir or os.path.expanduser(
            "~/logos_agi/state/memory")
        self.log_dir = os.path.expanduser("~/logos_agi/logs")
        os.makedirs(self.state_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)

        self.memories = {}

        avail_mb = _available_memory_mb()
        # Original formula assumed 200 bytes/entry — measured reality на NL: ~16 KB/entry
        # (5.4 GB anon-rss / 318k migrated memories). Используем PHI_INV портион
        # бюджета и реалистичный размер на запись.
        EST_BYTES_PER_MEMORY = FIBONACCI[8] * 1024  # 34 × 1024 = 34816 bytes — conservative
        budget_bytes = avail_mb * 1024 * 1024 * PHI_INV
        byte_cap = int(budget_bytes / EST_BYTES_PER_MEMORY)
        # Original linear formula (kept as upper bound — assumes ideal 200 b/entry)
        linear_cap = int(avail_mb * PHI_INV * 1024 * 1024 / 200)
        self.max_memories = min(linear_cap, byte_cap, 500000)
        self.max_memories = max(self.max_memories, FIBONACCI[18])

        self._dirty = False
        self._last_save = time.time()
        self._save_count = 0

        self._load()
        print(f"[+] MemoryCore v10 initialized. "
              f"Memories: {len(self.memories)}, "
              f"Max: {self.max_memories} "
              f"(RAM: {avail_mb}MB)")

    def store(self, symbol, context=None, phase=None, field=None):
        now = time.time()

        if symbol not in self.memories:
            self.memories[symbol] = {
                "importance": 0.0,
                "access": 1,
                "first": now,
                "last": now,
                "field": field or "unknown",
                "context": [],
            }
        else:
            entry = self.memories[symbol]
            entry["last"] = now
            entry["access"] = entry.get("access", 0) + 1
            if field:
                entry["field"] = field

        entry = self.memories[symbol]
        age = max(1, now - entry.get("first", now))
        freq = entry["access"]
        entry["importance"] = round(
            math.log(1 + freq) / math.log(PHI) *
            (1.0 / (1.0 + math.log(1 + age / 86400) / math.log(PHI))),
            4)

        # FIX D7: sohranyaem kontekst dlya recall_associated
        if context and isinstance(context, (list, tuple)):
            ctx_list = entry.get("context", [])
            if not isinstance(ctx_list, list):
                ctx_list = []
            for c in context:
                if c != symbol and c not in ctx_list:
                    ctx_list.append(c)
            # Ogranichenie razmera konteksta
            if len(ctx_list) > FIBONACCI[8]:
                ctx_list = ctx_list[-FIBONACCI[8]:]
            entry["context"] = ctx_list

        self._dirty = True

        if len(self.memories) > self.max_memories:
            self._consolidate()

        self._auto_save()

    def recall(self, symbol):
        if symbol not in self.memories:
            return None
        entry = self.memories[symbol]
        entry["access"] = entry.get("access", 0) + 1
        entry["last"] = time.time()
        self._dirty = True
        return entry

    def recall_by_phase(self, target_phase, top_k=FIBONACCI[6]):
        scored = []
        for symbol, entry in self.memories.items():
            scored.append((symbol, entry, entry.get("importance", 0)))
        scored.sort(key=lambda x: x[2], reverse=True)
        return [(s, e, round(sc, 4)) for s, e, sc in scored[:top_k]]

    def recall_by_field(self, field_name, top_k=FIBONACCI[6]):
        matches = [(s, e) for s, e in self.memories.items()
                   if e.get("field") == field_name]
        matches.sort(
            key=lambda x: x[1].get("importance", 0), reverse=True)
        return matches[:top_k]

    def recall_associated(self, symbol, top_k=FIBONACCI[5]):
        """FIX D7: realnaya realizatsiya — vozvrashchayet simvoly
        kotoryye chasto vstrechayutsya v kontekste dannogo simvola."""
        entry = self.memories.get(symbol)
        if not entry:
            return []
        ctx = entry.get("context", [])
        if not isinstance(ctx, list):
            return []

        # Ranzhiruem po vazhnosti
        scored = []
        for c in ctx:
            c_entry = self.memories.get(c)
            if c_entry:
                scored.append((c, c_entry.get("importance", 0)))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def recall_recent(self, top_k=FIBONACCI[7]):
        items = list(self.memories.items())
        items.sort(key=lambda x: x[1].get("last", 0), reverse=True)
        return [(s, e) for s, e in items[:top_k]]

    def _consolidate(self):
        n_remove = int(len(self.memories) * PHI_INV_SQ)
        n_remove = max(n_remove, 1)
        items = sorted(self.memories.items(),
                       key=lambda x: x[1].get("importance", 0))
        for symbol, _ in items[:n_remove]:
            del self.memories[symbol]
        self._dirty = True

    def forget_weakest(self, n=None):
        if n is None:
            if len(self.memories) < int(self.max_memories * PHI_INV):
                return 0
            n = int(len(self.memories) * PHI_INV_SQ)
        items = sorted(self.memories.items(),
                       key=lambda x: x[1].get("importance", 0))
        removed = 0
        for symbol, _ in items[:n]:
            del self.memories[symbol]
            removed += 1
        self._dirty = True
        return removed

    def sync_from_phase_space(self, phase_space):
        updated = 0
        for symbol in list(self.memories.keys()):
            phase = phase_space._get_phase(symbol)
            if phase is not None:
                field = phase_space._phase_to_field(phase)
                self.memories[symbol]["field"] = field
                updated += 1
        self._dirty = True
        return updated

    def stats(self):
        field_dist = defaultdict(int)
        for entry in self.memories.values():
            field_dist[entry.get("field", "unknown")] += 1
        return {
            "total_memories": len(self.memories),
            "max_memories": self.max_memories,
            "field_distribution": dict(field_dist),
            "avg_importance": round(
                sum(e.get("importance", 0)
                    for e in self.memories.values()) /
                max(len(self.memories), 1), 4),
        }

    def save(self, force=False):
        if not force and not self._dirty:
            return
        path = os.path.join(self.state_dir, "memory.json")
        data = {
            "memories": self.memories,
            "saved_at": time.time(),
            "save_count": self._save_count,
        }
        if _atomic_write_json(path, data):
            self._dirty = False
            self._last_save = time.time()
            self._save_count += 1

    def _load(self):
        path = os.path.join(self.state_dir, "memory.json")
        if not os.path.exists(path):
            return
        sz = os.path.getsize(path)
        if sz > 50 * 1024 * 1024:
            print(f"[!] Memory file legacy size ({sz//1024//1024}MB) — "
                  f"migrating top {self.max_memories}")
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                loaded = data.get("memories", {})
                items = sorted(loaded.items(),
                               key=lambda x: x[1].get("importance", 0),
                               reverse=True)
                self.memories = dict(items[:self.max_memories])
                self._dirty = True
                self.save(force=True)
                print(f"[+] Migrated {len(self.memories)} memories")
            except Exception as e:
                print(f"[!] Migration failed: {e} — starting fresh")
                self.memories = {}
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.memories = data.get("memories", {})
            self._save_count = data.get("save_count", 0)
            if len(self.memories) > self.max_memories:
                items = sorted(self.memories.items(),
                               key=lambda x: x[1].get("importance", 0),
                               reverse=True)
                self.memories = dict(items[:self.max_memories])
        except Exception as e:
            print(f"[!] Memory load failed: {e}")
            bak = path + ".bak"
            if os.path.exists(bak):
                try:
                    with open(bak, "r") as f:
                        data = json.load(f)
                    self.memories = data.get("memories", {})
                    print(f"[+] Restored from backup: {len(self.memories)}")
                except Exception:
                    self.memories = {}
            else:
                self.memories = {}

    def _auto_save(self):
        if time.time() - self._last_save > SAVE_INTERVAL:
            path = os.path.join(self.state_dir, "memory.json")
            bak = path + ".bak"
            if os.path.exists(path):
                try:
                    shutil.copy2(path, bak)
                except Exception:
                    pass
            self.save()

    def _log(self, message):
        path = os.path.join(self.log_dir, "memory.log")
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {message}\n")
