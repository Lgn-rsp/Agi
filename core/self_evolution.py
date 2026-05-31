"""
self_evolution.py v10 — Samomodifikatsiya.

FIX K2: _apply_params primenyaet k REALNYM atributam.
FIX v10: _run_tests vyzyvaet generator.respond() (ne brain.respond()).
FIX v10: tolerances -> phi-derived.

Vsyo cherez phi.
"""
import time
import os
import json

from core.resonance_constants import (
    PHI, PHI_INV, PHI_INV_SQ, PHI_INV_CUBE, FIBONACCI,
    phi_phase_distance
)


class SelfEvolution:
    """
    Nablyudayet rezultaty sistemy i korrektiruyet parametry.
    FIX K2: parametry teper primenyayutsya k realnym atributam.
    FIX v10: _run_tests ispolzuyet generator.respond().
    """

    def __init__(self, brain=None, log_dir=None):
        self.brain = brain
        self.log_dir = log_dir or os.path.expanduser("~/logos_agi/logs")
        os.makedirs(self.log_dir, exist_ok=True)

        # Parametry kotoryye mozhno menyat
        self.tunable = {
            "gen_threshold": PHI_INV_SQ,
            "field_activation_weight": PHI_INV,
            "chain_max_depth": FIBONACCI[5],
            "frame_weight": PHI_INV,
            "concept_weight": PHI_INV_SQ,
            "spreading_weight": PHI_INV,
        }

        self.experiments = []
        self.generation = 0

        self.test_queries = [
            "what is consciousness",
            "how does learning work",
            "what is truth",
            "why does water flow",
            "what connects music and mathematics",
        ]

        self._load()
        print(f"[+] SelfEvolution v10 initialized. "
              f"Generation: {self.generation}, "
              f"Experiments: {len(self.experiments)}")

    def evaluate_response(self, query, response_words):
        if not response_words or not self.brain:
            return {"coherence": 0, "diversity": 0, "relevance": 0, "total": 0}

        ws = self.brain.learner.spaces.get("words")
        if not ws:
            return {"coherence": 0, "diversity": 0, "relevance": 0, "total": 0}

        # 1. Coherence
        pairs_found = 0
        pairs_total = 0
        for i in range(len(response_words) - 1):
            a, b = response_words[i], response_words[i + 1]
            pairs_total += 1
            pa = ws.phases.get(a)
            pb = ws.phases.get(b)
            if pa is not None and pb is not None:
                dist = phi_phase_distance(pa, pb)
                if dist < PHI_INV:
                    pairs_found += 1
        coherence = pairs_found / max(pairs_total, 1)

        # 2. Diversity
        unique = len(set(response_words))
        diversity = unique / max(len(response_words), 1)

        # 3. Relevance
        query_words = query.lower().split()
        query_phases = [ws.phases.get(w) for w in query_words
                        if ws.phases.get(w) is not None]
        resp_phases = [ws.phases.get(w) for w in response_words
                       if ws.phases.get(w) is not None]

        resonance_count = 0
        resonance_total = 0
        for qp in query_phases:
            for rp in resp_phases:
                resonance_total += 1
                if phi_phase_distance(qp, rp) < PHI_INV_SQ:
                    resonance_count += 1
        relevance = resonance_count / max(resonance_total, 1)

        total = (coherence * PHI_INV +
                 diversity * PHI_INV_SQ +
                 relevance * PHI_INV_CUBE)

        return {
            "coherence": round(coherence, 4),
            "diversity": round(diversity, 4),
            "relevance": round(relevance, 4),
            "total": round(total, 4),
        }

    def run_experiment(self):
        if not self.brain:
            return None

        # 1. Baseline
        baseline_score = self._run_tests()

        # 2. Vybrat parametr
        param_names = list(self.tunable.keys())
        param_idx = self.generation % len(param_names)
        param_name = param_names[param_idx]
        old_value = self.tunable[param_name]

        # 3. Sdvig cherez phi
        direction = 1 if (self.generation // len(param_names)) % 2 == 0 else -1
        delta = old_value * PHI_INV_CUBE * direction
        new_value = max(PHI_INV_CUBE * PHI_INV_CUBE, min(1.0 - PHI_INV_CUBE, old_value + delta))
        self.tunable[param_name] = new_value

        # 4. Primenit
        self._apply_params()

        # 5. Otsenit
        new_score = self._run_tests()

        # 6. Reshit
        improved = new_score["avg_total"] > baseline_score["avg_total"]
        if not improved:
            self.tunable[param_name] = old_value
            self._apply_params()

        experiment = {
            "generation": self.generation,
            "param": param_name,
            "old_value": round(old_value, 6),
            "new_value": round(new_value, 6),
            "baseline": baseline_score["avg_total"],
            "result": new_score["avg_total"],
            "improved": improved,
            "kept": improved,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        self.experiments.append(experiment)
        self.generation += 1
        self._save()

        status = "KEPT ✓" if improved else "REVERTED ✗"
        self._log(
            f"Gen {experiment['generation']}: {param_name} "
            f"{old_value:.4f}→{new_value:.4f} | "
            f"score {baseline_score['avg_total']:.4f}→"
            f"{new_score['avg_total']:.4f} | {status}")

        return experiment

    def _run_tests(self):
        """FIX v10: vyzyvaem generator.respond() — on tochno sushchestvuyet."""
        scores = []
        for query in self.test_queries:
            try:
                gen = getattr(self.brain, 'generator', None)
                if gen is None:
                    scores.append({"total": 0})
                    continue
                result = gen.respond(query)
                if result and isinstance(result, dict):
                    words = result.get("words", [])
                    score = self.evaluate_response(query, words)
                    # Dobavlyaem verifier score esli dostupen
                    verifier = getattr(self.brain, 'verifier', None)
                    if verifier and words:
                        from core.generator import _is_content
                        content = [w for w in words if _is_content(w)]
                        if len(content) >= 2:
                            vr = verifier.verify(content)
                            score["verifier"] = round(vr.score, 4)
                            score["total"] = round(
                                score["total"] * PHI_INV + vr.score * PHI_INV_SQ, 4)
                    scores.append(score)
                else:
                    scores.append({"total": 0})
            except Exception as e:
                scores.append({"total": 0})

        avg_total = sum(s["total"] for s in scores) / max(len(scores), 1)
        return {"scores": scores, "avg_total": round(avg_total, 4)}

    def _apply_params(self):
        """FIX K2: primenyaem k REALNYM atributam sistemy."""
        if not self.brain:
            return

        gen = getattr(self.brain, 'generator', None)
        if not gen:
            return

        gen._evo_field_weight = self.tunable.get(
            "field_activation_weight", PHI_INV)
        gen._evo_spreading_weight = self.tunable.get(
            "spreading_weight", PHI_INV)
        gen._evo_frame_weight = self.tunable.get(
            "frame_weight", PHI_INV)
        gen._evo_chain_depth = int(self.tunable.get(
            "chain_max_depth", FIBONACCI[5]))

    def _log(self, message):
        ts = time.strftime("%Y-%m-%dT%H:%M:%S")
        log_path = os.path.join(self.log_dir, "evolution.log")
        try:
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(f"[EVO] {ts} → {message}\n")
        except Exception:
            pass

    def _save(self):
        path = os.path.join(self.log_dir, "evolution_state.json")
        try:
            data = {
                "generation": self.generation,
                "tunable": self.tunable,
                "experiments": self.experiments[-FIBONACCI[10]:],
            }
            # Canon rule #4: atomic write
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
        except Exception:
            pass

    def _load(self):
        path = os.path.join(self.log_dir, "evolution_state.json")
        try:
            with open(path) as f:
                data = json.load(f)
            self.generation = data.get("generation", 0)
            self.tunable.update(data.get("tunable", {}))
            self.experiments = data.get("experiments", [])
        except Exception:
            pass

    def stats(self):
        last_5 = self.experiments[-5:] if self.experiments else []
        improvements = sum(1 for e in self.experiments if e.get("improved"))
        return {
            "generation": self.generation,
            "total_experiments": len(self.experiments),
            "improvements": improvements,
            "current_params": {k: round(v, 4) for k, v in self.tunable.items()},
            "recent": last_5,
        }
