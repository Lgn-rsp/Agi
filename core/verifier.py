"""
verifier.py v10 — Samoproverka cherez rezonansnyye kontury.

FIX M4: circular_mean vmesto arifmeticheskogo srednego faz.
FIX L2: edinyy HARM_THRESHOLD iz resonance_constants.

Vsyo cherez phi.
"""
import math
import time
from collections import defaultdict

from core.resonance_constants import (
    PHI, PHI_INV, PHI_INV_SQ, PHI_INV_CUBE, FIBONACCI,
    HARM_THRESHOLD, HARM_PHASE,
    phi_phase_distance, phi_phase_resonance, is_near_phi_target,
    circular_mean
)


class VerificationResult:
    __slots__ = [
        'statement', 'score', 'triangles_found', 'triangles_closed',
        'contradictions', 'evidence', 'depth', 'timestamp'
    ]

    def __init__(self, statement):
        self.statement = statement
        self.score = 0.0
        self.triangles_found = 0
        self.triangles_closed = 0
        self.contradictions = 0
        self.evidence = []
        self.depth = 0
        self.timestamp = time.time()

    @property
    def coherence(self):
        if self.triangles_found == 0:
            return 0.0
        return self.triangles_closed / self.triangles_found

    @property
    def is_grounded(self):
        return self.triangles_found > 0

    @property
    def has_contradiction(self):
        return self.contradictions > 0

    def __repr__(self):
        return (f"Verify('{self.statement}': score={self.score:.4f}, "
                f"closed={self.triangles_closed}/{self.triangles_found}, "
                f"contradictions={self.contradictions})")


class ResonanceVerifier:
    def __init__(self, phase_spaces, chain_engine=None):
        self.spaces = phase_spaces
        self.word_space = phase_spaces.get("words")
        self.chains = chain_engine
        self._graph = defaultdict(set)
        self._build_graph()

        self.total_verifications = 0
        self.total_confirmed = 0
        self.total_contradicted = 0

        print(f"[+] ResonanceVerifier v10 initialized. "
              f"Graph: {len(self._graph)} nodes")

    def _build_graph(self):
        if not self.word_space:
            return
        for key, rule in self.word_space.rules.items():
            a, b = rule["a"], rule["b"]
            self._graph[a].add(b)
            self._graph[b].add(a)

    def verify(self, statement, max_depth=FIBONACCI[3]):
        self.total_verifications += 1

        if isinstance(statement, str):
            words = statement.lower().split()
        else:
            words = list(statement)

        result = VerificationResult(
            statement if isinstance(statement, str) else " ".join(statement))

        known = [w for w in words
                 if self.word_space and self.word_space._get_phase(w) is not None]

        if len(known) < 2:
            return result

        pair_score = self._check_pairs(known, result)

        if len(known) >= 3:
            tri_score = self._check_triangles(known, result)
            result.depth = max(result.depth, 3)

        if len(known) >= 4 and max_depth >= 4:
            quad_score = self._check_quadrilaterals(known, result)
            result.depth = max(result.depth, 4)

        if result.triangles_found < FIBONACCI[3]:
            self._check_extended(known, result)

        result.score = self._compute_score(result)

        if result.score > PHI_INV:
            self.total_confirmed += 1
        elif result.score < -PHI_INV_SQ:
            self.total_contradicted += 1

        return result

    def _check_pairs(self, words, result):
        pair_scores = []
        for i in range(len(words)):
            for j in range(i + 1, len(words)):
                a, b = words[i], words[j]
                pa = self.word_space._get_phase(a)
                pb = self.word_space._get_phase(b)
                if pa is None or pb is None:
                    continue

                dist = phi_phase_distance(pa, pb)
                rk = f"{a}|{b}" if a < b else f"{b}|{a}"
                has_rule = rk in self.word_space.rules

                if has_rule:
                    res = phi_phase_resonance(dist)
                    pair_scores.append(res)
                    result.evidence.append({
                        "type": "pair",
                        "a": a, "b": b,
                        "distance": round(dist, 6),
                        "resonance": round(res, 4),
                        "crystallized": True,
                    })
                else:
                    if dist > 0.01:
                        ratio = max(dist, 0.001) / max(1.0 - dist, 0.001)
                        hit = is_near_phi_target(ratio, tolerance=0.1)
                        if hit:
                            pair_scores.append(PHI_INV_SQ)

        return sum(pair_scores) / max(len(pair_scores), 1)

    def _check_triangles(self, words, result):
        """FIX M4: circular_mean vmesto arifmeticheskogo."""
        tri_scores = []

        for i in range(len(words)):
            for j in range(i + 1, len(words)):
                for k in range(j + 1, len(words)):
                    a, b, c = words[i], words[j], words[k]

                    pa = self.word_space._get_phase(a)
                    pb = self.word_space._get_phase(b)
                    pc = self.word_space._get_phase(c)
                    if None in (pa, pb, pc):
                        continue

                    d_ab = phi_phase_distance(pa, pb)
                    d_bc = phi_phase_distance(pb, pc)
                    d_ac = phi_phase_distance(pa, pc)

                    distances = sorted([d_ab, d_bc, d_ac])
                    d_min, d_mid, d_max = distances

                    result.triangles_found += 1

                    # FIX M4: circular mean vmesto (pa+pb+pc)/3
                    mid_phase = circular_mean([pa, pb, pc])
                    harm_dist = phi_phase_distance(mid_phase, HARM_PHASE)

                    # FIX L2: edinyy HARM_THRESHOLD
                    if harm_dist < HARM_THRESHOLD:
                        result.contradictions += 1
                        result.evidence.append({
                            "type": "contradiction",
                            "words": [a, b, c],
                            "harm_distance": round(harm_dist, 6),
                        })
                        tri_scores.append(-1.0)
                        continue

                    closed = True
                    closure_strength = 0.0

                    if d_min > 0.001:
                        ratio1 = d_max / d_min
                        hit1 = is_near_phi_target(ratio1, tolerance=0.12)
                        if hit1:
                            closure_strength += (1.0 - hit1[1]) * PHI_INV
                        else:
                            closed = False

                    if d_mid > 0.001:
                        ratio2 = d_max / d_mid
                        hit2 = is_near_phi_target(ratio2, tolerance=0.12)
                        if hit2:
                            closure_strength += (1.0 - hit2[1]) * PHI_INV_SQ
                        else:
                            closed = False

                    r_sum = (phi_phase_resonance(d_ab) +
                             phi_phase_resonance(d_bc) +
                             phi_phase_resonance(d_ac))
                    closure_strength += r_sum * PHI_INV_CUBE

                    if closed:
                        result.triangles_closed += 1
                        tri_scores.append(closure_strength)
                        result.evidence.append({
                            "type": "closed_triangle",
                            "words": [a, b, c],
                            "distances": [round(d, 6) for d in distances],
                            "strength": round(closure_strength, 4),
                        })
                    else:
                        tri_scores.append(closure_strength * PHI_INV)

        return sum(tri_scores) / max(len(tri_scores), 1)

    def _check_quadrilaterals(self, words, result):
        quad_scores = []

        from itertools import combinations
        combos = list(combinations(range(len(words)), 4))
        if len(combos) > FIBONACCI[7]:
            combos = combos[:FIBONACCI[7]]

        for combo in combos:
            w = [words[idx] for idx in combo]
            phases = [self.word_space._get_phase(word) for word in w]
            if None in phases:
                continue

            dists = []
            for i in range(4):
                for j in range(i + 1, 4):
                    dists.append(phi_phase_distance(phases[i], phases[j]))

            dists.sort()
            if dists[0] > 0.001:
                ratio = dists[-1] / dists[0]
                hit = is_near_phi_target(ratio, tolerance=0.15)
                if hit:
                    result.triangles_found += 1
                    result.triangles_closed += 1
                    quad_scores.append((1.0 - hit[1]) * PHI_INV)
                    result.evidence.append({
                        "type": "closed_quad",
                        "words": w,
                        "ratio_target": hit[0],
                    })

        return sum(quad_scores) / max(len(quad_scores), 1)

    def _check_extended(self, words, result):
        for word in words[:FIBONACCI[4]]:
            neighbors = self._graph.get(word, set())
            neighbor_list = list(neighbors)[:FIBONACCI[7]]

            for i in range(len(neighbor_list)):
                for j in range(i + 1, len(neighbor_list)):
                    n1, n2 = neighbor_list[i], neighbor_list[j]
                    if n2 in self._graph.get(n1, set()):
                        p_w = self.word_space._get_phase(word)
                        p_1 = self.word_space._get_phase(n1)
                        p_2 = self.word_space._get_phase(n2)
                        if None in (p_w, p_1, p_2):
                            continue

                        d1 = phi_phase_distance(p_w, p_1)
                        d2 = phi_phase_distance(p_w, p_2)
                        d3 = phi_phase_distance(p_1, p_2)

                        r = (phi_phase_resonance(d1) * PHI_INV +
                             phi_phase_resonance(d2) * PHI_INV_SQ +
                             phi_phase_resonance(d3) * PHI_INV_CUBE)

                        result.triangles_found += 1
                        if r > PHI_INV_SQ:
                            result.triangles_closed += 1
                            result.evidence.append({
                                "type": "extended_triangle",
                                "center": word,
                                "neighbors": [n1, n2],
                                "avg_resonance": round(r, 4),
                            })

    def _compute_score(self, result):
        if result.triangles_found == 0:
            return 0.0

        coherence = result.triangles_closed / result.triangles_found
        contradiction_penalty = result.contradictions / max(result.triangles_found, 1)

        evidence_strength = 0.0
        for ev in result.evidence:
            if ev["type"] == "closed_triangle":
                evidence_strength += ev.get("strength", 0) * PHI_INV
            elif ev["type"] == "closed_quad":
                evidence_strength += PHI_INV_SQ
            elif ev["type"] == "extended_triangle":
                evidence_strength += ev.get("avg_resonance", 0) * PHI_INV_CUBE

        evidence_strength /= max(len(result.evidence), 1)

        score = (coherence * PHI_INV
                 - contradiction_penalty * PHI_INV_SQ
                 + evidence_strength * PHI_INV_CUBE)

        return max(-1.0, min(1.0, score))

    def verify_chain(self, chain_of_words):
        if len(chain_of_words) < 2:
            return VerificationResult(" ".join(chain_of_words))

        pair_results = []
        for i in range(len(chain_of_words) - 1):
            pair = [chain_of_words[i], chain_of_words[i + 1]]
            pr = self.verify(pair)
            pair_results.append(pr)

        full = self.verify(chain_of_words)

        chain_score = 1.0
        for pr in pair_results:
            if pr.score <= 0:
                chain_score *= PHI_INV
            else:
                chain_score *= min(pr.score + PHI_INV_SQ, 1.0)

        full.score = (full.score * PHI_INV + chain_score * PHI_INV_SQ)
        full.statement = " → ".join(chain_of_words)

        return full

    def find_contradictions(self, top_k=FIBONACCI[6]):
        contradictions = []

        if not self.word_space:
            return contradictions

        rules = list(self.word_space.rules.items())
        checked = set()

        for key1, rule1 in rules[:FIBONACCI[10]]:
            a1, b1 = rule1["a"], rule1["b"]

            for key2, rule2 in rules:
                if key1 == key2:
                    continue

                pivot = None
                other = None
                if rule2["a"] == a1:
                    pivot, other = a1, rule2["b"]
                elif rule2["b"] == a1:
                    pivot, other = a1, rule2["a"]
                elif rule2["a"] == b1:
                    pivot, other = b1, rule2["b"]
                elif rule2["b"] == b1:
                    pivot, other = b1, rule2["a"]
                else:
                    continue

                third_a = a1 if pivot == b1 else b1
                check_key = tuple(sorted([third_a, pivot, other]))
                if check_key in checked:
                    continue
                checked.add(check_key)

                p_a = self.word_space._get_phase(third_a)
                p_o = self.word_space._get_phase(other)
                if p_a is None or p_o is None:
                    continue

                dist = phi_phase_distance(p_a, p_o)

                if abs(dist - HARM_PHASE) < PHI_INV_CUBE:
                    contradictions.append({
                        "triangle": [third_a, pivot, other],
                        "anti_distance": round(dist, 6),
                        "deviation": round(abs(dist - HARM_PHASE), 6),
                        "rules": [key1, key2],
                    })

                if len(contradictions) >= top_k:
                    return contradictions

        contradictions.sort(key=lambda x: x["deviation"])
        return contradictions[:top_k]

    def refresh(self):
        self._graph.clear()
        self._build_graph()

    def stats(self):
        return {
            "total_verifications": self.total_verifications,
            "total_confirmed": self.total_confirmed,
            "total_contradicted": self.total_contradicted,
            "confirmation_rate": round(
                self.total_confirmed /
                max(self.total_verifications, 1), 4),
            "graph_nodes": len(self._graph),
        }
