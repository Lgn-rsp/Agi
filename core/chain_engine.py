"""
chain_engine.py v10.1 — Deduktsiya cherez phi-tranzitivnost.

FIX C3: _content_graph teper stroitsya iz word_space rules.
FIX C2: harm_dist ispolzuyet circular_mean vmesto arifmeticheskogo.
FIX S6: 0.1 hardcoded -> HARM_THRESHOLD.

Vsyo cherez phi.
"""
import math
from collections import deque

from core.resonance_constants import (
    PHI, PHI_INV, PHI_INV_SQ, PHI_INV_CUBE, FIBONACCI,
    HARM_THRESHOLD,
    phi_phase_distance, phi_phase_resonance, is_near_phi_target,
    circular_mean
)


class ResonanceChain:
    __slots__ = ['steps', 'start', 'end', 'total_distance',
                 'phi_target', 'valid', 'strength']

    def __init__(self, steps, start, end, total_distance,
                 phi_target, valid, strength):
        self.steps = steps
        self.start = start
        self.end = end
        self.total_distance = total_distance
        self.phi_target = phi_target
        self.valid = valid
        self.strength = strength

    def __repr__(self):
        chain = " -> ".join([self.start] + [s[1] for s in self.steps])
        v = "VALID" if self.valid else "invalid"
        return f"Chain({chain}, {v}, target={self.phi_target})"


class ChainEngine:
    def __init__(self, phase_spaces):
        self.spaces = phase_spaces
        self.word_space = phase_spaces.get("words")
        self.total_inferences = 0
        self.valid_inferences = 0
        self._content_graph = None
        print(f"[+] ChainEngine v10.1 initialized.")

    def _ensure_content_graph(self):
        """FIX C3: Lazy build content-only graph iz word_space rules."""
        if self._content_graph is not None:
            return
        self._content_graph = {}
        if not self.word_space:
            return
        try:
            from core.generator import _is_content
        except ImportError:
            return

        # FIX C3: stroim iz word_space.rules, ne iz pustogo self._graph
        for key, rule in self.word_space.rules.items():
            a, b = rule["a"], rule["b"]
            if _is_content(a):
                if a not in self._content_graph:
                    self._content_graph[a] = set()
                if _is_content(b):
                    self._content_graph[a].add(b)
            if _is_content(b):
                if b not in self._content_graph:
                    self._content_graph[b] = set()
                if _is_content(a):
                    self._content_graph[b].add(a)
        print(f"  [ChainEngine] Content-only graph: {len(self._content_graph)} nodes")

    def infer(self, start, end, max_depth=FIBONACCI[4]):
        if not self.word_space:
            return None

        key1 = f"{start}|{end}" if start < end else f"{end}|{start}"
        if key1 in self.word_space.rules:
            rule = self.word_space.rules[key1]
            dist = phi_phase_distance(
                self.word_space._get_phase(start) or 0,
                self.word_space._get_phase(end) or 0)
            self.total_inferences += 1
            self.valid_inferences += 1
            return ResonanceChain(
                steps=[(start, end, dist, rule.get("phi_target", "?"))],
                start=start, end=end,
                total_distance=dist,
                phi_target=rule.get("phi_target", "?"),
                valid=True, strength=rule.get("count", 1))

        chain = self._find_chain(start, end, max_depth)
        if chain:
            self.total_inferences += 1
            if chain.valid:
                self.valid_inferences += 1
            return chain
        return None

    def _find_chain(self, start, end, max_depth):
        """Single shortest-path chain (legacy). Use _find_chains for multi-path."""
        chains = self._find_chains(start, end, max_depth, top_k=1)
        return chains[0] if chains else None

    def _build_graph(self):
        """Build adjacency from word_space rules (cached on first call)."""
        if hasattr(self, "_graph_cache"):
            return self._graph_cache
        graph = {}
        for key, rule in self.word_space.rules.items():
            a, b = rule["a"], rule["b"]
            graph.setdefault(a, {})[b] = rule
            graph.setdefault(b, {})[a] = rule
        self._graph_cache = graph
        return graph

    def _find_chains(self, start, end, max_depth, top_k=FIBONACCI[4]):
        """K-shortest-paths до end. Возвращает list валидных ResonanceChain,
        отсортированных по strength*validity descending.

        FIX 2026-04-23: раньше BFS останавливался на первом попадании и возвращал
        одну цепь → система имела только одну «точку зрения» на вывод. Теперь
        до `top_k` независимых цепей собирается — каждую можно валидировать
        отдельно, а combined evidence даёт более устойчивый inference.

        FIX 2026-04-28: добавлен beam-search cap на queue size. Без него
        depth=5 BFS на 219k-rule graph мог раздуть queue до миллионов
        partial-path tuple'ов → 2.7GB RSS на sister, D-state freeze.
        Cap = FIBONACCI[16]=987 одновременных partial paths — вмещает
        полезный поиск, не позволяет взорваться. Plus per-node branch cap
        FIBONACCI[10]=89 ограничивает hub-узлы (слова типа «the», «a»).
        """
        if not self.word_space:
            return []
        graph = self._build_graph()
        if start not in graph or end not in graph:
            return []

        # BFS-level iteration, собираем до top_k путей
        found_paths = []
        # очередь: (current, path, visited_in_path)
        queue = deque([(start, [], frozenset([start]))])
        max_queue = FIBONACCI[16]   # 987
        max_branches = FIBONACCI[10]  # 89
        while queue and len(found_paths) < top_k * 3:  # собрать больше, отсеем
            current, path, seen = queue.popleft()
            if len(path) >= max_depth:
                continue
            # Beam-search: only top-K branches per node by rule['count'] —
            # for hub-nodes (e.g. "the", "a") this prevents exponential
            # explosion. Strongest co-occurrences explored first.
            neighbours = graph.get(current, {})
            if len(neighbours) > max_branches:
                neighbours = sorted(
                    neighbours.items(),
                    key=lambda kv: -kv[1].get("count", 0),
                )[:max_branches]
            else:
                neighbours = neighbours.items()
            for neighbor, rule in neighbours:
                if neighbor == end:
                    full_path = path + [(current, neighbor, rule)]
                    found_paths.append(full_path)
                    if len(found_paths) >= top_k * 3:
                        break
                    continue
                if neighbor not in seen:
                    if len(queue) >= max_queue:
                        # queue cap reached — drop further partial paths
                        # for this node to bound memory
                        break
                    queue.append((neighbor, path + [(current, neighbor, rule)],
                                  seen | {neighbor}))

        # Валидация каждой цепи + ранжирование
        chains = []
        for p in found_paths:
            c = self._validate_chain(start, end, p)
            if c is not None:
                chains.append(c)
        # Rank: valid chains first, then by strength, then by fewer steps
        chains.sort(key=lambda c: (not c.valid, -c.strength, len(c.steps)))
        return chains[:top_k]

    def infer_multipath(self, start, end, max_depth=FIBONACCI[4],
                         top_k=FIBONACCI[4]):
        """Public multi-path inference.

        Возвращает dict {
          "chains": [ResonanceChain, ...],   # отсортированы по strength
          "composite_strength": float,       # sum(strength) / n_valid * phi
          "consensus_target": str,           # самая частая phi_target среди valid
          "phase_composition": float,        # circular_mean фаз всех endpoints
          "confidence": float,               # [0,1] согласованность цепей
        }
        Если цепей нет — возвращает None.

        Phase composition: для K независимых цепей A→...→B, усредняем фазы
        всех средних точек (circular_mean), получая «центр масс» пути. Если
        K цепей сходятся к одному центру — consensus высок.
        """
        chains = self._find_chains(start, end, max_depth, top_k)
        if not chains:
            return None
        valid = [c for c in chains if c.valid]
        if not valid:
            # есть цепи но ни одна не прошла phi-validation — слабый inference
            return {
                "chains": chains, "composite_strength": 0.0,
                "consensus_target": "none",
                "phase_composition": 0.0, "confidence": 0.0,
            }
        # consensus phi_target
        from collections import Counter
        target_votes = Counter(c.phi_target for c in valid if c.phi_target != "none")
        consensus_target = target_votes.most_common(1)[0][0] if target_votes else "none"
        # phase composition: средние точки каждой цепи
        midpoint_phases = []
        for c in valid:
            phases = []
            for step in c.steps:
                a, b = step[0], step[1]
                pa = self.word_space._get_phase(a)
                pb = self.word_space._get_phase(b)
                if pa is not None: phases.append(pa)
                if pb is not None: phases.append(pb)
            if phases:
                midpoint_phases.append(circular_mean(phases))
        composition = circular_mean(midpoint_phases) if midpoint_phases else 0.0
        # confidence: насколько близко midpoints (низкая дисперсия → высокая confidence)
        if len(midpoint_phases) > 1:
            spread = max(phi_phase_distance(p, composition) for p in midpoint_phases)
            confidence = max(0.0, 1.0 - spread / PHI_INV_SQ)  # PHI_INV_SQ = 0.382 как threshold
        else:
            confidence = PHI_INV_SQ  # одна цепь — baseline
        # composite strength: sum(strength) boosted by phi if multiple valid
        total_strength = sum(c.strength for c in valid)
        composite = total_strength * (1.0 + PHI_INV * (len(valid) - 1))  # bonus за каждую дополнительную цепь
        return {
            "chains": chains,
            "composite_strength": round(composite, 4),
            "consensus_target": consensus_target,
            "phase_composition": round(composition, 4),
            "confidence": round(confidence, 4),
            "n_valid": len(valid), "n_total": len(chains),
        }

    def _validate_chain(self, start, end, path):
        """FIX C2+S6: circular_mean + HARM_THRESHOLD."""
        _SKIP = {"the","a","an","is","are","was","were","and","or","but",
                 "in","on","at","to","for","of","by","with","from","as",
                 "it","its","not","has","have","had","do","does","did",
                 "this","that","which","who","so","if","no",
                 "и","в","на","с","что","но","а","к"}

        steps = []
        total_strength = 0

        for a, b, rule in path:
            if a.lower() in _SKIP or b.lower() in _SKIP:
                continue
            pa = self.word_space._get_phase(a)
            pb = self.word_space._get_phase(b)
            if pa is None or pb is None:
                continue
            dist = phi_phase_distance(pa, pb)
            target = rule.get("phi_target", "?")
            count = rule.get("count", 1)
            steps.append((a, b, dist, target))
            total_strength += math.log(1 + count) / math.log(PHI)

        if not steps:
            ps = self.word_space._get_phase(start)
            pe = self.word_space._get_phase(end)
            if ps is not None and pe is not None:
                dist = phi_phase_distance(ps, pe)
                ratio = max(dist, 0.001) / max(1.0 - dist, 0.001)
                hit = is_near_phi_target(ratio, tolerance=0.15)
                if hit:
                    return ResonanceChain(
                        steps=[(start, end, dist, hit[0])],
                        start=start, end=end,
                        total_distance=dist,
                        phi_target=hit[0], valid=True,
                        strength=1.0)
            return None

        n_steps = len(steps)
        expected_dist = PHI_INV ** min(n_steps, 5)

        ps = self.word_space._get_phase(start)
        pe = self.word_space._get_phase(end)
        if ps is None or pe is None:
            return None
        real_dist = phi_phase_distance(ps, pe)

        if expected_dist > 0:
            ratio = real_dist / expected_dist
            hit = is_near_phi_target(ratio, tolerance=0.15)
        else:
            hit = None

        # FIX C2: circular_mean vmesto (ps+pe)/2.0
        # FIX S6: HARM_THRESHOLD vmesto 0.1
        harm_dist = phi_phase_distance(
            circular_mean([ps, pe]), 0.5)
        in_harm = harm_dist < HARM_THRESHOLD

        valid = (hit is not None) and not in_harm
        phi_target = hit[0] if hit else "none"

        return ResonanceChain(
            steps=steps, start=start, end=end,
            total_distance=real_dist,
            phi_target=phi_target, valid=valid,
            strength=total_strength / n_steps)

    def reason_about(self, concept, depth=FIBONACCI[3]):
        if not self.word_space:
            return []

        results = []
        neighbors = set()
        for key, rule in self.word_space.rules.items():
            if rule["a"] == concept:
                neighbors.add(rule["b"])
            elif rule["b"] == concept:
                neighbors.add(rule["a"])

        for n1 in list(neighbors)[:FIBONACCI[6]]:
            for key, rule in self.word_space.rules.items():
                n2 = None
                if rule["a"] == n1 and rule["b"] != concept:
                    n2 = rule["b"]
                elif rule["b"] == n1 and rule["a"] != concept:
                    n2 = rule["a"]
                if n2 and n2 not in neighbors:
                    chain = self.infer(concept, n2, max_depth=depth)
                    if chain and chain.valid:
                        results.append(chain)
            if len(results) >= FIBONACCI[7]:
                break

        results.sort(key=lambda c: c.strength, reverse=True)
        return results[:FIBONACCI[6]]

    def stats(self):
        return {
            "total_inferences": self.total_inferences,
            "valid_inferences": self.valid_inferences,
            "validity_rate": round(
                self.valid_inferences /
                max(self.total_inferences, 1), 4),
        }
