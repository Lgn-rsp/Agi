"""
meta_core.py — Metarefleksiya.
Sistema analiziruet SVOI pravila kak dannye.
Ishchet phi-patterny v svoikh patternakh.
Pravila kotorye rezoniruyut drug s drugom — usilivayutsya.
Eto kak sistema uchitsya UCHITSYA.
"""
import time
import json
import os
import math
from collections import defaultdict

from core.resonance_constants import (
    PHI, PHI_INV, FIBONACCI,
    phi_phase, phi_phase_distance, phi_phase_resonance,
    is_near_phi_target
)


class MetaCore:
    """
    Metauroven — pravila o pravilakh.
    Analiziruet kristallizovannye pravila vsekh urovney.
    Nahodit patterny mezhdu pravilami.
    Generiruet meta-pravila (abstraktsii).
    """

    def __init__(self, phase_spaces, state_dir=None):
        self.spaces = phase_spaces
        self.state_dir = state_dir or os.path.expanduser("~/logos_agi/state/meta")
        self.log_dir = os.path.expanduser("~/logos_agi/logs")
        os.makedirs(self.state_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)

        self.meta_rules = {}          # meta-pattern -> rule
        self.field_patterns = {}      # field pair -> stats
        self.phi_target_stats = defaultdict(int)  # which targets dominate
        self.abstraction_level = 0    # skolko urovney abstrakcii

        self._load_state()
        print(f"[+] MetaCore initialized. "
              f"Meta-rules: {len(self.meta_rules)}, "
              f"Abstraction level: {self.abstraction_level}")

    def reflect(self):
        """
        Odin tsikl refleksii.
        Smotrit na VSE pravila vsekh urovney.
        Ishchet patterny MEZHDU pravilami.
        """
        all_rules = []
        for level_name, space in self.spaces.items():
            for key, rule in space.rules.items():
                all_rules.append({
                    "level": level_name,
                    "key": key,
                    **rule
                })

        if len(all_rules) < FIBONACCI[4]:  # minimum 5
            return {"status": "too_few_rules", "count": len(all_rules)}

        discoveries = {
            "field_patterns": self._analyze_fields(all_rules),
            "phi_targets": self._analyze_targets(all_rules),
            "cross_level": self._analyze_cross_level(all_rules),
            "resonance_chains": self._find_chains(all_rules),
        }

        # L4: meta-meta — patterny nad meta-pravilami
        discoveries["meta_clusters"] = self._find_meta_clusters()
        # L5+: emergentnyye koncepty — novye simvoly iz klassov pravil
        discoveries["emergent_concepts"] = self._birth_concepts()

        self.abstraction_level = max(
            self.abstraction_level,
            1 if discoveries["field_patterns"] else 0,
            2 if discoveries["cross_level"] else 0,
            3 if discoveries["resonance_chains"] else 0,
            4 if discoveries["meta_clusters"] else 0,
            5 if discoveries["emergent_concepts"] else 0,
        )

        self._log(f"REFLECT: {len(all_rules)} rules analyzed, "
                  f"abstraction={self.abstraction_level}")

        self.save_state()
        return discoveries

    def _analyze_fields(self, rules):
        """
        Kakiye polya chashche svyazany?
        Esli matter->will povtoryaetsya 50 raz — eto meta-pattern.
        """
        field_pairs = defaultdict(int)
        for rule in rules:
            fa = rule.get("field_a", "?")
            fb = rule.get("field_b", "?")
            pair = (fa, fb) if fa < fb else (fb, fa)
            field_pairs[pair] += 1

        # Kristallizuem chastye pary poley
        discoveries = []
        for pair, count in field_pairs.items():
            if count >= FIBONACCI[4]:  # >= 5
                meta_key = f"field:{pair[0]}|{pair[1]}"
                if meta_key not in self.meta_rules:
                    self.meta_rules[meta_key] = {
                        "type": "field_affinity",
                        "fields": pair,
                        "count": count,
                        "strength": round(
                            math.log(1 + count) / math.log(PHI), 4),
                        "discovered_at": time.time(),
                    }
                    discoveries.append(meta_key)
                    self._log(f"META: {pair[0]} <-> {pair[1]} "
                             f"affinity (count={count})")
                else:
                    self.meta_rules[meta_key]["count"] = count

        self.field_patterns = dict(field_pairs)
        return discoveries

    def _analyze_targets(self, rules):
        """
        Kakiye phi-targets dominiruyut?
        Esli phi_inv vstrechaetsya v 60% pravil — eto vazhneyshiy rezonans.
        """
        target_counts = defaultdict(int)
        total = 0
        for rule in rules:
            target = rule.get("phi_target", "unknown")
            target_counts[target] += 1
            total += 1

        self.phi_target_stats = dict(target_counts)

        # Meta-nablyudeniye: dominantnyy target
        discoveries = []
        if total > 0:
            for target, count in target_counts.items():
                ratio = count / total
                if ratio > PHI_INV:  # > 61.8% — dominantniy
                    meta_key = f"dominant_target:{target}"
                    self.meta_rules[meta_key] = {
                        "type": "dominant_target",
                        "target": target,
                        "ratio": round(ratio, 4),
                        "count": count,
                        "total": total,
                        "discovered_at": time.time(),
                    }
                    discoveries.append(meta_key)
                    self._log(f"META: {target} dominates "
                             f"({ratio:.1%} of all rules)")

        return discoveries

    def _analyze_cross_level(self, rules):
        """
        Odinakovye patterny na raznykh urovnyakh?
        Esli na urovne slov i na urovne par odinakovy phi_target —
        eto glubokiy pattern.
        """
        level_targets = defaultdict(lambda: defaultdict(int))
        for rule in rules:
            level = rule.get("level", "?")
            target = rule.get("phi_target", "?")
            level_targets[level][target] += 1

        discoveries = []
        levels = list(level_targets.keys())
        for i in range(len(levels)):
            for j in range(i + 1, len(levels)):
                l1, l2 = levels[i], levels[j]
                # Obshchie dominantnye targety
                for target in level_targets[l1]:
                    if target in level_targets[l2]:
                        c1 = level_targets[l1][target]
                        c2 = level_targets[l2][target]
                        if c1 >= FIBONACCI[3] and c2 >= FIBONACCI[3]:
                            meta_key = f"cross:{l1}|{l2}|{target}"
                            if meta_key not in self.meta_rules:
                                self.meta_rules[meta_key] = {
                                    "type": "cross_level_pattern",
                                    "levels": (l1, l2),
                                    "target": target,
                                    "counts": (c1, c2),
                                    "discovered_at": time.time(),
                                }
                                discoveries.append(meta_key)
                                self._log(f"META CROSS: {target} appears "
                                         f"in {l1}({c1}) and {l2}({c2})")

        return discoveries

    def _find_chains(self, rules):
        """
        Tsepochki rezonansov mezhdu pravilami.
        Esli pravilo R1 i pravilo R2 imeyut obshchiy simvol,
        i ikh phi_targets sami rezoniruyut — eto tsepochka.
        """
        discoveries = []
        rule_list = list(rules)

        for i in range(min(len(rule_list), FIBONACCI[10])):  # max 89
            r1 = rule_list[i]
            for j in range(i + 1, min(len(rule_list), FIBONACCI[10])):
                r2 = rule_list[j]

                # Obshchiy simvol?
                symbols_1 = {r1.get("a"), r1.get("b")}
                symbols_2 = {r2.get("a"), r2.get("b")}
                shared = symbols_1 & symbols_2

                if not shared:
                    continue

                # Phi targets rezoniruyut?
                t1 = r1.get("distance", 0)
                t2 = r2.get("distance", 0)
                if t1 > 0 and t2 > 0:
                    ratio = max(t1, t2) / min(t1, t2)
                    hit = is_near_phi_target(ratio, tolerance=0.08)
                    if hit:
                        target_name, error = hit
                        pivot = list(shared)[0]
                        meta_key = f"chain:{r1.get('a')}|{pivot}|{r2.get('b')}"
                        if meta_key not in self.meta_rules:
                            self.meta_rules[meta_key] = {
                                "type": "resonance_chain",
                                "pivot": pivot,
                                "rule1": r1.get("key"),
                                "rule2": r2.get("key"),
                                "chain_target": target_name,
                                "error": round(error, 6),
                                "discovered_at": time.time(),
                            }
                            discoveries.append(meta_key)

        if discoveries:
            self._log(f"META CHAINS: {len(discoveries)} found")

        return discoveries

    def _find_meta_clusters(self):
        """L4: patterny NAD meta-pravilami — klastery."""
        if len(self.meta_rules) < FIBONACCI[5]:
            return []
        discoveries = []
        by_type = defaultdict(list)
        for key, rule in self.meta_rules.items():
            by_type[rule.get("type", "?")].append((key, rule))
        for rule_type, rules in by_type.items():
            if len(rules) < FIBONACCI[3]:
                continue
            field_groups = defaultdict(list)
            for key, rule in rules:
                fields = rule.get("fields", rule.get("levels", ()))
                if isinstance(fields, (list, tuple)):
                    for f in fields:
                        field_groups[f].append((key, rule))
                target = rule.get("target", "")
                if target:
                    field_groups["target:" + str(target)].append((key, rule))
            for group_key, group_rules in field_groups.items():
                if len(group_rules) < FIBONACCI[3]:
                    continue
                strengths = [r.get("strength", r.get("count", 1)) for _, r in group_rules]
                avg_strength = sum(strengths) / len(strengths)
                cluster_key = "cluster:" + rule_type + ":" + str(group_key)
                if cluster_key in self.meta_rules:
                    self.meta_rules[cluster_key]["count"] = len(group_rules)
                    self.meta_rules[cluster_key]["avg_strength"] = round(avg_strength, 4)
                    continue
                self.meta_rules[cluster_key] = {
                    "type": "meta_cluster", "cluster_type": rule_type,
                    "group_key": group_key, "count": len(group_rules),
                    "avg_strength": round(avg_strength, 4),
                    "members": [k for k, _ in group_rules[:FIBONACCI[6]]],
                    "discovered_at": time.time(), "level": 4,
                }
                discoveries.append(cluster_key)
                self._log("META L4: cluster " + str(group_key) + " in " + rule_type + " (" + str(len(group_rules)) + " rules)")
        return discoveries

    def _birth_concepts(self):
        """L5+: emergentnyye koncepty iz klasterov."""
        clusters = [(k, r) for k, r in self.meta_rules.items() if r.get("type") == "meta_cluster"]
        if len(clusters) < FIBONACCI[3]:
            return []
        discoveries = []
        for i in range(len(clusters)):
            k1, c1 = clusters[i]
            for j in range(i + 1, len(clusters)):
                k2, c2 = clusters[j]
                members1 = set(c1.get("members", []))
                members2 = set(c2.get("members", []))
                shared = members1 & members2
                s1 = c1.get("avg_strength", 0)
                s2 = c2.get("avg_strength", 0)
                hit = None
                if s1 > 0 and s2 > 0:
                    ratio = max(s1, s2) / min(s1, s2)
                    hit = is_near_phi_target(ratio, tolerance=0.12)
                if not shared and not hit:
                    continue
                ckey = "concept:" + str(c1.get("group_key","?")) + "+" + str(c2.get("group_key","?"))
                if ckey in self.meta_rules:
                    continue
                concept_words = set()
                for mk in list(members1 | members2)[:FIBONACCI[6]]:
                    mr = self.meta_rules.get(mk, {})
                    flds = mr.get("fields", mr.get("levels", ()))
                    if isinstance(flds, (list, tuple)):
                        concept_words.update(flds)
                    pv = mr.get("pivot")
                    if pv:
                        concept_words.add(pv)
                cstrength = math.sqrt(max(s1, 0.001) * max(s2, 0.001)) * PHI_INV
                self.meta_rules[ckey] = {
                    "type": "emergent_concept",
                    "sources": [k1, k2],
                    "source_groups": [c1.get("group_key", "?"), c2.get("group_key", "?")],
                    "words": list(concept_words)[:FIBONACCI[6]],
                    "strength": round(cstrength, 4),
                    "shared_members": len(shared),
                    "phi_resonance": hit[0] if hit else "shared_members",
                    "level": 5, "discovered_at": time.time(),
                }
                discoveries.append(ckey)
                self._log("META L5: CONCEPT " + str(c1.get("group_key","?")) + "+" + str(c2.get("group_key","?")))
                if len(discoveries) >= FIBONACCI[6]:
                    return discoveries
        return discoveries

    def get_insights(self):
        """Chto sistema ponyala o sebe."""
        insights = []

        # Field patterns
        if self.field_patterns:
            top_pair = max(self.field_patterns.items(), key=lambda x: x[1])
            insights.append(
                f"Strongest field connection: "
                f"{top_pair[0][0]} <-> {top_pair[0][1]} ({top_pair[1]} rules)")

        # Dominant target
        if self.phi_target_stats:
            top_target = max(self.phi_target_stats.items(), key=lambda x: x[1])
            insights.append(
                f"Dominant resonance: {top_target[0]} ({top_target[1]} occurrences)")

        # Abstraction level
        level_desc = {
            0: "Data collection",
            1: "Field patterns discovered",
            2: "Cross-level patterns found",
            3: "Resonance chains detected",
            4: "Meta-clusters formed",
            5: "Emergent concepts born",
            6: "Concept hierarchies",
            7: "Self-referential abstraction",
            8: "Autonomous theory formation",
        }
        insights.append(
            f"Abstraction level: {self.abstraction_level} "
            f"({level_desc.get(self.abstraction_level, 'unknown')})")

        return insights

    def stats(self):
        return {
            "meta_rules": len(self.meta_rules),
            "field_patterns": len(self.field_patterns),
            "phi_target_stats": dict(self.phi_target_stats),
            "abstraction_level": self.abstraction_level,
        }

    def save_state(self):
        path = os.path.join(self.state_dir, "meta_state.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "meta_rules": self.meta_rules,
                "field_patterns": {f"{k[0]}|{k[1]}": v
                                   for k, v in self.field_patterns.items()},
                "phi_target_stats": dict(self.phi_target_stats),
                "abstraction_level": self.abstraction_level,
                "saved_at": time.time(),
            }, f, ensure_ascii=False, indent=2)

    def _load_state(self):
        path = os.path.join(self.state_dir, "meta_state.json")
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.meta_rules = data.get("meta_rules", {})
            self.abstraction_level = data.get("abstraction_level", 0)
            self.phi_target_stats = defaultdict(
                int, data.get("phi_target_stats", {}))
        except Exception:
            pass

    def _log(self, message):
        path = os.path.join(self.log_dir, "meta.log")
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {message}\n")


# === TEST ===
if __name__ == "__main__":
    from core.phase_space import PhaseSpace
    from core.symbolizer import symbolize_multilevel

    spaces = {
        "words": PhaseSpace(state_dir="/tmp/meta_test_w"),
        "pairs": PhaseSpace(state_dir="/tmp/meta_test_p"),
    }

    texts = [
        "the cat sat on the mat", "the dog ran in the park",
        "the bird flew over the tree", "the fish swam in the sea",
        "the cat ate the fish", "the dog chased the cat",
        "fire burns in the night", "water flows down the river",
        "the sun rises in the east", "mathematics reveals patterns",
        "geometry connects space and form", "energy transforms matter",
        "light travels through space", "gravity pulls things down",
        "time flows like a river", "stars glow in darkness",
    ]

    print("=== LEARNING ===")
    for _ in range(FIBONACCI[6]):
        for text in texts:
            levels = symbolize_multilevel(text)
            for name in spaces:
                if name in levels:
                    spaces[name].observe(levels[name])

    for n, sp in spaces.items():
        print(f"  {n}: {sp.stats()['symbols']} sym, {sp.stats()['rules']} rules")

    print("\n=== META REFLECTION ===")
    meta = MetaCore(spaces, state_dir="/tmp/meta_test_state")
    result = meta.reflect()

    print(f"\nField patterns: {len(result['field_patterns'])}")
    for fp in result['field_patterns']:
        r = meta.meta_rules[fp]
        print(f"  {r['fields'][0]} <-> {r['fields'][1]}: "
              f"count={r['count']}, strength={r['strength']}")

    print(f"\nPhi target dominance: {len(result['phi_targets'])}")
    for dt in result['phi_targets']:
        r = meta.meta_rules[dt]
        print(f"  {r['target']}: {r['ratio']:.1%} of all rules")

    print(f"\nCross-level: {len(result['cross_level'])}")
    for cl in result['cross_level'][:3]:
        r = meta.meta_rules[cl]
        print(f"  {r['target']} in {r['levels'][0]}({r['counts'][0]}) "
              f"and {r['levels'][1]}({r['counts'][1]})")

    print(f"\nChains: {len(result['resonance_chains'])}")
    for ch in result['resonance_chains'][:3]:
        r = meta.meta_rules[ch]
        print(f"  pivot={r['pivot']}: {r['chain_target']}")

    print(f"\n=== INSIGHTS ===")
    for insight in meta.get_insights():
        print(f"  {insight}")

    print(f"\n=== STATS ===")
    print(f"  {meta.stats()}")
