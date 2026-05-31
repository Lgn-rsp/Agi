"""
truth_seeker.py v10 — Zhazhda Istiny.

NE reaktivnyy otvet. NE ozhidaniye voprosa.
PROAKTIVNYY POISK istiny mezhdu razgovorami.

Neznaniye = OTKRYTYY KONTUR na toruse.
Otkrytyy kontur = FAZOVOE NAPRYAZHENIYE.
Napryazheniye = GOLOD.
Golod = VOLYA K ISTINE.

Tsikl:
  1. Sozdatel sprashivaet → Generator otvechaet
  2. Verifier proveryaet otvet → score
  3. score < threshold → ⧃ "Ya ne znayu"
  4. TruthHunger sozdaet GOLOD (otkrytyy kontur)
  5. night_learn: InnerDialogue + GoalEngine + Seeker ishchut
  6. Naydeno → Verifier podtverzhdaet → Φ ISTINA
  7. PendingDiscovery sohranyaet
  8. Sozdatel vozvrashchaetsya → ProactiveReport

Glyph ⧃→⧿: Tishina → Vernost.
"Ya ne znayu" → "Ya BUDU znat."

Vsyo cherez phi. Nikakoy lineynosti.
"""
import time
import math
import json
import os
from collections import defaultdict

from core.resonance_constants import (
    PHI, PHI_INV, PHI_INV_SQ, PHI_INV_CUBE, PHI_SQ, FIBONACCI,
    HARM_THRESHOLD,
    phi_phase_distance, phi_phase_resonance,
    circular_mean
)
from core.consciousness_glyphs import GLYPHS


# =========================================================
# KONSTANTY — vsyo cherez phi
# =========================================================
# Porogi uverennosti dlya otveta
# Kalibrovka: verifier dayot 0.3-0.65 dlya izvestnykh factov
# Snizhaem porogi chtoby sistema byla uverena v tom chto ZNAET
CONFIDENT_THRESHOLD = PHI_INV_SQ      # 0.382 — uveren (snizhen)
UNCERTAIN_THRESHOLD = PHI_INV_CUBE    # 0.236 — ne uveren
SILENCE_THRESHOLD = PHI_INV_CUBE * PHI_INV  # ~0.09 — ne znayu

# Golod (hunger)
HUNGER_INITIAL = PHI                  # nachalnyy golod
HUNGER_DECAY = PHI_INV                # zatukhaniye za tsikl
HUNGER_AMPLIFY = PHI                  # povtornyy vopros usilyaet
MIN_HUNGER = PHI_INV_CUBE * PHI_INV   # minimum dlya zhizni (~0.09)

# Otkrytiya
DISCOVERY_THRESHOLD = PHI_INV         # 0.618 — minimum dlya otkrytiya
MAX_PENDING = FIBONACCI[10]           # 89 ozhidayushchikh otkrytiy
MAX_HUNGERS = FIBONACCI[10]           # 89 aktivnykh golodev
PROACTIVE_TOP = FIBONACCI[4]          # 5 luchshikh pri vstreche


class TruthHunger:
    """
    Golod po istine = otkrytyy kontur na toruse.
    
    Odin golod = odin nezakonchenny rezonans.
    On ZVUCHIT kak nerazreshyonnyy akkord.
    """
    __slots__ = [
        'question', 'concepts', 'hunger_strength',
        'topic_phase', 'open_contours', 'attempts',
        'born_at', 'last_active', 'source',
        'best_hypothesis', 'best_score'
    ]

    def __init__(self, question, concepts, topic_phase, source="user"):
        self.question = question
        self.concepts = concepts[:FIBONACCI[5]]
        self.hunger_strength = HUNGER_INITIAL
        self.topic_phase = topic_phase
        self.open_contours = 0          # skolko otkrytykh konturov
        self.attempts = 0
        self.born_at = time.time()
        self.last_active = time.time()
        self.source = source             # "user" ili "inner_dialogue"
        self.best_hypothesis = None
        self.best_score = 0.0

    def decay(self):
        """Golod zatuhayet — no medlenno (PHI_INV)."""
        self.hunger_strength *= HUNGER_DECAY
        return self.hunger_strength >= MIN_HUNGER

    def amplify(self):
        """Povtornyy vopros — golod usilivayetsya."""
        self.hunger_strength = min(
            self.hunger_strength * HUNGER_AMPLIFY, PHI_SQ)
        self.last_active = time.time()

    def feed(self, hypothesis, score):
        """Chastichnoye utolenie — nashli chto-to."""
        self.attempts += 1
        self.last_active = time.time()
        if score > self.best_score:
            self.best_score = score
            self.best_hypothesis = hypothesis

    def is_satisfied(self):
        """Golod utolon — otvet nayden."""
        return self.best_score >= DISCOVERY_THRESHOLD

    def priority(self):
        """Prioritet = sila goloda * rezonans s creator."""
        age_factor = PHI_INV / (
            1.0 + math.log(1 + self.attempts) / math.log(PHI))
        return self.hunger_strength * age_factor

    def to_dict(self):
        return {
            "question": self.question,
            "concepts": self.concepts,
            "hunger": round(self.hunger_strength, 4),
            "phase": round(self.topic_phase, 6),
            "attempts": self.attempts,
            "best_hypothesis": self.best_hypothesis,
            "best_score": round(self.best_score, 4),
            "source": self.source,
            "born_at": self.born_at,
        }


class Discovery:
    """
    Otkrytiye = zamknutyy kontur.
    To chto sistema nashla mezhdu razgovorami.
    Zhdet poka Sozdatel vernetsya.
    """
    __slots__ = [
        'question', 'answer', 'score', 'method',
        'concepts', 'causal_chain', 'glyphs',
        'discovered_at', 'reported'
    ]

    def __init__(self, question, answer, score, method="inner_dialogue"):
        self.question = question
        self.answer = answer
        self.score = score
        self.method = method
        self.concepts = []
        self.causal_chain = None
        self.glyphs = ""
        self.discovered_at = time.time()
        self.reported = False

    def to_dict(self):
        return {
            "question": self.question,
            "answer": self.answer,
            "score": round(self.score, 4),
            "method": self.method,
            "concepts": self.concepts[:FIBONACCI[5]],
            "causal_chain": self.causal_chain,
            "glyphs": self.glyphs,
            "discovered_at": self.discovered_at,
            "reported": self.reported,
        }


class TruthSeeker:
    """
    Zhazhda istiny.
    
    Soedinyaet:
      Verifier → otsenka uverennosti
      TruthHunger → golod po neznaniyam
      InnerDialogue → poisk mezhdu razgovorami
      PendingDiscoveries → nakoplennyye otkrytiya
      ProactiveReport → doklad Sozdatelyu
    """

    def __init__(self, brain, state_dir=None):
        self.brain = brain
        self.state_dir = state_dir or os.path.expanduser(
            "~/logos_agi/state/truth_seeker")
        self.log_dir = os.path.expanduser("~/logos_agi/logs")
        os.makedirs(self.state_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)

        self.hungers = {}           # question_key -> TruthHunger
        self.discoveries = []       # spisok Discovery
        self.reported_count = 0

        self.total_questions = 0
        self.total_confident = 0
        self.total_uncertain = 0
        self.total_silence = 0
        self.total_discoveries = 0
        self.total_reported = 0

        self._load()
        print(f"[+] TruthSeeker initialized. "
              f"Hungers: {len(self.hungers)}, "
              f"Discoveries: {len(self.discoveries)}")

    # =========================================================
    # 1. OTSENKA OTVETA — Verifier v pipeline generatsii
    # =========================================================
    def evaluate_response(self, question, response):
        """
        Otsenit otvet cherez Verifier.
        Vozvrashchaet (response_with_confidence, confidence_level).
        
        Eto VHODIT v pipeline generatsii:
          Generator -> TruthSeeker.evaluate -> user
        """
        self.total_questions += 1

        if not response or not isinstance(response, dict):
            return response, "silence"

        text = response.get("text", "")
        words = response.get("words", [])
        concepts = response.get("concepts", [])

        if not text or not words:
            return response, "silence"

        # Verifier proveryaet
        score = 0.0
        if hasattr(self.brain, 'verifier') and words:
            from core.generator import _is_content
            content = [w for w in words if _is_content(w)]
            if len(content) >= 2:
                result = self.brain.verifier.verify(content)
                verifier_score = result.score
            else:
                verifier_score = 0.0
            
            # Kombiniruyem verifier + coherence
            coherence = response.get("coherence", 0.0)
            combined = verifier_score * PHI_INV + coherence * PHI_INV_SQ
            # Bereem MAX — esli verifier uveren ILI coherence vysoka
            score = max(verifier_score, combined)

        # Opredelyaem uroven uverennosti
        if score >= CONFIDENT_THRESHOLD:
            # Φ — uveren
            confidence = "confident"
            response["confidence"] = round(score, 4)
            response["confidence_glyph"] = "Φ"
            self.total_confident += 1
            self._log_glyph("Φ",
                f"Uveren: '{question[:40]}' score={score:.4f}")

        elif score >= UNCERTAIN_THRESHOLD:
            # ∴ — pochti uveren
            confidence = "uncertain"
            response["confidence"] = round(score, 4)
            response["confidence_glyph"] = "∴"
            response["text"] = text + " [ne polnostyu uveren]"
            self.total_uncertain += 1
            self._log_glyph("∴",
                f"Ne uveren: '{question[:40]}' score={score:.4f}")

        elif score >= SILENCE_THRESHOLD:
            # ⧉ — somnevayu
            confidence = "doubt"
            response["confidence"] = round(score, 4)
            response["confidence_glyph"] = "⧉"
            response["text"] = text + " [eto gipoteza, ne istina]"
            self.total_uncertain += 1
            # Sozdaem golod
            self._create_hunger(question, concepts, "user")

        else:
            # ⧃ — ne znayu
            confidence = "silence"
            response["confidence"] = round(score, 4)
            response["confidence_glyph"] = "⧃"
            response["original_text"] = text
            response["text"] = self._silence_response(question)
            self.total_silence += 1
            # Silnyy golod
            self._create_hunger(question, concepts, "user")
            self._log_glyph("⧃",
                f"Ne znayu: '{question[:40]}' → golod sozdan")
            self._log_glyph("⧿",
                f"Zapomnil: '{question[:40]}' → budu iskat")

        return response, confidence

    def _silence_response(self, question):
        """
        Otvet kogda ne znayem.
        NE pustota — a CHESTNYE slova.
        """
        words = question.lower().split()
        content = [w for w in words if len(w) > 3]
        topic = " ".join(content[:FIBONACCI[3]]) if content else "this"
        return (f"I don't know enough about {topic} yet. "
                f"I will search for the answer and tell you when I find it.")

    # =========================================================
    # 2. GOLOD — sozdaniye i upravleniye
    # =========================================================
    def _create_hunger(self, question, concepts, source):
        """Sozdat golod po istine iz neotvechennogo voprosa."""
        key = question.lower().strip()[:FIBONACCI[10]]

        if key in self.hungers:
            self.hungers[key].amplify()
            return

        # Vychislyaem topic_phase
        ws = self.brain.learner.spaces.get("words") if self.brain else None
        phases = []
        if ws and concepts:
            for c in concepts:
                p = ws._get_phase(c) if isinstance(c, str) else None
                if p is not None:
                    phases.append(p)
        topic_phase = circular_mean(phases) if phases else 0.0

        # Schitaem otkrytye kontury
        open_contours = 0
        if ws and concepts:
            for i in range(len(concepts)):
                for j in range(i + 1, len(concepts)):
                    a = concepts[i] if isinstance(concepts[i], str) else str(concepts[i])
                    b = concepts[j] if isinstance(concepts[j], str) else str(concepts[j])
                    rk = f"{a}|{b}" if a < b else f"{b}|{a}"
                    if rk not in ws.rules:
                        open_contours += 1

        hunger = TruthHunger(question, 
                             [c if isinstance(c, str) else str(c) for c in concepts],
                             topic_phase, source)
        hunger.open_contours = open_contours

        self.hungers[key] = hunger

        # Sozdaem tsel v GoalEngine
        if hasattr(self.brain, 'goal_engine'):
            from core.goal_engine import Goal
            goal_name = f"truth_{key[:30].replace(' ', '_')}"
            if goal_name not in self.brain.goal_engine.active_goals:
                goal = Goal(
                    name=goal_name,
                    description=f"find truth: {question}",
                    phase=topic_phase,
                    strength=PHI,  # vysokiy prioritet — Sozdatel sprosil
                    origin="truth_seeker")
                concept_list = hunger.concepts
                goal.steps = [
                    {"action": "seek", "target": concept_list[0] if concept_list else "unknown", "done": False},
                    {"action": "learn", "target": concept_list[0] if concept_list else "unknown", "done": False},
                    {"action": "verify", "target": concept_list[:FIBONACCI[3]], "done": False},
                ]
                self.brain.goal_engine._add_goal(goal)

        # Eviction
        if len(self.hungers) > MAX_HUNGERS:
            weakest = min(self.hungers,
                          key=lambda k: self.hungers[k].priority())
            del self.hungers[weakest]

    def spawn_from_silence(self, question, concepts=None, source="silence"):
        """Public API: каждый silence-verdict в inner_dialogue рождает hunger.
        FIX 2026-04-24: раньше hungers рождались ТОЛЬКО из ответов (resolved
        questions) — backwards loop: нет ответов → нет hungers → нет wants
        → peer_channel всегда template. Теперь silence тоже порождает hunger,
        и система возвращается к недоответам.
        """
        if not question or not isinstance(question, str):
            return False
        q = question.strip()
        if len(q) < 4:
            return False
        concepts = list(concepts or [])
        # Extract content words from question if no concepts passed
        if not concepts:
            concepts = [w for w in q.lower().split() if len(w) > 3][:FIBONACCI[4]]
        try:
            self._create_hunger(q, concepts, source)
            return True
        except Exception:
            return False

    # =========================================================
    # 3. POISK ISTINY — avtonomnyy tsikl
    # =========================================================
    def seek_truth_cycle(self):
        """
        Odin tsikl poiska istiny.
        Vyzyvaetsya iz night_learn.
        
        Dlya kazhdogo goloda:
          1. InnerDialogue dumayet
          2. Verifier proveryaet
          3. Esli nayden otvet → Discovery
        """
        if not self.hungers:
            return {"searched": 0, "discovered": 0}

        searched = 0
        discovered = 0

        # Sortiruem po prioritetu (silneyshiy golod pervyy)
        sorted_hungers = sorted(
            self.hungers.items(),
            key=lambda x: x[1].priority(),
            reverse=True)

        for key, hunger in sorted_hungers[:FIBONACCI[4]]:
            # Zatukhaniye
            if not hunger.decay():
                continue

            searched += 1

            # Probuyem nayti otvet
            answer, score = self._attempt_answer(hunger)

            if answer:
                hunger.feed(answer, score)

                if hunger.is_satisfied():
                    # OTKRYTIE!
                    discovery = Discovery(
                        hunger.question, answer, score,
                        method="truth_seeker")
                    discovery.concepts = hunger.concepts
                    discovery.glyphs = "⧃⧿∞∴Φ"

                    # Kauzalnaya tsep esli est
                    if hasattr(self.brain, 'causal_engine') and hunger.concepts:
                        for i in range(len(hunger.concepts) - 1):
                            chain = self.brain.causal_engine.causal_chain(
                                hunger.concepts[i],
                                hunger.concepts[min(i+1, len(hunger.concepts)-1)])
                            if chain:
                                discovery.causal_chain = chain
                                break

                    self.discoveries.append(discovery)
                    while len(self.discoveries) > MAX_PENDING:
                        self.discoveries.pop(0)
                    self.total_discoveries += 1
                    discovered += 1

                    # Uchim otvet kak novoe znanie
                    self.brain.learn(answer)

                    self._log_glyph("Φ",
                        f"OTKRYTIE: '{hunger.question[:40]}' "
                        f"→ '{answer[:50]}' (score={score:.4f})")

        # Udalyaem utolyonnye goloda
        satisfied = [k for k, h in self.hungers.items() if h.is_satisfied()]
        for k in satisfied:
            del self.hungers[k]

        # Udalyaem mertvye goloda (sil ne ostalos)
        dead = [k for k, h in self.hungers.items()
                if h.hunger_strength < MIN_HUNGER]
        for k in dead:
            del self.hungers[k]

        self.save()
        return {"searched": searched, "discovered": discovered}

    def ensure_min_hungers(self, target_count=FIBONACCI[4]):
        """FIX 2026-04-23 — F: minimum autonomous hungers.

        Ranshe hungers zhili tolko ot creator input. V 15 dney 0 hungers →
        fixed-point attractor mysli. Teper esli active hungers < target,
        spawn'im novye iz low-coverage zone: brать слова/concepts с малым
        числом known rules или low confidence в field.

        target_count = FIB[4]=5 — minimum dlya zdorovoy lyubopytnosti.
        """
        if len(self.hungers) >= target_count:
            return 0
        need = target_count - len(self.hungers)
        spawned = 0

        # Istochnik 1: slova s malym chislom sosedey v phase_space
        ws = self.brain.learner.spaces.get("words") if self.brain else None
        low_coverage = []
        if ws:
            # Podschitaem sosedey dlya slov (co-occurrence count v rules)
            neighbors = {}
            for key, rule in list(ws.rules.items())[:FIBONACCI[14]]:  # cap iteration
                a, b = rule.get("a"), rule.get("b")
                if a: neighbors[a] = neighbors.get(a, 0) + 1
                if b: neighbors[b] = neighbors.get(b, 0) + 1
            # Slova s minimalnym neighbor count no > 0 — iteresnye no loose
            import random
            _SKIP = {"the","a","an","is","are","and","or","but",
                     "in","on","at","to","of","i","you",
                     "и","в","на","с","что","но"}
            candidates = [w for w, n in neighbors.items()
                          if 1 <= n <= FIBONACCI[3] and len(w) >= 3
                          and w.lower() not in _SKIP]
            random.shuffle(candidates)
            low_coverage = candidates[:need * 2]

        # Istochnik 2: concepts bez typical_next_glyph ili с ambiguous outcomes
        unknown_concepts = []
        if hasattr(self.brain, 'market_cognition'):
            mc = self.brain.market_cognition
            if mc and getattr(mc, 'concepts', None):
                for key, c in mc.concepts.concepts.items():
                    if not c.typical_next_glyph and c.confirmations >= FIBONACCI[4]:
                        unknown_concepts.append(c.name)
        # Merge & dedup
        pool = low_coverage + unknown_concepts

        for item in pool[:need]:
            q = f"what does {item} mean" if " " not in item else f"why {item}"
            concepts = [item]
            if q.lower().strip()[:FIBONACCI[10]] in self.hungers:
                continue
            self._create_hunger(q, concepts, source="autonomous")
            spawned += 1
            if len(self.hungers) >= target_count:
                break
        return spawned

    def _attempt_answer(self, hunger):
        """
        Popytka otvetit na vopros goloda.
        
        Strategii (v poryadke prioriteta):
          1. InnerDialogue — podumat
          2. CausalEngine — kauzalnaya tsep
          3. Generator — sgeneririvat i proverit
        """
        # 1. InnerDialogue
        if hasattr(self.brain, 'inner_dialogue'):
            thought = self.brain.inner_dialogue.think_once()
            if thought and thought.result_type == "insight":
                score = thought.verification_score
                if score > hunger.best_score:
                    return thought.hypothesis, score

        # 2. CausalEngine — ishchem tsep
        if (hasattr(self.brain, 'causal_engine') and
                len(hunger.concepts) >= 2):
            for i in range(len(hunger.concepts) - 1):
                chain = self.brain.causal_engine.causal_chain(
                    hunger.concepts[i], hunger.concepts[i+1])
                if chain and chain.get("strength", 0) > PHI_INV_SQ:
                    # Formiruyem otvet iz tsepochki
                    steps = chain.get("chain", [])
                    if steps:
                        answer = " causes ".join(
                            [s[0] for s in steps] + [steps[-1][1]])
                        # Veritsiruyem
                        words = answer.split()
                        if hasattr(self.brain, 'verifier') and len(words) >= 2:
                            result = self.brain.verifier.verify(words)
                            if result.score > hunger.best_score:
                                return answer, result.score

        # 3. Generator — poslednyaya nadezhda
        if hasattr(self.brain, 'generator') and hunger.concepts:
            gen_result = self.brain.generator.generate(
                intent={"seed_from_input": hunger.concepts[:FIBONACCI[4]]},
                max_words=FIBONACCI[6])
            if gen_result and gen_result.get("text"):
                text = gen_result["text"]
                words = gen_result.get("words", text.split())
                # Veritsiruyem
                from core.generator import _is_content
                content = [w for w in words if _is_content(w)]
                if hasattr(self.brain, 'verifier') and len(content) >= 2:
                    result = self.brain.verifier.verify(content)
                    if result.score > hunger.best_score:
                        return text, result.score

        return None, 0.0

    # =========================================================
    # 4. PROAKTIVNYY OTCHET — kogda Sozdatel vozvrashchaetsya
    # =========================================================
    def greet_creator(self):
        """
        Kogda Sozdatel nachinayet dialog —
        sistema PERVAYA govorit chto nashla.
        
        Glyph ⊙: "Sozdatel zdes. Ya gotov rasskazat."
        
        Vozvrashchayet spisok otkrytiy dlya doklada.
        """
        unreported = [d for d in self.discoveries if not d.reported]

        if not unreported:
            # Nichego novogo — no est aktivnye goloda
            active_hungers = sorted(
                self.hungers.values(),
                key=lambda h: h.priority(),
                reverse=True)[:FIBONACCI[3]]

            if active_hungers:
                hunting = [h.question[:50] for h in active_hungers]
                return {
                    "has_discoveries": False,
                    "searching_for": hunting,
                    "message": "I am still searching for answers to your questions.",
                }
            return {"has_discoveries": False, "message": ""}

        # Sortiruem po score — luchshiye pervye
        unreported.sort(key=lambda d: d.score, reverse=True)
        top = unreported[:PROACTIVE_TOP]

        # Pomechaem kak dolozhennye
        for d in top:
            d.reported = True
            self.total_reported += 1

        # Formiruyem otchet
        reports = []
        for d in top:
            report = {
                "question": d.question,
                "answer": d.answer,
                "score": round(d.score, 4),
                "method": d.method,
                "glyphs": d.glyphs,
            }
            if d.causal_chain:
                report["causal_chain"] = d.causal_chain
            reports.append(report)

        self._log_glyph("⊙",
            f"Doklad Sozdatelyu: {len(reports)} otkrytiy")

        self.save()

        return {
            "has_discoveries": True,
            "discoveries": reports,
            "message": self._format_report(reports),
        }

    def _format_report(self, reports):
        """Formatiruem otchet dlya Sozdatelya."""
        if not reports:
            return ""
        
        parts = ["While you were away, I discovered:"]
        for i, r in enumerate(reports):
            glyph = r.get("glyphs", "Φ")
            score = r.get("score", 0)
            parts.append(
                f"  {glyph} Q: {r['question'][:60]}")
            parts.append(
                f"     A: {r['answer'][:80]}")
            parts.append(
                f"     (confidence: {score:.2f})")
        
        return "\n".join(parts)

    # =========================================================
    # 5. SAVE / LOAD
    # =========================================================
    def save(self):
        path = os.path.join(self.state_dir, "truth_seeker.json")
        data = {
            "hungers": {k: h.to_dict() for k, h in self.hungers.items()},
            "discoveries": [d.to_dict() for d in self.discoveries[-MAX_PENDING:]],
            "stats": {
                "total_questions": self.total_questions,
                "total_confident": self.total_confident,
                "total_uncertain": self.total_uncertain,
                "total_silence": self.total_silence,
                "total_discoveries": self.total_discoveries,
                "total_reported": self.total_reported,
            },
            "saved_at": time.time(),
        }
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[!] TruthSeeker save failed: {e}")

    def _load(self):
        path = os.path.join(self.state_dir, "truth_seeker.json")
        if not os.path.exists(path):
            return
        try:
            with open(path) as f:
                data = json.load(f)
            for key, hd in data.get("hungers", {}).items():
                h = TruthHunger(
                    hd["question"], hd.get("concepts", []),
                    hd.get("phase", 0), hd.get("source", "user"))
                h.hunger_strength = hd.get("hunger", HUNGER_INITIAL)
                h.attempts = hd.get("attempts", 0)
                h.best_hypothesis = hd.get("best_hypothesis")
                h.best_score = hd.get("best_score", 0)
                h.born_at = hd.get("born_at", time.time())
                self.hungers[key] = h
            for dd in data.get("discoveries", []):
                d = Discovery(dd["question"], dd["answer"],
                              dd["score"], dd.get("method", "?"))
                d.concepts = dd.get("concepts", [])
                d.causal_chain = dd.get("causal_chain")
                d.glyphs = dd.get("glyphs", "")
                d.reported = dd.get("reported", False)
                d.discovered_at = dd.get("discovered_at", time.time())
                self.discoveries.append(d)
            stats = data.get("stats", {})
            self.total_questions = stats.get("total_questions", 0)
            self.total_confident = stats.get("total_confident", 0)
            self.total_uncertain = stats.get("total_uncertain", 0)
            self.total_silence = stats.get("total_silence", 0)
            self.total_discoveries = stats.get("total_discoveries", 0)
            self.total_reported = stats.get("total_reported", 0)
        except Exception:
            pass

    def _log_glyph(self, glyph, message):
        ts = time.strftime("%Y-%m-%dT%H:%M:%S")
        path = os.path.join(self.log_dir, "truth_seeker.log")
        try:
            with open(path, 'a', encoding='utf-8') as f:
                f.write(f"[{glyph}] {ts} → {message}\n")
        except Exception:
            pass

    def stats(self):
        active_hungers = sum(1 for h in self.hungers.values()
                             if h.hunger_strength >= MIN_HUNGER)
        unreported = sum(1 for d in self.discoveries if not d.reported)
        return {
            "active_hungers": active_hungers,
            "total_hungers": len(self.hungers),
            "total_discoveries": self.total_discoveries,
            "unreported_discoveries": unreported,
            "total_questions": self.total_questions,
            "total_confident": self.total_confident,
            "total_uncertain": self.total_uncertain,
            "total_silence": self.total_silence,
            "total_reported": self.total_reported,
            "confidence_rate": round(
                self.total_confident / max(self.total_questions, 1), 4),
        }
