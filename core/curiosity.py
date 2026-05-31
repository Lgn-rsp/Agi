"""
curiosity.py — Dvigatel lyubopytstva.
Sistema SAMA reshaet chto izuchat dalshe.
Voprosy rozhdayutsya iz fazovykh anomaliy —
patterny kotorye POCHTI rezoniruyut no ne tochno.
Chem blizhe k rezonansu i chem chashche — tem vazhneye vopros.
"""
import time
import json
import os
from collections import defaultdict

from core.resonance_constants import (
    PHI, PHI_INV, FIBONACCI,
    phi_phase_distance, phi_phase_resonance,
    is_near_phi_target
)


class Question:
    """Odin vopros sistemy."""
    __slots__ = ['pair', 'level', 'distance', 'nearest_target',
                 'gap', 'count', 'priority', 'created_at',
                 'attempts', 'resolved']

    def __init__(self, pair, level, distance, nearest_target,
                 gap, count):
        self.pair = pair
        self.level = level
        self.distance = distance
        self.nearest_target = nearest_target
        self.gap = gap
        self.count = count
        self.priority = count * (0.15 - gap) if gap < 0.15 else 0
        self.created_at = time.time()
        self.attempts = 0
        self.resolved = False

    def to_dict(self):
        return {
            "pair": self.pair,
            "level": self.level,
            "distance": round(self.distance, 6),
            "nearest_target": self.nearest_target,
            "gap": round(self.gap, 6),
            "count": self.count,
            "priority": round(self.priority, 4),
            "created_at": self.created_at,
            "attempts": self.attempts,
            "resolved": self.resolved,
        }

    def __repr__(self):
        return (f"Q({self.pair}, target={self.nearest_target}, "
                f"gap={self.gap:.4f}, priority={self.priority:.2f})")


class CuriosityEngine:
    """
    Sobiraet anomalii so vsekh urovney.
    Ranzhiruet po prioritetu.
    Predlagaet chto issledovat.
    """

    def __init__(self, phase_spaces, state_dir=None):
        self.spaces = phase_spaces
        self.state_dir = state_dir or os.path.expanduser("~/logos_agi/state")
        self.log_dir = os.path.expanduser("~/logos_agi/logs")
        os.makedirs(self.state_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)

        self.questions = []       # aktivnye voprosy
        self.resolved = []        # reshennye
        self.max_questions = FIBONACCI[12]   # 233
        self.max_resolved = FIBONACCI[14]    # 610

        self._load_state()
        print(f"[+] CuriosityEngine initialized. "
              f"Active: {len(self.questions)}, "
              f"Resolved: {len(self.resolved)}")

    def scan(self, top_per_level=FIBONACCI[6]):
        """
        Skaniryet vse urovni, sobiraet anomalii,
        sozdaet voprosy.
        """
        new_questions = 0

        for level_name, space in self.spaces.items():
            anomalies = space.find_anomalies(top_per_level)

            for anomaly in anomalies:
                # Ne dubliruem
                pair_key = f"{anomaly['pair'][0]}||{anomaly['pair'][1]}"
                if any(f"{q.pair[0]}||{q.pair[1]}" == pair_key
                       and q.level == level_name
                       for q in self.questions):
                    continue

                q = Question(
                    pair=anomaly["pair"],
                    level=level_name,
                    distance=anomaly["distance"],
                    nearest_target=anomaly["nearest_target"],
                    gap=anomaly["gap"],
                    count=anomaly["count"],
                )
                self.questions.append(q)
                new_questions += 1

        # Sort by priority
        self.questions.sort(key=lambda q: q.priority, reverse=True)

        # Trim
        while len(self.questions) > self.max_questions:
            self.questions.pop()

        return new_questions

    def top_questions(self, n=FIBONACCI[5]):
        """Top n=8 voprosov po prioritetu."""
        return [q for q in self.questions[:n] if not q.resolved]

    def get_research_targets(self, n=FIBONACCI[4]):
        """
        Chto issledovat? Vozvrashchaet simvoly
        kotorye nuzhno nablyudat bolshe.
        n=5 targetov.
        """
        targets = set()
        for q in self.top_questions(n * 2):
            targets.add(q.pair[0])
            targets.add(q.pair[1])
            if len(targets) >= n * 2:
                break
        return list(targets)

    def check_resolved(self):
        """
        Proveryaem: mozhet nekotorye voprosy uzhe resheny?
        (fazy sdvinulis i teper rezoniruyut)
        """
        newly_resolved = 0
        still_active = []

        for q in self.questions:
            if q.resolved:
                continue

            space = self.spaces.get(q.level)
            if not space:
                still_active.append(q)
                continue

            phase_a = space._get_phase(q.pair[0])
            phase_b = space._get_phase(q.pair[1])

            if phase_a is None or phase_b is None:
                still_active.append(q)
                continue

            dist = phi_phase_distance(phase_a, phase_b)
            if dist > 0.01:
                ratio = max(dist, 0.001) / max(1.0 - dist, 0.001)
                hit = is_near_phi_target(ratio, tolerance=0.05)
                if hit:
                    q.resolved = True
                    self.resolved.append(q)
                    newly_resolved += 1

                    self._log(f"RESOLVED: {q.pair} -> {hit[0]} "
                             f"(was gap={q.gap:.4f})")
                    continue

            q.attempts += 1
            still_active.append(q)

        self.questions = still_active

        # Trim resolved
        while len(self.resolved) > self.max_resolved:
            self.resolved.pop(0)

        return newly_resolved

    def formulate_search_query(self, question):
        """
        Prevrashchaet vopros v poiskovyy zapros.
        Dlya budushchego web_core.
        """
        a, b = question.pair
        level = question.level
        target = question.nearest_target

        if level == "words":
            return f"{a} {b} relationship meaning"
        elif level == "pairs":
            parts_a = a.split("_")
            parts_b = b.split("_")
            return f"{' '.join(parts_a)} {' '.join(parts_b)} pattern"
        elif level == "chars":
            return f"letter combination {a}{b} frequency language"
        else:
            return f"{a} {b} connection"

    def stats(self):
        return {
            "active_questions": len(self.questions),
            "resolved_questions": len(self.resolved),
            "top_priority": round(
                self.questions[0].priority, 2) if self.questions else 0,
            "research_targets": len(self.get_research_targets()),
        }

    def save_state(self):
        path = os.path.join(self.state_dir, "curiosity.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "questions": [q.to_dict() for q in self.questions[:FIBONACCI[10]]],
                "resolved_count": len(self.resolved),
                "saved_at": time.time(),
            }, f, ensure_ascii=False, indent=2)

    def _load_state(self):
        path = os.path.join(self.state_dir, "curiosity.json")
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for qd in data.get("questions", []):
                q = Question(
                    pair=tuple(qd["pair"]),
                    level=qd["level"],
                    distance=qd["distance"],
                    nearest_target=qd["nearest_target"],
                    gap=qd["gap"],
                    count=qd["count"],
                )
                q.attempts = qd.get("attempts", 0)
                self.questions.append(q)
        except Exception:
            pass

    def _log(self, message):
        path = os.path.join(self.log_dir, "curiosity.log")
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {message}\n")


# === TEST ===
if __name__ == "__main__":
    from core.phase_space import PhaseSpace
    from core.symbolizer import symbolize_multilevel

    # Uchim
    space = PhaseSpace(state_dir="/tmp/curiosity_test")
    texts = [
        "the cat sat on the mat",
        "the dog ran in the park",
        "the bird flew over the tree",
        "the fish swam in the sea",
        "the cat ate the fish",
        "the dog chased the cat",
        "fire burns in the night",
        "water flows down the river",
        "the sun rises in the east",
        "the moon shines in the west",
        "stars glow in the dark sky",
        "wind blows through the trees",
        "rain falls on the ground",
    ]

    for _ in range(FIBONACCI[6]):
        for text in texts:
            words = text.lower().split()
            space.observe(words)

    print(f"Symbols: {space.stats()['symbols']}, "
          f"Rules: {space.stats()['rules']}")

    # Curiosity
    spaces = {"words": space}
    curiosity = CuriosityEngine(spaces, state_dir="/tmp/curiosity_test")

    new_q = curiosity.scan()
    print(f"\nNew questions: {new_q}")

    print(f"\n=== TOP QUESTIONS ===")
    for q in curiosity.top_questions():
        search = curiosity.formulate_search_query(q)
        print(f"  {q}")
        print(f"    -> search: '{search}'")

    print(f"\n=== RESEARCH TARGETS ===")
    targets = curiosity.get_research_targets()
    print(f"  Need more data on: {targets}")

    print(f"\n=== STATS ===")
    print(f"  {curiosity.stats()}")

    curiosity.save_state()
    print(f"\n[+] Saved")
