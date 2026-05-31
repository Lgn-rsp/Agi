"""concept_graph.py — Rezonansnyy graf mezhdu konceptami.

Filosofiya:
  Conceptsy ne zhivut izolirovanno. Dva concepta s blizkoy phazoy REZONIRUYUT —
  oni 'znayut drug o druge' cherez fazovoy rezonans, dazhe yesli ikh patterny
  ne peresekayutsya. Eto pozvolyaet:

  1. Higher-order inference: C_i predicts outcome X, C_i resonates with C_j →
     C_j takzhe hints at X s oslablennym vesom PHI_INV.
  2. Concept family detection: klastery rezonansnykh conceptov — ob'edineniya
     patternov, imeyushchikh odno 'nastroeniye'.
  3. Analogy transfer: kogda language brain znaet analogi, cross-domain transfer
     cherez fazovoy rezonans.

Canon:
  Resonance weight = 1 - phi_phase_distance(p_i, p_j) / PHI_INV_SQ, napravleno
  v [0, 1]. Hranim tolko edges s weight > PHI_INV_CUBE (0.236 — HARM_THRESHOLD).
  Graph atomicheski persistentnyy (tempfile + os.replace).
"""
import os
import json
import tempfile
import time
from collections import defaultdict

from core.resonance_constants import (
    PHI, PHI_INV, PHI_INV_SQ, PHI_INV_CUBE, FIBONACCI,
    phi_phase_distance, circular_mean
)


class ConceptResonanceGraph:
    """Graf rezonansov mezhdu concepts.

    edges: {(key_i, key_j): weight}, kanonicheskiy order (sorted).
    node_phases: {key: phase} — snapshot phases na moment poslednogo rebuild.
    """

    def __init__(self, state_path=None):
        self.state_path = state_path
        self.edges = {}           # (k_i, k_j) -> weight in [0,1]
        self.node_phases = {}     # key -> phase
        self.last_rebuild_bar = 0
        self.rebuild_count = 0

    def rebuild(self, concepts, bar_idx):
        """Perestroit graf po aktualnym conceptam.

        concepts: dict {key: Concept} iz ConceptFormation.
        Complexity O(N^2) po concepts — O.K. do ~FIB[13]=233 conceptov;
        dalshe uzhe dorogovato, no dream-cycle redkiy, tak chto OK.
        """
        self.edges.clear()
        self.node_phases.clear()
        keys = [k for k, c in concepts.items() if c.confirmations >= FIBONACCI[4]]
        for k in keys:
            self.node_phases[k] = concepts[k].phase
        # pairwise resonance
        for i, k_i in enumerate(keys):
            p_i = self.node_phases[k_i]
            for k_j in keys[i+1:]:
                p_j = self.node_phases[k_j]
                d = phi_phase_distance(p_i, p_j)
                if d >= PHI_INV_SQ:  # 0.382 — too far, no edge
                    continue
                weight = max(0.0, 1.0 - d / PHI_INV_SQ)
                if weight < PHI_INV_CUBE:
                    continue
                pair = tuple(sorted([k_i, k_j]))
                self.edges[pair] = round(weight, 4)
        self.last_rebuild_bar = bar_idx
        self.rebuild_count += 1
        return len(self.edges)

    def resonant_with(self, concept_key, min_weight=PHI_INV_CUBE):
        """Vsе resonant neighbors of concept — list (neighbor_key, weight)."""
        out = []
        for (a, b), w in self.edges.items():
            if w < min_weight:
                continue
            if a == concept_key:
                out.append((b, w))
            elif b == concept_key:
                out.append((a, w))
        out.sort(key=lambda x: x[1], reverse=True)
        return out

    def inferred_outcome(self, concept_key, concepts):
        """Higher-order inference: kombiniruem outcomes direct concept s oslablennymi
        outcomes rezonansnykh neighbors.

        Vozvrashchaet dict {"up": count, "down": count, "flat": count} — vzveshenny
        sovokupnyy forecast. Neighbor votes weighted by edge weight * PHI_INV.
        """
        if concept_key not in concepts:
            return {}
        from collections import Counter
        combined = Counter(concepts[concept_key].outcomes)
        for neighbor_key, w in self.resonant_with(concept_key):
            nc = concepts.get(neighbor_key)
            if not nc:
                continue
            factor = w * PHI_INV  # penalty for indirect evidence
            for outcome, cnt in nc.outcomes.items():
                combined[outcome] += cnt * factor
        return dict(combined)

    def clusters(self, min_weight=PHI_INV):
        """Connected components at high resonance — concept families."""
        # Union-find
        parent = {}
        def find(x):
            while parent.get(x, x) != x:
                parent[x] = parent.get(parent[x], parent[x])
                x = parent[x]
            return x
        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb
        for node in self.node_phases:
            parent[node] = node
        for (a, b), w in self.edges.items():
            if w >= min_weight:
                union(a, b)
        groups = defaultdict(list)
        for node in self.node_phases:
            groups[find(node)].append(node)
        # Return only non-trivial clusters
        return [sorted(v) for v in groups.values() if len(v) > 1]

    def save(self):
        if not self.state_path:
            return
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
        data = {
            "edges": {f"{a}|{b}": w for (a, b), w in self.edges.items()},
            "node_phases": self.node_phases,
            "last_rebuild_bar": self.last_rebuild_bar,
            "rebuild_count": self.rebuild_count,
            "saved_at": time.time(),
        }
        # Canon rule #4: atomic write
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(self.state_path), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            os.replace(tmp, self.state_path)
        except Exception:
            try: os.unlink(tmp)
            except Exception: pass
            raise

    def load(self):
        if not self.state_path or not os.path.exists(self.state_path):
            return
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            edges = {}
            for key, w in data.get("edges", {}).items():
                if "|" not in key:
                    continue
                a, b = key.split("|", 1)
                edges[(a, b)] = float(w)
            self.edges = edges
            self.node_phases = data.get("node_phases", {})
            self.last_rebuild_bar = data.get("last_rebuild_bar", 0)
            self.rebuild_count = data.get("rebuild_count", 0)
        except Exception:
            pass

    def stats(self):
        return {
            "nodes": len(self.node_phases),
            "edges": len(self.edges),
            "clusters_strong": len(self.clusters(min_weight=PHI_INV)),
            "clusters_weak": len(self.clusters(min_weight=PHI_INV_CUBE)),
            "last_rebuild_bar": self.last_rebuild_bar,
            "rebuild_count": self.rebuild_count,
        }
