"""
grounding_torus.py v10 — Kross-modalnoye zazemleniye.

FIX M3: observe_text nablyudayet VSE slova >= 3 simvolov,
dazhe esli oni eshchyo ne v toruse. Kogda slovo poyavitsya
v toruse — ego ground_phase uzhe budet gotova.

Vsyo cherez phi.
"""
import math
import re
import json
import os
import time
from collections import defaultdict

from core.resonance_constants import (
    PHI, PHI_INV, PHI_INV_SQ, PHI_INV_CUBE, FIBONACCI,
    phi_phase, phi_phase_distance, phi_phase_resonance
)


NUMBER_RE = re.compile(
    r'(?<![a-zA-Z])'
    r'([+-]?'
    r'(?:\d+\.?\d*|\.\d+)'
    r'(?:[eE][+-]?\d+)?)'
    r'(?![a-zA-Z])'
)


class GroundingTorus:
    def __init__(self, phase_torus, state_dir=None):
        self.torus = phase_torus
        self.state_dir = state_dir or os.path.expanduser(
            "~/logos_agi/state/grounding")
        os.makedirs(self.state_dir, exist_ok=True)

        self.observations = defaultdict(list)
        self.ground_phases = {}

        self.total_observed = 0
        self.total_grounded = 0
        self.total_cross_modal = 0

        self.max_observations = FIBONACCI[10]

        self._load()
        self._recompute_phases()

        print(f"[+] GroundingTorus v10 initialized. "
              f"Observed words: {len(self.observations)}, "
              f"Grounded: {len(self.ground_phases)}")

    def observe_text(self, text):
        """FIX M3: nablyudayet VSE slova >= 3 simvolov, ne tolko te chto v toruse."""
        if not text:
            return 0

        tokens = text.lower().split()
        if len(tokens) < 2:
            return 0

        observed = 0

        number_positions = []
        for i, token in enumerate(tokens):
            match = NUMBER_RE.match(token)
            if match:
                try:
                    value = float(match.group(1))
                    if value != 0 and not math.isnan(value) and not math.isinf(value):
                        number_positions.append((i, value))
                except ValueError:
                    continue

        if not number_positions:
            return 0

        window = FIBONACCI[4]
        for num_pos, value in number_positions:
            for offset in range(-window, window + 1):
                if offset == 0:
                    continue
                word_pos = num_pos + offset
                if word_pos < 0 or word_pos >= len(tokens):
                    continue

                word = tokens[word_pos]

                if NUMBER_RE.match(word):
                    continue
                # FIX M3: prinimaem VSE slova >= 3 simvolov
                # Ne tolko te chto uzhe v toruse
                if len(word) < 3:
                    continue

                distance = abs(offset)
                weight = PHI_INV ** distance

                obs_list = self.observations[word]
                obs_list.append((value, weight))

                if len(obs_list) > self.max_observations:
                    obs_list.sort(key=lambda x: x[1], reverse=True)
                    self.observations[word] = obs_list[:self.max_observations]

                observed += 1

        self.total_observed += observed
        return observed

    def _recompute_phases(self):
        min_observations = FIBONACCI[3]
        self.ground_phases.clear()

        for word, obs_list in self.observations.items():
            if len(obs_list) < min_observations:
                continue

            weighted_phases = []
            for value, weight in obs_list:
                p = phi_phase(abs(value), 1.0)
                weighted_phases.append((p, weight))

            if not weighted_phases:
                continue

            best_phase = 0.0
            best_resonance = -1.0

            candidates = [p for p, w in weighted_phases]
            for k in range(FIBONACCI[5]):
                candidates.append((k * PHI_INV) % 1.0)

            for candidate in candidates:
                total_res = 0.0
                total_w = 0.0
                for p, w in weighted_phases:
                    dist = phi_phase_distance(candidate, p)
                    res = phi_phase_resonance(dist)
                    total_res += res * w
                    total_w += w

                avg_res = total_res / max(total_w, 0.001)
                if avg_res > best_resonance:
                    best_resonance = avg_res
                    best_phase = candidate

            self.ground_phases[word] = best_phase
            self.total_grounded += 1

    def crystallize(self):
        old_count = len(self.ground_phases)
        self._recompute_phases()
        new_count = len(self.ground_phases)
        return new_count - old_count

    def apply_to_torus(self):
        if not self.torus:
            return 0

        applied = 0
        for word, gp in self.ground_phases.items():
            if word not in self.torus._torus:
                continue

            current = self.torus._torus[word]

            if len(current) < 3:
                current.append(gp)
            else:
                old = current[2]
                diff = gp - old
                if diff > 0.5:
                    diff -= 1.0
                elif diff < -0.5:
                    diff += 1.0
                current[2] = (old + diff * PHI_INV) % 1.0

            applied += 1

        if applied > 0:
            self.torus.N = max(self.torus.N, 3)

        self.total_cross_modal += applied
        return applied

    def find_similar(self, word, top_k=FIBONACCI[6]):
        gp = self.ground_phases.get(word)
        if gp is None:
            return []

        results = []
        for other, other_gp in self.ground_phases.items():
            if other == word:
                continue
            dist = phi_phase_distance(gp, other_gp)
            res = phi_phase_resonance(dist)
            if res > PHI_INV_CUBE:
                results.append((other, round(dist, 6), round(res, 4)))

        results.sort(key=lambda x: x[2], reverse=True)
        return results[:top_k]

    def cross_modal_resonance(self, word_a, word_b):
        gp_a = self.ground_phases.get(word_a)
        gp_b = self.ground_phases.get(word_b)
        if gp_a is None or gp_b is None:
            return 0.0
        dist = phi_phase_distance(gp_a, gp_b)
        return phi_phase_resonance(dist)

    def what_numbers(self, word, top_k=FIBONACCI[5]):
        obs = self.observations.get(word, [])
        if not obs:
            return []
        sorted_obs = sorted(obs, key=lambda x: x[1], reverse=True)
        return [(round(v, 4), round(w, 4)) for v, w in sorted_obs[:top_k]]

    def save(self):
        path = os.path.join(self.state_dir, "groundings.json")
        min_obs = FIBONACCI[3]
        filtered_obs = {
            w: obs for w, obs in self.observations.items()
            if len(obs) >= min_obs
        }
        data = {
            "observations": filtered_obs,
            "ground_phases": {k: round(v, 8)
                              for k, v in self.ground_phases.items()},
            "total_observed": self.total_observed,
            "total_grounded": self.total_grounded,
            "total_cross_modal": self.total_cross_modal,
            "saved_at": time.time(),
        }
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception as e:
            print(f"[!] Grounding save failed: {e}")

    def _load(self):
        path = os.path.join(self.state_dir, "groundings.json")
        if not os.path.exists(path):
            return
        try:
            with open(path) as f:
                data = json.load(f)
            for word, obs in data.get("observations", {}).items():
                self.observations[word] = [
                    (float(v), float(w)) for v, w in obs
                ]
            self.total_observed = data.get("total_observed", 0)
            self.total_grounded = data.get("total_grounded", 0)
            self.total_cross_modal = data.get("total_cross_modal", 0)
        except Exception as e:
            print(f"[!] Grounding load failed: {e}")

    def stats(self):
        n_obs = sum(len(v) for v in self.observations.values())
        return {
            "observed_words": len(self.observations),
            "total_observations": n_obs,
            "grounded_words": len(self.ground_phases),
            "total_observed_ops": self.total_observed,
            "total_cross_modal": self.total_cross_modal,
        }
