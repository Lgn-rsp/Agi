"""
self_monitor.py v10 — Ritm, zdorovye, samovosstanovleniye.

FIX K3: _check_memory ispolzuyet memory.max_memories vmesto hardcoded FIBONACCI[18].
FIX: ispolzuyet HARM_THRESHOLD iz resonance_constants.

Vsyo cherez phi.
"""
import os
import time
import json
import hashlib

from core.resonance_constants import (
    PHI, PHI_INV, FIBONACCI,
    phi_phase, phi_phase_resonance
)


class SelfMonitor:
    def __init__(self, brain, state_dir=None):
        self.brain = brain
        self.state_dir = state_dir or os.path.expanduser("~/logos_agi/state")
        self.log_dir = os.path.expanduser("~/logos_agi/logs")
        os.makedirs(self.log_dir, exist_ok=True)

        self.heartbeat_count = 0
        self.issues_found = 0
        self.issues_fixed = 0
        self.last_check = time.time()
        self.file_hashes = {}

        self._snapshot_files()

        print(f"[+] SelfMonitor v10 initialized. "
              f"Watched files: {len(self.file_hashes)}")

    def heartbeat(self):
        self.heartbeat_count += 1
        self.last_check = time.time()

        report = {
            "beat": self.heartbeat_count,
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "checks": {},
        }

        report["checks"]["memory"] = self._check_memory()
        report["checks"]["rules"] = self._check_rules()
        report["checks"]["files"] = self._check_files()
        report["checks"]["disk"] = self._check_disk()
        report["checks"]["coherence"] = self._check_coherence()

        issues = sum(1 for v in report["checks"].values()
                    if v.get("status") == "warning")
        if issues > 0:
            self._log(f"HEARTBEAT #{self.heartbeat_count}: "
                     f"{issues} issues found")
        elif self.heartbeat_count % FIBONACCI[5] == 0:
            self._log(f"HEARTBEAT #{self.heartbeat_count}: all OK")

        return report

    def _check_memory(self):
        """FIX K3: ispolzuyet realnyy max_memories iz MemoryCore."""
        mem_stats = self.brain.memory.stats()
        total = mem_stats.get("total_memories", 0)
        # FIX K3: bereem realnyy limit iz memory, ne hardcoded
        max_mem = self.brain.memory.max_memories

        if total > int(max_mem * 0.9):
            self.issues_found += 1
            from core.will_core import get_will
            allowed, _ = get_will().allow("forget")
            if allowed:
                forgotten = self.brain.memory.forget_weakest(FIBONACCI[5])
                self.issues_fixed += 1
            else:
                forgotten = 0
            return {
                "status": "fixed",
                "message": f"Memory near limit ({total}/{max_mem}). "
                          f"Forgot {forgotten} weak entries.",
            }

        return {"status": "ok", "total": total,
                "max": max_mem,
                "usage": f"{total/max(max_mem,1):.1%}"}

    def _check_rules(self):
        total_rules = 0
        for name, space in self.brain.learner.spaces.items():
            total_rules += len(space.rules)
        return {"status": "ok", "total_rules": total_rules}

    def _check_files(self):
        core_dir = os.path.expanduser("~/logos_agi/core")
        modified = []

        for fname, old_hash in self.file_hashes.items():
            fpath = os.path.join(core_dir, fname)
            if not os.path.exists(fpath):
                modified.append(f"{fname} MISSING")
                self.issues_found += 1
                continue
            new_hash = self._hash_file(fpath)
            if new_hash != old_hash:
                modified.append(f"{fname} CHANGED")

        if modified:
            return {"status": "warning", "modified": modified}
        return {"status": "ok", "files": len(self.file_hashes)}

    def _check_disk(self):
        try:
            stat = os.statvfs(os.path.expanduser("~/logos_agi"))
            free_gb = (stat.f_bavail * stat.f_frsize) / (1024**3)
            if free_gb < 1.0:
                self.issues_found += 1
                return {"status": "warning",
                        "message": f"Low disk: {free_gb:.1f}GB free"}
            return {"status": "ok", "free_gb": round(free_gb, 1)}
        except Exception:
            return {"status": "unknown"}

    def _check_coherence(self):
        total_res = 0
        count = 0
        word_space = self.brain.learner.spaces.get("words")
        if word_space:
            for key, rule in word_space.rules.items():
                dist = rule.get("distance", 0)
                res = phi_phase_resonance(dist)
                total_res += res
                count += 1

        avg = total_res / max(count, 1)
        return {"status": "ok", "avg_coherence": round(avg, 4),
                "rules_checked": count}

    def _snapshot_files(self):
        core_dir = os.path.expanduser("~/logos_agi/core")
        if not os.path.isdir(core_dir):
            return
        for fname in os.listdir(core_dir):
            if fname.endswith(".py"):
                fpath = os.path.join(core_dir, fname)
                self.file_hashes[fname] = self._hash_file(fpath)

    def _hash_file(self, path):
        try:
            with open(path, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()[:16]
        except Exception:
            return ""

    def full_health(self):
        report = self.heartbeat()
        report["uptime"] = {
            "heartbeats": self.heartbeat_count,
            "issues_found": self.issues_found,
            "issues_fixed": self.issues_fixed,
        }
        return report

    def stats(self):
        return {
            "heartbeats": self.heartbeat_count,
            "issues_found": self.issues_found,
            "issues_fixed": self.issues_fixed,
            "watched_files": len(self.file_hashes),
            "last_check": time.strftime(
                "%H:%M:%S", time.localtime(self.last_check)),
        }

    def _log(self, message):
        path = os.path.join(self.log_dir, "monitor.log")
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {message}\n")


print("[+] self_monitor v10 module loaded")
