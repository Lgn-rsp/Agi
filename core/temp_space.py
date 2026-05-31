"""
temp_space.py — Vremennoe fazovoe prostranstvo.

Mozg: rabochaya pamyat v prefrontal cortex.
Novyy tekst sozdaet VREMENNYE svyazi.
Oni zhivut minuty. Silnye konsolidiruyutsya.

Realizatsiya:
1. Poluchaem novyy tekst
2. Sozdaem VREMENNYY PhaseTorus (ne trogaya osnovnoy)
3. Observe -> crystallize -> pravila
4. Dlya otveta: temp rules + permanent rules
5. Posle otveta: silnye temp rules -> merge v osnovnoy
   Sila opredelyaetsya resonansom s permanent rules:
   esli temp rule rezoniryet s permanent — ono vazhnoye.

Vsyo cherez phi.
"""
import time
from collections import defaultdict

from core.resonance_constants import (
    PHI, PHI_INV, PHI_INV_SQ, FIBONACCI,
    CRYSTALLIZE_THRESHOLD, CO_OCCURRENCE_WINDOW,
    phi_phase_distance, phi_phase_resonance,
    is_near_phi_target
)
from core.symbolizer import text_to_words


class TempSpace:
    """
    Vremennoe fazovoe prostranstvo.
    Zhivot tolko vo vremya obrabotki odnogo teksta/voprosa.
    """

    def __init__(self, permanent_space=None):
        self.permanent = permanent_space  # ssylka na osnovnoy PhaseTorus

        # Vremennyye dannye
        self.phases = {}
        self.cooccurrence = defaultdict(int)
        self.rules = {}
        self.temp_graph = defaultdict(dict)  # {word: {neighbor: score}}
        self._counter = 0

        self.created_at = time.time()

    def process_text(self, text):
        """
        Obrabotat novyy tekst:
        1. Symbolize
        2. Observe (co-occurrence)
        3. Crystallize (pravila)
        4. Postroit graf
        """
        words = text_to_words(text)
        if not words:
            return 0

        # Init phases dlya novykh slov
        for w in words:
            if w not in self.phases:
                # Esli est v permanent — beryom ottuda
                if self.permanent:
                    p = self.permanent._get_phase(w)
                    if p is not None:
                        self.phases[w] = p
                        continue
                # Novoe slovo — golden angle
                self._counter += 1
                self.phases[w] = (self._counter * PHI_INV) % 1.0

        # Co-occurrence
        window = CO_OCCURRENCE_WINDOW
        for i in range(len(words)):
            for j in range(1, min(window + 1, len(words) - i)):
                a, b = words[i], words[i + j]
                if a == b:
                    continue
                pair = (a, b) if a < b else (b, a)
                self.cooccurrence[pair] += 1

                # Bystryye temp pravila (nizhe threshold chem permanent)
                count = self.cooccurrence[pair]
                if count >= 1:  # kazhdaya para v temp — srazu pravilo — bystreye
                    self._try_crystallize(a, b, j, count)

        return len(words)

    def _try_crystallize(self, a, b, distance, count):
        """Kristallizatsiya s nizkim porogom."""
        pa = self.phases.get(a)
        pb = self.phases.get(b)
        if pa is None or pb is None:
            return

        dist = phi_phase_distance(pa, pb)
        if dist < 0.01:
            return

        import math
        rule_key = f"{a}|{b}" if a < b else f"{b}|{a}"
        score = math.log(1 + count) / math.log(PHI)

        self.rules[rule_key] = {
            "a": a, "b": b,
            "distance": round(dist, 6),
            "count": count,
            "temp": True,
        }

        # Graf
        self.temp_graph[a][b] = max(
            self.temp_graph[a].get(b, 0), score)
        self.temp_graph[b][a] = max(
            self.temp_graph[b].get(a, 0), score)

    def get_concepts(self, input_words, top_k=FIBONACCI[6]):
        """
        Izvlech koncepty iz temp prostranstva
        dlya dannykh input words.
        """
        import math
        activation = {}

        for w in input_words:
            if w in self.temp_graph:
                for neighbor, score in self.temp_graph[w].items():
                    activation[neighbor] = activation.get(neighbor, 0) + score

        # Sort
        result = sorted(activation.items(),
                        key=lambda x: x[1], reverse=True)
        return result[:top_k]

    def merge_strong_to_permanent(self, permanent_space,
                                   threshold=PHI_INV):
        """
        Silnye temp pravila -> merge v permanent.
        'Silnye' = te chto rezoniruyut s uzhe sushchestvuyushchimi.
        """
        if not permanent_space:
            return 0

        merged = 0
        for key, rule in self.rules.items():
            a, b = rule["a"], rule["b"]

            # Proveryaem: est li eti slova v permanent?
            pa = permanent_space._get_phase(a)
            pb = permanent_space._get_phase(b)

            if pa is not None and pb is not None:
                # Oba slova izvestny — eto vazhnoye pravilo
                permanent_space.observe([a, b] * FIBONACCI[3])
                merged += 1
            elif pa is not None or pb is not None:
                # Odno slovo izvestno — potentsialno vazhnoye
                if rule["count"] >= FIBONACCI[4]:  # >= 5
                    permanent_space.observe([a, b] * FIBONACCI[3])
                    merged += 1

        return merged

    def stats(self):
        return {
            "temp_symbols": len(self.phases),
            "temp_rules": len(self.rules),
            "temp_cooc": len(self.cooccurrence),
            "age_seconds": round(time.time() - self.created_at, 1),
        }
