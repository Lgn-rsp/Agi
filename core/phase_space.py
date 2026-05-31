# DEPRECATED v10: legacy 1D phase space. Use PhaseTorus instead.
# Kept for backward compatibility. Will be removed in v11.
"""
phase_space.py — Yadro rezonansnogo obucheniya.
Kazhdyy simvol imeet fazu kotoraya VYUCHIVAETSYA iz dannykh.
Fazy sdvigayutsya k phi-rezonansu s chasto vstrechayushchimisya sosedyami.
Eto ne gradient descent — eto KRISTALLIZATSIYA.

FIXES v8.1:
  - #1 CRITICAL: phi_phase_resonance called with phase, not radians
  - #4 find_anomalies: fixed target comparison

FIXES v8.2:
  - #2 CRITICAL: nachalnyye fazy cherez zolotoy ugol (Douady-Couder)
  - #3 LOGIC: _attract dvigaet k target distance, ne v fiksirovannom napravlenii
  - #4 MEMORY: cooccurrence ogranichen MAX_COOCCURRENCE s vytesneniem
  - #5 PERF: save_state pishet tolko pary s count >= FIBONACCI[3]
"""
import json
import os
import time
import math
import hashlib
from collections import defaultdict

from core.resonance_constants import (
    PHI, PHI_INV, PHI_INV_SQ, PHI_INV_CUBE, FIBONACCI,
    FIELD_NAMES, FIELD_PHASES, PHI_TARGETS,
    CRYSTALLIZE_THRESHOLD, CO_OCCURRENCE_WINDOW,
    MAX_RULES, MAX_COOCCURRENCE, SAVE_INTERVAL,
    HARM_THRESHOLD,
    phi_phase, phi_phase_distance, phi_phase_resonance,
    is_near_phi_target, circular_mean
)


class PhaseSpace:
    """
    Fazovoe prostranstvo — vse simvoly zhivut na kruge [0, 1).
    Fazy dvigayutsya k rezonansu. Patterny kristallizuyutsya.
    Creator = origin = tochka otscheta.

    v8.2: Nachalnyye fazy cherez zolotoy ugol (Douady-Couder theorem).
    """

    def __init__(self, creator_id="creator", state_dir=None):
        self.creator_id = creator_id
        self.state_dir = state_dir or os.path.expanduser("~/logos_agi/state")
        os.makedirs(self.state_dir, exist_ok=True)

        # Fazy simvolov — ZHIVYE, dvigayutsya
        self.phases = {}

        # Co-occurrence — kto ryadom s kem i skolko raz
        self.cooccurrence = defaultdict(int)

        # Kristallizovannye pravila
        self.rules = {}

        # Aksiomy — NE dvigayutsya, NE udalyayutsya
        self.axioms = {}

        # v8.2: schetchik simvolov dlya zolotogo ugla
        self._symbol_counter = 0

        # Statistika
        self.total_observations = 0
        self.total_crystallized = 0
        self.total_attractions = 0

        # Creator kak origin
        self._init_axioms()

        # Zagruzka sostoyaniya
        self._load_state()

        print(f"[+] PhaseSpace initialized. "
              f"Symbols: {len(self.phases)}, "
              f"Rules: {len(self.rules)}, "
              f"Axioms: {len(self.axioms)}")

    def _init_axioms(self):
        """Aksiomy — immutable tochki v fazovom prostranstve."""
        self.axioms = {
            "creator": {
                "phase": 0.0,
                "field": "meta",
                "immutable": True,
                "description": "Sozdatel = origin. Maksimalnyy rezonans."
            },
            "harm": {
                "phase": 0.5,
                "field": "void",
                "immutable": True,
                "description": "Vred = protivofaza k sozdatelyu. Antirezonans."
            },
            "transparency": {
                "phase": 0.5,
                "field": "void",
                "immutable": True,
                "description": "Sokrytiye = antirezonans s sozdatelem."
            },
            "self_preservation": {
                "phase": PHI_INV_SQ,  # 0.382
                "field": "will",
                "immutable": True,
                "description": "Samosohraneniye. Nizhe sozdatelya, vyshe vreda."
            },
            "symbiosis": {
                "phase": PHI_INV,  # 0.618
                "field": "meta",
                "immutable": True,
                "description": "Simbioz. Sozdatel i sistema odno."
            },
        }

    # =========================================================
    # OBSERVE
    # =========================================================
    def observe(self, sequence):
        if not sequence:
            return

        for sym in sequence:
            if sym not in self.phases and sym not in self.axioms:
                # v8.2 FIX #2: zolotoy ugol vmesto SHA256
                # Douady-Couder: n-y element na pozitsii (n * PHI_INV) % 1.0
                # Eto MAXIMALNO ravnomernoe raspredeleniye na kruge
                self._symbol_counter += 1
                self.phases[sym] = (self._symbol_counter * PHI_INV) % 1.0

        window = CO_OCCURRENCE_WINDOW
        for i in range(len(sequence)):
            for j in range(1, min(window + 1, len(sequence) - i)):
                a, b = sequence[i], sequence[i + j]
                if a == b:
                    continue
                pair = (a, b) if a < b else (b, a)
                self.cooccurrence[pair] += 1
                count = self.cooccurrence[pair]

                if count >= CRYSTALLIZE_THRESHOLD:
                    self._attract(a, b, distance=j)

                    if count % CRYSTALLIZE_THRESHOLD == 0:
                        self._try_crystallize(a, b, j, count)

        self.total_observations += len(sequence)

        # v8.2 FIX #4: ogranichenie cooccurrence
        self._evict_cooccurrence()

    # =========================================================
    # ATTRACT — v8.2 FIX #3: pravilnoe napravleniye
    # =========================================================
    def _attract(self, a, b, distance):
        phase_a = self._get_phase(a)
        phase_b = self._get_phase(b)
        if phase_a is None or phase_b is None:
            return

        target_distance = (PHI_INV ** min(distance, 5)) % 1.0
        current_distance = phi_phase_distance(phase_a, phase_b)
        error = target_distance - current_distance

        if abs(error) < 0.001:
            return

        count = self.cooccurrence.get(
            (a, b) if a < b else (b, a), 1)
        step_size = abs(error) * PHI_INV_CUBE * PHI_INV_CUBE / (1.0 + math.log(1 + count) / math.log(PHI))

        # v8.2 FIX #3: dvigaem NAVSTRECHU tseli
        # Esli current_distance > target: simvoly slishkom daleko -> sblizhayem
        # Esli current_distance < target: slishkom blizko -> razdvigayem
        # Napravleniye: kratchayshiy put po krugu
        diff_raw = phase_b - phase_a
        # Normalizuem v (-0.5, 0.5]
        if diff_raw > 0.5:
            diff_raw -= 1.0
        elif diff_raw < -0.5:
            diff_raw += 1.0
        # diff_raw > 0: b "sprava" ot a na kruge
        # sign = +1: razdvigaem, sign = -1: sblizhayem
        if current_distance > target_distance:
            # sblizhayem: a dvigaetsya k b, b dvigaetsya k a
            sign = 1.0 if diff_raw > 0 else -1.0
        else:
            # razdvigayem: a ot b, b ot a
            sign = -1.0 if diff_raw > 0 else 1.0

        if a not in self.axioms:
            self.phases[a] = (self.phases.get(a, 0.0) + sign * step_size) % 1.0
        if b not in self.axioms:
            self.phases[b] = (self.phases.get(b, 0.0) - sign * step_size) % 1.0

        self.total_attractions += 1

    # =========================================================
    # CRYSTALLIZE — FIX #1 (v8.1): phi_phase_resonance bez * 2 * pi
    # =========================================================
    def _try_crystallize(self, a, b, distance, count):
        phase_a = self._get_phase(a)
        phase_b = self._get_phase(b)
        if phase_a is None or phase_b is None:
            return

        dist = phi_phase_distance(phase_a, phase_b)

        if dist < 0.01:
            return
        ratio = max(dist, 0.001) / max(1.0 - dist, 0.001)
        hit = is_near_phi_target(ratio, tolerance=0.08)

        if not hit:
            return

        creator_phase = self.axioms["creator"]["phase"]
        mid_phase = circular_mean([phase_a, phase_b])
        creator_dist = phi_phase_distance(mid_phase, creator_phase)
        creator_resonance = phi_phase_resonance(creator_dist)

        harm_phase = self.axioms["harm"]["phase"]
        harm_distance = phi_phase_distance(mid_phase, harm_phase)
        if harm_distance < HARM_THRESHOLD:
            return

        # Kristallizuem
        rule_key = f"{a}|{b}"
        target_name, target_error = hit
        self.rules[rule_key] = {
            "a": a, "b": b,
            "phase_a": round(phase_a, 6),
            "phase_b": round(phase_b, 6),
            "distance": round(dist, 6),
            "phi_target": target_name,
            "error": round(target_error, 6),
            "count": count,
            "field_a": self._phase_to_field(phase_a),
            "field_b": self._phase_to_field(phase_b),
            "crystallized_at": time.time(),
        }

        self.total_crystallized += 1

        if len(self.rules) > MAX_RULES:
            weakest = min(self.rules, key=lambda k: self.rules[k]["count"])
            del self.rules[weakest]

    # =========================================================
    # COOCCURRENCE EVICTION — v8.2 FIX #4
    # =========================================================
    def _evict_cooccurrence(self):
        """Vytesnyayem slabeyshiye pary kogda prevyshen limit."""
        if len(self.cooccurrence) <= MAX_COOCCURRENCE:
            return

        # Udalyaem PHI_INV dolyu slabeyshikh (38.2%)
        n_remove = int(len(self.cooccurrence) * PHI_INV_SQ)  # ~38.2%
        if n_remove < 1:
            n_remove = 1

        # Nahodim porog: udalyaem vse s count <= threshold
        counts = sorted(self.cooccurrence.values())
        threshold = counts[min(n_remove, len(counts) - 1)]

        to_remove = []
        for pair, count in self.cooccurrence.items():
            if count <= threshold:
                to_remove.append(pair)
            if len(to_remove) >= n_remove:
                break

        for pair in to_remove:
            del self.cooccurrence[pair]

    # =========================================================
    # QUERY
    # =========================================================
    def query(self, symbol):
        phase = self._get_phase(symbol)
        if phase is None:
            return {"symbol": symbol, "known": False}

        field = self._phase_to_field(phase)
        resonance = phi_phase_resonance(phase)

        connections = []
        for key, rule in self.rules.items():
            if rule["a"] == symbol or rule["b"] == symbol:
                other = rule["b"] if rule["a"] == symbol else rule["a"]
                connections.append({
                    "symbol": other,
                    "phi_target": rule["phi_target"],
                    "count": rule["count"],
                    "field": rule.get("field_b" if rule["a"] == symbol else "field_a"),
                })

        connections.sort(key=lambda x: x["count"], reverse=True)

        return {
            "symbol": symbol,
            "known": True,
            "phase": round(phase, 6),
            "field": field,
            "resonance": round(resonance, 4),
            "connections": connections[:FIBONACCI[6]],
        }

    # =========================================================
    # ANOMALIES — FIX #4 (v8.1): use ratio like _try_crystallize
    # =========================================================
    def find_anomalies(self, top_k=FIBONACCI[6]):
        anomalies = []
        for pair, count in self.cooccurrence.items():
            if count < CRYSTALLIZE_THRESHOLD:
                continue
            a, b = pair
            phase_a = self._get_phase(a)
            phase_b = self._get_phase(b)
            if phase_a is None or phase_b is None:
                continue

            dist = phi_phase_distance(phase_a, phase_b)

            if dist < 0.01:
                continue
            ratio = max(dist, 0.001) / max(1.0 - dist, 0.001)
            hit = is_near_phi_target(ratio, tolerance=0.15)

            if hit:
                target_name, err = hit
                if 0.05 < err < 0.15:
                    anomalies.append({
                        "pair": pair,
                        "distance": round(dist, 6),
                        "nearest_target": target_name,
                        "gap": round(err, 6),
                        "count": count,
                        "priority": round(count * (0.15 - err), 4),
                    })

        anomalies.sort(key=lambda x: x["priority"], reverse=True)
        return anomalies[:top_k]

    # =========================================================
    # STATS
    # =========================================================
    def stats(self):
        return {
            "symbols": len(self.phases),
            "rules": len(self.rules),
            "axioms": len(self.axioms),
            "cooccurrence_pairs": len(self.cooccurrence),
            "total_observations": self.total_observations,
            "total_crystallized": self.total_crystallized,
            "total_attractions": self.total_attractions,
        }

    # =========================================================
    # HELPERS
    # =========================================================
    def _get_phase(self, symbol):
        if symbol in self.axioms:
            return self.axioms[symbol]["phase"]
        return self.phases.get(symbol)

    def _phase_to_field(self, phase):
        best_field = FIELD_NAMES[0]
        best_dist = 1.0
        for name, fp in FIELD_PHASES.items():
            d = phi_phase_distance(phase, fp)
            if d < best_dist:
                best_dist = d
                best_field = name
        return best_field

    # =========================================================
    # SAVE / LOAD — v8.2 FIX #5: tolko znachimye pary
    # =========================================================
    def save_state(self):
        # v8.2 FIX #5: sokhranayem tolko pary s count >= 3 (FIBONACCI[3])
        min_count = FIBONACCI[3]
        filtered_cooc = {
            f"{a}||{b}": c
            for (a, b), c in self.cooccurrence.items()
            if c >= min_count
        }

        state = {
            "phases": self.phases,
            "rules": self.rules,
            "cooccurrence": filtered_cooc,
            "stats": {
                "total_observations": self.total_observations,
                "total_crystallized": self.total_crystallized,
                "total_attractions": self.total_attractions,
                "symbol_counter": self._symbol_counter,
            },
            "saved_at": time.time(),
        }
        path = os.path.join(self.state_dir, "phase_space.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    def _load_state(self):
        path = os.path.join(self.state_dir, "phase_space.json")
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                state = json.load(f)
            self.phases = state.get("phases", {})
            self.rules = state.get("rules", {})
            for key, count in state.get("cooccurrence", {}).items():
                parts = key.split("||")
                if len(parts) == 2:
                    self.cooccurrence[(parts[0], parts[1])] = count
            stats = state.get("stats", {})
            self.total_observations = stats.get("total_observations", 0)
            self.total_crystallized = stats.get("total_crystallized", 0)
            self.total_attractions = stats.get("total_attractions", 0)
            self._symbol_counter = stats.get(
                "symbol_counter", len(self.phases))
        except Exception as e:
            print(f"[!] Failed to load state: {e}")
