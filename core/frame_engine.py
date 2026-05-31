"""
frame_engine.py v10 — Grammatika iz trigramm.

FIX: connect_concepts ispolzuet RAZNYE freymi dlya raznykh par.
Ne "X is Y is Z is W" a "X is Y of Z and W".

Freym = pattern s slotami: [?] connector [?]
Rozhdayetsya kogda connector vstrechaetsya v seredine
>= CRYSTALLIZE_THRESHOLD trigramm.
"""
import math
from collections import defaultdict

from core.resonance_constants import (
    PHI, PHI_INV, PHI_INV_SQ, FIBONACCI, CRYSTALLIZE_THRESHOLD
)


class Frame:
    __slots__ = ['connector', 'pattern', 'examples',
                 'count', 'strength', 'lang']

    def __init__(self, connector, count, lang="en"):
        self.connector = connector
        self.pattern = f"?_{connector}_?"
        self.examples = []
        self.count = count
        self.strength = math.log(1 + count) / math.log(PHI)
        self.lang = lang

    def add_example(self, subject, predicate, count=1):
        for i, (s, p, c) in enumerate(self.examples):
            if s == subject and p == predicate:
                self.examples[i] = (s, p, c + count)
                return
        self.examples.append((subject, predicate, count))
        self.examples.sort(key=lambda x: x[2], reverse=True)
        if len(self.examples) > FIBONACCI[8]:
            self.examples = self.examples[:FIBONACCI[8]]

    def has_pair(self, subj, pred):
        for s, p, c in self.examples:
            if s == subj and p == pred:
                return c
            if s == pred and p == subj:
                return c * PHI_INV
        return 0

    def has_word_as(self, word, role="subject"):
        for s, p, c in self.examples:
            if role == "subject" and s == word:
                return True
            if role == "predicate" and p == word:
                return True
        return False

    def __repr__(self):
        return f"Frame('{self.pattern}', n={self.count}, ex={len(self.examples)})"


class FrameEngine:
    def __init__(self, phase_spaces):
        self.spaces = phase_spaces
        self.trigram_space = phase_spaces.get("trigrams")
        self.frames = {}
        self.total_frames = 0
        self._extract_frames()
        print(f"[+] FrameEngine initialized. Frames: {len(self.frames)}")

    def _extract_frames(self):
        if not self.trigram_space:
            return
        middle_counts = defaultdict(int)
        middle_examples = defaultdict(list)

        for key, rule in self.trigram_space.rules.items():
            for sym in [rule["a"], rule["b"]]:
                parts = sym.split("_")
                if len(parts) != 3:
                    continue
                subj, mid, pred = parts
                if len(mid) < 1 or len(subj) < 2 or len(pred) < 2:
                    continue
                middle_counts[mid] += rule.get("count", 1)
                middle_examples[mid].append(
                    (subj, pred, rule.get("count", 1)))

        for connector, count in middle_counts.items():
            if count < CRYSTALLIZE_THRESHOLD:
                continue
            from core.lang_detect import _CYR
            lang = "ru" if any(c in _CYR for c in connector) else "en"
            frame = Frame(connector, count, lang)
            ec = defaultdict(int)
            for subj, pred, c in middle_examples[connector]:
                ec[(subj, pred)] += c
            for (subj, pred), c in sorted(ec.items(), key=lambda x: x[1], reverse=True)[:FIBONACCI[8]]:
                frame.add_example(subj, pred, c)
            self.frames[connector] = frame
            self.total_frames += 1

    def best_frame_for_pair(self, word_a, word_b, lang="en", exclude=None):
        """
        Luchshiy freym dlya soedineniya dvukh konceptov.
        exclude = set konnekorov kotorye uzhe ispolzovany
        (chtoby ne povtoryat "is is is")
        """
        exclude = exclude or set()
        best_conn = None
        best_score = -1

        for conn, frame in self.frames.items():
            if conn in exclude:
                continue
            # Yazyk dolzhen sovpadat
            if lang != "mix" and frame.lang != lang:
                continue

            score = 0
            # Tochnoe sovpadeniye (a, b)
            exact = frame.has_pair(word_a, word_b)
            if exact > 0:
                score = exact * frame.strength * PHI

            # A kak subject, B kak predicate
            elif frame.has_word_as(word_a, "subject") and frame.has_word_as(word_b, "predicate"):
                score = frame.strength * PHI_INV

            # Obratniy poryadok
            elif frame.has_word_as(word_b, "subject") and frame.has_word_as(word_a, "predicate"):
                score = frame.strength * PHI_INV_SQ

            if score > best_score:
                best_score = score
                best_conn = conn

        return best_conn, best_score

    def connect_concepts(self, concepts, lang="en"):
        """
        v10: RAZNYE freymi dlya raznykh par.
        [logos, patterns, resonance, observed] ->
        "logos is patterns of resonance and observed"
        NE "logos is patterns is resonance is observed"
        """
        if not concepts or len(concepts) < 2:
            return concepts

        result = [concepts[0]]
        used_connectors = set()

        for i in range(1, len(concepts)):
            prev = concepts[i - 1]
            curr = concepts[i]

            # Ishchem luchshiy freym, NE povtoryaya predydushchiy
            conn, score = self.best_frame_for_pair(
                prev, curr, lang, exclude=used_connectors)

            if conn and score > 0:
                result.append(conn)
                used_connectors.add(conn)
                result.append(curr)
            else:
                # Fallback: lyuboy neispolzovnnyy connector
                if lang == "ru":
                    fallbacks = ["это", "и", "в", "с", "для", "через"]
                else:
                    fallbacks = ["is", "and", "of", "in", "with", "through"]

                added = False
                for fb in fallbacks:
                    if fb not in used_connectors and fb in self.frames:
                        result.append(fb)
                        used_connectors.add(fb)
                        result.append(curr)
                        added = True
                        break

                if not added:
                    # Sbros used — razreshaem povtory
                    used_connectors.clear()
                    if lang == "ru":
                        result.append("и")
                    else:
                        result.append("and")
                    result.append(curr)

        return result

    def refresh(self):
        self.frames.clear()
        self.total_frames = 0
        self._extract_frames()

    def stats(self):
        lc = defaultdict(int)
        for f in self.frames.values():
            lc[f.lang] += 1
        top = sorted(self.frames.values(), key=lambda f: f.count, reverse=True)
        return {
            "total_frames": self.total_frames,
            "languages": dict(lc),
            "top_frames": [(f.connector, f.count, len(f.examples))
                          for f in top[:FIBONACCI[5]]],
        }
