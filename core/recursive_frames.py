"""
recursive_frames.py — Rekursivnye freymi.

Muzyka: obertony. Kazhdyy oberton rezoniryet s osnovnoy
chastotoy v otnoshenii phi.

Predlozheniye = osnovnaya chastota.
Pridatochnoye = oberton (sila * PHI_INV).
Vlozhennoe pridatochnoye = oberton obertona (sila * PHI_INV^2).

Glubina rekursii opredelyaetsya ESTESTVENNO:
kogda sila obertona < PHI_INV_CUBE — ostanovka.
Eto kak zvuk zatuhayet — ne potomu chto kto-to reshayet
ostanovit ego, a potomu chto energiya rasseivaetsya.

Svyazuyushchiye slova mezhdu urovnyami:
  EN: that, which, where, because, through, when, while
  RU: который, где, потому что, через, когда, пока, что

Eto kak v muzike — perekhod mezhdu obertonami cherez
konsonantnye intervaly.

Vsyo cherez phi.
"""
import math
from collections import defaultdict

from core.resonance_constants import (
    PHI, PHI_INV, PHI_INV_SQ, PHI_INV_CUBE, FIBONACCI,
    phi_phase_distance, phi_phase_resonance
)


# Svyazuyushchiye slova = PEREKHODY mezhdu obertonami
SUBORDINATORS_EN = {
    "that": 0.8,    # samyy neutralnyy
    "which": 0.7,   # opisatelnyy
    "where": 0.6,   # mesto
    "because": 0.9, # prichina (silnyy)
    "through": 0.7, # sposob
    "when": 0.6,    # vremya
    "while": 0.5,   # odnovremennost
    "who": 0.7,     # akter
    "whose": 0.5,   # prinadlezhnost
    "if": 0.8,      # usloviye
    "as": 0.6,      # kak
    "since": 0.7,   # s tekh por kak / potomu chto
}

SUBORDINATORS_RU = {
    "который": 0.8,
    "которая": 0.8,
    "которое": 0.8,
    "которые": 0.8,
    "где": 0.6,
    "когда": 0.6,
    "потому": 0.9,
    "через": 0.7,
    "пока": 0.5,
    "если": 0.8,
    "как": 0.6,
    "что": 0.7,
    "чтобы": 0.7,
}


class RecursiveFrame:
    """
    Odin uroven rekursivnogo freyma.
    Imeet: slova (content) + potomki (sub-frames).
    """
    __slots__ = ['words', 'connector', 'children', 'depth', 'strength']

    def __init__(self, words, connector=None, depth=0, strength=1.0):
        self.words = words          # spisok slov etogo urovnya
        self.connector = connector  # svyazka s roditelем ("that", "which"...)
        self.children = []          # podchinonnyye freymi
        self.depth = depth
        self.strength = strength    # zatukhayеt s PHI_INV na kazhdoy glubine

    def add_child(self, child_frame):
        self.children.append(child_frame)

    def to_text(self):
        """Rekursivno sobrat tekst."""
        parts = list(self.words)
        for child in self.children:
            if child.connector:
                parts.append(child.connector)
            parts.extend(child.to_text_list())
        return " ".join(parts)

    def to_text_list(self):
        """Rekursivno sobrat spisok slov."""
        result = list(self.words)
        for child in self.children:
            if child.connector:
                result.append(child.connector)
            result.extend(child.to_text_list())
        return result

    def total_words(self):
        n = len(self.words)
        for child in self.children:
            n += child.total_words()
            if child.connector:
                n += 1
        return n


class RecursiveFrameEngine:
    """
    Stroyet rekursivnye predlozheniya iz konceptov.

    Printsip:
    1. Top koncepty -> osnovnoy freym (root)
    2. Dlya kazhdogo koncepta v root:
       ishchem ego svyazi -> podfreeym s subordinatorom
    3. Dlya kazhdogo podfreyma — eshchyo glubzhe
    4. Ostanovka kogda sila < PHI_INV_CUBE

    Glubina = log_phi(n_concepts) estestvenno.
    """

    def __init__(self, frame_engine, chain_engine, phase_spaces):
        self.frames = frame_engine
        self.chains = chain_engine
        self.word_space = phase_spaces.get("words")
        self._graph = defaultdict(dict)
        self._build_graph()

        print(f"[+] RecursiveFrameEngine initialized. "
              f"Graph: {len(self._graph)} nodes")

    def _build_graph(self):
        """Postroit graf iz pravil dlya poiska svyazey."""
        if not self.word_space:
            return
        for key, rule in self.word_space.rules.items():
            a, b = rule["a"], rule["b"]
            score = math.log(1 + rule.get("count", 1)) / math.log(PHI)
            self._graph[a][b] = max(self._graph[a].get(b, 0), score)
            self._graph[b][a] = max(self._graph[b].get(a, 0), score)

    def build_sentence(self, concepts, lang="en", max_depth=FIBONACCI[3]):
        """
        Postroit rekursivnoye predlozheniye iz konceptov.

        concepts: [(word, score), ...]
        Vozvrashchaet RecursiveFrame (root).
        """
        if not concepts:
            return None

        # Razdelyaem: top = root level, ostalnye = candidates dlya podfreymov
        root_concepts = concepts[:FIBONACCI[3]]  # top 3 v root
        sub_candidates = concepts[FIBONACCI[3]:]  # ostalnyye — na podfreymi

        # ROOT freym
        root_words = self._connect_words(
            [w for w, s in root_concepts], lang)
        root = RecursiveFrame(root_words, depth=0, strength=1.0)

        # PODFREYMI — rekursivno
        if sub_candidates:
            self._add_subframes(
                root, root_concepts, sub_candidates, lang,
                depth=1, max_depth=max_depth)

        return root

    def _add_subframes(self, parent, parent_concepts, candidates,
                        lang, depth, max_depth):
        """Rekursivno dobavlyaem podfreymi."""
        if depth > max_depth:
            return
        if not candidates:
            return

        # Sila na etoy glubine
        strength = PHI_INV ** depth
        if strength < PHI_INV_CUBE:
            return  # Estestvennoye zatukhaniye

        # Beryom FIBONACCI[3]=3 kandidatov dlya etogo urovnya
        level_concepts = candidates[:FIBONACCI[3]]
        remaining = candidates[FIBONACCI[3]:]

        # Ishchem luchshiy subordinator
        subordinator = self._find_subordinator(
            parent_concepts, level_concepts, lang)

        # Stroim slova podfreyma
        sub_words = self._connect_words(
            [w for w, s in level_concepts], lang)

        sub_frame = RecursiveFrame(
            sub_words,
            connector=subordinator,
            depth=depth,
            strength=strength)

        parent.add_child(sub_frame)

        # Glubzhe — esli est eshchyo kandidaty
        if remaining:
            self._add_subframes(
                sub_frame, level_concepts, remaining, lang,
                depth + 1, max_depth)

    def _find_subordinator(self, parent_concepts, child_concepts, lang):
        """
        Nayti luchshiy subordinator mezhdu roditelskivmi i detskimi konceptami.
        Osnovan na tom kakie subordinatory vstrechayutsya mezhdu etimi slovami v grafe.
        """
        subs = SUBORDINATORS_RU if lang == "ru" else SUBORDINATORS_EN
        best_sub = None
        best_score = -1

        parent_words = [w for w, s in parent_concepts]
        child_words = [w for w, s in child_concepts]

        for sub, weight in subs.items():
            score = 0
            # Proveryaem: est li sub v grafe mezhdu parent i child slovami?
            for pw in parent_words:
                if sub in self._graph.get(pw, {}):
                    score += self._graph[pw].get(sub, 0) * weight
            for cw in child_words:
                if sub in self._graph.get(cw, {}):
                    score += self._graph[cw].get(sub, 0) * weight

            if score > best_score:
                best_score = score
                best_sub = sub

        # Fallback
        if not best_sub:
            if lang == "ru":
                best_sub = "который" if best_score < 0 else "что"
            else:
                best_sub = "that"

        return best_sub

    def _connect_words(self, words, lang="en"):
        """Soedinit slova cherez FrameEngine."""
        if self.frames and len(words) >= 2:
            connected = self.frames.connect_concepts(words, lang)
            if connected:
                return connected
        return words

    def format(self, root_frame):
        """Formatirovat rekursivnyy freym v tekst."""
        if not root_frame:
            return ""
        text = root_frame.to_text()
        if text:
            text = text[0].upper() + text[1:]
            if not text.endswith("."):
                text += "."
        return text

    def refresh(self):
        self._graph.clear()
        self._build_graph()

    def stats(self):
        return {
            "graph_nodes": len(self._graph),
        }
