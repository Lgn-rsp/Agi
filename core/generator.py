"""
generator.py v10.1 — Resonance Path Generation.

FIX C4: _best_next role gravity poluchayet current_result kak argument.

Vsyo cherez phi. Nikakoy lineynosti.
"""
import hashlib
import math
import random
from collections import defaultdict

from core.resonance_constants import (
    PHI, PHI_INV, PHI_INV_SQ, PHI_INV_CUBE, PHI_SQ, FIBONACCI,
    phi_phase_distance, phi_phase_resonance
)
from core.lang_detect import detect_lang, _CYR


_FUNCTION_WORDS_EN = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "am", "do", "does", "did", "has", "have", "had", "will",
    "would", "could", "should", "may", "might", "can", "shall",
    "and", "or", "but", "if", "then", "that", "this", "these",
    "those", "it", "its", "in", "on", "at", "to", "for", "of",
    "by", "with", "from", "as", "not", "no", "so", "up",
    "he", "she", "we", "they", "me", "him", "her", "us", "them",
    "my", "his", "our", "your", "their", "who", "whom",
    "which", "what", "where", "when", "how", "why",
    "also", "such", "than", "other", "more", "some", "any",
    "there", "here", "all", "each", "every", "both", "few",
    "many", "much", "own", "same", "just", "very", "too",
}
_FUNCTION_WORDS_RU = {
    "и", "в", "не", "на", "с", "что", "а", "к", "но", "по",
    "из", "у", "за", "о", "от", "до", "для", "при", "же",
    "бы", "ли", "так", "как", "это", "его", "её", "их",
    "он", "она", "оно", "они", "мы", "вы", "ты", "я",
    "мне", "нам", "вам", "им", "нас", "вас", "них",
    "мой", "твой", "наш", "ваш", "свой",
    "был", "была", "было", "были", "есть", "быть",
    "тот", "этот", "эта", "эти", "тем", "то", "те",
    "ещё", "уже", "ни", "да", "нет", "или",
    "где", "кто", "чем", "чего", "кого", "кому",
    "все", "всё", "когда", "если", "только", "более",
}

def _is_content(word):
    w = word.lower()
    if any(c in _CYR for c in w):
        return w not in _FUNCTION_WORDS_RU and len(w) > 2
    return w not in _FUNCTION_WORDS_EN and len(w) > 2

def _word_lang(word):
    return "ru" if any(c in _CYR for c in word.lower()) else "en"


class ResonanceGenerator:
    def __init__(self, phase_spaces, memory=None,
                 resonance_field=None, frame_engine=None,
                 chain_engine=None, dialogue_context=None):
        self.spaces = phase_spaces
        self.word_space = phase_spaces.get("words")
        self.pair_space = phase_spaces.get("pairs")
        self.trigram_space = phase_spaces.get("trigrams")
        self.memory = memory
        self.field = resonance_field
        self.frames = frame_engine
        self.chains = chain_engine
        self.context = dialogue_context

        self._graph = defaultdict(dict)
        self._freq = {}
        self._vocab = {}
        self._torus = {}
        self._pair_set = set()
        self._pair_freq = defaultdict(int)
        self._next_words = defaultdict(dict)
        self._prev_words = defaultdict(dict)
        self._median_freq = 1

        self._evo_field_weight = PHI_INV
        self._evo_spreading_weight = PHI_INV
        self._evo_frame_weight = PHI_INV
        self._evo_chain_depth = FIBONACCI[5]

        self._build()
        self._verifier = None
        self._role_engine = None
        self._causal_engine = None
        self.total_generated = 0

        modules = []
        if self.field: modules.append("field")
        if self.frames: modules.append("frames")
        if self.chains: modules.append("chains")
        if self.context: modules.append("context")
        print(f"[+] ResonanceGenerator v10.1: {len(self._vocab)} words, "
              f"{len(self._pair_set)} pairs, "
              f"modules=[{','.join(modules)}]")

    def _build(self):
        if not self.word_space:
            return
        for w, p in self.word_space.phases.items():
            self._vocab[w] = p
            t = self.word_space._torus.get(w)
            if t:
                self._torus[w] = t
        for key, rule in self.word_space.rules.items():
            a, b, c = rule["a"], rule["b"], rule["count"]
            self._freq[a] = self._freq.get(a, 0) + c
            self._freq[b] = self._freq.get(b, 0) + c
            score = math.log(1 + c) / math.log(PHI)
            self._graph[a][b] = max(self._graph[a].get(b, 0), score)
            self._graph[b][a] = max(self._graph[b].get(a, 0), score)
        if self.pair_space:
            for key, rule in self.pair_space.rules.items():
                for sym in [rule["a"], rule["b"]]:
                    if "_" in sym:
                        self._pair_set.add(sym)
                        parts = sym.split("_", 1)
                        if len(parts) == 2:
                            w1, w2 = parts
                            pair_score = math.log(1 + rule.get("count", 1)) / math.log(PHI)
                            self._pair_freq[sym] = max(self._pair_freq.get(sym, 0), rule.get("count", 1))
                            self._next_words[w1][w2] = max(self._next_words[w1].get(w2, 0), pair_score)
                            self._prev_words[w2][w1] = max(self._prev_words[w2].get(w1, 0), pair_score)
        freqs = sorted(self._freq.values())
        self._median_freq = freqs[len(freqs)//2] if freqs else 1

    def rebuild(self):
        self._graph.clear(); self._freq.clear(); self._vocab.clear()
        self._torus.clear(); self._pair_set.clear(); self._pair_freq.clear()
        self._next_words.clear(); self._prev_words.clear()
        self._build()
        if self.frames: self.frames.refresh()

    def _select_concepts(self, input_words, lang="en"):
        scores = {}
        if self.field:
            field_weight = self._evo_field_weight
            activated = self.field.activate_phrase(input_words)
            for sym_name, activation in activated[:FIBONACCI[6]]:
                source_words = self.field.get_source_words(sym_name)
                for w in source_words:
                    if w in self._vocab and _is_content(w):
                        lang_match = (lang == _word_lang(w)) or lang == "mix"
                        mult = PHI if lang_match else PHI_INV_CUBE
                        scores[w] = scores.get(w, 0) + activation * field_weight * mult
        has_content = False
        for w in input_words:
            if w in self._vocab and _is_content(w):
                freq = self._freq.get(w, 1)
                info = math.log(1 + self._median_freq / max(freq, 1)) / math.log(PHI)
                scores[w] = scores.get(w, 0) + max(info, PHI_INV) * PHI
                has_content = True
        if not has_content:
            for w in input_words:
                if w in self._vocab:
                    freq = self._freq.get(w, 1)
                    info = math.log(1 + self._median_freq / max(freq, 1)) / math.log(PHI)
                    scores[w] = scores.get(w, 0) + max(info, PHI_INV)
        if self.context:
            context_bonus = self.context.get_context_bonus()
            for w, bonus in context_bonus.items():
                if w in self._vocab:
                    lang_match = (lang == _word_lang(w)) or lang == "mix"
                    if lang_match:
                        scores[w] = scores.get(w, 0) + bonus * PHI_INV_SQ
        extra = {}
        input_set = set(input_words)
        spreading_weight = self._evo_spreading_weight
        for w in input_words:
            if w not in self._graph: continue
            base_score = scores.get(w, PHI_INV)
            for neighbor, edge in self._graph[w].items():
                if _is_content(neighbor) and neighbor not in input_set:
                    lang_match = (lang == _word_lang(neighbor)) or lang == "mix"
                    if lang_match:
                        extra[neighbor] = extra.get(neighbor, 0) + edge * base_score * spreading_weight
        for w, s in extra.items():
            scores[w] = scores.get(w, 0) + s
        for w in list(scores.keys()):
            if w not in input_set:
                is_neighbor = any(w in self._graph.get(iw, {}) for iw in input_words if iw in self._graph)
                if not is_neighbor:
                    scores[w] *= PHI_INV_CUBE
        if self.context:
            prev_words = self.context.get_recent_output_words()
            if prev_words:
                for w in list(scores.keys()):
                    if w in prev_words and w not in input_set:
                        scores[w] *= PHI_INV_CUBE
        input_set = set(input_words)
        all_scores = sorted(scores.values(), reverse=True)
        floor_score = all_scores[0] * PHI if all_scores else PHI_SQ
        anchored = []
        floating = []
        for w, s in scores.items():
            if w in input_set and _is_content(w) and w in self._vocab:
                anchor_score = max(s, floor_score) * PHI
                anchored.append((w, anchor_score))
                scores[w] = anchor_score
            else:
                floating.append((w, s))
        anchored.sort(key=lambda x: x[1], reverse=True)
        floating.sort(key=lambda x: x[1], reverse=True)
        concepts = anchored[:FIBONACCI[4]] + floating
        concepts = concepts[:FIBONACCI[6]]
        return concepts, scores

    def _validate_concepts(self, concepts, input_words):
        if not self.chains or not concepts: return concepts
        validated = []
        input_set = set(input_words)
        input_content = [w for w in input_words if w in self._vocab and _is_content(w)]
        if not input_content: return concepts
        chain_depth = self._evo_chain_depth
        for word, score in concepts:
            if word in input_set:
                validated.append((word, score)); continue
            is_direct = False
            for iw in input_content:
                if word in self._graph.get(iw, {}):
                    is_direct = True; break
            if is_direct:
                validated.append((word, score * PHI)); continue
            valid = False
            for iw in input_content[:FIBONACCI[3]]:
                chain = self.chains.infer(iw, word, max_depth=chain_depth)
                if chain and chain.valid:
                    validated.append((word, score)); valid = True; break
            if not valid:
                validated.append((word, score * PHI_INV_SQ))
        if self._verifier and len(validated) >= 3:
            content_words = [w for w, s in validated if _is_content(w)]
            if len(content_words) >= 2:
                vr = self._verifier.verify(content_words[:FIBONACCI[4]])
                if vr.score > PHI_INV_SQ:
                    verified_words = set()
                    for ev in vr.evidence:
                        if ev.get("type") in ("closed_triangle", "closed_quad"):
                            for w in ev.get("words", []): verified_words.add(w)
                    if verified_words:
                        validated = [(w, s * PHI if w in verified_words else s) for w, s in validated]
        validated.sort(key=lambda x: x[1], reverse=True)
        return validated[:FIBONACCI[6]]

    def _assemble(self, concepts, lang="en"):
        if not concepts or len(concepts) < 2: return None
        concept_words = set(w for w, s in concepts)
        used_concepts = set()
        result = []
        input_content = [w for w, s in concepts if w in self._vocab and _is_content(w)]
        seed = self._best_seed(concepts, lang, input_words=input_content)
        if not seed: seed = concepts[0][0]
        result.append(seed); used_concepts.add(seed); current = seed
        max_words = FIBONACCI[7]
        for step in range(max_words - 1):
            input_phases = [self._vocab[w] for w, s in concepts[:FIBONACCI[5]] if w in self._vocab]
            next_word = self._best_next(current, concept_words, used_concepts, lang, input_phases=input_phases, current_result=result)
            if next_word:
                result.append(next_word)
                if _is_content(next_word): used_concepts.add(next_word)
                current = next_word
            else:
                bridge_word, target = self._find_bridge(current, concept_words, used_concepts, lang)
                if bridge_word and target:
                    result.append(bridge_word); result.append(target)
                    used_concepts.add(target); current = target
                else:
                    remaining = [w for w, s in concepts if w not in used_concepts]
                    if remaining:
                        result.append("и" if lang == "ru" else "and")
                        next_c = remaining[0]; result.append(next_c)
                        used_concepts.add(next_c); current = next_c
                    else: break
            if used_concepts >= concept_words:
                tail = self._best_next(current, set(), set(), lang, current_result=result)
                if tail and tail not in result[-2:]: result.append(tail)
                break
        return result if len(result) >= 3 else None

    def _best_seed(self, concepts, lang, input_words=None):
        best_word = None; best_score = -1
        if input_words:
            for word in input_words:
                if word not in self._vocab or not _is_content(word): continue
                next_count = len(self._next_words.get(word, {}))
                if next_count > 0:
                    seed_score = PHI * PHI + next_count * PHI_INV_SQ
                    if seed_score > best_score: best_score = seed_score; best_word = word
        if best_word: return best_word
        if input_words:
            for word in input_words:
                if word in self._vocab: return word
        for word, concept_score in concepts[:FIBONACCI[5]]:
            next_count = len(self._next_words.get(word, {}))
            prev_count = len(self._prev_words.get(word, {}))
            if next_count > 0:
                seed_score = concept_score * PHI_INV + next_count * PHI_INV_SQ - prev_count * PHI_INV_CUBE
                if seed_score > best_score: best_score = seed_score; best_word = word
        return best_word

    def _best_next(self, current, target_concepts, used, lang,
                    input_phases=None, current_result=None):
        """FIX C4: current_result peredaetsya kak argument."""
        candidates = self._next_words.get(current, {})
        if not candidates: return None
        best_word = None; best_score = -1
        for next_w, pair_score in candidates.items():
            if _is_content(next_w) and next_w in used: continue
            if lang != "mix" and _word_lang(next_w) != lang: continue
            score = pair_score
            if input_phases and next_w in self._vocab:
                next_phase = self._vocab[next_w]
                gravity = 0.0
                for inp_phase in input_phases:
                    dist = phi_phase_distance(next_phase, inp_phase)
                    gravity += phi_phase_resonance(dist)
                if input_phases: gravity /= len(input_phases)
                score *= (PHI_INV_SQ + gravity * PHI_INV)
            if next_w in target_concepts and next_w not in used:
                score *= PHI_SQ
            # FIX C4: role gravity s current_result
            if self._role_engine and current_result:
                role_phases_so_far = []
                for w in current_result:
                    rp = self._role_engine.get_role_phase(w)
                    if rp is not None: role_phases_so_far.append(rp)
                expected_role = self._role_engine.suggest_next_role(role_phases_so_far)
                actual_role = self._role_engine.get_role_phase(next_w)
                if actual_role is not None:
                    role_dist = phi_phase_distance(expected_role, actual_role)
                    role_res = phi_phase_resonance(role_dist)
                    score *= (PHI_INV_SQ + role_res * PHI_INV_SQ)
            if not _is_content(next_w):
                next_next = self._next_words.get(next_w, {})
                has_target = any(w in target_concepts and w not in used for w in next_next)
                score *= PHI_INV if has_target else PHI_INV_CUBE
            # F (2026-04-24): ground in trade-outcome feedback. Words that
            # appeared during winning shadow-trades get weight boost.
            # weight in [PHI_INV_CUBE, 1.0] — never silences unknown words.
            try:
                from core import grounded_vocabulary as _gv
                score *= _gv.get_weight(next_w)
            except Exception:
                pass
            if score > best_score: best_score = score; best_word = next_w
        return best_word

    def _find_bridge(self, current, target_concepts, used, lang):
        candidates = self._next_words.get(current, {})
        for bridge_w, score1 in sorted(candidates.items(), key=lambda x: x[1], reverse=True):
            if _is_content(bridge_w): continue
            next_after = self._next_words.get(bridge_w, {})
            for target_w, score2 in sorted(next_after.items(), key=lambda x: x[1], reverse=True):
                if target_w in target_concepts and target_w not in used:
                    if lang == "mix" or _word_lang(target_w) == lang:
                        return bridge_w, target_w
        return None, None

    def _polish(self, words):
        if not words: return words
        result = [words[0]]
        for w in words[1:]:
            if w != result[-1]: result.append(w)
        if self._torus and len(result) >= 3:
            for _ in range(FIBONACCI[3]):
                swapped = False
                for i in range(len(result) - 1):
                    pk_fwd = f"{result[i]}_{result[i+1]}"
                    pk_rev = f"{result[i+1]}_{result[i]}"
                    fwd_freq = self._pair_freq.get(pk_fwd, 0)
                    rev_freq = self._pair_freq.get(pk_rev, 0)
                    if rev_freq > fwd_freq * PHI:
                        result[i], result[i+1] = result[i+1], result[i]
                        swapped = True
                if not swapped: break
        return result

    def generate(self, intent=None, max_words=FIBONACCI[7], temperature=PHI_INV):
        if len(self._vocab) < 5: return None
        input_words = []
        if intent:
            input_words = intent.get("seed_from_input", [])
            if not input_words and intent.get("seed"): input_words = [intent["seed"]]
        lang = detect_lang(" ".join(input_words))
        concepts, scores = self._select_concepts(input_words, lang)
        if not concepts: return None
        concepts = self._validate_concepts(concepts, input_words)

        # FIX 2026-04-23 — #1: anti-attractor STM penalty at PHRASE level.
        # Word-level penalty уже есть (line 189-194), но она не ломает
        # phrase-attractors типа "another neuron comes into close apposition"
        # которые фразой живут в phase-space. Track recent trigrams;
        # если candidate может продолжить recent trigram — penalty × PHI_INV_SQ.
        if not hasattr(self, '_recent_trigrams'):
            from collections import deque
            self._recent_trigrams = deque(maxlen=FIBONACCI[8])  # 34 last trigrams
        recent_trigrams = set(self._recent_trigrams)
        if recent_trigrams:
            # Penalize words that complete a recent trigram prefix.
            # Build prefix→continuation map from recent trigrams.
            prefix_completions = {}
            for tri in recent_trigrams:
                if len(tri) >= 3:
                    prefix_completions.setdefault((tri[0], tri[1]), set()).add(tri[2])
                    prefix_completions.setdefault((tri[1],), set()).add(tri[2])
            penalized = {}
            # Last 2 words of input serve as rolling prefix
            last2 = tuple(input_words[-2:]) if len(input_words) >= 2 else None
            last1 = (input_words[-1],) if input_words else None
            targets = set()
            if last2 and last2 in prefix_completions:
                targets |= prefix_completions[last2]
            if last1 and last1 in prefix_completions:
                targets |= prefix_completions[last1]
            if targets:
                concepts = [(w, s * PHI_INV_SQ if w in targets else s)
                            for w, s in concepts]
                concepts.sort(key=lambda x: x[1], reverse=True)

        if temperature > PHI_INV_CUBE:
            noised = [(w, s + random.random() * temperature * s * PHI_INV_SQ) for w, s in concepts]
            noised.sort(key=lambda x: x[1], reverse=True)
            concepts = noised
        words = self._assemble(concepts, lang)
        if not words: return None
        words = words[:max_words]
        words = self._polish(words)
        # Записываем выходные trigrams в STM для следующих calls
        if hasattr(self, '_recent_trigrams') and len(words) >= 3:
            for i in range(len(words) - 2):
                self._recent_trigrams.append((words[i], words[i+1], words[i+2]))
        if self.context:
            out_concepts = [(w, scores.get(w, 1.0)) for w in words if _is_content(w)]
            self.context.new_turn([(w, s) for w, s in concepts[:FIBONACCI[5]]] + out_concepts)
        self.total_generated += 1
        return {"text": " ".join(words), "words": words, "coherence": round(self._coherence(words), 4),
                "length": len(words), "intent": intent, "concepts": [w for w, s in concepts[:FIBONACCI[5]]], "lang": lang}

    def respond(self, input_text, max_words=FIBONACCI[7]):
        input_words = input_text.lower().split()
        known = [w for w in input_words if w in self._vocab]
        if not known:
            for uw in input_words:
                h = int(hashlib.sha256(uw.encode('utf-8')).hexdigest()[:8], 16)
                tp = (h / (2**32) * PHI_INV) % 1.0
                best_w, best_d = None, 1.0
                for w, p in self._vocab.items():
                    d = phi_phase_distance(p, tp)
                    if d < best_d: best_d = d; best_w = w
                if best_w: known.append(best_w)
                if len(known) >= FIBONACCI[3]: break
        lang = detect_lang(" ".join(input_words))
        all_input = known + [w for w in input_words if w not in known]
        concepts, scores = self._select_concepts(all_input, lang)
        if not concepts: return None
        concepts = self._validate_concepts(concepts, input_words)
        content_start = [w for w in known if _is_content(w) and w in self._vocab]
        concept_words = set(w for w, s in concepts)
        used = set(content_start); result = list(content_start)
        if result: current = result[-1]
        else:
            seed = self._best_seed(concepts, lang, input_words=known)
            if not seed: return None
            result = [seed]; used = {seed}; current = seed
        remaining_budget = max_words - len(result)
        input_phases = [self._vocab[w] for w, s in concepts[:FIBONACCI[5]] if w in self._vocab]
        for step in range(remaining_budget):
            next_word = self._best_next(current, concept_words, used, lang, input_phases=input_phases, current_result=result)
            if next_word:
                result.append(next_word)
                if _is_content(next_word): used.add(next_word)
                current = next_word
            else:
                bridge_word, target = self._find_bridge(current, concept_words, used, lang)
                if bridge_word and target:
                    result.append(bridge_word); result.append(target); used.add(target); current = target
                else: break
        result = self._polish(result)
        if self.context:
            out_concepts = [(w, scores.get(w, 1.0)) for w in result if _is_content(w)]
            self.context.new_turn([(w, s) for w, s in concepts[:FIBONACCI[5]]] + out_concepts)
        self.total_generated += 1
        return {"text": " ".join(result), "words": result, "coherence": round(self._coherence(result), 4),
                "length": len(result), "concepts": [w for w, s in concepts[:FIBONACCI[5]]], "lang": lang}

    def _coherence(self, words):
        if len(words) < 2: return 0.0
        hits = 0
        for i in range(len(words) - 1):
            pk = f"{words[i]}_{words[i+1]}"
            if pk in self._pair_set: hits += 1.0
            else:
                a, b = words[i], words[i+1]
                rk = f"{a}|{b}" if a < b else f"{b}|{a}"
                if self.word_space and rk in self.word_space.rules: hits += 0.5
        return hits / (len(words) - 1)

    def stats(self):
        ctx = self.context.stats() if self.context else {}
        return {"total_generated": self.total_generated, "vocabulary": len(self._vocab),
                "pair_index": len(self._pair_set), "next_words_index": len(self._next_words),
                "rules": len(self.word_space.rules) if self.word_space else 0,
                "field": self.field is not None,
                "frames": self.frames.stats() if self.frames else {},
                "chains": self.chains.stats() if self.chains else {},
                "context": ctx}
