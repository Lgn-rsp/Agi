"""
polarity_engine.py v10.3 — Polyarnost kak izmerenie tora (dim 5).

FILOSOFIYA:
  Protivopolozhnost — eto NE fazovoe rasstoyanie na semanticheskom izmerenii.
  Hot i cold semanticheski BLIZKI (oba pro temperaturu),
  no polyarno PROTIVOPOLOZHNY.

  Poetomu polyarnost — OTDELNOE izmerenie tora.

  dim 0-1: semantika + sintaksis (PhaseTorus T^2)
  dim 2:   grounding / chislovaya shkala
  dim 3:   rolevaya faza
  dim 4:   kauzalnaya faza
  dim 5:   POLYARNAYA FAZA (etot modul)

ISTOCHNIKI POLYARNOSTI:
  1. PATTERNY v tekste:
     "X is the opposite of Y"
     "X not Y", "X unlike Y", "X vs Y", "X or Y" (kontrast)

  2. SHARED NEIGHBORS:
     hot i cold imeyut MNOGO obshchikh sosedey (temperature, weather, water)
     Eto signal chto oni SVYAZANY.
     Esli pri etom oni redko stoyat RYADOM kak para —
     eto signal chto oni protivopolozhny.

POLYARNYE FAZY:
  Slovo-agent kontrasta → phase ≈ 0.0
  Slovo-target kontrasta → phase ≈ 0.5 (antifaza)
  Odinakovaya polyarnost → close phase
  Protivopolozhnaya → distance ≈ 0.5

Vsyo cherez phi. Nikakikh lineynykh konstant.
"""
import time
import math
import json
import os
import re
from collections import defaultdict

from core.resonance_constants import (
    PHI, PHI_INV, PHI_INV_SQ, PHI_INV_CUBE, PHI_SQ, FIBONACCI,
    phi_phase_distance, phi_phase_resonance, circular_mean
)


# =========================================================
# PATTERNY KONTRASTA
# =========================================================
# Regex dlya izvlecheniya par protivopolozhnostey iz teksta
OPPOSITE_PATTERNS = [
    # "X is the opposite of Y"
    re.compile(r'\b(\w+)\s+is\s+the\s+opposite\s+of\s+(\w+)\b', re.I),
    # "X is opposite to Y"
    re.compile(r'\b(\w+)\s+is\s+opposite\s+to\s+(\w+)\b', re.I),
    # "X unlike Y"
    re.compile(r'\b(\w+)\s+unlike\s+(\w+)\b', re.I),
    # "X vs Y"
    re.compile(r'\b(\w+)\s+vs\.?\s+(\w+)\b', re.I),
    # "X not Y" (v kontekste kontrasta)
    re.compile(r'\b(\w+)\s+not\s+(\w+)\b', re.I),
    # "opposite of X is Y"
    re.compile(r'opposite\s+of\s+(\w+)\s+is\s+(\w+)\b', re.I),
    # "X or Y" — slabee, tolko dlya korotkikh kontrastov
    re.compile(r'\b(\w+)\s+or\s+(\w+)\b', re.I),
]

# Vesa dlya kazhdogo patterna (pervye sil'neye)
PATTERN_WEIGHTS = [
    PHI_SQ,       # "is the opposite of" — silnyy signal
    PHI_SQ,       # "is opposite to" — silnyy signal
    PHI,          # "unlike" — sredniy signal
    PHI,          # "vs" — sredniy signal
    PHI_INV,      # "not" — slabyy signal (mnogo lozhnykh)
    PHI_SQ,       # "opposite of X is Y" — silnyy signal
    PHI_INV_SQ,   # "or" — ochen slabyy signal
]

# Minimalnye nablyudeniya dlya kristallizatsii polyarnosti
MIN_POLARITY_OBS = FIBONACCI[4]  # 5
# Max slov s polyarnostyu
MAX_POLARITY_WORDS = FIBONACCI[17]  # 1597
# Zatukhanie starykh nablyudeniy
POLARITY_DECAY = PHI_INV


class PolarityEngine:
    """
    Polyarnyy rezonans — dim 5 tora.

    Opredelyayet protivopolozhnosti cherez:
    1. Patterny v tekste ("X is the opposite of Y")
    2. Shared neighbors (hot/cold imeyut obshchie sosedi)

    Primeniyaet kak dim 5 tora.
    """

    def __init__(self, phase_spaces, state_dir=None):
        self.spaces = phase_spaces
        self.word_space = phase_spaces.get("words")

        self.state_dir = state_dir or os.path.expanduser(
            "~/logos_agi/state/polarity")
        self.log_dir = os.path.expanduser("~/logos_agi/logs")
        os.makedirs(self.state_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)

        # Pary protivopolozhnostey: (word_a, word_b) → total_weight
        self.opposite_pairs = defaultdict(float)

        # Skolko raz slovo bylo "agentom" kontrasta (pervym v pare)
        self.agent_count = defaultdict(float)
        # Skolko raz slovo bylo "targetom" kontrasta (vtorym v pare)
        self.target_count = defaultdict(float)

        # Itogovye polyarnye fazy: word → float [0, 1)
        self.polarity_phases = {}

        # Statistika
        self.total_observed = 0
        self.total_pairs_found = 0
        self.total_crystallized = 0

        self._load()

        print(f"[+] PolarityEngine v10.3 initialized. "
              f"Pairs: {len(self.opposite_pairs)}, "
              f"Polarity phases: {len(self.polarity_phases)}")

    # =========================================================
    # 1. NABLYUDENIYE — iz teksta
    # =========================================================
    def observe_text(self, text):
        """
        Izvlech pary protivopolozhnostey iz teksta.
        Ispolzuyet patterny: "X is the opposite of Y", "X vs Y", etc.
        """
        if not text or len(text) < FIBONACCI[5]:
            return 0

        observed = 0
        text_lower = text.lower()

        for pattern, weight in zip(OPPOSITE_PATTERNS, PATTERN_WEIGHTS):
            for match in pattern.finditer(text_lower):
                word_a = match.group(1).strip()
                word_b = match.group(2).strip()

                # Filtruem slishkom korotkie i odinakovye
                # FIBONACCI[2]=2: propuskaem tolko 1-simvolnye
                if len(word_a) < FIBONACCI[2] or len(word_b) < FIBONACCI[2]:
                    continue
                if word_a == word_b:
                    continue

                # Zatukhanie starykh
                if self.total_observed > 0 and self.total_observed % FIBONACCI[7] == 0:
                    self._decay_observations()

                # Dobavlyaem paru (v obe storony)
                pair_key = tuple(sorted([word_a, word_b]))
                self.opposite_pairs[pair_key] += weight

                # Agent/target counts
                self.agent_count[word_a] += weight
                self.target_count[word_b] += weight

                observed += 1
                self.total_pairs_found += 1

        self.total_observed += 1
        return observed

    def observe_pair(self, word_a, word_b, weight=PHI):
        """Nablyudat paru protivopolozhnostey напрямую."""
        if len(word_a) < FIBONACCI[2] or len(word_b) < FIBONACCI[2]:
            return
        if word_a == word_b:
            return

        pair_key = tuple(sorted([word_a, word_b]))
        self.opposite_pairs[pair_key] += weight
        self.agent_count[word_a] += weight
        self.target_count[word_b] += weight
        self.total_pairs_found += 1

    def _decay_observations(self):
        """Zatukhanie starykh nablyudeniy."""
        for key in self.opposite_pairs:
            self.opposite_pairs[key] *= POLARITY_DECAY
        for key in self.agent_count:
            self.agent_count[key] *= POLARITY_DECAY
        for key in self.target_count:
            self.target_count[key] *= POLARITY_DECAY

    # =========================================================
    # 2. SHARED NEIGHBORS — dopolnitelnyy signal
    # =========================================================
    def detect_shared_neighbor_opposites(self, generator_graph, min_shared=FIBONACCI[4]):
        """
        Nayti pary slov s MNOGO obshchimi sosedyami
        no kotorye redko stoyat RYADOM.

        hot i cold: obshchie sosedi = temperature, weather, water, ...
        Esli oni redko stoyat ryadom (net bigram hot-cold) —
        eto signal protivopolozhnosti.
        """
        if not generator_graph:
            return 0

        found = 0
        # Berem tolko slova uzhe s kakoy-to polyarnostyu
        known_polar = set(self.agent_count.keys()) | set(self.target_count.keys())
        if not known_polar:
            return 0

        for word in list(known_polar)[:FIBONACCI[10]]:
            w_neighbors = set(generator_graph.get(word, {}).keys())
            if len(w_neighbors) < min_shared:
                continue

            for other in list(known_polar)[:FIBONACCI[10]]:
                if other == word:
                    continue
                o_neighbors = set(generator_graph.get(other, {}).keys())
                shared = len(w_neighbors & o_neighbors)

                if shared >= min_shared:
                    # Mnogo obshchikh sosedey — svyazany
                    # Proveryaem: stoyat li oni ryadom (bigram)?
                    direct_link = (other in generator_graph.get(word, {}) or
                                   word in generator_graph.get(other, {}))

                    pair_key = tuple(sorted([word, other]))
                    if pair_key in self.opposite_pairs:
                        # Uzhe izvestnaya para — usilivayem
                        boost = shared * PHI_INV_SQ
                        if not direct_link:
                            boost *= PHI  # Eshcho silneye esli ne ryadom
                        self.opposite_pairs[pair_key] += boost
                        found += 1

        return found

    # =========================================================
    # 3. KRISTALLIZATSIYA — vychislenie polyarnykh faz
    # =========================================================
    def compute_polarity_phases(self):
        """
        Vychislit polarity_phase dlya kazhdogo slova.

        NOVYY PODKHOD: grafovaya 2-raskraska (bipartite coloring).

        Pary protivopolozhnostey obrazuyut GRAF.
        hot--cold, big--small, up--down...
        Etot graf (pochti vsegda) bipartitnyy.

        Naznachayem:
          Odna storona → phase 0.0
          Drugaya storona → phase PHI_INV ≈ 0.618

        Protivopolozhnosti VSEGDA na rasstoyanii PHI_INV drug ot druga.
        Slova v odnoy gruppe (hot, big, fast) — na rasstoyanii 0.0.
        """
        self.polarity_phases.clear()

        # Stroyim graf sosedstva iz par
        adj = defaultdict(set)
        for (word_a, word_b), weight in self.opposite_pairs.items():
            if weight >= PHI_INV:  # Minimum threshold
                adj[word_a].add(word_b)
                adj[word_b].add(word_a)

        if not adj:
            return 0

        # BFS 2-raskraska po komponentam svyaznosti
        colored = {}  # word → 0 or 1
        for start in adj:
            if start in colored:
                continue
            # BFS
            queue = [start]
            colored[start] = 0
            while queue:
                current = queue.pop(0)
                current_color = colored[current]
                for neighbor in adj[current]:
                    if neighbor not in colored:
                        colored[neighbor] = 1 - current_color
                        queue.append(neighbor)
                    # Esli uzhe okrasheno v tot zhe tsvet — ne bipartitnyy,
                    # no my prosto ignoriruyem (ne menyaem)

        # Naznachayem fazy: tsvet 0 → phase 0.0, tsvet 1 → phase PHI_INV
        for word, color in colored.items():
            if color == 0:
                self.polarity_phases[word] = 0.0
            else:
                self.polarity_phases[word] = PHI_INV  # ≈ 0.618

        self.total_crystallized = len(self.polarity_phases)
        return self.total_crystallized

    # =========================================================
    # 4. PRIMENENIE K TORUSU — dim 5
    # =========================================================
    def apply_to_torus(self):
        """
        Vnedrit polyarnye fazy kak dim 5 tora.
        """
        if not self.word_space:
            return 0

        applied = 0
        for word, pp in self.polarity_phases.items():
            if word not in self.word_space._torus:
                continue

            current = self.word_space._torus[word]

            # Dorastit do dim 5 esli nuzhno
            while len(current) < FIBONACCI[4]:  # 5
                current.append((current[-1] * PHI) % 1.0)

            if len(current) == FIBONACCI[4]:
                # Novaya razmernost
                current.append(pp)
            else:
                # Plavnoye obnovleniye
                old = current[FIBONACCI[4]]  # dim 5
                diff = pp - old
                # Circular phase wrap: 0.5 = topologicheskaya antifaza na kruge [0,1)
                if diff > 0.5:
                    diff -= 1.0
                elif diff < -0.5:
                    diff += 1.0
                current[FIBONACCI[4]] = (old + diff * PHI_INV) % 1.0

            applied += 1

        # Obnovlyaem razmernost tora
        if applied > 0:
            self.word_space.N = max(self.word_space.N, FIBONACCI[4] + 1)

        return applied

    # =========================================================
    # 5. ZAPROS — polyarnost slova
    # =========================================================
    def get_polarity(self, word):
        """Poluchit polyarnuyu fazu slova."""
        return self.polarity_phases.get(word)

    def polarity_distance(self, word_a, word_b):
        """Polyarnoye rasstoyanie mezhdu dvumya slovami."""
        pa = self.polarity_phases.get(word_a)
        pb = self.polarity_phases.get(word_b)
        if pa is None or pb is None:
            return None
        return phi_phase_distance(pa, pb)

    def find_opposites(self, word, top_k=FIBONACCI[5]):
        """
        Nayti protivopolozhnosti slova.
        Ischem slova s polyarnym rasstoyaniem blizkim k PHI_INV
        (protivopolozhnaya gruppa v bipartitnom grafe).
        """
        wp = self.polarity_phases.get(word)
        if wp is None:
            return []

        scored = []
        for other, op in self.polarity_phases.items():
            if other == word:
                continue
            dist = phi_phase_distance(wp, op)
            # Protivopolozhnost = rasstoyanie ≈ PHI_INV (drugaya gruppa)
            if dist > PHI_INV_CUBE:
                # Dopolnitelnyy ves dlya par kotorye napryamuyu svyazany
                pair_key = tuple(sorted([word, other]))
                pair_weight = self.opposite_pairs.get(pair_key, 0)
                total_score = dist + pair_weight * PHI_INV_SQ
                scored.append((other, round(total_score, 4)))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def is_opposite(self, word_a, word_b, threshold=PHI_INV_CUBE):
        """Yavlyayutsya li dva slova protivopolozhnostyami?"""
        dist = self.polarity_distance(word_a, word_b)
        if dist is None:
            return None
        return dist > threshold

    # =========================================================
    # 6. POLNYY TSIKL
    # =========================================================
    def polarity_cycle(self, generator_graph=None):
        """
        Polnyy tsikl polyarnogo analiza.
        Vyzyvaetsya iz brain.cycle().
        """
        result = {
            "computed": 0,
            "applied": 0,
            "shared_detected": 0,
        }

        if generator_graph:
            result["shared_detected"] = self.detect_shared_neighbor_opposites(
                generator_graph)

        result["computed"] = self.compute_polarity_phases()
        result["applied"] = self.apply_to_torus()

        self.save()
        return result

    # =========================================================
    # SAVE / LOAD
    # =========================================================
    def save(self):
        path = os.path.join(self.state_dir, "polarity.json")

        # Filtruyem slabye nablyudeniya
        pairs_data = {}
        for pair_key, weight in self.opposite_pairs.items():
            if weight >= PHI_INV:
                pairs_data[f"{pair_key[0]}|{pair_key[1]}"] = round(weight, 4)

        data = {
            "opposite_pairs": pairs_data,
            "agent_count": {k: round(v, 4) for k, v in self.agent_count.items()
                           if v >= PHI_INV},
            "target_count": {k: round(v, 4) for k, v in self.target_count.items()
                            if v >= PHI_INV},
            "polarity_phases": {k: round(v, 8) for k, v in self.polarity_phases.items()},
            "stats": {
                "total_observed": self.total_observed,
                "total_pairs_found": self.total_pairs_found,
                "total_crystallized": self.total_crystallized,
            },
            "saved_at": time.time(),
        }
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception as e:
            print(f"[!] PolarityEngine save failed: {e}")

    def _load(self):
        path = os.path.join(self.state_dir, "polarity.json")
        if not os.path.exists(path):
            return
        try:
            with open(path) as f:
                data = json.load(f)

            for pair_str, weight in data.get("opposite_pairs", {}).items():
                parts = pair_str.split("|", 1)
                if len(parts) == 2:
                    pair_key = tuple(sorted(parts))
                    self.opposite_pairs[pair_key] = weight

            self.agent_count = defaultdict(float,
                data.get("agent_count", {}))
            self.target_count = defaultdict(float,
                data.get("target_count", {}))
            self.polarity_phases = data.get("polarity_phases", {})

            stats = data.get("stats", {})
            self.total_observed = stats.get("total_observed", 0)
            self.total_pairs_found = stats.get("total_pairs_found", 0)
            self.total_crystallized = stats.get("total_crystallized", 0)

        except Exception as e:
            print(f"[!] PolarityEngine load failed: {e}")

    def stats(self):
        return {
            "opposite_pairs": len(self.opposite_pairs),
            "words_with_polarity": len(self.polarity_phases),
            "total_observed": self.total_observed,
            "total_pairs_found": self.total_pairs_found,
            "total_crystallized": self.total_crystallized,
        }
