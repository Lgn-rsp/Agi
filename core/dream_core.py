"""
dream_core.py — Sny sistemy.

FIXES v8.1:
  - #3: validate_dream poluchaet phase_spaces dlya realnyh faz
  - #5: _dream_bridge proveryaet oba konca pravila kak pivot
"""
import random
import time
import math
import json
import os
from collections import defaultdict

from core.resonance_constants import (
    PHI, PHI_INV, FIBONACCI, FIELD_NAMES,
    DREAM_INTERVAL, CRYSTALLIZE_THRESHOLD,
    phi_phase, phi_phase_distance, phi_phase_resonance,
    is_near_phi_target,
    circular_mean, HARM_THRESHOLD, HARM_PHASE
)
from core.creator_identity import get_creator


class DreamEngine:
    def __init__(self, phase_spaces, state_dir=None):
        self.spaces = phase_spaces
        self.state_dir = state_dir or os.path.expanduser("~/logos_agi/state")
        self.log_dir = os.path.expanduser("~/logos_agi/logs")
        os.makedirs(self.log_dir, exist_ok=True)

        self.dream_log = []
        self.max_dream_log = FIBONACCI[15]  # 987
        self.total_dreams = 0
        self.total_discoveries = 0

        self._load_log()
        print(f"[+] DreamEngine initialized. "
              f"Past dreams: {len(self.dream_log)}")

    def dream_once(self, level="words"):
        space = self.spaces.get(level)
        if not space or len(space.phases) < 3:
            return None

        symbols = list(space.phases.keys())
        dream_type = random.choice(["recombine", "bridge", "spiral"])

        if dream_type == "recombine":
            result = self._dream_recombine(space, symbols)
        elif dream_type == "bridge":
            result = self._dream_bridge(space, symbols)
        else:
            result = self._dream_spiral(space, symbols)

        if result:
            self.total_dreams += 1
            self.dream_log.append({
                "type": dream_type,
                "level": level,
                "result": result,
                "timestamp": time.time(),
            })
            while len(self.dream_log) > self.max_dream_log:
                self.dream_log.pop(0)

        return result

    def _dream_recombine(self, space, symbols):
        a = random.choice(symbols)
        b = random.choice(symbols)
        if a == b:
            return None

        phase_a = space.phases[a]
        phase_b = space.phases[b]
        dist = phi_phase_distance(phase_a, phase_b)

        rule_key = f"{a}|{b}" if a < b else f"{b}|{a}"
        if rule_key in space.rules:
            return None

        if dist > 0.01:
            ratio = max(dist, 0.001) / max(1.0 - dist, 0.001)
            hit = is_near_phi_target(ratio, tolerance=0.06)
            if hit:
                target_name, error = hit
                mid = circular_mean([phase_a, phase_b])
                harm_dist = phi_phase_distance(mid, HARM_PHASE)
                if harm_dist < HARM_THRESHOLD:
                    return None

                # FIX #3: peredaem phase_spaces dlya realnyh faz
                creator = get_creator()
                dream_result = {"a": a, "b": b, "method": "recombine"}
                if not creator.validate_dream(dream_result, phase_spaces=self.spaces):
                    return None

                self.total_discoveries += 1
                discovery = {
                    "a": a, "b": b,
                    "distance": round(dist, 6),
                    "phi_target": target_name,
                    "error": round(error, 6),
                    "method": "dream_recombine",
                }

                space.observe([a, b] * FIBONACCI[3])

                self._log_dream(f"RECOMBINE: {a} <-> {b} = "
                               f"{target_name} (err={error:.4f})")
                return discovery

        return None

    def _dream_bridge(self, space, symbols):
        """FIX #5: proveryaem oba konca pravila kak pivot."""
        if len(space.rules) < 2:
            return None

        rule_keys = list(space.rules.keys())
        rule1 = space.rules[random.choice(rule_keys)]

        # FIX #5: probuyem oba konca kak pivot
        for pivot in [rule1["a"], rule1["b"]]:
            other_end = rule1["b"] if pivot == rule1["a"] else rule1["a"]

            for key in rule_keys:
                rule2 = space.rules[key]
                # Ishchem rule2 gde pivot — odin iz kontsov
                next_sym = None
                if rule2["a"] == pivot and rule2["b"] != other_end:
                    next_sym = rule2["b"]
                elif rule2["b"] == pivot and rule2["a"] != other_end:
                    next_sym = rule2["a"]

                if next_sym is None:
                    continue

                phase_a = space._get_phase(other_end)
                phase_c = space._get_phase(next_sym)
                if phase_a is None or phase_c is None:
                    continue

                dist = phi_phase_distance(phase_a, phase_c)
                if dist > 0.01:
                    ratio = max(dist, 0.001) / max(1.0 - dist, 0.001)
                    hit = is_near_phi_target(ratio, tolerance=0.08)
                    if hit:
                        target_name, error = hit
                        creator = get_creator()
                        dream_result = {"a": other_end, "b": pivot, "c": next_sym, "method": "bridge"}
                        if not creator.validate_dream(dream_result, phase_spaces=self.spaces):
                            continue

                        self.total_discoveries += 1
                        discovery = {
                            "a": other_end, "bridge": pivot, "c": next_sym,
                            "phi_target": target_name,
                            "chain": f"{rule1['phi_target']}->{rule2['phi_target']}->{target_name}",
                            "method": "dream_bridge",
                        }
                        space.observe([other_end, next_sym] * FIBONACCI[3])
                        self._log_dream(f"BRIDGE: {other_end}-[{pivot}]-{next_sym} = "
                                       f"{target_name}")
                        return discovery

        return None

    def _dream_spiral(self, space, symbols):
        if len(space.rules) < 3:
            return None

        start = random.choice(symbols)
        chain = [start]
        current = start
        max_depth = FIBONACCI[4]

        for _ in range(max_depth):
            found = False
            for key, rule in space.rules.items():
                next_sym = None
                if rule["a"] == current and rule["b"] not in chain:
                    next_sym = rule["b"]
                elif rule["b"] == current and rule["a"] not in chain:
                    next_sym = rule["a"]

                if next_sym:
                    chain.append(next_sym)
                    current = next_sym
                    found = True
                    break

            if not found:
                break

        if len(chain) < 3:
            return None

        phase_first = space._get_phase(chain[0])
        phase_last = space._get_phase(chain[-1])
        if phase_first is None or phase_last is None:
            return None

        dist = phi_phase_distance(phase_first, phase_last)
        if dist > 0.01:
            ratio = max(dist, 0.001) / max(1.0 - dist, 0.001)
            hit = is_near_phi_target(ratio, tolerance=0.08)
            if hit:
                target_name, error = hit
                creator = get_creator()
                dream_result = {"a": chain[0], "b": chain[-1], "method": "spiral"}
                if not creator.validate_dream(dream_result, phase_spaces=self.spaces):
                    return None

                self.total_discoveries += 1
                discovery = {
                    "chain": chain,
                    "closure": target_name,
                    "length": len(chain),
                    "method": "dream_spiral",
                }
                self._log_dream(f"SPIRAL: {' -> '.join(chain[:5])} "
                               f"(closure={target_name})")
                return discovery

        return None

    def dream_session(self, n_dreams=FIBONACCI[7], level="words"):
        discoveries = []
        for _ in range(n_dreams):
            result = self.dream_once(level)
            if result:
                discoveries.append(result)
        return discoveries

    def dream_all_levels(self, n_per_level=FIBONACCI[6]):
        all_discoveries = {}
        for level in self.spaces:
            discoveries = self.dream_session(n_per_level, level)
            if discoveries:
                all_discoveries[level] = discoveries
        return all_discoveries

    def stats(self):
        return {
            "total_dreams": self.total_dreams,
            "total_discoveries": self.total_discoveries,
            "dream_log_size": len(self.dream_log),
            "discovery_rate": round(
                self.total_discoveries / max(self.total_dreams, 1), 4),
        }

    def save_log(self):
        path = os.path.join(self.state_dir, "dream_log.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "total_dreams": self.total_dreams,
                "total_discoveries": self.total_discoveries,
                "recent": self.dream_log[-FIBONACCI[8]:],
            }, f, ensure_ascii=False, indent=2)

    def _load_log(self):
        path = os.path.join(self.state_dir, "dream_log.json")
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.total_dreams = data.get("total_dreams", 0)
            self.total_discoveries = data.get("total_discoveries", 0)
            self.dream_log = data.get("recent", [])
        except Exception:
            pass

    def _log_dream(self, message):
        path = os.path.join(self.log_dir, "dreams.log")
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {message}\n")
