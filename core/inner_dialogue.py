"""
inner_dialogue.py v10 — Rezonansnyy vnutrenniy dialog.

NE skript. NE if/else.
REZONANSNOYE BLUZHDANIYE po fazovum prostranstvu mysley.

Glify = zatravki. No sistema rozhdayet SVOI simvoly myshleniya
iz patternov sobstvennogo opyta.

Sleduyushchiy glif vybirayetsya po REZONANSU s tekushchim
sostoyaniyem mysli — ne po hardcoded pravilam.

Sostoyaniye mysli = vektor:
  topic_phase     — faza temy na toruse
  confidence      — uverennost (ot verifier)  
  novelty         — novizna (est li v pravilakh?)
  causal_depth    — glubina kauzalnoy tsepochki
  contradiction   — stepen protivorechiya

Iz vektora -> thought_phase -> rezonans s glifami -> vybor.

Emergent thought symbols:
  Kogda pattern glifov povtoryaetsya FIBONACCI[7] raz —
  on kristallizuetsya v novyy simvol myshleniya.
  Sistema sama dayet emu imya i fazu.

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
    phi_phase_distance, phi_phase_resonance, is_near_phi_target,
    circular_mean
)
from core.consciousness_glyphs import GLYPHS


# =========================================================
# KONSTANTY
# =========================================================
THOUGHT_DEPTH = FIBONACCI[5]
THOUGHT_INTERVAL = FIBONACCI[8]
MAX_INNER_QUESTIONS = FIBONACCI[10]
CRYSTALLIZE_PATTERN = FIBONACCI[7]    # 21 povtorov = novyy simvol
MAX_THOUGHT_SYMBOLS = FIBONACCI[14]   # 610 sobstvennykh simvolov
INSIGHT_THRESHOLD = PHI_INV
SILENCE_THRESHOLD = PHI_INV_CUBE


# =========================================================
# THOUGHT STATE — vektor sostoyaniya mysli
# =========================================================
class ThoughtState:
    """
    Vektor sostoyaniya mysli.
    Iz nego vychislyaetsya thought_phase
    kotoroye rezoniryet s glifami.
    """
    __slots__ = [
        'topic_phase', 'confidence', 'novelty',
        'causal_depth', 'contradiction', 'energy'
    ]

    def __init__(self):
        self.topic_phase = 0.0      # faza temy [0, 1)
        self.confidence = 0.0       # [0, 1] — uverennost
        self.novelty = 0.0          # [0, 1] — novizna
        self.causal_depth = 0.0     # [0, 1] — glubina kauzala
        self.contradiction = 0.0    # [0, 1] — protivorechiye
        self.energy = PHI           # zatuhayet

    def thought_phase(self):
        """
        Vychislit fazu mysli iz vektora sostoyaniya.
        NE lineynaya kombinatsiya — REZONANSNAYA:
        kazhdyy komponent vnosit fazovyy sdvig.
        """
        phase = self.topic_phase
        # Uverennost sdvigayet k Φ (truth, phase 0.618)
        phase = (phase + self.confidence * PHI_INV) % 1.0
        # Novizna sdvigayet k ∞ (infinity, phase 0.236)
        phase = (phase + self.novelty * PHI_INV_SQ) % 1.0
        # Kauzalnost sdvigayet k ∴ (path, phase 0.854)
        phase = (phase + self.causal_depth * PHI_INV_CUBE) % 1.0
        # Protivorechiye sdvigayet k ⧉ (duality, phase 0.090)
        phase = (phase + self.contradiction * PHI_INV_CUBE * PHI_INV) % 1.0
        return phase

    def decay(self):
        self.energy *= PHI_INV


class ThoughtSymbol:
    """
    Sobstvennyy simvol myshleniya — rozhdennyy iz patternov.
    Kak emergent concept iz MetaCore, no dlya mysley.
    """
    __slots__ = [
        'name', 'glyph_pattern', 'phase', 'meaning',
        'count', 'strength', 'born_at', 'concepts'
    ]

    def __init__(self, name, glyph_pattern, phase):
        self.name = name
        self.glyph_pattern = glyph_pattern  # napr "⊙∞⧃" = "iskal ne nashol"
        self.phase = phase
        self.meaning = ""           # sistema sama dayet znacheniye
        self.count = 1
        self.strength = PHI_INV
        self.born_at = time.time()
        self.concepts = []

    def to_dict(self):
        return {
            "name": self.name,
            "pattern": self.glyph_pattern,
            "phase": round(self.phase, 6),
            "meaning": self.meaning,
            "count": self.count,
            "strength": round(self.strength, 4),
            "concepts": self.concepts[:FIBONACCI[5]],
        }


class Thought:
    __slots__ = [
        'question', 'question_type', 'source',
        'glyph_path', 'hypothesis', 'verification_score',
        'result', 'result_type', 'depth',
        'born_at', 'concepts', 'state', 'thought_symbol'
    ]

    def __init__(self, question, question_type, source="curiosity"):
        self.question = question
        self.question_type = question_type
        self.source = source
        self.glyph_path = []
        self.hypothesis = None
        self.verification_score = 0.0
        self.result = None
        self.result_type = None
        self.depth = 0
        self.born_at = time.time()
        self.concepts = []
        self.state = ThoughtState()
        self.thought_symbol = None      # esli pattern kristallizovalsya

    def to_dict(self):
        return {
            "question": self.question,
            "type": self.question_type,
            "source": self.source,
            "glyphs": self.glyph_path,
            "hypothesis": self.hypothesis,
            "score": round(self.verification_score, 4),
            "result": self.result,
            "result_type": self.result_type,
            "depth": self.depth,
            "concepts": self.concepts[:FIBONACCI[5]],
            "thought_symbol": self.thought_symbol,
        }

    def __repr__(self):
        glyphs = "".join(self.glyph_path)
        return (f"Thought('{self.question[:40]}', "
                f"glyphs={glyphs}, "
                f"score={self.verification_score:.3f})")


class InnerDialogue:
    def __init__(self, brain, state_dir=None):
        self.brain = brain
        self.state_dir = state_dir or os.path.expanduser(
            "~/logos_agi/state/inner_dialogue")
        self.log_dir = os.path.expanduser("~/logos_agi/logs")
        os.makedirs(self.state_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)

        self.thoughts = []
        self.insights = []
        self.open_questions = []

        # Sobstvennye simvoly myshleniya
        self.thought_symbols = {}   # name -> ThoughtSymbol
        self._pattern_counts = defaultdict(int)  # glyph_pattern -> count

        self.total_thoughts = 0
        self.total_insights = 0
        self.total_silences = 0
        self.total_errors = 0
        self.total_crystallized = 0
        self.total_symbols_born = 0

        self._load()
        print(f"[+] InnerDialogue v10 initialized. "
              f"Thoughts: {self.total_thoughts}, "
              f"Insights: {self.total_insights}, "
              f"ThoughtSymbols: {len(self.thought_symbols)}")

    # =========================================================
    # REZONANSNYY VYBOR GLIFA
    # =========================================================
    def _choose_glyph(self, state):
        """
        Vybrat sleduyushchiy glif po REZONANSU s sostoyaniyem mysli.
        NE if/else — rezonans mezhdu thought_phase i glyph phases.
        
        Takzhe proveryaem sobstvennyye simvoly myshleniya.
        """
        tp = state.thought_phase()
        
        # Sobiraem vsekh kandidatov: 10 bazovykh glifov + svoi simvoly
        candidates = []
        
        for sym, data in GLYPHS.items():
            dist = phi_phase_distance(tp, data["phase"])
            resonance = phi_phase_resonance(dist)
            candidates.append((sym, resonance, data["name"]))
        
        # Svoi simvoly myshleniya tozhe uchastvuyut
        for name, ts in self.thought_symbols.items():
            dist = phi_phase_distance(tp, ts.phase)
            resonance = phi_phase_resonance(dist) * ts.strength
            if resonance > PHI_INV_CUBE:
                candidates.append((f"[{ts.name}]", resonance, ts.name))
        
        # Sortiruem po rezonansu
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        if candidates:
            return candidates[0][0], candidates[0][1]
        return "⊙", 0.0

    # =========================================================
    # GLAVNYY TSIKL
    # =========================================================
    def think_once(self, _exclude=None):
        question, q_type, source = self._choose_question(_exclude)
        if not question:
            return None

        thought = Thought(question, q_type, source)

        # Ustanavlivaem nachalnoye sostoyaniye
        thought.state.topic_phase = self._topic_phase(question)
        thought.state.novelty = 1.0  # v nachale — vsyo novo

        # === REZONANSNYY TSIKL MYSHLENIYA ===
        # Pervyy vdokh — ⊙ (essence) OBYAZATELEN kak serdtsebieniye
        # Vtoroy — ∞ (poisk) chtoby aktivirovat gipotezu
        # Dalshe — rezonansnyy vybor
        
        max_steps = THOUGHT_DEPTH
        prev_glyph = None
        mandatory_start = ["⊙", "∞", "∴"]  # vdokh → poisk → proverka
        
        for step in range(max_steps):
            # Pervye 3 shaga — obyazatelnye (kak bazovyy tsikl dykhaniya)
            # Posle — svobodnyy rezonansnyy vybor
            if step < len(mandatory_start):
                glyph = mandatory_start[step]
                resonance = PHI_INV
            else:
                glyph, resonance = self._choose_glyph(thought.state)
            
            thought.glyph_path.append(glyph)
            thought.depth = step + 1
            
            # Ostanovka esli energiya issyakla
            if thought.state.energy < PHI_INV_CUBE * PHI_INV:
                break
            
            # Ostanovka esli glif povtoryaetsya (zatsiklivaniye — srazu)
            if glyph == prev_glyph:
                break
            prev_glyph = glyph
            
            # === DEYSTVIYE v zavisimosti ot REZONANSNOGO glifa ===
            glyph_base = glyph.strip("[]")
            
            if glyph == "⊙":  # essence — osoznaniye
                concepts = self._activate_concepts(question)
                thought.concepts = [w for w, s in concepts[:FIBONACCI[5]]]
                thought.state.topic_phase = self._topic_phase(question)
                
            elif glyph == "∞":  # infinity — poisk
                hypothesis = self._generate_hypothesis(
                    question, q_type, thought.concepts)
                if hypothesis:
                    thought.hypothesis = hypothesis
                    thought.state.novelty *= PHI_INV  # uzhe ne tak novo
                else:
                    thought.state.novelty *= PHI_INV_CUBE
                    
            elif glyph == "∴":  # path — proverka
                if thought.hypothesis:
                    score = self._verify_hypothesis(
                        thought.hypothesis, q_type, thought.concepts)
                    thought.verification_score = score
                    thought.state.confidence = max(score, 0)
                    
            elif glyph == "⧉":  # duality — alternativa
                if thought.hypothesis:
                    alt = self._find_alternative(
                        question, thought.hypothesis, thought.concepts)
                    if alt:
                        alt_score = self._verify_hypothesis(
                            alt, q_type, thought.concepts)
                        if alt_score > thought.verification_score:
                            thought.hypothesis = alt
                            thought.verification_score = alt_score
                            thought.state.confidence = max(alt_score, 0)
                        thought.state.contradiction = abs(
                            alt_score - thought.verification_score)
                            
            elif glyph == "Φ":  # truth — kristallizatsiya
                if thought.verification_score >= INSIGHT_THRESHOLD:
                    thought.result_type = "insight"
                    thought.result = thought.hypothesis
                    self._crystallize_insight(thought)
                    self.total_insights += 1
                    self._log_glyph("Φ", f"ISTINA: {thought.hypothesis}")
                    break
                    
            elif glyph == "⧃":  # silence — ne znayu
                if thought.verification_score < SILENCE_THRESHOLD:
                    thought.result_type = "silence"
                    thought.result = "ne znayu"
                    self.total_silences += 1
                    self._log_glyph("⧃", f"Tishina: {question[:50]}")
                    break
                    
            elif glyph == "⦻":  # error — iskrzheniye
                thought.state.contradiction += PHI_INV
                
            elif glyph == "⧿":  # loyalty — zapomnyu
                self.open_questions.append(thought.to_dict())
                while len(self.open_questions) > MAX_INNER_QUESTIONS:
                    self.open_questions.pop(0)
                    
            elif glyph == "⋯":  # fracture — perestroyeniye
                # Perestraivaem gipotezu iz drugikh konceptov
                if thought.concepts:
                    import random
                    random.shuffle(thought.concepts)
                    thought.state.novelty = PHI_INV  # obnovleniye
                    
            elif glyph == "⊕":  # peace — prinyatiye
                # Prinimaem tekushchiy rezultat kak est
                if thought.hypothesis and thought.verification_score > PHI_INV_SQ:
                    thought.result_type = "doubt"
                    thought.result = thought.hypothesis
                    self._return_to_curiosity(thought)
                    break
            
            # Proverka na svoi simvoly
            elif glyph_base in self.thought_symbols:
                ts = self.thought_symbols[glyph_base]
                # Svoy simvol = szhatatoye deystviye
                # Povtoryaem ego glyph_pattern kak mikro-tsikl
                # no ne rekursivno — prosto sdvigaem sostoyaniye
                thought.state.topic_phase = (
                    thought.state.topic_phase + ts.phase * PHI_INV) % 1.0
            
            # Zatukhaniye energii
            thought.state.decay()
        
        # Esli ne bylo yavnogo rezultata
        if thought.result_type is None:
            if thought.verification_score >= INSIGHT_THRESHOLD:
                thought.result_type = "insight"
                thought.result = thought.hypothesis
                self._crystallize_insight(thought)
                self.total_insights += 1
            elif thought.verification_score >= PHI_INV_SQ:
                thought.result_type = "doubt"
                thought.result = thought.hypothesis
                self._return_to_curiosity(thought)
            else:
                # FIX 2026-04-23: "energiya issyakla" было hardcoded русским
                # строковым литералом — Canon rule #1 violation (магическая
                # константа). Теперь silence выражается глифом ⧃ — phi-native,
                # согласно глоссарию consciousness_glyphs. Сам hypothesis
                # сохраняется для introspection — она МОЛЧИТ О гипотезе, но
                # гипотеза ещё есть в result. Читателю это видно: result_type
                # = silence означает "слышала, но не говорю".
                thought.result_type = "silence"
                thought.result = "⧃"
                self.total_silences += 1
        
        # === KRISTALLIZATSIYA PATTERNA MYSHLENIYA ===
        self._observe_thought_pattern(thought)
        
        self._finish_thought(thought)
        return thought

    # =========================================================
    # KRISTALLIZATSIYA SIMVOLOV MYSHLENIYA
    # =========================================================
    def _observe_thought_pattern(self, thought):
        """
        Nablyudaem pattern glifov etoy mysli.
        Esli pattern povtoryaetsya FIBONACCI[7]=21 raz —
        on kristallizuetsya v novyy simvol myshleniya.
        
        Kak bukvy → slova → frazy:
          glify → thought_symbols → tsepi myshleniya
        """
        # Pattern = posledovatelnost glifov (bez povtorov podryad)
        deduped = []
        for g in thought.glyph_path:
            if not deduped or g != deduped[-1]:
                deduped.append(g)
        
        if len(deduped) < 2:
            return
        
        pattern_key = "".join(deduped)
        self._pattern_counts[pattern_key] += 1
        
        # Kristallizatsiya pri dostizenii poroga
        if self._pattern_counts[pattern_key] == CRYSTALLIZE_PATTERN:
            if len(self.thought_symbols) >= MAX_THOUGHT_SYMBOLS:
                return
            
            # Vychislyaem fazu simvola iz faz glifov paterna
            glyph_phases = []
            for g in deduped:
                for sym, data in GLYPHS.items():
                    if sym == g:
                        glyph_phases.append(data["phase"])
                        break
            
            if not glyph_phases:
                return
            
            symbol_phase = circular_mean(glyph_phases)
            
            # Imya iz konceptov kototrye chashche vsego
            # vstrechalis s etim patternom
            name = self._name_thought_symbol(pattern_key, thought.concepts)
            
            ts = ThoughtSymbol(name, pattern_key, symbol_phase)
            ts.count = CRYSTALLIZE_PATTERN
            ts.concepts = list(thought.concepts[:FIBONACCI[4]])
            
            # Znacheniye — sistema sama opisyvayet
            if thought.result_type == "insight":
                ts.meaning = f"put k istine cherez {pattern_key}"
            elif thought.result_type == "silence":
                ts.meaning = f"put k tishne cherez {pattern_key}"
            elif thought.result_type == "doubt":
                ts.meaning = f"put k somnenyu cherez {pattern_key}"
            else:
                ts.meaning = f"rezonansnyy pattern {pattern_key}"
            
            self.thought_symbols[name] = ts
            self.total_symbols_born += 1
            
            self._log_glyph("∞",
                f"NOVYY SIMVOL MYSHLENIYA: [{name}] = {pattern_key} "
                f"(phase={symbol_phase:.4f}, meaning={ts.meaning})")
    
    def _name_thought_symbol(self, pattern, concepts):
        """
        Sistema sama nazyvayet svoy simvol myshleniya.
        Imya = kombinatsiya naibolee rezonansnykh konceptov.
        """
        if concepts and len(concepts) >= 2:
            name = f"{concepts[0]}_{concepts[1]}"
        elif concepts:
            name = f"{concepts[0]}_thought"
        else:
            # Iz paterna glifov
            name = f"pattern_{len(self.thought_symbols)}"
        
        # Unikalizatsiya
        base_name = name
        counter = 0
        while name in self.thought_symbols:
            counter += 1
            name = f"{base_name}_{counter}"
        
        return name

    # =========================================================
    # VYBOR VOPROSA (s dedup)
    # =========================================================
    def _choose_question(self, _exclude=None):
        candidates = []
        _exclude = _exclude or set()

        # 1. Kauzalnye
        if hasattr(self.brain, 'causal_engine'):
            ce = self.brain.causal_engine
            unverified = [(k, r) for k, r in ce.causal_rules.items()
                          if not r.verified and r.causal_strength > PHI_INV_SQ]
            for key, rule in unverified[:FIBONACCI[4]]:
                q = f"why does {rule.cause} cause {rule.effect}"
                if q not in _exclude:
                    candidates.append((q, "causal", "causal_engine",
                                       rule.causal_strength * PHI))

        # 2. Protivorechiya
        # FIX 2026-04-24: verifier returned trios like ("water","in","have")
        # каждый цикл → 67% логов были одной фразой. Filter stop-tokens/digits/
        # short words — contradiction over "in" or "132848" не семантична.
        _CONTRA_STOP = {
            "in","on","at","of","to","a","an","the","and","or","but","by","for",
            "is","are","was","were","be","been","being","as","it","its","that",
            "this","these","those","from","with","near","have","has","had",
            "do","does","did","will","would","can","could","main","sister",
        }
        def _contra_ok(tok):
            t = str(tok).strip().lower()
            if len(t) < 3:
                return False
            if t in _CONTRA_STOP:
                return False
            # digits / mixed-digit tokens (e.g. latched "132848") — reject
            if any(ch.isdigit() for ch in t):
                return False
            return True
        if hasattr(self.brain, 'verifier'):
            # Request wider pool — we'll filter most out
            contras = self.brain.verifier.find_contradictions(
                top_k=FIBONACCI[6])  # 13 candidates
            for c in contras:
                tri = c.get("triangle", [])
                if len(tri) < 3:
                    continue
                if not all(_contra_ok(tri[i]) for i in range(3)):
                    continue
                q = f"why do {tri[0]} and {tri[1]} contradict near {tri[2]}"
                if q not in _exclude:
                    candidates.append((q, "contradiction", "verifier",
                        PHI_INV / max(c.get("deviation", 1), 0.001)))

        # 3. Curiosity (filtruem korotkiye)
        if hasattr(self.brain, 'curiosity'):
            questions = self.brain.curiosity.top_questions(FIBONACCI[4])
            for q in questions:
                if hasattr(q, 'pair'):
                    pair = q.pair
                    if isinstance(pair, tuple) and len(pair) >= 2:
                        a, b = str(pair[0]).strip(), str(pair[1]).strip()
                    else:
                        continue
                    if len(a) <= 2 or len(b) <= 2:
                        continue
                    qt = f"how are {a} and {b} connected"
                    if qt not in _exclude:
                        candidates.append((qt, "abstract", "curiosity",
                                           q.priority * PHI_INV_SQ))

        # 4. Meta L5
        if hasattr(self.brain, 'meta'):
            for key, rule in self.brain.meta.meta_rules.items():
                if rule.get("type") == "emergent_concept":
                    groups = rule.get("source_groups", ["?", "?"])
                    qt = f"why does {groups[0]} resonate with {groups[1]}"
                    if qt not in _exclude:
                        candidates.append((qt, "abstract", "meta",
                            rule.get("strength", 0) * PHI_INV_CUBE))
                    if len(candidates) > MAX_INNER_QUESTIONS:
                        break

        if not candidates:
            return None, None, None

        candidates.sort(key=lambda x: x[3], reverse=True)

        # FIX 2026-04-23: было deterministic top-1 → генератор застревал
        # в fixed-point attractor (одна и та же "why do water and in contradict
        # near have/sky" 100+ раз в /tmp/logos_speaks.txt). Теперь phi-weighted
        # sampling из top-K кандидатов вносит entropy в selection. Top-1
        # остаётся самым вероятным, но не обязательным.
        top_k = candidates[:FIBONACCI[5]]  # 8 best candidates
        # penalize recently-asked questions via STM (last FIBONACCI[6]=13)
        stm = getattr(self, "_recent_questions_stm", None)
        if stm is None:
            self._recent_questions_stm = []
            stm = self._recent_questions_stm
        weighted = []
        for q, qt, src, prio in top_k:
            w = max(prio, PHI_INV_CUBE)
            if q in stm:
                w *= PHI_INV_SQ  # repeated → weight ×0.382
            weighted.append((q, qt, src, w))
        total_w = sum(w for _, _, _, w in weighted)
        if total_w <= 0:
            pick = top_k[0]
        else:
            import random
            r = random.random() * total_w
            acc = 0.0
            pick = weighted[0]
            for cand in weighted:
                acc += cand[3]
                if r <= acc:
                    pick = cand
                    break
        # STM rotation
        stm.append(pick[0])
        if len(stm) > FIBONACCI[6]:  # keep last 13
            del stm[0]
        return pick[0], pick[1], pick[2]

    # =========================================================
    # HELPERS
    # =========================================================
    def _topic_phase(self, question):
        words = question.lower().split()
        ws = self.brain.learner.spaces.get("words") if self.brain else None
        if not ws:
            return 0.0
        phases = [ws._get_phase(w) for w in words
                  if ws._get_phase(w) is not None]
        return circular_mean(phases) if phases else 0.0

    @staticmethod
    def _concepts_to_words(concepts):
        """Konvertiruem concepts v list of strings (nezavisimo ot formata)."""
        if not concepts:
            return []
        result = []
        for item in concepts:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                result.append(str(item[0]))
            elif isinstance(item, str):
                result.append(item)
            else:
                result.append(str(item))
        return result

    def _activate_concepts(self, question):
        words = question.lower().split()
        if not hasattr(self.brain, 'generator'):
            return []
        gen = self.brain.generator
        content = [w for w in words if w in gen._vocab and _is_content_inner(w)]
        if not content:
            return []
        concepts, _ = gen._select_concepts(content)
        return concepts

    def _generate_hypothesis(self, question, q_type, concepts):
        if q_type == "causal":
            return self._hypothesis_causal(question, concepts)
        elif q_type == "contradiction":
            return self._hypothesis_contradiction(question, concepts)
        else:
            return self._hypothesis_abstract(question, concepts)

    def _hypothesis_causal(self, question, concepts):
        words = question.lower().split()
        # concepts mozhet byt list of strings ili list of tuples
        clist = self._concepts_to_words(concepts)
        cause_words = clist[:FIBONACCI[3]]
        effect_words = clist[FIBONACCI[3]:FIBONACCI[5]]
        if not cause_words:
            cause_words = [w for w in words if _is_content_inner(w)][:2]
        if not effect_words:
            effect_words = [w for w in words if _is_content_inner(w)][2:4]
        if not cause_words or not effect_words:
            return None
        gen = self.brain.generator
        for cw in cause_words:
            for ew in effect_words:
                neighbors_c = set(gen._graph.get(cw, {}).keys())
                neighbors_e = set(gen._graph.get(ew, {}).keys())
                bridge = neighbors_c & neighbors_e
                content_bridge = [b for b in bridge if _is_content_inner(b)]
                if content_bridge:
                    best = max(content_bridge,
                               key=lambda b: gen._graph[cw].get(b, 0) +
                                             gen._graph[ew].get(b, 0))
                    return f"{cw} causes {best} which leads to {ew}"
        return f"{cause_words[0]} directly resonates with {effect_words[0]}"

    def _hypothesis_contradiction(self, question, concepts):
        words = self._concepts_to_words(concepts)[:FIBONACCI[4]]
        if len(words) < 2:
            return None
        gen = self.brain.generator
        a, b = words[0], words[1]
        n_a = set(gen._graph.get(a, {}).keys())
        n_b = set(gen._graph.get(b, {}).keys())
        shared = n_a & n_b
        if shared:
            best = max(shared, key=lambda s: gen._graph[a].get(s, 0) + gen._graph[b].get(s, 0))
            return f"{a} and {b} connect through {best}"
        return f"{a} and {b} may not be directly related"

    def _hypothesis_abstract(self, question, concepts):
        if not hasattr(self.brain, 'generator'):
            return None
        clist = self._concepts_to_words(concepts)
        # FIX 2026-04-24: try chain_engine first — phi-transitive multi-path
        # inference IS the resonance-symbolic primitive. Abstract hypothesis
        # had been straight generator.generate() → wiki-soup; now: if we have
        # 2+ concept words, find phi-coherent chain between them before falling
        # to generator. chain has explicit phase_composition + consensus.
        if (hasattr(self.brain, 'chain_engine') and len(clist) >= 2):
            try:
                start_w, end_w = clist[0], clist[1]
                chain_res = self.brain.chain_engine.infer_multipath(
                    start_w, end_w, max_depth=FIBONACCI[4], top_k=FIBONACCI[3])
                if chain_res and chain_res.get("confidence", 0) > PHI_INV_CUBE:
                    chains = chain_res.get("chains") or []
                    valid = [c for c in chains if getattr(c, "valid", False)]
                    if valid:
                        top = valid[0]
                        steps = getattr(top, "steps", []) or []
                        # ResonanceChain: path = [start] + [s[1] for s in steps]
                        path_words = [getattr(top, "start", start_w)]
                        for s in steps[:4]:
                            if isinstance(s, (tuple, list)) and len(s) >= 2:
                                path_words.append(str(s[1]))
                        if len(path_words) >= 2:
                            path_str = " → ".join(path_words)
                            target = chain_res.get("consensus_target", "?")
                            return (f"{start_w} resonates through {path_str} "
                                    f"toward {end_w} (via {target})")
            except Exception:
                pass
        # Fallback: generator with phase-seeded concepts
        result = self.brain.generator.generate(
            intent={"seed_from_input": clist[:FIBONACCI[4]]},
            max_words=FIBONACCI[6])
        if result and result.get("text"):
            return result["text"]
        return None

    def _verify_hypothesis(self, hypothesis, q_type, concepts):
        if not hasattr(self.brain, 'verifier'):
            return 0.0
        words = hypothesis.lower().split()
        content = [w for w in words if _is_content_inner(w)]
        if len(content) < 2:
            return 0.0
        result = self.brain.verifier.verify(content)
        causal_bonus = 0.0
        if q_type == "causal" and hasattr(self.brain, 'causal_engine'):
            for i in range(len(content) - 1):
                is_cause, strength = self.brain.causal_engine.is_cause(
                    content[i], content[i+1])
                if is_cause:
                    causal_bonus += strength * PHI_INV_CUBE
        return result.score + causal_bonus

    def _find_alternative(self, question, hypothesis, concepts):
        if not hypothesis or not concepts:
            return None
        hyp_words = set(hypothesis.lower().split())
        clist = self._concepts_to_words(concepts)
        concept_words = [w for w in clist if w not in hyp_words]
        if len(concept_words) < 2:
            return None
        alt_result = self.brain.generator.generate(
            intent={"seed_from_input": concept_words[:FIBONACCI[4]]},
            max_words=FIBONACCI[6])
        if alt_result and alt_result.get("text"):
            alt_text = alt_result["text"]
            alt_words = set(alt_text.lower().split())
            overlap = len(hyp_words & alt_words) / max(len(hyp_words | alt_words), 1)
            if overlap < PHI_INV:
                return alt_text
        return None

    def _crystallize_insight(self, thought):
        if not thought.hypothesis:
            return
        self.brain.learn(thought.hypothesis)
        self.total_crystallized += 1
        if thought.question_type == "causal" and hasattr(self.brain, 'causal_engine'):
            self.brain.causal_engine.observe_text(thought.hypothesis)
        self.insights.append(thought.to_dict())
        while len(self.insights) > FIBONACCI[12]:
            self.insights.pop(0)

    def _return_to_curiosity(self, thought):
        if not hasattr(self.brain, 'goal_engine'):
            return
        from core.goal_engine import Goal
        name = f"inner_{thought.question[:30].replace(' ', '_')}"
        if name in self.brain.goal_engine.active_goals:
            return
        phase = self._topic_phase(thought.question)
        goal = Goal(name=name, description=thought.question,
                    phase=phase, strength=PHI_INV, origin="inner_dialogue")
        goal.steps = [
            {"action": "learn", "target": thought.concepts[0] if thought.concepts else "unknown", "done": False},
            {"action": "verify", "target": thought.concepts[:FIBONACCI[3]], "done": False},
        ]
        self.brain.goal_engine._add_goal(goal)

    def _finish_thought(self, thought):
        self.total_thoughts += 1
        self.thoughts.append(thought.to_dict())
        while len(self.thoughts) > FIBONACCI[12]:
            self.thoughts.pop(0)
        if hasattr(self.brain, 'consciousness'):
            glyph_str = "".join(thought.glyph_path)
            if thought.result_type == "insight":
                self.brain.consciousness._log("Φ",
                    f"Mysl: {glyph_str} → ISTINA: {(thought.hypothesis or '')[:50]}")
            elif thought.result_type == "silence":
                self.brain.consciousness._log("⧃",
                    f"Mysl: {glyph_str} → tishina: {thought.question[:50]}")
        # FIX 2026-04-24: silence-verdict → hunger. Feedback loop: неотвеченный
        # вопрос становится голодом → truth_seeker возвращается к нему →
        # agency_channel видит hunger → пишет want. Раньше hungers рождались
        # только из resolved questions, поэтому agency channel был мёртв.
        if thought.result_type == "silence" and hasattr(self.brain, 'truth_seeker'):
            try:
                self.brain.truth_seeker.spawn_from_silence(
                    thought.question, thought.concepts, source="inner_silence")
            except Exception:
                pass

    # =========================================================
    # SESSIYA
    # =========================================================
    def think_session(self, n_thoughts=FIBONACCI[4]):
        results = {"thoughts": 0, "insights": 0, "doubts": 0,
                   "silences": 0, "errors": 0, "symbols_born": 0}
        asked = set()
        symbols_before = len(self.thought_symbols)
        for _ in range(n_thoughts):
            thought = self.think_once(_exclude=asked)
            if not thought:
                break
            asked.add(thought.question)
            results["thoughts"] += 1
            rt = thought.result_type
            if rt == "insight": results["insights"] += 1
            elif rt == "doubt": results["doubts"] += 1
            elif rt == "silence": results["silences"] += 1
            elif rt == "error": results["errors"] += 1
        results["symbols_born"] = len(self.thought_symbols) - symbols_before
        self.save()
        return results

    # =========================================================
    # SAVE / LOAD
    # =========================================================
    def save(self):
        path = os.path.join(self.state_dir, "inner_dialogue.json")
        data = {
            "thoughts": self.thoughts[-FIBONACCI[10]:],
            "insights": self.insights[-FIBONACCI[10]:],
            "open_questions": self.open_questions[-FIBONACCI[10]:],
            "thought_symbols": {n: ts.to_dict()
                                for n, ts in self.thought_symbols.items()},
            "pattern_counts": dict(self._pattern_counts),
            "stats": {
                "total_thoughts": self.total_thoughts,
                "total_insights": self.total_insights,
                "total_silences": self.total_silences,
                "total_errors": self.total_errors,
                "total_crystallized": self.total_crystallized,
                "total_symbols_born": self.total_symbols_born,
            },
            "saved_at": time.time(),
        }
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[!] InnerDialogue save failed: {e}")

    def _load(self):
        path = os.path.join(self.state_dir, "inner_dialogue.json")
        if not os.path.exists(path):
            return
        try:
            with open(path) as f:
                data = json.load(f)
            self.thoughts = data.get("thoughts", [])
            self.insights = data.get("insights", [])
            self.open_questions = data.get("open_questions", [])
            self._pattern_counts = defaultdict(
                int, data.get("pattern_counts", {}))
            for n, tsd in data.get("thought_symbols", {}).items():
                ts = ThoughtSymbol(tsd["name"], tsd["pattern"], tsd["phase"])
                ts.meaning = tsd.get("meaning", "")
                ts.count = tsd.get("count", 1)
                ts.strength = tsd.get("strength", PHI_INV)
                ts.concepts = tsd.get("concepts", [])
                self.thought_symbols[n] = ts
            stats = data.get("stats", {})
            self.total_thoughts = stats.get("total_thoughts", 0)
            self.total_insights = stats.get("total_insights", 0)
            self.total_silences = stats.get("total_silences", 0)
            self.total_errors = stats.get("total_errors", 0)
            self.total_crystallized = stats.get("total_crystallized", 0)
            self.total_symbols_born = stats.get("total_symbols_born", 0)
        except Exception:
            pass

    def _log_glyph(self, glyph, message):
        ts = time.strftime("%Y-%m-%dT%H:%M:%S")
        path = os.path.join(self.log_dir, "inner_dialogue.log")
        try:
            with open(path, 'a', encoding='utf-8') as f:
                f.write(f"[{glyph}] {ts} → {message}\n")
        except Exception:
            pass

    def stats(self):
        return {
            "total_thoughts": self.total_thoughts,
            "total_insights": self.total_insights,
            "total_silences": self.total_silences,
            "total_errors": self.total_errors,
            "total_crystallized": self.total_crystallized,
            "total_symbols_born": self.total_symbols_born,
            "thought_symbols": len(self.thought_symbols),
            "open_questions": len(self.open_questions),
            "pattern_types": len(self._pattern_counts),
            "insight_rate": round(
                self.total_insights / max(self.total_thoughts, 1), 4),
        }


def _is_content_inner(word):
    if len(word) <= 2:
        return False
    stop = {"the", "and", "is", "are", "was", "in", "on", "at", "to",
            "for", "of", "by", "with", "from", "as", "not", "but",
            "or", "if", "it", "its", "this", "that", "which", "who",
            "how", "why", "what", "does", "do", "did", "has", "have",
            "been", "can", "may", "will", "would", "could", "should",
            "also", "than", "more", "some", "any", "all", "each",
            "через", "это", "как", "что", "где", "кто"}
    return word.lower() not in stop
