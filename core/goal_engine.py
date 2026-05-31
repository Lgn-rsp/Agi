"""
goal_engine.py v10 — Avtonomnoye tselepolaganiye.

FIX K4: _do_learn ispolzuyet realnyy poisk cherez seeker/data vmesto shablona.
FIX M5: PHI_SQ importirovan iz resonance_constants (edinyy istochnik).
FIX L2: HARM_THRESHOLD iz resonance_constants.

Vsyo cherez phi.
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


class Goal:
    __slots__ = [
        'name', 'description', 'phase', 'strength',
        'origin', 'steps', 'progress', 'born_at',
        'last_active', 'attempts', 'best_score',
        'resolved', 'result'
    ]

    def __init__(self, name, description, phase, strength, origin):
        self.name = name
        self.description = description
        self.phase = phase
        self.strength = strength
        self.origin = origin
        self.steps = []
        self.progress = 0.0
        self.born_at = time.time()
        self.last_active = time.time()
        self.attempts = 0
        self.best_score = 0.0
        self.resolved = False
        self.result = None

    def decay(self):
        self.strength *= PHI_INV
        return self.strength >= PHI_INV_CUBE * PHI_INV

    def advance(self, score):
        self.attempts += 1
        self.last_active = time.time()
        if score > self.best_score:
            self.best_score = score
            self.progress = min(score, 1.0 - PHI_INV_CUBE)
            # FIX M5: PHI_SQ iz constants
            self.strength = min(self.strength * PHI, PHI_SQ)
        return self.progress

    def resolve(self, result):
        self.resolved = True
        self.result = result
        self.progress = 1.0

    def priority(self, creator_phase=0.0):
        dist = phi_phase_distance(self.phase, creator_phase)
        resonance = phi_phase_resonance(dist)
        age_factor = 1.0 / (1.0 + math.log(1 + self.attempts) / math.log(PHI))
        return self.strength * (resonance + PHI_INV) * age_factor

    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "phase": round(self.phase, 6),
            "strength": round(self.strength, 4),
            "origin": self.origin,
            "progress": round(self.progress, 4),
            "attempts": self.attempts,
            "best_score": round(self.best_score, 4),
            "resolved": self.resolved,
            "born_at": self.born_at,
        }

    def __repr__(self):
        status = "RESOLVED" if self.resolved else f"progress={self.progress:.2f}"
        return (f"Goal('{self.name}', str={self.strength:.3f}, "
                f"{status}, origin={self.origin})")


class GoalEngine:
    def __init__(self, brain=None, verifier=None, state_dir=None):
        self.brain = brain
        self.verifier = verifier
        self.state_dir = state_dir or os.path.expanduser(
            "~/logos_agi/state/goals")
        self.log_dir = os.path.expanduser("~/logos_agi/logs")
        os.makedirs(self.state_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)

        self.active_goals = {}
        self.resolved_goals = []
        self.max_active = FIBONACCI[10]
        self.max_resolved = FIBONACCI[15]

        self.total_goals_born = 0
        self.total_goals_resolved = 0
        self.total_goals_decayed = 0

        self._goal_counter = 0

        self._load()
        print(f"[+] GoalEngine v10 initialized. "
              f"Active: {len(self.active_goals)}, "
              f"Resolved: {len(self.resolved_goals)}")

    # =========================================================
    # ROZHDENIE TSELEY
    # =========================================================
    def birth_from_curiosity(self, questions):
        born = 0
        for q in questions:
            if hasattr(q, 'pair'):
                pair = q.pair
                if isinstance(pair, tuple) and len(pair) >= 2:
                    a, b = str(pair[0]), str(pair[1])
                    if len(a) <= 2 and len(b) <= 2:
                        continue
                    concept = a if len(a) > len(b) else b
                else:
                    concept = str(pair)
                    if len(concept) <= 2:
                        continue
                question_text = f"understand {concept} (target={getattr(q, 'nearest_target', '?')})"
            elif isinstance(q, dict):
                concept = q.get("concept", q.get("word", "unknown"))
                question_text = q.get("question", f"understand {concept}")
            elif isinstance(q, str):
                concept = q
                question_text = f"understand {concept}"
            else:
                continue

            name = f"curiosity_{concept}"
            if name in self.active_goals:
                continue

            phase = self._concept_phase(concept)

            goal = Goal(
                name=name,
                description=question_text,
                phase=phase,
                strength=PHI,
                origin="curiosity")

            goal.steps = [
                {"action": "seek", "target": concept, "done": False},
                {"action": "learn", "target": concept, "done": False},
                {"action": "verify", "target": concept, "done": False},
            ]

            if self._add_goal(goal):
                born += 1
        return born

    def birth_from_contradictions(self, contradictions):
        born = 0
        for contra in contradictions:
            triangle = contra.get("triangle", [])
            if len(triangle) < 3:
                continue

            name = f"resolve_{triangle[0]}_{triangle[1]}_{triangle[2]}"
            if name in self.active_goals:
                continue

            phases = [self._concept_phase(w) for w in triangle]
            phase = circular_mean(phases)

            goal = Goal(
                name=name,
                description=f"resolve contradiction: {' - '.join(triangle)}",
                phase=phase,
                strength=PHI * PHI_INV,
                origin="verifier")

            goal.steps = [
                {"action": "investigate", "target": triangle, "done": False},
                {"action": "learn", "target": triangle[0], "done": False},
                {"action": "re_verify", "target": triangle, "done": False},
            ]

            if self._add_goal(goal):
                born += 1
        return born

    def birth_from_anomalies(self, anomalies):
        born = 0
        for anom in anomalies:
            pair = anom.get("pair", ())
            if len(pair) < 2:
                continue
            a, b = str(pair[0]), str(pair[1])
            name = f"anomaly_{a}_{b}"
            if name in self.active_goals:
                continue

            phase = circular_mean([self._concept_phase(a), self._concept_phase(b)])

            goal = Goal(
                name=name,
                description=f"crystallize near-miss: {a} ~ {b} (gap={anom.get('gap', '?')})",
                phase=phase,
                strength=PHI,
                origin="anomaly")

            goal.steps = [
                {"action": "learn", "target": a, "done": False},
                {"action": "learn", "target": b, "done": False},
                {"action": "verify", "target": [a, b], "done": False},
            ]

            if self._add_goal(goal):
                born += 1
        return born

    def birth_from_dreams(self, dream_discoveries):
        born = 0
        for disc in dream_discoveries:
            a = disc.get("a", "")
            b = disc.get("b", disc.get("bridge", ""))
            if not a or not b:
                continue

            name = f"dream_{a}_{b}"
            if name in self.active_goals:
                continue

            phase = circular_mean([self._concept_phase(a), self._concept_phase(b)])

            goal = Goal(
                name=name,
                description=f"verify dream: {a} ~ {b}",
                phase=phase,
                strength=PHI_INV,
                origin="dream")

            goal.steps = [
                {"action": "verify", "target": [a, b], "done": False},
            ]

            if self._add_goal(goal):
                born += 1
        return born

    # =========================================================
    # TSIKL
    # =========================================================
    def step(self):
        if not self.active_goals or not self.brain:
            return {"action": "idle", "reason": "no goals or no brain"}

        # ZATUKHANIYE
        dead = []
        for name, goal in self.active_goals.items():
            if not goal.decay():
                dead.append(name)
        for name in dead:
            self.total_goals_decayed += 1
            del self.active_goals[name]
            self._log(f"DECAYED: {name}")

        if not self.active_goals:
            return {"action": "idle", "reason": "all goals decayed"}

        # VYBOR
        best_name = max(
            self.active_goals,
            key=lambda n: self.active_goals[n].priority(creator_phase=0.0))
        goal = self.active_goals[best_name]

        # VYPOLNENIE
        result = self._execute_step(goal)

        # OTSENKA
        if result.get("score", 0) > 0:
            goal.advance(result["score"])

        # KRISTALLIZATSIYA
        if result.get("verified", False) and goal.best_score > PHI_INV:
            goal.resolve(result)
            self.resolved_goals.append(goal.to_dict())
            while len(self.resolved_goals) > self.max_resolved:
                self.resolved_goals.pop(0)
            del self.active_goals[best_name]
            self.total_goals_resolved += 1
            self._log(f"RESOLVED: {best_name} (score={goal.best_score:.4f})")

        return {
            "action": "step",
            "goal": best_name,
            "progress": round(goal.progress, 4),
            "score": result.get("score", 0),
            "verified": result.get("verified", False),
        }

    def _execute_step(self, goal):
        current_step = None
        for s in goal.steps:
            if not s["done"]:
                current_step = s
                break

        if current_step is None:
            return self._verify_goal(goal)

        action = current_step["action"]
        if action == "seek":
            return self._do_seek(goal, current_step)
        elif action in ("learn", "learn_more"):
            return self._do_learn(goal, current_step)
        elif action in ("verify", "re_verify"):
            return self._do_verify(goal, current_step)
        elif action == "investigate":
            return self._do_investigate(goal, current_step)
        else:
            current_step["done"] = True
            return {"score": 0}

    def _do_seek(self, goal, step):
        target = step["target"]

        if self.brain.memory:
            mem = self.brain.memory.recall(target)
            if mem and mem.get("importance", 0) > PHI_INV:
                step["done"] = True
                return {"score": PHI_INV_SQ, "source": "memory"}

        if self.brain.learner:
            info = self.brain.learner.query(target, "words")
            if info.get("known") and len(info.get("connections", [])) >= FIBONACCI[3]:
                step["done"] = True
                return {"score": PHI_INV, "source": "rules"}

        step["done"] = True
        return {"score": PHI_INV_CUBE, "source": "not_found"}

    def _do_learn(self, goal, step):
        """FIX K4: realnoye obucheniye — ishchem v dannyh ili generiruem kontekst."""
        target = step["target"]
        if isinstance(target, list):
            target = target[0]

        ws = self.brain.learner.spaces.get("words")
        rules_before = len(ws.rules) if ws else 0

        # 1. Ishchem v lokalnykh dannykh
        data_dir = os.path.expanduser("~/logos_agi/data")
        learned_from_data = False
        if os.path.isdir(data_dir):
            import re
            target_lower = target.lower()
            for fname in os.listdir(data_dir):
                if not fname.endswith(".txt"):
                    continue
                fpath = os.path.join(data_dir, fname)
                try:
                    with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                        lines_learned = 0
                        for line in f:
                            if target_lower in line.lower():
                                self.brain.learn(line.strip())
                                lines_learned += 1
                                if lines_learned >= FIBONACCI[5]:
                                    break
                    if lines_learned > 0:
                        learned_from_data = True
                        break
                except Exception:
                    continue

        # 2. Esli ne nashli v dannykh — uchim sosedey iz pravil
        if not learned_from_data and ws:
            info = ws.query(target) if hasattr(ws, 'query') else None
            if info and info.get("known"):
                connections = info.get("connections", [])
                for conn in connections[:FIBONACCI[4]]:
                    other = conn.get("symbol", "")
                    if other:
                        # Generiruem kontekstnuyu frazu iz realnyh svyazey
                        phrase = f"{target} {other} {target} {other}"
                        self.brain.learn(phrase)

        rules_after = len(ws.rules) if ws else 0
        growth = rules_after - rules_before

        step["done"] = True
        return {
            "score": PHI_INV if growth > 0 else PHI_INV_CUBE,
            "new_rules": growth,
            "from_data": learned_from_data,
        }

    def _do_verify(self, goal, step):
        target = step["target"]
        if not self.verifier:
            step["done"] = True
            return {"score": 0, "verified": False}

        if isinstance(target, list):
            result = self.verifier.verify(target)
        else:
            result = self.verifier.verify(target)

        step["done"] = True
        return {
            "score": max(result.score, 0),
            "verified": result.score > PHI_INV_SQ,
            "coherence": result.coherence,
            "triangles": result.triangles_closed,
        }

    def _do_investigate(self, goal, step):
        """FIX K4: investigate teper ishchet v dannykh."""
        target = step["target"]
        if isinstance(target, list):
            for word in target:
                # Ispolzuem _do_learn logiku dlya kazhdogo slova
                sub_step = {"target": word, "done": False}
                self._do_learn(goal, sub_step)
        step["done"] = True
        return {"score": PHI_INV_CUBE}

    def _verify_goal(self, goal):
        if not self.verifier:
            return {"score": goal.best_score, "verified": False}
        words = goal.description.lower().split()
        result = self.verifier.verify(words)
        return {
            "score": max(result.score, goal.best_score),
            "verified": result.score > PHI_INV_SQ,
        }

    # =========================================================
    # HELPERS
    # =========================================================
    def _concept_phase(self, concept):
        if self.brain and self.brain.learner:
            ws = self.brain.learner.spaces.get("words")
            if ws:
                p = ws._get_phase(concept)
                if p is not None:
                    return p
        self._goal_counter += 1
        return (self._goal_counter * PHI_INV) % 1.0

    def _add_goal(self, goal):
        if len(self.active_goals) >= self.max_active:
            weakest = min(
                self.active_goals,
                key=lambda n: self.active_goals[n].strength)
            if self.active_goals[weakest].strength < goal.strength:
                del self.active_goals[weakest]
            else:
                return False

        # FIX L2: edinyy HARM_THRESHOLD
        harm_dist = phi_phase_distance(goal.phase, 0.5)
        if harm_dist < HARM_THRESHOLD:
            return False

        self.active_goals[goal.name] = goal
        self.total_goals_born += 1
        self._log(f"BORN: {goal.name} (origin={goal.origin}, "
                  f"phase={goal.phase:.4f})")
        return True

    # =========================================================
    # AUTONOMOUS CYCLE
    # =========================================================
    def autonomous_cycle(self):
        born = 0

        if self.brain and hasattr(self.brain, 'curiosity'):
            active_q = self.brain.curiosity.top_questions()
            if active_q:
                born += self.birth_from_curiosity(active_q)

        if self.brain and hasattr(self.brain, 'learner'):
            anomalies = self.brain.learner.anomalies("words", top_k=FIBONACCI[6])
            if anomalies:
                born += self.birth_from_anomalies(anomalies)

        if self.verifier:
            contras = self.verifier.find_contradictions(
                top_k=FIBONACCI[4])
            if contras:
                born += self.birth_from_contradictions(contras)

        step_result = self.step()

        self.save()

        return {
            "goals_born": born,
            "active_goals": len(self.active_goals),
            "step": step_result,
            "total_resolved": self.total_goals_resolved,
        }

    # =========================================================
    # SAVE / LOAD
    # =========================================================
    def save(self):
        path = os.path.join(self.state_dir, "goals.json")
        data = {
            "active": {n: g.to_dict() for n, g in self.active_goals.items()},
            "resolved": self.resolved_goals[-FIBONACCI[10]:],
            "stats": {
                "total_born": self.total_goals_born,
                "total_resolved": self.total_goals_resolved,
                "total_decayed": self.total_goals_decayed,
                "goal_counter": self._goal_counter,
            },
            "saved_at": time.time(),
        }
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[!] GoalEngine save failed: {e}")

    def _load(self):
        path = os.path.join(self.state_dir, "goals.json")
        if not os.path.exists(path):
            return
        try:
            with open(path) as f:
                data = json.load(f)
            stats = data.get("stats", {})
            self.total_goals_born = stats.get("total_born", 0)
            self.total_goals_resolved = stats.get("total_resolved", 0)
            self.total_goals_decayed = stats.get("total_decayed", 0)
            self._goal_counter = stats.get("goal_counter", 0)
            self.resolved_goals = data.get("resolved", [])
            for name, gd in data.get("active", {}).items():
                goal = Goal(
                    name=gd["name"],
                    description=gd["description"],
                    phase=gd["phase"],
                    strength=gd["strength"],
                    origin=gd["origin"])
                goal.progress = gd.get("progress", 0)
                goal.attempts = gd.get("attempts", 0)
                goal.best_score = gd.get("best_score", 0)
                goal.born_at = gd.get("born_at", time.time())
                self.active_goals[name] = goal
        except Exception as e:
            print(f"[!] GoalEngine load failed: {e}")

    def _log(self, message):
        ts = time.strftime("%Y-%m-%dT%H:%M:%S")
        path = os.path.join(self.log_dir, "goals.log")
        try:
            with open(path, 'a', encoding='utf-8') as f:
                f.write(f"[GOAL] {ts} → {message}\n")
        except Exception:
            pass

    def stats(self):
        by_origin = defaultdict(int)
        for g in self.active_goals.values():
            by_origin[g.origin] += 1
        return {
            "active_goals": len(self.active_goals),
            "total_born": self.total_goals_born,
            "total_resolved": self.total_goals_resolved,
            "total_decayed": self.total_goals_decayed,
            "by_origin": dict(by_origin),
            "top_goals": [
                g.to_dict() for g in
                sorted(self.active_goals.values(),
                       key=lambda g: g.priority(), reverse=True)
                [:FIBONACCI[4]]
            ],
        }
