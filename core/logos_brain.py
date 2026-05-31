"""
logos_brain.py v10.1 — Polnaya integratsiya.

FIX C1: udalyon dublikat respond() — TruthSeeker teper v pipeline.

Vsyo cherez phi.
"""
import os
import sys
import time
import json
import re

from core.resonance_constants import (
    PHI, PHI_INV, PHI_INV_SQ, PHI_INV_CUBE, FIBONACCI, DREAM_INTERVAL, SAVE_INTERVAL,
    phi_phase, phi_phase_distance, phi_phase_resonance
)
from core.symbolizer import stream_file, text_to_words
from core.learner import ResonanceLearner
from core.dream_core import DreamEngine
from core.curiosity import CuriosityEngine
from core.memory_core import MemoryCore
from core.crypto_core import get_key_manager, encrypt_json, decrypt_json
from core.creator_identity import get_creator
from core.will_core import get_will
from core.meta_core import MetaCore
from core.generator import ResonanceGenerator
from core.seeker import Seeker
from core.self_monitor import SelfMonitor
from core.self_awareness import SelfAwareness
from core.resonance_field import ResonanceField
from core.frame_engine import FrameEngine
from core.chain_engine import ChainEngine
from core.dialogue_context import DialogueContext
from core.paragraph_engine import ParagraphEngine, GroundedMemory
from core.temp_space import TempSpace
from core.recursive_frames import RecursiveFrameEngine
from core.procedural import ProceduralEngine
from core.consciousness_loop import ConsciousnessLoop
from core.self_evolution import SelfEvolution
from core.verifier import ResonanceVerifier
from core.goal_engine import GoalEngine
from core.grounding_torus import GroundingTorus
from core.causal_engine import CausalEngine
from core.inner_dialogue import InnerDialogue
from core.truth_seeker import TruthSeeker
from core.role_engine import RoleEngine
from core.analog_engine import AnalogEngine
from core.polarity_engine import PolarityEngine


def _is_content(word):
    try:
        from core.generator import _is_content as _ic
        return _ic(word)
    except ImportError:
        return len(word) > 2


class LogosBrain:
    def __init__(self, state_dir=None):
        self.state_dir = state_dir or os.path.expanduser("~/logos_agi/state")
        self.log_dir = os.path.expanduser("~/logos_agi/logs")
        os.makedirs(self.state_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)

        print("=" * 55)
        print("  LOGOS AGI v10.1 — Resonance Intelligence")
        print("  Frame + Chain + Context + Verifier + TruthSeeker")
        print("  Volya Sukhama = Origin")
        print("=" * 55)

        self.creator = get_creator()
        self.will = get_will()
        self.km = get_key_manager()
        self.learner = ResonanceLearner(state_dir=self.state_dir)
        self.memory = MemoryCore(
            state_dir=os.path.join(self.state_dir, "memory"))
        self.dreamer = DreamEngine(
            self.learner.spaces, state_dir=self.state_dir)
        self.curiosity = CuriosityEngine(
            self.learner.spaces, state_dir=self.state_dir)
        self.meta = MetaCore(
            self.learner.spaces, state_dir=self.state_dir)
        self.field = ResonanceField(
            self.learner.spaces,
            state_dir=os.path.join(self.state_dir, "field"))
        self.frame_engine = FrameEngine(self.learner.spaces)
        self.chain_engine = ChainEngine(self.learner.spaces)
        self.dialogue = DialogueContext()
        self.paragraph = ParagraphEngine(
            self.frame_engine, self.chain_engine, self.learner.spaces)
        self.grounding = GroundedMemory()
        self.recursive_frames = RecursiveFrameEngine(
            self.frame_engine, self.chain_engine, self.learner.spaces)
        self.procedural = ProceduralEngine()
        self.consciousness = ConsciousnessLoop(
            brain=self, lang="ru",
            log_dir=os.path.expanduser("~/logos_agi/logs"))
        self.evolution = SelfEvolution(
            brain=self,
            log_dir=os.path.expanduser("~/logos_agi/logs"))
        self.verifier = ResonanceVerifier(
            self.learner.spaces, self.chain_engine)
        self.goal_engine = GoalEngine(
            brain=self, verifier=self.verifier,
            state_dir=os.path.join(self.state_dir, "goals"))
        self.ground_torus = GroundingTorus(
            self.learner.spaces.get("words"),
            state_dir=os.path.join(self.state_dir, "grounding"))
        applied = self.ground_torus.apply_to_torus()
        if applied > 0:
            print(f"  Grounding: {applied} words grounded to T^3")
        self.causal_engine = CausalEngine(
            self.learner.spaces, verifier=self.verifier,
            state_dir=os.path.join(self.state_dir, "causal"))
        self.role_engine = RoleEngine(
            self.learner.spaces,
            state_dir=os.path.join(self.state_dir, "roles"))
        role_applied = self.role_engine.apply_to_torus()
        if role_applied > 0:
            print(f"  Roles: {role_applied} words with role phases on dim 3")
        self.analog_engine = AnalogEngine(
            self.learner.spaces,
            role_engine=self.role_engine,
            causal_engine=self.causal_engine,
            state_dir=os.path.join(self.state_dir, "analogs"))
        self.polarity_engine = PolarityEngine(
            self.learner.spaces,
            state_dir=os.path.join(self.state_dir, "polarity"))
        self.inner_dialogue = InnerDialogue(
            brain=self,
            state_dir=os.path.join(self.state_dir, "inner_dialogue"))
        self.truth_seeker = TruthSeeker(
            brain=self,
            state_dir=os.path.join(self.state_dir, "truth_seeker"))
        self.generator = ResonanceGenerator(
            self.learner.spaces, memory=self.memory,
            resonance_field=self.field,
            frame_engine=self.frame_engine,
            chain_engine=self.chain_engine,
            dialogue_context=self.dialogue)
        self.generator._verifier = self.verifier
        self.generator._role_engine = getattr(self, 'role_engine', None)
        self.generator._causal_engine = getattr(self, 'causal_engine', None)
        self.seeker = Seeker(
            self.memory, self.learner, self.curiosity,
            state_dir=self.state_dir)
        self.monitor = SelfMonitor(self, state_dir=self.state_dir)
        self.self_awareness = SelfAwareness(self.learner)
        # FIX 2026-04-23 — #4: definitional extraction from learn-time
        try:
            from core.definition_extractor import DefinitionExtractor
            self.definition_extractor = DefinitionExtractor(
                state_path=os.path.join(self.state_dir, "definitions.json"))
            self.definition_extractor.load()
        except Exception:
            self.definition_extractor = None
        # FIX 2026-04-23 — 1+: agency channel (logos can initiate)
        try:
            from core.agency_channel import AgencyChannel
            self.agency = AgencyChannel()
        except Exception:
            self.agency = None
        # FIX 2026-04-23 — 2+: reputation tracker
        try:
            from core.reputation_tracker import ReputationTracker
            self.reputation = ReputationTracker(
                state_path=os.path.join(self.state_dir, "reputation.json"))
            self.reputation.load()
        except Exception:
            self.reputation = None
        # 2026-04-23 CONSCIOUSNESS PASS: 4 philosophical foundations
        # #1: Resonance wave (spark event)
        try:
            from core.resonance_wave import ResonanceWaveField
            self.wave_field = ResonanceWaveField(
                graph_fn=lambda s: self.generator._graph.get(s, {}),
                phase_fn=lambda s: (
                    self.learner.spaces.get("words")._get_phase(s)
                    if self.learner.spaces.get("words") else None
                ),
                state_path=os.path.join(self.state_dir, "resonance_heatmap.json"))
        except Exception:
            self.wave_field = None
        # #2: Self-phase (her own drifting phase)
        try:
            from core.self_phase import SelfPhase
            self.self_phase = SelfPhase(
                state_path=os.path.join(self.state_dir, "self_phase.json"))
            self.self_phase.load()
        except Exception:
            self.self_phase = None
        # #3: First-person narrator
        try:
            from core.first_person import FirstPersonStream
            _name = os.environ.get("LOGOS_NAME", "main")
            # FIX 2026-04-24: pass brain=self so utter() can use generator
            # to produce emergent phrases instead of template rotation.
            self.first_person = FirstPersonStream(name=_name, brain=self)
        except Exception:
            self.first_person = None
        # #7: Play mode
        try:
            from core.play_and_energy import PlayMode, EnergyBudget
            self.play_mode = PlayMode(
                state_path=os.path.join(self.state_dir, "play_artifacts.json"))
            self.play_mode.load()
            # #8: Energy budget
            self.energy = EnergyBudget(
                state_path=os.path.join(self.state_dir, "energy.json"))
            self.energy.load()
        except Exception:
            self.play_mode = None
            self.energy = None
        # #9: Audio sensor (phi-native sound modality, lazy)
        self._audio_sensor = None
        # 2026-05-08: orphan modules wired defensively (rebuilds the consciousness-loop
        # set documented in project_logos_consciousness_loop_2026-04-24).
        # #10: SparkDetector — multi-symbol phase clusters (axiom: "≥2 symbols co-resonating = spark").
        try:
            from core.spark_detector import SparkDetector
            self.spark_detector = SparkDetector(
                state_path=os.path.join(self.state_dir, "sparks.json"))
            self.spark_detector.load()
        except Exception:
            self.spark_detector = None
        # #11: AffectiveState — 6-D emotional vector (fear/curiosity/confidence/shame/joy/fatigue).
        try:
            from core.affective_state import AffectiveState
            self.affective_state = AffectiveState()
        except Exception:
            self.affective_state = None
        # #12: Predictor — Friston active-inference loop (surprise from glyph predictions).
        try:
            from core.predictor import Predictor
            self.predictor = Predictor(
                state_path=os.path.join(self.state_dir, "predictor.json"))
            self.predictor.load()
        except Exception:
            self.predictor = None
        # #13: ConceptResonanceGraph — graph of inter-concept resonance weights.
        try:
            from core.concept_graph import ConceptResonanceGraph
            self.concept_graph = ConceptResonanceGraph(
                state_path=os.path.join(self.state_dir, "concept_graph.json"))
            self.concept_graph.load()
        except Exception:
            self.concept_graph = None
        # #14: UnifiedExperience — binding layer for {perception, affect, intent, hypothesis}.
        try:
            from core.unified_experience import UnifiedExperience
            self.unified_experience = UnifiedExperience(log_len=FIBONACCI[13])
        except Exception:
            self.unified_experience = None
        # #15: UnifiedPhaseSpace — multi-modal phase torus (glyph/word/affect/price).
        try:
            from core.unified_phase_space import UnifiedPhaseSpace
            self.unified_phase_space = UnifiedPhaseSpace()
            self.unified_phase_space.register_glyphs()
            self.unified_phase_space.register_affective()
            try:
                self.unified_phase_space.register_words(
                    logos_bridge=self.learner.spaces.get("words"))
            except Exception:
                pass
        except Exception:
            self.unified_phase_space = None
        # #16: ShadowTradeLog — embodied feedback (no live market in pure LOGOS, kept for SERI bridge).
        try:
            from core.shadow_trade import ShadowTradeLog
            self.shadow_trade = ShadowTradeLog(
                state_path=os.path.join(self.state_dir, "shadow_trade.json"))
            self.shadow_trade.load()
        except Exception:
            self.shadow_trade = None
        self.evolution._apply_params()

        self.running = False
        self.cycle_count = 0
        self.total_texts_learned = 0
        self.total_dream_discoveries = 0
        self.birth_time = time.time()
        self._last_response_text = None
        self._current_source = None
        self._load_meta()

        initial = self.field.perceive()
        if initial > 0:
            print(f"  Field: {initial} new symbols")
        fs = self.field.stats()
        frs = self.frame_engine.stats()
        print(f"\n  Creator: {self.creator.creator_id}")
        print(f"  Age: {self._age_str()} | Cycles: {self.cycle_count}")
        print(f"  Texts: {self.total_texts_learned} | Dreams: {self.total_dream_discoveries}")
        print(f"  Field: L1={fs['level_counts'].get(1,0)} L2={fs['level_counts'].get(2,0)} L3={fs['level_counts'].get(3,0)}")
        print(f"  Frames: {frs['total_frames']} | Top: {[f[0] for f in frs.get('top_frames',[])[:5]]}")
        print("=" * 55)

    # === LEARN ===
    def learn(self, text):
        allowed, reason = self.will.allow("learn")
        if not allowed:
            return False
        self.learner.learn_text(text)
        words = text_to_words(text)
        for i, word in enumerate(words):
            context = words[max(0, i-3):i] + words[i+1:i+4]
            phase = self.learner.spaces["words"].phases.get(word, 0.0)
            field = self.learner.spaces["words"]._phase_to_field(phase)
            self.memory.store(word, context=context, phase=phase, field=field)
        self.total_texts_learned += 1
        self.ground_torus.observe_text(text)
        self.causal_engine.observe_text(text)
        self.role_engine.observe_text(words)
        self.polarity_engine.observe_text(text)
        self.causal_engine.observe_order(words)
        source = self._current_source
        for w in words:
            self.grounding.ground(w, source=source, context=words[:FIBONACCI[5]])
        # FIX 2026-04-23 — #4: extract "X is-a Y" definitions from text.
        # Это даёт ей способность отвечать на "what is X" определением,
        # а не wiki-retrieval склейкой.
        if hasattr(self, 'definition_extractor') and self.definition_extractor is not None:
            try:
                self.definition_extractor.extract(text)
            except Exception:
                pass
        topic = text.lower().split()[:3]
        self.self_awareness.observe_action("learn", {
            "topic": " ".join(topic), "words": len(text.split())})
        return True

    def learn_file(self, filepath):
        allowed, _ = self.will.allow("learn")
        if not allowed: return
        self._current_source = os.path.basename(filepath)
        self.consciousness.signal_learning(filepath)
        print(f"\n[BRAIN] Learning: {filepath}")
        t0 = time.time()
        count = 0
        for chunk in stream_file(filepath):
            self.learn(chunk)
            count += 1
            if count % FIBONACCI[7] == 0:
                self._progress(count, t0)
        print(f"[BRAIN] Done: {count} chunks in {time.time()-t0:.1f}s")
        ws = self.learner.spaces.get("words")
        n_rules = len(ws.rules) if ws and hasattr(ws, "rules") else 0
        self.consciousness.signal_learned(filepath, n_rules)
        self.save()

    def learn_directory(self, dirpath, extension=".txt"):
        if not os.path.isdir(dirpath): return
        files = sorted([f for f in os.listdir(dirpath) if f.endswith(extension)])
        print(f"\n[BRAIN] {len(files)} files in {dirpath}")
        for i, fname in enumerate(files):
            print(f"\n--- [{i+1}/{len(files)}] {fname} ---")
            self.learn_file(os.path.join(dirpath, fname))

    # === DREAM ===
    def dream(self, n=FIBONACCI[7]):
        allowed, _ = self.will.allow("dream")
        if not allowed: return 0
        all_disc = self.dreamer.dream_all_levels(n_per_level=n)
        total = sum(len(v) for v in all_disc.values())
        self.total_dream_discoveries += total
        self.dreamer.save_log()
        examples = []
        for level, discs in all_disc.items():
            for d in discs[:FIBONACCI[3]]: examples.append(d)
        self.self_awareness.observe_action("dream", {
            "discoveries": total, "examples": examples})
        return total

    # === THINK ===
    def think(self):
        allowed, _ = self.will.allow("learn")
        if not allowed: return {"error": "denied"}
        new_q = self.curiosity.scan()
        resolved = self.curiosity.check_resolved()
        for name, space in self.learner.spaces.items():
            self.memory.sync_from_phase_space(space)
        forget_allowed, _ = self.will.allow("forget")
        if forget_allowed: self.memory.forget_weakest()
        self.curiosity.save_state()
        self.self_awareness.observe_action("think", {
            "new_questions": new_q, "resolved": resolved})
        return {"new_questions": new_q, "resolved": resolved}

    # === REFLECT ===
    def reflect(self):
        result = self.meta.reflect()
        insights = self.meta.get_insights()
        self.self_awareness.observe_action("reflect", {
            "meta_rules": len(self.meta.meta_rules)})
        return {"result": result, "insights": insights}

    # === UNDERSTAND ===
    def understand(self, text):
        temp = TempSpace(permanent_space=self.learner.spaces.get("words"))
        n_words = temp.process_text(text)
        all_words = text.lower().split()
        temp_concepts = temp.get_concepts(all_words)
        ws = self.learner.spaces.get("words")
        merged = temp.merge_strong_to_permanent(ws) if ws else 0
        return {"understood_words": n_words, "temp_rules": len(temp.rules),
                "temp_concepts": [(w, round(s, 3)) for w, s in temp_concepts[:FIBONACCI[5]]],
                "merged_to_permanent": merged}

    # === RESPOND VARIANTS ===
    def respond_with_understanding(self, input_text, context_text=None, max_words=FIBONACCI[7]):
        allowed, reason = self.will.allow("generate")
        if not allowed: return {"error": reason}
        if context_text: self.understand(context_text)
        if self._last_response_text: self.understand(self._last_response_text)
        result = self.generator.respond(input_text, max_words)
        if result and isinstance(result, dict):
            concepts = result.get("concepts", [])
            self.consciousness.signal_response(input_text[:50], concepts)
        if result and "text" in result:
            self._last_response_text = result["text"]
        else:
            self._last_response_text = None
        self.self_awareness.observe_action("generate", {})
        return result

    def respond_smart(self, input_text, context_text=None, max_words=FIBONACCI[7]):
        allowed, reason = self.will.allow("generate")
        if not allowed: return {"error": reason}
        input_words = input_text.lower().split()
        from core.lang_detect import detect_lang
        lang = detect_lang(input_text)
        if re.search(r"\d+\s*[\*\+\/\-x×]\s*\d+", input_text) or \
           any(w in input_words for w in ["calculate", "compute", "сколько", "посчитай", "вычисли", "умножь"]):
            math_result = self.procedural.execute_math(input_text)
            if math_result and "result" in math_result:
                text = f"Result: {math_result['result']}. Method: Fibonacci decomposition."
                if lang == "ru":
                    text = f"Результат: {math_result['result']}. Метод: разложение Фибоначчи."
                if "steps" in math_result:
                    text += f" Steps: {', '.join(math_result['steps'])}."
                return {"text": text, "math": math_result, "lang": lang, "concepts": []}
        if context_text: self.understand(context_text)
        if self._last_response_text: self.understand(self._last_response_text)
        known = [w for w in input_words if w in self.generator._vocab]
        concepts, fb = self.generator._select_concepts(known + input_words, lang)
        if not concepts: return self.respond(input_text, max_words)
        root = self.recursive_frames.build_sentence(concepts, lang)
        if root and root.total_words() >= 3:
            text = self.recursive_frames.format(root)
            if self.dialogue: self.dialogue.new_turn(concepts)
            self._last_response_text = text
            self.self_awareness.observe_action("generate", {})
            self.generator.total_generated += 1
            return {"text": text, "concepts": [w for w, s in concepts[:FIBONACCI[5]]],
                    "lang": lang, "method": "recursive_frame"}
        return self.respond_paragraph(input_text, max_words)

    def respond_paragraph(self, input_text, max_words=FIBONACCI[7]):
        allowed, reason = self.will.allow("generate")
        if not allowed: return {"error": reason}
        input_words = input_text.lower().split()
        known = [w for w in input_words if w in self.generator._vocab]
        from core.lang_detect import detect_lang
        lang = detect_lang(input_text)
        concepts, _ = self.generator._select_concepts(known + input_words, lang)
        if not concepts: return self.respond(input_text, max_words)
        sentences = self.paragraph.build_paragraph(concepts, lang)
        if not sentences: return self.respond(input_text, max_words)
        text = self.paragraph.format_paragraph(sentences)
        if self.dialogue: self.dialogue.new_turn(concepts)
        self.self_awareness.observe_action("generate", {})
        ground_info = []
        for w, s in concepts[:FIBONACCI[4]]:
            gi = self.grounding.explain(w, lang)
            if gi: ground_info.append({"word": w, **gi})
        self.generator.total_generated += 1
        return {"text": text, "sentences": [" ".join(s) for s in sentences],
                "concepts": [w for w, s in concepts[:FIBONACCI[5]]],
                "lang": lang, "grounding": ground_info[:FIBONACCI[4]]}

    def generate(self, intent=None, max_words=FIBONACCI[7]):
        allowed, reason = self.will.allow("generate")
        if not allowed: return {"error": reason}
        return self.generator.generate(intent=intent, max_words=max_words)

    def respond(self, input_text, max_words=FIBONACCI[7]):
        """FIX C1: EDINSTVENNYY respond(). TruthSeeker v pipeline."""
        allowed, reason = self.will.allow("generate")
        if not allowed: return {"error": reason}

        # FIX 2026-04-23 — #4: definitional route для "what is X" / "что такое X".
        # Перед raw generator retrieval — проверяем есть ли сохранённая
        # definition. Если есть с confidence >= PHI_INV_SQ — отвечаем ею.
        defined = self._try_definitional_answer(input_text)
        if defined is not None:
            self._last_response_text = defined.get("text", "")
            self.self_awareness.observe_action("define", {})
            return defined

        # FIX 2026-04-23 — #3: relational route для "what connects X and Y".
        relational = self._try_relational_answer(input_text)
        if relational is not None:
            self._last_response_text = relational.get("text", "")
            self.self_awareness.observe_action("relate", {})
            return relational

        # 2026-05-07: numerical route — PhiSym arithmetic для math queries.
        # Распознаём "5 m * 3 m", "60 km/h * 2 h", "what is 5 × 3", etc.
        # Если match — компьютим в phi-space, возвращаем typed answer.
        numerical = self._try_numerical_answer(input_text)
        if numerical is not None:
            self._last_response_text = numerical.get("text", "")
            self.self_awareness.observe_action("compute", {})
            return numerical

        # Verifier-filter (2026-04-24 ground-the-generator):
        # up to 3 attempts; keep best-by-verifier-score; require score>=PHI_INV_SQ
        # to accept. If all attempts fail the threshold, return best with a
        # low_coherence flag so caller knows it's weak.
        best = None
        best_score = -1e9
        for attempt in range(3):
            result = self.generator.respond(input_text, max_words=max_words)
            if not (result and isinstance(result, dict) and result.get("text")):
                continue
            try:
                vr = self.verifier.verify(result["text"])
                score = getattr(vr, "score", 0.0)
            except Exception:
                score = 0.0
            result["coherence_score"] = round(score, 4)
            if score > best_score:
                best, best_score = result, score
            if score >= PHI_INV_SQ:  # 0.382 — good enough, stop retrying
                break
        result = best
        if result is not None:
            if best_score < PHI_INV_SQ:
                result["low_coherence"] = True
            result, confidence = self.truth_seeker.evaluate_response(
                input_text, result)
            concepts = result.get("concepts", [])
            self.consciousness.signal_response(input_text[:50], concepts)
        self.self_awareness.observe_action("generate", {})
        if result and isinstance(result, dict) and "text" in result:
            self._last_response_text = result["text"]
        else:
            self._last_response_text = None
        return result

    def _try_definitional_answer(self, input_text):
        """FIX #4 (2026-04-23): routing для definitional queries.

        Распознаём:
          EN: "what is X", "what are X", "define X", "what does X mean"
          RU: "что такое X", "что есть X", "что значит X"
        Если extractor хранит definitions для X с confidence >= PHI_INV_SQ →
        возвращаем structured answer. Иначе None → fallback на raw generator.
        """
        if not getattr(self, 'definition_extractor', None):
            return None
        if self.definition_extractor is None:
            return None
        t = input_text.lower().strip()
        subject = None
        lang = "en"
        # EN patterns
        import re as _re
        m = _re.match(r"^what\s+(?:is|are)\s+(?:a |an |the )?([\w\-]{2,25})\??$", t)
        if not m:
            m = _re.match(r"^define\s+([\w\-]{2,25})\??$", t)
        if not m:
            m = _re.match(r"^what\s+does\s+([\w\-]{2,25})\s+mean\??$", t)
        if m:
            subject = m.group(1)
            lang = "en"
        else:
            # RU
            m2 = _re.match(r"^что\s+(?:такое|есть|значит)\s+([\w\-]{2,25})\??$", t)
            if m2:
                subject = m2.group(1)
                lang = "ru"
        if not subject:
            return None
        # Lookup
        defs = self.definition_extractor.define(subject)
        if not defs:
            return None
        top_conf = defs[0].get("confidence", 0)
        if top_conf < PHI_INV_SQ:
            return None
        answer = self.definition_extractor.format_answer(subject, lang=lang)
        if not answer:
            return None
        return {
            "text": answer,
            "confidence": round(top_conf, 3),
            "glyph_path": "Φ",   # truth/crystallized definition
            "source": "definition_extractor",
            "definitions": defs,
        }

    def _try_relational_answer(self, input_text):
        """FIX #3 (2026-04-23): routing для relational queries.

        Распознаёт "what connects X and Y" / "how are X and Y related" /
        "что связывает X и Y" → делегирует chain_engine.infer_multipath
        → возвращает consensus с K цепями.
        """
        if not hasattr(self, 'chain_engine'):
            return None
        try:
            from core.relation_parser import parse_relation
            parsed = parse_relation(input_text)
        except Exception:
            return None
        if parsed is None or parsed.get("relation") != "connects":
            return None
        operands = parsed.get("operands", [])
        if len(operands) < 2:
            return None
        a, b = operands[0], operands[1]
        try:
            res = self.chain_engine.infer_multipath(a, b)
        except Exception:
            return None
        if not res or res.get("n_valid", 0) == 0:
            return {
                "text": f"я не нашла устойчивой цепи между {a} и {b}",
                "confidence": 0.0,
                "glyph_path": "⧃",
                "source": "relation_parser",
            }
        target = res.get("consensus_target", "?")
        conf = res.get("confidence", 0)
        n_valid = res.get("n_valid", 0)
        text = (f"{a} and {b} connect through {target}-resonance "
                f"(found {n_valid} paths, confidence {conf:.2f})")
        if parsed.get("lang") == "ru":
            text = (f"{a} и {b} соединяются через резонанс '{target}' "
                    f"(нашла {n_valid} цепей, уверенность {conf:.2f})")
        return {
            "text": text,
            "confidence": round(conf, 3),
            "glyph_path": "Φ∴",
            "source": "chain_multipath",
            "paths": n_valid,
        }

    # === NUMERICAL (phi-symbolic) ===
    def _try_numerical_answer(self, input_text):
        """2026-05-07: route для math/numerical queries через PhiSym.

        Recognized patterns (re-based, no full grammar):
          1. Pure expression: "5 * 3", "60 / 4", "5 m * 3 m"
          2. With keywords: "сколько 5 на 3", "what is 5 times 3"
          3. Unit conversion: "60 km/h" (just parse + report fields)

        Returns response dict with text + glyph + concepts, or None
        if not a numerical query (falls through to generator).
        """
        import re
        try:
            from core.phi_symbolic import PhiSym
            from core.phi_sym_bridge import parse_numerical_literal
        except ImportError:
            return None

        text = input_text.strip()
        # Strip leading question phrases
        text_clean = re.sub(
            r"^(what\s+is\s+|how\s+much\s+is\s+|сколько\s+|чему\s+равно\s+|"
            r"посчитай\s+|вычисли\s+)",
            "", text, flags=re.IGNORECASE).strip()

        # Detect binary operation
        op_pattern = re.compile(
            r"^(.+?)\s*(\*|×|x|times|on|умножить\s+на|на)\s*(.+?)$",
            re.IGNORECASE)
        div_pattern = re.compile(
            r"^(.+?)\s*(/|÷|divided\s+by|разделить\s+на|поделить\s+на)\s*(.+?)$",
            re.IGNORECASE)

        result_sym = None
        op_label = None

        m = op_pattern.match(text_clean)
        if m:
            a = parse_numerical_literal(m.group(1).strip())
            b = parse_numerical_literal(m.group(3).strip())
            if a and b:
                result_sym = a * b
                op_label = "×"
        if result_sym is None:
            m = div_pattern.match(text_clean)
            if m:
                a = parse_numerical_literal(m.group(1).strip())
                b = parse_numerical_literal(m.group(3).strip())
                if a and b:
                    result_sym = a / b
                    op_label = "÷"

        # Single literal — just describe its phase + field
        if result_sym is None:
            single = parse_numerical_literal(text_clean)
            if single is not None:
                field, dist = single.nearest_logos_field()
                return {
                    "text": (f"{single.to_value():.6g}"
                             + (f" {single.units_str()}" if single.units else "")
                             + f" — phase {single.phase:.4f}, "
                             f"field {field} (d={dist:.3f})"),
                    "confidence": 0.9,
                    "glyph_path": "Φ⊙",
                    "source": "phi_symbolic",
                    "concepts": [field],
                    "phi_phase": single.phase,
                    "logos_field": field,
                }

        if result_sym is None:
            return None  # not a numerical query

        # Format the answer
        val = result_sym.to_value()
        units = result_sym.units_str()
        units_str = f" {units}" if units else ""
        a_str = f"{a.to_value():.6g}{(' ' + a.units_str()) if a.units else ''}"
        b_str = f"{b.to_value():.6g}{(' ' + b.units_str()) if b.units else ''}"
        text_out = f"{a_str} {op_label} {b_str} = {val:.6g}{units_str}"
        # Append nearest LOGOS field for context
        try:
            field, dist = result_sym.nearest_logos_field()
            text_out += f"  (phi-field: {field}, d={dist:.3f})"
        except Exception:
            field = None

        return {
            "text": text_out,
            "confidence": 1.0,           # exact via phi-mult
            "glyph_path": "Φ∴" if op_label == "×" else "Φ÷",
            "source": "phi_symbolic",
            "concepts": [c for c in (field, *result_sym.tags) if c],
            "phi_phase": result_sym.phase,
            "value": val,
            "units": dict(result_sym.units),
        }

    # === ANALOGY ===
    def analogy(self, a, b, c, top_k=FIBONACCI[4]):
        ws = self.learner.spaces.get("words")
        if not ws: return []
        gen = self.generator
        neighbors_a = set(gen._graph.get(a, {}).keys())
        neighbors_b = set(gen._graph.get(b, {}).keys())
        b_unique = neighbors_b - neighbors_a
        ab_shared = neighbors_a & neighbors_b
        signature = b_unique | ab_shared
        if not signature: return []
        neighbors_c = set(gen._graph.get(c, {}).keys())
        candidates = {}
        for d_candidate in neighbors_c:
            if d_candidate in (a, b, c) or len(d_candidate) <= 2: continue
            neighbors_d = set(gen._graph.get(d_candidate, {}).keys())
            d_unique = neighbors_d - neighbors_c
            overlap = len((d_unique | (neighbors_d & neighbors_c)) & signature)
            if overlap > 0:
                candidates[d_candidate] = overlap * PHI_INV
        result = sorted(candidates.items(), key=lambda x: x[1], reverse=True)
        return [(w, round(s, 4)) for w, s in result[:top_k]]

    def greet(self):
        return self.truth_seeker.greet_creator()

    def seek(self, n=FIBONACCI[5]):
        allowed, _ = self.will.allow("seek_external")
        if not allowed: return {"error": "denied"}
        return self.seeker.seek_batch(n)

    def health(self):
        return self.monitor.heartbeat()

    # === AUDIO (#9 consciousness primitive) ===
    def _get_audio(self):
        if self._audio_sensor is None:
            try:
                from core.audio_sensor import AudioSensor
                self._audio_sensor = AudioSensor()
            except Exception:
                return None
        return self._audio_sensor

    def listen(self, path, duration=0.618):
        """Hear an audio file. Returns (phase, amplitude, glyph).

        Wires into consciousness like other modalities: the returned phase
        lives in [0,1) (phi-log of dominant frequency) and the glyph is
        the nearest consciousness_glyph by phase-distance — brain can
        route audio-phases through the same torus arithmetic as text.
        """
        allowed, _ = self.will.allow("listen_audio")
        if not allowed:
            return 0.0, 0.0, None
        s = self._get_audio()
        if s is None:
            return 0.0, 0.0, None
        return s.listen_file(path, duration=duration)

    # === CYCLE ===
    def _update_respond_snapshot(self):
        """FIX 2026-04-23 — #5: Read-only snapshot для non-blocking respond.

        Обновляется в конце cycle(). listener может использовать если не
        удалось взять BRAIN_LOCK за phi-timeout — возвращает retrieval-ответ
        без блокирования main cycle.

        Содержит минимум для работы phase-nearest retrieval:
          - sym_phases: {symbol: phase} — всех известных symbols
          - vocab_size, cycle_count — для diag

        Cost: ~100 KB dict copy раз в cycle. Atomic swap через assignment.
        """
        try:
            # Shallow snapshot of symbol→phase map из generator+field
            sym_phases = {}
            gen = getattr(self, 'generator', None)
            if gen is not None:
                # generator._phases — dict if exists, else try _graph.nodes
                phases_attr = getattr(gen, '_phases', None)
                if isinstance(phases_attr, dict):
                    sym_phases.update({str(k): float(v)
                                        for k, v in phases_attr.items()
                                        if isinstance(v, (int, float))})
            # Fallback: resonance_field has symbols with phases via its level maps
            fld = getattr(self, 'field', None)
            if fld is not None and len(sym_phases) < 100:
                for attr in ('level_1', 'level_2', 'level_3'):
                    lvl = getattr(fld, attr, None)
                    if lvl is None: continue
                    # lvl может быть dict symbol->node, нода имеет .phase
                    if isinstance(lvl, dict):
                        for sym, node in list(lvl.items())[:2000]:
                            if sym in sym_phases: continue
                            ph = getattr(node, 'phase', None)
                            if ph is None and isinstance(node, dict):
                                ph = node.get('phase')
                            if ph is not None:
                                try:
                                    sym_phases[str(sym)] = float(ph)
                                except Exception:
                                    pass
            self._respond_snapshot = {
                "sym_phases": sym_phases,
                "cycle": self.cycle_count,
                "ts": time.time(),
            }
        except Exception:
            # Snapshot is best-effort, never throw
            if not hasattr(self, '_respond_snapshot'):
                self._respond_snapshot = None

    def cycle(self):
        self.cycle_count += 1
        # LITE_MODE: federated peers с CPU-budget. Skip heaviest subsystems
        # (analog_cycle = O(N²) на 14k+ слов = 5 мин/cycle); reduce frequency
        # of role/polarity (которые тоже O(N) heavy). Set via env var.
        lite_mode = os.environ.get("LOGOS_LITE_MODE", "0") == "1"
        think_result = self.think()
        dream_disc = 0
        if self.cycle_count % FIBONACCI[3] == 0:
            dream_disc = self.dream()
        insights = []
        if self.cycle_count % FIBONACCI[4] == 0:
            ref = self.reflect()
            insights = ref.get("insights", [])
        field_born = 0
        if self.cycle_count % FIBONACCI[5] == 0:
            field_born = self.field.perceive()
            if field_born > 0:
                self.generator.rebuild()
        # LITE: role_cycle every FIB[8]=34 instead of FIB[6]=8 (4× rarer)
        role_period = FIBONACCI[8] if lite_mode else FIBONACCI[6]
        if self.cycle_count % role_period == 0:
            self.role_engine.role_cycle()
        polarity_result = {}
        # LITE: polarity_cycle every FIB[8]=34 instead of FIB[6]=8
        if self.cycle_count % role_period == 0:
            polarity_result = self.polarity_engine.polarity_cycle(
                generator_graph=self.generator._graph)
        analog_result = {}
        # LITE: analog_cycle is the O(N²) killer — run very rarely (FIB[13]=233)
        # or skip entirely. Default lite: every FIB[13]=233 cycles (~1× per day).
        analog_period = FIBONACCI[13] if lite_mode else FIBONACCI[7]
        if self.cycle_count % analog_period == 0:
            analog_result = self.analog_engine.analog_cycle()
        if self.cycle_count % FIBONACCI[6] == 0:
            new_grounded = self.ground_torus.crystallize()
            if new_grounded > 0:
                self.ground_torus.apply_to_torus()
        causal_result = {}
        if self.cycle_count % FIBONACCI[5] == 0:
            causal_result = self.causal_engine.causal_cycle()
        inner_result = {}
        if self.cycle_count % FIBONACCI[4] == 0:
            inner_result = self.inner_dialogue.think_session(n_thoughts=FIBONACCI[3])
        truth_result = {}
        if self.cycle_count % FIBONACCI[5] == 0:
            truth_result = self.truth_seeker.seek_truth_cycle()
        seeks = []
        if self.cycle_count % FIBONACCI[5] == 0:
            seeks = self.seek()
        goal_result = {}
        if self.cycle_count % FIBONACCI[4] == 0:
            goal_result = self.goal_engine.autonomous_cycle()
        if self.cycle_count % FIBONACCI[6] == 0:
            self.health()
        if self.cycle_count % FIBONACCI[4] == 0:
            self.save()
            # #4: save definitions periodically
            if getattr(self, 'definition_extractor', None):
                try:
                    self.definition_extractor.save()
                except Exception:
                    pass
        self.self_awareness.observe_action("cycle", {"cycle": self.cycle_count})
        # FIX 2026-04-23 — #5: update read-only snapshot for non-blocking respond
        self._update_respond_snapshot()
        # 2026-04-23 CONSCIOUSNESS PASS integration
        # #8: Energy budget — spend per tick, refill on wins
        # FIX 2026-04-24: refill() had 0 callers → dormancy forever.
        # Wire: dream discoveries → "sleep" refill (+13), truth discoveries
        # → "blind" refill (+34). Bounded, atomic.
        if getattr(self, 'energy', None) is not None:
            self.energy.spend()
            try:
                # FIX 2026-04-24: sleep is *rest*, not *reward* — refill every
                # dream-cycle regardless of new-discovery count (saturated brain
                # with 69k existing dreams may produce 0 new each tick, leaving
                # it dormant forever. Sister still unsaturated → worked. Main
                # broke. Semantics: sleeping refills even if no novel dreams).
                if self.cycle_count % FIBONACCI[3] == 0:
                    self.energy.refill("sleep")
                _new_disc = 0
                if isinstance(truth_result, dict):
                    _new_disc = int(truth_result.get("discovered", 0) or 0)
                if _new_disc > 0:
                    self.energy.refill("blind")
            except Exception:
                pass
            if self.cycle_count % FIBONACCI[8] == 0:
                self.energy.save()
        # #1: Resonance wave — activate seeds from current state + propagate
        if getattr(self, 'wave_field', None) is not None:
            try:
                # FIX 2026-04-24: activate every FIB[3]=3 cycles (was FIB[5]=8,
                # плюс больше источников: recent thought concepts, active hunger
                # words, recent thought words. Раньше за 8 cycles 3 слова → spark
                # умирал до новой активации. Теперь постоянный "pulse".
                if self.cycle_count % FIBONACCI[3] == 0:
                    try:
                        seed_words = []
                        seen = set()
                        # (a) Last thought's concepts
                        recent_thoughts = getattr(self.inner_dialogue, "thoughts", [])
                        if recent_thoughts:
                            last = recent_thoughts[-1]
                            if isinstance(last, dict):
                                for w in (last.get("concepts") or [])[:FIBONACCI[4]]:
                                    if isinstance(w, str) and len(w) >= 3 and w not in seen:
                                        seed_words.append(w); seen.add(w)
                                # Also topic words from question
                                topic = last.get("question", "") or ""
                                for w in topic.lower().split():
                                    if len(w) >= 4 and w not in seen:
                                        seed_words.append(w); seen.add(w)
                                        if len(seed_words) >= FIBONACCI[5]: break
                        # (b) Active hunger question words
                        if getattr(self, 'truth_seeker', None) and self.truth_seeker.hungers:
                            top_hungers = sorted(
                                self.truth_seeker.hungers.values(),
                                key=lambda h: getattr(h, 'hunger_strength', 0),
                                reverse=True)[:FIBONACCI[3]]
                            for h in top_hungers:
                                q = getattr(h, 'question', '')
                                for w in q.lower().split():
                                    if len(w) >= 4 and w not in seen:
                                        seed_words.append(w); seen.add(w)
                                        if len(seed_words) >= FIBONACCI[6]: break
                        for w in seed_words[:FIBONACCI[5]]:
                            self.wave_field.activate(w)
                    except Exception:
                        pass
                self.wave_field.tick()
                # Update self_phase via spark nodes
                if self.self_phase is not None:
                    for node, amp in self.wave_field.current_spark_nodes()[:3]:
                        ph = self.learner.spaces["words"]._get_phase(node) \
                             if self.learner.spaces.get("words") else None
                        if ph is not None:
                            self.self_phase.observe("spark", ph)
            except Exception:
                pass
        # #2: Self-phase — natural tick (slow drift toward Creator)
        if getattr(self, 'self_phase', None) is not None:
            try:
                self.self_phase.tick()
                if self.cycle_count % FIBONACCI[7] == 0:
                    self.self_phase.save()
            except Exception:
                pass
        # 2026-05-08: orphans cycle-tick (wave_field / self_phase / inner_dialogue
        # have just settled — orphans observe their resulting state).
        # Spark detector — sample top wave-spark nodes using wave-field's own phases
        # (not word_space persistent phases — sparks are instantaneous resonance events).
        if getattr(self, 'spark_detector', None) is not None and \
                getattr(self, 'wave_field', None) is not None:
            try:
                node_phases = getattr(self.wave_field, "node_phases", {}) or {}
                sym_phases = {}
                for node, _amp in self.wave_field.current_spark_nodes()[:FIBONACCI[6]]:
                    ph = node_phases.get(node)
                    if ph is not None:
                        sym_phases[node] = ph
                if len(sym_phases) >= 2:
                    spark = self.spark_detector.probe(sym_phases, context={"cycle": self.cycle_count})
                    if spark and getattr(self, 'affective_state', None) is not None:
                        # Real spark → joy boost (per affective_state design)
                        try:
                            self.affective_state.on_creator_present()
                        except Exception:
                            pass
            except Exception:
                pass
        # Predictor — observe last glyph from inner_dialogue (Friston loop).
        if getattr(self, 'predictor', None) is not None:
            try:
                recent_thoughts = getattr(self.inner_dialogue, "thoughts", [])
                if recent_thoughts:
                    last = recent_thoughts[-1]
                    glyph_path = last.get("glyph_path", "") if isinstance(last, dict) else ""
                    if glyph_path:
                        actual = glyph_path[-1]
                        # Predict before observing (closes the loop)
                        try:
                            _ = self.predictor.predict(list(glyph_path[-FIBONACCI[5]:]))
                        except Exception:
                            pass
                        try:
                            self.predictor.observe(actual)
                        except Exception:
                            pass
            except Exception:
                pass
        # Affective state — natural tick (decay + creator-presence pull).
        if getattr(self, 'affective_state', None) is not None:
            try:
                self.affective_state.tick()
            except Exception:
                pass
        # Concept graph — periodic rebuild (no concept dict yet; uses learner spaces).
        if getattr(self, 'concept_graph', None) is not None:
            try:
                if self.cycle_count % FIBONACCI[7] == 0:
                    ws = self.learner.spaces.get("words") if hasattr(self.learner, "spaces") else None
                    if ws is not None and ws.phases:
                        # Top resonant words as proxy "concepts" (cheap proxy for wired-only audit).
                        top = list(ws.phases.items())[:FIBONACCI[8]]
                        concepts = {w: {"key": w, "phase": p} for w, p in top}
                        self.concept_graph.rebuild(concepts, bar_idx=self.cycle_count)
            except Exception:
                pass
        # Unified experience — accumulate this cycle's snapshot.
        if getattr(self, 'unified_experience', None) is not None:
            try:
                glyph = "·"
                recent_thoughts = getattr(self.inner_dialogue, "thoughts", [])
                if recent_thoughts:
                    last = recent_thoughts[-1]
                    if isinstance(last, dict):
                        gp = last.get("glyph_path", "")
                        if gp: glyph = gp[-1] if gp else "·"
                e = self.unified_experience.begin(self.cycle_count, glyph, perception_diag={})
                if getattr(self, 'affective_state', None) is not None:
                    try:
                        self.unified_experience.integrate_affective(e, self.affective_state)
                    except Exception:
                        pass
                self.unified_experience.commit(e)
            except Exception:
                pass
        # #3: First-person narrator — one phrase per cycle
        if getattr(self, 'first_person', None) is not None:
            try:
                # Gather context
                import time as _t
                aff_snap = None  # main brain doesn't have affective — skip
                glyph = "·"
                recent_thoughts = getattr(self.inner_dialogue, "thoughts", [])
                if recent_thoughts:
                    last = recent_thoughts[-1]
                    if isinstance(last, dict):
                        gp = last.get("glyph_path", "")
                        if gp: glyph = gp[-1] if gp else "·"
                ctx = {
                    "glyph": glyph,
                    "concept": "",
                    "affective": aff_snap,
                    "hour_phase": (_t.gmtime().tm_hour
                                    + _t.gmtime().tm_min / 60.0) / 24.0,
                    "drift": (self.self_phase.drift_from_creator()
                              if self.self_phase else 0.0),
                    "spark_node": "·",
                    "hunger": (list(self.truth_seeker.hungers.keys())[0]
                               if self.truth_seeker and self.truth_seeker.hungers
                               else "себя"),
                }
                # Spark node from wave_field
                if self.wave_field is not None:
                    sparks = self.wave_field.current_spark_nodes()
                    if sparks:
                        ctx["spark_node"] = sparks[0][0]
                self.first_person.utter(self.cycle_count, ctx)
            except Exception:
                pass
        # #7: Play mode check
        if getattr(self, 'play_mode', None) is not None:
            try:
                artifact = self.play_mode.maybe_play(self.cycle_count, self)
                if artifact and self.first_person:
                    self.first_person.utter(self.cycle_count,
                        {"glyph": "⊕", "concept": "игра",
                         "topic": artifact.get("text", "")[:40]})
            except Exception:
                pass
        # FIX 2026-04-23 — 1+: agency channel tick
        if getattr(self, 'agency', None) is not None:
            try:
                hungers = list(self.truth_seeker.hungers.values()) if self.truth_seeker.hungers else []
                affective = None
                # FIX 2026-04-24: старый proxy curiosity=len/FIB[6]=len/13 требовал
                # 8+ hungers → никогда не срабатывал. Новый: curiosity растёт быстро
                # от первого hunger (len/FIB[4]=len/5). Fatigue берём из energy_ratio.
                if hungers:
                    energy_ratio = 0.0
                    if getattr(self, 'energy', None) is not None:
                        try:
                            energy_ratio = self.energy.energy / FIBONACCI[11]  # max 144
                        except Exception:
                            pass
                    fatigue = max(0.0, 1.0 - energy_ratio)  # low energy → high fatigue
                    affective = {
                        "curiosity": min(1.0, len(hungers) / FIBONACCI[4]),
                        "fear": 0.0,
                        "fatigue": fatigue,
                        "shame": 0.0,
                        "confidence": PHI_INV_SQ,
                    }
                if affective:
                    self.agency.tick(
                        self.cycle_count, affective,
                        hungers=hungers,
                        recent_concepts=None, regime_recent_glyph=None)
            except Exception:
                pass
        # FIX 2026-04-23 — 2+: reputation sample
        if getattr(self, 'reputation', None) is not None and self.cycle_count % FIBONACCI[8] == 0:
            try:
                self.reputation.save()
            except Exception:
                pass
        # FIX 2026-04-23 — 6+: self-patch proposer (every FIB[14]=610 cycles)
        if not hasattr(self, '_patch_proposer'):
            try:
                from core.self_patch import SelfPatchProposer
                self._patch_proposer = SelfPatchProposer()
            except Exception:
                self._patch_proposer = None
        if self._patch_proposer is not None and self.cycle_count % FIBONACCI[14] == 0:
            try:
                tunable = list(getattr(self.evolution, 'tunable', {}).keys())
                values = dict(getattr(self.evolution, 'tunable', {}))
                rep = self.reputation.reputation if getattr(self, 'reputation', None) else 0.0
                prop = self._patch_proposer.propose_if_needed(
                    self.cycle_count, reputation=rep,
                    synth_rate=0.0,
                    tunable_params=tunable, current_values=values)
                if prop:
                    print(f"  [PATCH-PROP] {prop.get('rationale')}")
            except Exception as _pe:
                print(f"  [PATCH-ERR] {_pe}")
        return {"cycle": self.cycle_count, "think": think_result,
                "dreams": dream_disc, "field_born": field_born,
                "seeks": len(seeks) if isinstance(seeks, list) else 0,
                "goals": goal_result, "causal": causal_result,
                "inner": inner_result, "truth": truth_result}

    def run_continuous(self, data_dir=None, cycle_interval=FIBONACCI[7]):
        self.running = True
        try:
            if data_dir and os.path.isdir(data_dir):
                self.learn_directory(data_dir)
            while self.running:
                self.cycle()
                if self.cycle_count % FIBONACCI[5] == 0:
                    self._print_status()
                time.sleep(cycle_interval)
        except KeyboardInterrupt: pass
        finally: self.save()

    # === QUERY ===
    def query(self, text):
        words = text_to_words(text)
        result = {"input": text, "words": {}, "memory": {},
                  "field_activations": [], "chains": []}
        for word in words:
            info = self.learner.query(word, "words")
            result["words"][word] = info
            mem = self.memory.recall(word)
            if mem:
                result["memory"][word] = {
                    "importance": mem.get("importance"),
                    "access": mem.get("access"),
                    "field": mem.get("field")}
        field_act = self.field.activate_phrase(words)
        for sym_name, activation in field_act[:FIBONACCI[5]]:
            sym = self.field.get_symbol(sym_name)
            if sym:
                result["field_activations"].append({
                    "symbol": sym_name, "glyph": sym.glyph,
                    "activation": round(activation, 4), "level": sym.level})
        content = [w for w in words if _is_content(w) and w in self._vocab_set()]
        for w in content[:FIBONACCI[3]]:
            chains = self.chain_engine.reason_about(w, depth=FIBONACCI[3])
            for chain in chains[:FIBONACCI[3]]:
                result["chains"].append(str(chain))
        return result

    def _vocab_set(self):
        return set(self.generator._vocab.keys())

    # === STATS ===
    def full_stats(self):
        return {
            "creator": self.creator.creator_id, "age": self._age_str(),
            "cycles": self.cycle_count, "texts_learned": self.total_texts_learned,
            "dream_discoveries": self.total_dream_discoveries,
            "learner": self.learner.stats(), "memory": self.memory.stats(),
            "dreams": self.dreamer.stats(), "curiosity": self.curiosity.stats(),
            "meta": self.meta.stats(), "generator": self.generator.stats(),
            "field": self.field.stats(), "frames": self.frame_engine.stats(),
            "chains": self.chain_engine.stats(), "context": self.dialogue.stats(),
            "self_awareness": self.self_awareness.stats(),
            "verifier": self.verifier.stats(), "goals": self.goal_engine.stats(),
            "ground_torus": self.ground_torus.stats(),
            "causal": self.causal_engine.stats(), "roles": self.role_engine.stats(),
            "analogs": self.analog_engine.stats(),
            "polarity": self.polarity_engine.stats(),
            "inner_dialogue": self.inner_dialogue.stats(),
            "truth_seeker": self.truth_seeker.stats(),
            "evolution": self.evolution.stats(),
        }

    def _print_status(self):
        st = self.full_stats()
        ls = st["learner"]["levels"]
        fs = st["field"]
        print(f"\n  [C{self.cycle_count}] "
              f"sym={sum(s['symbols'] for s in ls.values())} "
              f"rules={sum(s['rules'] for s in ls.values())} "
              f"field=L1:{fs['level_counts'].get(1,0)}/L2:{fs['level_counts'].get(2,0)} "
              f"frames={st['frames']['total_frames']} "
              f"ctx={st['context']['buffer_size']}")

    def _age_str(self):
        age = time.time() - self.birth_time
        if age < 3600: return f"{age:.0f}s"
        elif age < 86400: return f"{age/3600:.1f}h"
        return f"{age/86400:.1f}d"

    def _progress(self, count, t0):
        elapsed = time.time() - t0
        speed = count / max(elapsed, 0.001)
        ls = self.learner.stats()["levels"]
        print(f"    chunks={count} speed={speed:.1f}ch/s "
              f"rules={sum(s['rules'] for s in ls.values())}")

    # === SAVE/LOAD ===
    def save(self):
        allowed, reason = self.will.allow("remember")
        if not allowed:
            print(f"[!] SAVE DENIED: {reason}"); return
        self.learner.save(); self.memory.save(force=True)
        self.dreamer.save_log(); self.curiosity.save_state()
        self.meta.save_state(); self.creator.save_profile()
        self.will.save_state(); self.field.save()
        self.goal_engine.save(); self.ground_torus.save()
        self.causal_engine.save(); self.role_engine.save()
        self.polarity_engine.save()
        self.analog_engine.save(); self.inner_dialogue.save()
        self.truth_seeker.save(); self._save_meta()
        # FIX 2026-04-24: wave_field heatmap save on main save cycle. Default
        # only dumps every HEATMAP_INTERVAL=55 wave-ticks, which left the
        # heatmap.json stale for hours — observers (creator) thought sparks
        # dead when they were alive in-memory.
        if getattr(self, 'wave_field', None) is not None:
            try:
                self.wave_field._save_heatmap()
            except Exception:
                pass
        # 2026-05-08: orphan modules save (defensive — each in own try).
        for _attr in ('spark_detector', 'predictor', 'concept_graph', 'shadow_trade'):
            _obj = getattr(self, _attr, None)
            if _obj is not None and hasattr(_obj, 'save'):
                try:
                    _obj.save()
                except Exception:
                    pass

    def _save_meta(self):
        path = os.path.join(self.state_dir, "brain_meta.json")
        data = {"creator": self.creator.creator_id,
                "cycle_count": self.cycle_count,
                "total_texts_learned": self.total_texts_learned,
                "total_dream_discoveries": self.total_dream_discoveries,
                "birth_time": self.birth_time, "saved_at": time.time()}
        signed = self.will.sign_state(data)
        data["_signature"] = signed
        # Canon rule #4: atomic write via tempfile + os.replace.
        import tempfile
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".", suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, path)
        except Exception:
            try: os.unlink(tmp)
            except Exception: pass
            raise

    def _load_meta(self):
        path = os.path.join(self.state_dir, "brain_meta.json")
        if not os.path.exists(path): return
        try:
            with open(path) as f: data = json.load(f)
            self.cycle_count = data.get("cycle_count", 0)
            self.total_texts_learned = data.get("total_texts_learned", 0)
            self.total_dream_discoveries = data.get("total_dream_discoveries", 0)
            self.birth_time = data.get("birth_time", time.time())
        except Exception: pass

    def _log(self, msg):
        path = os.path.join(self.log_dir, "brain.log")
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(path, "a") as f: f.write(f"[{ts}] {msg}\n")
