"""
paragraph_engine.py — Mnogofrazazovaya generatsiya.

Mozg: theta-gamma nesting na urovne PREDLOZHENIY.
Odin theta-tsikl = odno predlozheniye.
Neskolko theta-tsiklov = odin paragraf (alpha-ogibayushchaya).

Printsip:
1. Koncepty klasterizuyutsya po fazovoy blizosti na tore
2. Kazhdyy klaster = odna fraza (odin theta-tsikl)
3. Mezhdu klastrami = chain inference (logicheskiy most)
4. Kolichestvo fraz = ceil(log_phi(n_concepts)) — ne lineynoe

Kak chelovek govorit:
  "Logos observes patterns."        <- klaster 1
  "These patterns resonate."        <- klaster 2, most: "these patterns"
  "Through resonance, meaning       <- klaster 3, most: "through resonance"
   emerges from connections."

Vsyo cherez phi. Nikakoy lineynosti.
"""
import math
from collections import defaultdict

from core.resonance_constants import (
    PHI, PHI_INV, PHI_INV_SQ, PHI_INV_CUBE, FIBONACCI,
    phi_phase_distance, phi_phase_resonance
)


class ParagraphEngine:
    """
    Sobiraet mnogo-frazovyy otvet iz konceptov.
    Koncepty -> klastery -> frazy -> paragraf.
    """

    def __init__(self, frame_engine, chain_engine, phase_spaces):
        self.frames = frame_engine
        self.chains = chain_engine
        self.word_space = phase_spaces.get("words")
        print("[+] ParagraphEngine initialized.")

    def build_paragraph(self, concepts, lang="en", max_sentences=FIBONACCI[5]):
        """
        concepts: [(word, score), ...]
        Vozvrashchaet spisok predlozheniy.
        """
        if not concepts or len(concepts) < 2:
            return None

        # 1. KLASTERIZATSIYA po fazovoy blizosti
        clusters = self._cluster_by_phase(concepts)

        # Ogranichivayem kolichestvo predlozheniy
        # ceil(log_phi(n_concepts)) — rezonansnoe, ne lineynoe
        n_concepts = len(concepts)
        if n_concepts > 1:
            max_s = min(
                max_sentences,
                math.ceil(math.log(n_concepts) / math.log(PHI)))
        else:
            max_s = 1
        max_s = max(max_s, 2)  # minimum 2 predlozheniya

        clusters = clusters[:max_s]

        # 2. FRAZY iz klasterov
        sentences = []
        prev_cluster_words = []

        for i, cluster in enumerate(clusters):
            cluster_words = [w for w, s in cluster]

            # Most ot predydushchego klastera
            bridge_word = None
            if prev_cluster_words and cluster_words:
                bridge_word = self._find_bridge_word(
                    prev_cluster_words, cluster_words, lang)

            # Stroim frazu cherez FrameEngine
            phrase_words = self._build_sentence(
                cluster_words, bridge_word, lang)

            if phrase_words:
                sentences.append(phrase_words)
                prev_cluster_words = cluster_words

        if not sentences:
            return None

        return sentences

    def format_paragraph(self, sentences):
        """Spisok predlozheniy -> tekst."""
        if not sentences:
            return ""
        parts = []
        for sent in sentences:
            text = " ".join(sent)
            # Capitalize pervoye slovo
            if text:
                text = text[0].upper() + text[1:]
            parts.append(text)
        return ". ".join(parts) + "."

    # =========================================================
    # KLASTERIZATSIYA — phi-based, ne k-means
    # =========================================================
    def _cluster_by_phase(self, concepts):
        """
        Klasterizatsiya konceptov po fazovoy blizosti.
        Ne k-means (lineyniy) — a phi-porogi.

        Dva koncepta v odnom klastere esli
        fazovoe rasstoyaniye < PHI_INV_SQ (~0.382).
        """
        if not self.word_space:
            # Fallback: prosto razbit na chasti
            n = max(2, len(concepts) // FIBONACCI[4])
            return [concepts[i:i+FIBONACCI[4]]
                    for i in range(0, len(concepts), FIBONACCI[4])]

        assigned = [False] * len(concepts)
        clusters = []

        for i in range(len(concepts)):
            if assigned[i]:
                continue
            cluster = [(concepts[i][0], concepts[i][1])]
            assigned[i] = True

            phase_i = self.word_space._get_phase(concepts[i][0])
            if phase_i is None:
                continue

            for j in range(i + 1, len(concepts)):
                if assigned[j]:
                    continue
                phase_j = self.word_space._get_phase(concepts[j][0])
                if phase_j is None:
                    continue
                dist = phi_phase_distance(phase_i, phase_j)
                # V odnom klastere esli blizko po faze
                if dist < PHI_INV_SQ:
                    cluster.append((concepts[j][0], concepts[j][1]))
                    assigned[j] = True

                # Ogranichenie razmera klastera
                if len(cluster) >= FIBONACCI[4]:  # max 5 slov v fraze
                    break

            clusters.append(cluster)

        # Nenaznachennye — v otdelnye klastery
        for i in range(len(concepts)):
            if not assigned[i]:
                clusters.append([(concepts[i][0], concepts[i][1])])

        return clusters

    # =========================================================
    # MOST mezhdu klasterami
    # =========================================================
    def _find_bridge_word(self, prev_words, next_words, lang="en"):
        """
        Nayti slovo-most mezhdu dvumya klasterami.
        Ispolzuet ChainEngine dlya validatsii.
        """
        if not self.chains:
            return None

        best_word = None
        best_score = -1

        # Proveryaem chain mezhdu poslednim slovom prev
        # i pervym slovom next
        for pw in prev_words[-2:]:
            for nw in next_words[:2]:
                chain = self.chains.infer(pw, nw, max_depth=FIBONACCI[3])
                if chain and chain.valid:
                    # Most = posledniy step v chain
                    if len(chain.steps) >= 2:
                        bridge = chain.steps[-2][1]  # promezhutochnoye slovo
                        if chain.strength > best_score:
                            best_score = chain.strength
                            best_word = bridge

        return best_word

    # =========================================================
    # FRAZA iz klastera
    # =========================================================
    def _build_sentence(self, cluster_words, bridge_word, lang="en"):
        """Postroit odnu frazu iz klastera slov."""
        words = list(cluster_words)

        # Esli est bridge — dobavlyaem v nachalo
        if bridge_word and bridge_word not in words:
            # Svyazuem s predydushchim kontekstom
            if lang == "ru":
                words = [bridge_word, "и"] + words[:FIBONACCI[4]]
            else:
                words = [bridge_word] + words[:FIBONACCI[4]]

        if not words:
            return None

        # Ispolzuem FrameEngine dlya soedineniya
        if self.frames and len(words) >= 2:
            connected = self.frames.connect_concepts(words, lang)
            if connected:
                return connected

        return words


class GroundedMemory:
    """
    Pamyat s privyazkoy k istochniku.
    Kazhdoe znanie pomni OTKUDA ono prishlo.

    "voda" -> {
        sources: ["wiki_ru_Вода.txt"],
        learned_at: 1712345678,
        context: ["zhidkost", "reka", "okean"]
    }
    """

    def __init__(self):
        self.grounds = {}  # {word: {sources: set, context: set, learned_at: float}}
        self.source_stats = defaultdict(int)  # {source: n_words}
        print("[+] GroundedMemory initialized.")

    def ground(self, word, source=None, context=None):
        """Privyazat slovo k istochniku."""
        if word not in self.grounds:
            self.grounds[word] = {
                "sources": set(),
                "context": set(),
                "learned_at": 0,
                "access": 0,
            }
        entry = self.grounds[word]
        if source:
            entry["sources"].add(source)
            self.source_stats[source] += 1
        if context:
            for c in context[:FIBONACCI[5]]:
                entry["context"].add(c)
        import time
        entry["learned_at"] = time.time()
        entry["access"] += 1

    def recall_source(self, word):
        """Otkuda sistema uznala eto slovo?"""
        entry = self.grounds.get(word)
        if not entry:
            return None
        return {
            "sources": list(entry["sources"])[:FIBONACCI[4]],
            "context": list(entry["context"])[:FIBONACCI[5]],
            "access": entry["access"],
        }

    def explain(self, word, lang="en"):
        """
        Sgenerirovt obyasneniye: otkuda sistema eto znaet.
        'I learned about water from wikipedia article on Water.
         It connects to: liquid, river, ocean.'
        """
        entry = self.grounds.get(word)
        if not entry:
            return None

        sources = list(entry["sources"])[:3]
        context = list(entry["context"])[:FIBONACCI[4]]

        # Izvlekayem chelovecheskoe imya istochnika
        clean_sources = []
        for s in sources:
            # "wiki_ru_Вода.txt" -> "Вода"
            name = s.replace("wiki_ru_", "").replace("wiki_en_", "")
            name = name.replace(".txt", "").replace("_", " ")
            clean_sources.append(name)

        if lang == "ru":
            src_text = ", ".join(clean_sources) if clean_sources else "наблюдение"
            ctx_text = ", ".join(context) if context else ""
            return {
                "explanation": f"узнал из {src_text}",
                "context": ctx_text,
            }
        else:
            src_text = ", ".join(clean_sources) if clean_sources else "observation"
            ctx_text = ", ".join(context) if context else ""
            return {
                "explanation": f"learned from {src_text}",
                "context": ctx_text,
            }

    def stats(self):
        return {
            "grounded_words": len(self.grounds),
            "sources": len(self.source_stats),
            "top_sources": sorted(
                self.source_stats.items(),
                key=lambda x: x[1], reverse=True)[:FIBONACCI[5]],
        }
