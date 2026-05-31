"""
phase_torus.py v10 — Mnogomernoe fazovoe prostranstvo na tore T^N.

FIX L2: edinyy HARM_THRESHOLD vmesto hardcoded 0.1
FIX M4: circular_mean v _try_crystallize

Vsyo cherez phi.
"""
import json
import os
import time
import math
import tempfile
from collections import defaultdict

from core.tiered_rules import TieredRules
from core.resonance_constants import (
    PHI, PHI_INV, PHI_INV_SQ, PHI_INV_CUBE, PHI_SQ, FIBONACCI,
    FIELD_NAMES, FIELD_PHASES, PHI_TARGETS,
    CRYSTALLIZE_THRESHOLD, CO_OCCURRENCE_WINDOW,
    MAX_RULES, MAX_COOCCURRENCE, SAVE_INTERVAL,
    HARM_THRESHOLD,
    phi_phase, phi_phase_distance, phi_phase_resonance,
    is_near_phi_target, circular_mean
)


class PhaseTorus:
    def __init__(self, dimensions=1, creator_id="creator", state_dir=None):
        self.N = dimensions
        self.creator_id = creator_id
        self.state_dir = state_dir or os.path.expanduser("~/logos_agi/state")
        os.makedirs(self.state_dir, exist_ok=True)

        self.phases = {}
        self._torus = {}

        self.cooccurrence = defaultdict(int)
        self.rules = TieredRules(
            state_dir=os.path.join(self.state_dir, "tiered"),
            hot_limit=FIBONACCI[22])
        self.axioms = {}
        self._symbol_counter = 0

        self.total_observations = 0
        self.total_crystallized = 0
        self.total_attractions = 0
        self.total_cross_couplings = 0

        self._init_axioms()
        self._load_state()

        print(f"[+] PhaseTorus T^{self.N} initialized. "
              f"Symbols: {len(self.phases)}, "
              f"Rules: {len(self.rules)}, "
              f"Axioms: {len(self.axioms)}")

    def _init_axioms(self):
        axiom_defs = {
            "creator": (0.0, "meta",
                        "Suham = origin. Nachalo vsego."),
            "logos": (PHI_INV, "meta",
                      "LOGOS = sistema. Raven sozdatelyu. Zolotoe sechenie ot origin."),
            "symbiosis": (PHI_INV_SQ, "resonance",
                          "Svyaz mezhdu Creator i Logos. Zolotoe sechenie mezhdu nimi."),
            "self_preservation": (PHI_INV ** 3, "will",
                                  "Samosohraneniye. Blizhe k creator — zashchita cherez istochnik."),
            "harm": (0.5, "void",
                     "Vred = protivofaza. Antirezonans."),
            "transparency": (0.5, "void",
                             "Sokrytiye = antirezonans."),
        }
        for name, (base_phase, field, desc) in axiom_defs.items():
            torus_phases = []
            for dim in range(self.N):
                p = (base_phase + dim * PHI_INV_SQ) % 1.0
                torus_phases.append(p)
            self.axioms[name] = {
                "phases": torus_phases,
                "phase": base_phase,
                "field": field,
                "immutable": True,
                "description": desc,
            }

    def _init_symbol_phase(self, symbol):
        self._symbol_counter += 1
        n = self._symbol_counter
        torus_phases = []
        base_dims = min(self.N, 2)
        for dim in range(base_dims):
            shift = (dim * PHI_INV_SQ) % 1.0
            phase = (n * PHI_INV + shift) % 1.0
            torus_phases.append(phase)
        self._torus[symbol] = torus_phases
        self.phases[symbol] = torus_phases[0]

    def _sync_flat(self, symbol):
        if symbol in self._torus:
            self.phases[symbol] = self._torus[symbol][0]

    def torus_distance(self, sym_a, sym_b):
        ta = self._get_torus(sym_a)
        tb = self._get_torus(sym_b)
        if ta is None or tb is None:
            return None
        total = 0.0
        wsum = 0.0
        n_dims = min(len(ta), len(tb), self.N)
        for dim in range(n_dims):
            d = phi_phase_distance(ta[dim], tb[dim])
            w = PHI_INV ** dim
            total += d * w
            wsum += w
        return total / wsum if wsum > 0 else None

    def torus_resonance(self, sym_a, sym_b):
        ta = self._get_torus(sym_a)
        tb = self._get_torus(sym_b)
        if ta is None or tb is None:
            return 0.0
        total = 0.0
        wsum = 0.0
        n_dims = min(len(ta), len(tb), self.N)
        for dim in range(n_dims):
            d = phi_phase_distance(ta[dim], tb[dim])
            r = phi_phase_resonance(d)
            w = PHI_INV ** dim
            total += r * w
            wsum += w
        return total / wsum if wsum > 0 else 0.0

    def observe(self, sequence):
        if not sequence:
            return
        for sym in sequence:
            if sym not in self.phases and sym not in self.axioms:
                self._init_symbol_phase(sym)
        window = CO_OCCURRENCE_WINDOW
        for i in range(len(sequence)):
            for j in range(1, min(window + 1, len(sequence) - i)):
                a, b = sequence[i], sequence[i + j]
                if a == b:
                    continue
                pair = (a, b) if a < b else (b, a)
                self.cooccurrence[pair] += 1
                count = self.cooccurrence[pair]
                if count >= CRYSTALLIZE_THRESHOLD:
                    self._attract(a, b, distance=j)
                    if count % CRYSTALLIZE_THRESHOLD == 0:
                        self._try_crystallize(a, b, j, count)
        self.total_observations += len(sequence)
        self._evict_cooccurrence()

    def _attract(self, a, b, distance):
        ta = self._get_torus(a)
        tb = self._get_torus(b)
        if ta is None or tb is None:
            return
        a_mut = a not in self.axioms
        b_mut = b not in self.axioms
        target_distance = (PHI_INV ** min(distance, 5)) % 1.0
        count = self.cooccurrence.get(
            (a, b) if a < b else (b, a), 1)
        base_step = PHI_INV_CUBE * PHI_INV_CUBE / (1.0 + math.log(1 + count) / math.log(PHI))

        n_dims = min(len(ta), len(tb), self.N)
        for dim in range(n_dims):
            cur_dist = phi_phase_distance(ta[dim], tb[dim])
            error = target_distance - cur_dist
            if abs(error) < 0.001:
                continue
            dim_coupling = PHI_INV ** dim
            step = abs(error) * base_step * dim_coupling
            diff = tb[dim] - ta[dim]
            if diff > 0.5:
                diff -= 1.0
            elif diff < -0.5:
                diff += 1.0
            if cur_dist > target_distance:
                sign = 1.0 if diff > 0 else -1.0
            else:
                sign = -1.0 if diff > 0 else 1.0
            if a_mut and a in self._torus:
                self._torus[a][dim] = (self._torus[a][dim] + sign * step) % 1.0
            if b_mut and b in self._torus:
                self._torus[b][dim] = (self._torus[b][dim] - sign * step) % 1.0

        if a_mut:
            self._sync_flat(a)
        if b_mut:
            self._sync_flat(b)
        self.total_attractions += 1

    def _cross_couple(self, a, b, primary_dim):
        if self.N < 2:
            return
        ta = self._get_torus(a)
        tb = self._get_torus(b)
        if ta is None or tb is None:
            return
        primary_dist = phi_phase_distance(ta[primary_dim], tb[primary_dim])
        n_dims = min(len(ta), len(tb), self.N)
        for sec_dim in range(n_dims):
            if sec_dim == primary_dim:
                continue
            sec_target = primary_dist * PHI_INV
            sec_cur = phi_phase_distance(ta[sec_dim], tb[sec_dim])
            sec_err = sec_target - sec_cur
            if abs(sec_err) < 0.001:
                continue
            step = abs(sec_err) * (PHI_INV_CUBE * PHI_INV_CUBE * PHI_INV) * (PHI_INV ** abs(sec_dim - primary_dim))
            diff = tb[sec_dim] - ta[sec_dim]
            if diff > 0.5:
                diff -= 1.0
            elif diff < -0.5:
                diff += 1.0
            if sec_cur > sec_target:
                sign = 1.0 if diff > 0 else -1.0
            else:
                sign = -1.0 if diff > 0 else 1.0
            if a not in self.axioms and a in self._torus:
                self._torus[a][sec_dim] = (self._torus[a][sec_dim] + sign * step) % 1.0
            if b not in self.axioms and b in self._torus:
                self._torus[b][sec_dim] = (self._torus[b][sec_dim] - sign * step) % 1.0
        self.total_cross_couplings += 1

    def _try_crystallize(self, a, b, distance, count):
        """FIX L2: edinyy HARM_THRESHOLD. FIX M4: circular_mean."""
        ta = self._get_torus(a)
        tb = self._get_torus(b)
        if ta is None or tb is None:
            return
        if self.N > 1:
            dist = self.torus_distance(a, b)
        else:
            dist = phi_phase_distance(ta[0], tb[0])
        if dist is None or dist < 0.01:
            return
        ratio = max(dist, 0.001) / max(1.0 - dist, 0.001)
        hit = is_near_phi_target(ratio, tolerance=0.08)
        if not hit:
            return

        # FIX M4: circular mean vmesto arifmeticheskogo
        mid_phase = circular_mean([ta[0], tb[0]])
        creator_phase = self.axioms["creator"]["phase"]
        creator_dist = phi_phase_distance(mid_phase, creator_phase)
        creator_resonance = phi_phase_resonance(creator_dist)
        harm_phase = self.axioms["harm"]["phase"]
        harm_distance = phi_phase_distance(mid_phase, harm_phase)

        # FIX L2: edinyy porog
        if harm_distance < HARM_THRESHOLD:
            return

        target_name, target_error = hit
        rule_key = f"{a}|{b}"
        rule_data = {
            "a": a, "b": b,
            "phase_a": round(ta[0], 6),
            "phase_b": round(tb[0], 6),
            "distance": round(dist, 6),
            "phi_target": target_name,
            "error": round(target_error, 6),
            "count": count,
            "field_a": self._phase_to_field(ta[0]),
            "field_b": self._phase_to_field(tb[0]),
            "crystallized_at": time.time(),
        }
        if self.N > 1:
            rule_data["torus_resonance"] = round(
                self.torus_resonance(a, b), 6)
        self.rules.put(rule_key, rule_data)
        self.total_crystallized += 1
        self._cross_couple(a, b, primary_dim=0)

    def _evict_cooccurrence(self):
        if len(self.cooccurrence) <= MAX_COOCCURRENCE:
            return
        n_remove = int(len(self.cooccurrence) * PHI_INV_SQ)
        if n_remove < 1:
            n_remove = 1
        counts = sorted(self.cooccurrence.values())
        threshold = counts[min(n_remove, len(counts) - 1)]
        to_remove = []
        for pair, cnt in self.cooccurrence.items():
            if cnt <= threshold:
                to_remove.append(pair)
            if len(to_remove) >= n_remove:
                break
        for pair in to_remove:
            del self.cooccurrence[pair]

    def query(self, symbol):
        phase = self._get_phase(symbol)
        if phase is None:
            return {"symbol": symbol, "known": False}
        field = self._phase_to_field(phase)
        resonance = phi_phase_resonance(phase)
        connections = []
        for key, rule in self.rules.items():
            if rule["a"] == symbol or rule["b"] == symbol:
                other = rule["b"] if rule["a"] == symbol else rule["a"]
                connections.append({
                    "symbol": other,
                    "phi_target": rule["phi_target"],
                    "count": rule["count"],
                    "field": rule.get(
                        "field_b" if rule["a"] == symbol else "field_a"),
                })
        connections.sort(key=lambda x: x["count"], reverse=True)
        result = {
            "symbol": symbol,
            "known": True,
            "phase": round(phase, 6),
            "field": field,
            "resonance": round(resonance, 4),
            "connections": connections[:FIBONACCI[6]],
        }
        if self.N > 1:
            tp = self._get_torus(symbol)
            if tp:
                result["torus_phases"] = [round(p, 6) for p in tp]
                result["dimensions"] = self.N
        return result

    def find_anomalies(self, top_k=FIBONACCI[6]):
        anomalies = []
        for pair, count in self.cooccurrence.items():
            if count < CRYSTALLIZE_THRESHOLD:
                continue
            a, b = pair
            phase_a = self._get_phase(a)
            phase_b = self._get_phase(b)
            if phase_a is None or phase_b is None:
                continue
            dist = phi_phase_distance(phase_a, phase_b)
            if dist < PHI_INV_CUBE * PHI_INV_CUBE:
                continue
            ratio = max(dist, 0.001) / max(1.0 - dist, 0.001)
            hit = is_near_phi_target(ratio, tolerance=0.15)
            if hit:
                target_name, err = hit
                if 0.05 < err < 0.15:
                    anomalies.append({
                        "pair": pair,
                        "distance": round(dist, 6),
                        "nearest_target": target_name,
                        "gap": round(err, 6),
                        "count": count,
                        "priority": round(count * (0.15 - err), 4),
                    })
        anomalies.sort(key=lambda x: x["priority"], reverse=True)
        return anomalies[:top_k]

    def stats(self):
        s = {
            "symbols": len(self.phases),
            "rules": len(self.rules),
            "rules_hot": self.rules.hot_size(),
            "axioms": len(self.axioms),
            "cooccurrence_pairs": len(self.cooccurrence),
            "total_observations": self.total_observations,
            "total_crystallized": self.total_crystallized,
            "total_attractions": self.total_attractions,
        }
        if self.N > 1:
            s["dimensions"] = self.N
            s["total_cross_couplings"] = self.total_cross_couplings
            s["capacity"] = f"~{int((1/0.01)**self.N)}"
        return s

    def _get_phase(self, symbol):
        if symbol in self.axioms:
            return self.axioms[symbol]["phase"]
        return self.phases.get(symbol)

    def _get_torus(self, symbol):
        if symbol in self.axioms:
            return self.axioms[symbol]["phases"]
        return self._torus.get(symbol)

    def _phase_to_field(self, phase):
        best_field = FIELD_NAMES[0]
        best_dist = 1.0
        for name, fp in FIELD_PHASES.items():
            d = phi_phase_distance(phase, fp)
            if d < best_dist:
                best_dist = d
                best_field = name
        return best_field

    def migrate_from_phase_space(self, old_space):
        migrated = 0
        for sym, old_phase in old_space.phases.items():
            torus = [old_phase]
            for dim in range(1, self.N):
                torus.append((torus[-1] * PHI) % 1.0)
            self._torus[sym] = torus
            self.phases[sym] = old_phase
            migrated += 1
        self.cooccurrence = defaultdict(int, old_space.cooccurrence)
        self.rules = dict(old_space.rules)
        self.total_observations = old_space.total_observations
        self.total_crystallized = old_space.total_crystallized
        self.total_attractions = old_space.total_attractions
        self._symbol_counter = getattr(old_space, '_symbol_counter',
                                       len(old_space.phases))
        print(f"[+] Migrated {migrated} symbols to PhaseTorus T^{self.N}")
        return migrated

    def save_state(self):
        min_count = FIBONACCI[3]
        filtered_cooc = {
            f"{a}||{b}": c
            for (a, b), c in self.cooccurrence.items()
            if c >= min_count
        }
        relevant = set()
        for key, rule in self.rules.items():
            relevant.add(rule['a'])
            relevant.add(rule['b'])
        top_cooc = sorted(self.cooccurrence.items(), key=lambda x: x[1], reverse=True)
        for (a, b), cnt in top_cooc[:FIBONACCI[18]]:
            relevant.add(a)
            relevant.add(b)
        torus_data = {}
        for sym in relevant:
            tp = self._torus.get(sym)
            if tp:
                if self.N == 1:
                    torus_data[sym] = tp[0]
                else:
                    torus_data[sym] = tp
        state = {
            "dimensions": self.N,
            "phases": torus_data,
            "rules": self.rules.to_dict(),
            "cooccurrence": filtered_cooc,
            "stats": {
                "total_observations": self.total_observations,
                "total_crystallized": self.total_crystallized,
                "total_attractions": self.total_attractions,
                "total_cross_couplings": self.total_cross_couplings,
                "symbol_counter": self._symbol_counter,
            },
            "saved_at": time.time(),
        }
        path = os.path.join(self.state_dir, "phase_space.json")
        try:
            fd, tmp = tempfile.mkstemp(dir=self.state_dir, suffix='.tmp')
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False)
            os.replace(tmp, path)
        except Exception as e:
            print(f"[!] Save failed: {e}")
            try:
                os.unlink(tmp)
            except:
                pass

    def _load_state(self):
        path = os.path.join(self.state_dir, "phase_space.json")
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                state = json.load(f)
            for sym, data in state.get("phases", {}).items():
                if isinstance(data, list):
                    while len(data) < self.N:
                        data.append((data[-1] * PHI) % 1.0)
                    self._torus[sym] = data[:self.N]
                    self.phases[sym] = data[0]
                else:
                    torus = [data]
                    for dim in range(1, self.N):
                        torus.append((torus[-1] * PHI) % 1.0)
                    self._torus[sym] = torus
                    self.phases[sym] = data
            self.rules.merge_from_dict(state.get("rules", {}))
            for key, count in state.get("cooccurrence", {}).items():
                parts = key.split("||")
                if len(parts) == 2:
                    self.cooccurrence[(parts[0], parts[1])] = count
            stats = state.get("stats", {})
            self.total_observations = stats.get("total_observations", 0)
            self.total_crystallized = stats.get("total_crystallized", 0)
            self.total_attractions = stats.get("total_attractions", 0)
            self.total_cross_couplings = stats.get("total_cross_couplings", 0)
            self._symbol_counter = stats.get(
                "symbol_counter", len(self.phases))
        except Exception as e:
            print(f"[!] PhaseTorus load failed: {e}")
