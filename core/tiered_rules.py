"""
tiered_rules.py v10 — Ierarkhicheskoye khranenie pravil.

FIX K5: __delitem__ udalyaet s diska
FIX K6: threading.Lock dlya thread safety
FIX L3: all_items() iterator po hot + warm

Tri urovnya:
  HOT (RAM):  chasto ispolzuyemye, bystryy dostup
              limit = FIBONACCI[22] = 28657
  WARM (disk): vse kogda-libo sozdannye
              bez limita, lazy load

Vsyo cherez phi.
"""
import os
import json
import time
import math
import tempfile
import threading
from collections import defaultdict

from core.resonance_constants import (
    PHI, PHI_INV, PHI_INV_SQ, FIBONACCI,
    phi_phase_distance, phi_phase_resonance,
    is_near_phi_target, CRYSTALLIZE_THRESHOLD
)


class TieredRules:
    """
    Ierarkhicheskiy khranilishche pravil.
    Hot (RAM) + Warm (disk) = neogranichennoe kolichestvo.
    FIX K6: vse operatsii pod lock.
    """

    def __init__(self, state_dir, hot_limit=FIBONACCI[22]):  # 28657
        self.state_dir = state_dir
        self.warm_dir = os.path.join(state_dir, "warm_rules")
        os.makedirs(self.warm_dir, exist_ok=True)

        self.hot = {}           # key -> rule (v RAM)
        self.hot_limit = hot_limit
        self.warm_index = {}    # key -> filename (na diske)
        self.warm_count = 0

        self.total_compressions = 0
        self.total_evictions = 0

        # FIX K6: thread safety
        self._lock = threading.Lock()

        self._load_warm_index()
        print(f"[+] TieredRules: hot_limit={hot_limit}, "
              f"warm={self.warm_count}")

    # =========================================================
    # OSNOVNYE OPERATSII
    # =========================================================
    def get(self, key):
        """Poluchit pravilo po klyuchu. Hot -> Warm."""
        with self._lock:
            if key in self.hot:
                return self.hot[key]
            # Lazy load iz warm
            if key in self.warm_index:
                rule = self._load_warm_rule(key)
                if rule:
                    # Promote to hot
                    self.hot[key] = rule
                    self._check_hot_limit()
                    return rule
        return None

    def put(self, key, rule):
        """Dobavit/obnovit pravilo."""
        with self._lock:
            self.hot[key] = rule
            self._check_hot_limit()

    def contains(self, key):
        with self._lock:
            return key in self.hot or key in self.warm_index

    def items(self):
        """Iterator po vsem hot pravilam."""
        with self._lock:
            return list(self.hot.items())

    def keys(self):
        """Klyuchi hot pravil."""
        with self._lock:
            return list(self.hot.keys())

    def values(self):
        """Znacheniya hot pravil."""
        with self._lock:
            return list(self.hot.values())

    def __iter__(self):
        with self._lock:
            return iter(list(self.hot))

    def __getitem__(self, key):
        """dict-style access: rules[key]."""
        with self._lock:
            if key in self.hot:
                return self.hot[key]
            if key in self.warm_index:
                rule = self._load_warm_rule(key)
                if rule:
                    self.hot[key] = rule
                    self._check_hot_limit()
                    return rule
        raise KeyError(key)

    def __setitem__(self, key, value):
        """dict-style set: rules[key] = value."""
        self.put(key, value)

    def __delitem__(self, key):
        """FIX K5: dict-style del — udalyaet i s diska."""
        with self._lock:
            if key in self.hot:
                del self.hot[key]
            if key in self.warm_index:
                # FIX K5: udalyaem iz batch fayla na diske
                filename = self.warm_index[key]
                del self.warm_index[key]
                self.warm_count -= 1
                if os.path.exists(filename):
                    try:
                        with open(filename) as f:
                            batch = json.load(f)
                        if key in batch:
                            del batch[key]
                            if batch:
                                with open(filename, 'w') as f:
                                    json.dump(batch, f, ensure_ascii=False)
                            else:
                                os.unlink(filename)
                    except Exception:
                        pass

    def __len__(self):
        with self._lock:
            return len(self.hot) + self.warm_count

    def __contains__(self, key):
        with self._lock:
            return key in self.hot or key in self.warm_index

    def hot_size(self):
        with self._lock:
            return len(self.hot)

    # =========================================================
    # FIX L3: ALL_ITEMS — iterator po HOT + WARM
    # =========================================================
    def all_items(self):
        """
        Iterator po VSEM pravilam: hot + warm.
        Warm zagruzhayutsya lenivo po batch-am.
        """
        with self._lock:
            # Snachala hot
            for key, rule in self.hot.items():
                yield key, rule
            # Zatem warm (ne dubliruem to chto uzhe v hot)
            hot_keys = set(self.hot.keys())

        # Warm batchi chitaem bez lock (tolko chtenie)
        if not os.path.isdir(self.warm_dir):
            return
        for fname in os.listdir(self.warm_dir):
            if not fname.endswith('.json'):
                continue
            fpath = os.path.join(self.warm_dir, fname)
            try:
                with open(fpath) as f:
                    batch = json.load(f)
                for key, rule in batch.items():
                    if key not in hot_keys:
                        yield key, rule
            except Exception:
                continue

    def all_keys(self):
        """Vse klyuchi: hot + warm."""
        with self._lock:
            result = set(self.hot.keys())
            result.update(self.warm_index.keys())
        return result

    # =========================================================
    # EVICTION — szhatie v warm
    # =========================================================
    def _check_hot_limit(self):
        """Vyzyvaetsya UZhE pod lock."""
        if len(self.hot) <= self.hot_limit:
            return

        n_over = len(self.hot) - self.hot_limit
        n_evict = max(n_over, int(len(self.hot) * PHI_INV_SQ))

        sorted_rules = sorted(
            self.hot.items(),
            key=lambda x: x[1].get("count", 0))

        evicted = 0
        for key, rule in sorted_rules[:n_evict]:
            self._evict_to_warm(key, rule)
            evicted += 1

        for key, _ in sorted_rules[:n_evict]:
            if key in self.hot:
                del self.hot[key]

        self.total_evictions += evicted

    def _evict_to_warm(self, key, rule):
        """Perenosim pravilo na disk. Vyzyvaetsya pod lock."""
        batch_id = self.warm_count // FIBONACCI[10]  # 89 rules per file
        batch_file = os.path.join(
            self.warm_dir, f"warm_{batch_id:06d}.json")

        batch = {}
        if os.path.exists(batch_file):
            try:
                with open(batch_file) as f:
                    batch = json.load(f)
            except Exception:
                batch = {}

        batch[key] = rule

        # FIX K6: atomarnaya zapis
        try:
            fd, tmp = tempfile.mkstemp(
                dir=self.warm_dir, suffix='.tmp')
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(batch, f, ensure_ascii=False)
            os.replace(tmp, batch_file)
        except Exception:
            try:
                os.unlink(tmp)
            except Exception:
                pass

        if key not in self.warm_index:
            self.warm_count += 1
        self.warm_index[key] = batch_file

    def _load_warm_rule(self, key):
        """Lazy load pravila s diska. Vyzyvaetsya pod lock."""
        filename = self.warm_index.get(key)
        if not filename or not os.path.exists(filename):
            return None
        try:
            with open(filename) as f:
                batch = json.load(f)
            return batch.get(key)
        except Exception:
            return None

    # =========================================================
    # BULK OPERATIONS
    # =========================================================
    def get_weakest(self, n):
        """N slabeyshikh pravil iz hot."""
        with self._lock:
            sorted_rules = sorted(
                self.hot.items(),
                key=lambda x: x[1].get("count", 0))
            return sorted_rules[:n]

    def merge_from_dict(self, rules_dict):
        """Import pravil iz obychnogo dict (migratsiya)."""
        with self._lock:
            for key, rule in rules_dict.items():
                self.hot[key] = rule
            self._check_hot_limit()

    def to_dict(self):
        """Export hot pravil kak dict (sovmestimost)."""
        with self._lock:
            return dict(self.hot)

    # =========================================================
    # SAVE / LOAD
    # =========================================================
    def save_hot(self, path):
        """Sokhranit hot pravila."""
        with self._lock:
            data = dict(self.hot)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)

    def load_hot(self, path):
        """Zagruzit hot pravila."""
        if not os.path.exists(path):
            return
        try:
            with open(path) as f:
                data = json.load(f)
            with self._lock:
                self.hot = data
        except Exception:
            pass

    def _load_warm_index(self):
        """Postroit index teplykh pravil."""
        if not os.path.isdir(self.warm_dir):
            return
        for fname in os.listdir(self.warm_dir):
            if not fname.endswith('.json'):
                continue
            fpath = os.path.join(self.warm_dir, fname)
            try:
                with open(fpath) as f:
                    batch = json.load(f)
                for key in batch:
                    self.warm_index[key] = fpath
                    self.warm_count += 1
            except Exception:
                continue

    def stats(self):
        with self._lock:
            hot_len = len(self.hot)
        return {
            "hot_rules": hot_len,
            "hot_limit": self.hot_limit,
            "warm_rules": self.warm_count,
            "total_rules": hot_len + self.warm_count,
            "total_evictions": self.total_evictions,
            "total_compressions": self.total_compressions,
        }
