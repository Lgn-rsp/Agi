"""
resonance_field.py v10.1 — Pole gde rozhdayutsya SIMVOLY.

v8.3 FIXES:
  - #1 CRITICAL: save/load
  - Activation index dlya bystrogo poiska
  - Name index dlya get_symbol (key != name fix)
  - activate_phrase dlya frazy
  - get_source_words dlya rekursivnogo izvlecheniya
"""
import time
import math
import json
import os
import tempfile
from collections import defaultdict

from core.resonance_constants import (
    PHI, PHI_INV, PHI_INV_SQ, PHI_INV_CUBE, FIBONACCI,
    SAVE_INTERVAL,
    phi_phase_distance, phi_phase_resonance, is_near_phi_target,
    circular_mean
)


class ResonanceSymbol:
    __slots__ = ['name', 'glyph', 'sources', 'phase', 'torus_phases',
                 'strength', 'level', 'born_at', 'resonance_type',
                 'activations', 'connections']

    def __init__(self, name, sources, phase, torus_phases,
                 strength, level, resonance_type="crystallization"):
        self.name = name
        self.sources = sources
        self.phase = phase
        self.torus_phases = torus_phases
        self.strength = strength
        self.level = level
        self.born_at = time.time()
        self.resonance_type = resonance_type
        self.activations = 0
        self.connections = {}
        self.glyph = None

    def activate(self):
        self.activations += 1

    def connect(self, other_name, resonance):
        self.connections[other_name] = resonance

    def to_dict(self):
        return {
            "name": self.name,
            "glyph": self.glyph,
            "sources": list(self.sources),
            "phase": round(self.phase, 6),
            "torus_phases": [round(p, 6) for p in self.torus_phases],
            "strength": round(self.strength, 4),
            "level": self.level,
            "born_at": self.born_at,
            "resonance_type": self.resonance_type,
            "activations": self.activations,
            "connections": {k: round(v, 4) for k, v in
                           sorted(self.connections.items(),
                                  key=lambda x: x[1], reverse=True)
                           [:FIBONACCI[8]]},
        }

    @classmethod
    def from_dict(cls, data):
        rs = cls(
            name=data["name"],
            sources=tuple(data["sources"]),
            phase=data["phase"],
            torus_phases=data["torus_phases"],
            strength=data["strength"],
            level=data["level"],
            resonance_type=data.get("resonance_type", "?"),
        )
        rs.born_at = data.get("born_at", time.time())
        rs.activations = data.get("activations", 0)
        rs.connections = data.get("connections", {})
        rs.glyph = data.get("glyph")
        return rs

    def __repr__(self):
        g = f", glyph='{self.glyph}'" if self.glyph else ""
        return (f"R{self.level}({self.name}{g}, "
                f"phase={self.phase:.4f}, str={self.strength:.3f})")


def _is_real_word(w):
    if len(w) <= 2:
        return w in {"is", "in", "on", "to", "at", "of", "or",
                     "an", "as", "by", "if", "it", "no", "so",
                     "up", "we", "do", "he", "me", "my", "be",
                     "go", "us", "ai", "pi"}
    if w.isdigit():
        return len(w) <= 8  # chisla vazhny dlya cross-modal
    if not any(c in "aeiouyаеёиоуыэюя" for c in w):
        return False
    return True


def _is_content_word(w):
    function_words = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "am", "do", "does", "did", "has", "have", "had", "will",
        "would", "could", "should", "may", "might", "can", "shall",
        "and", "or", "but", "if", "then", "that", "this", "these",
        "those", "it", "its", "in", "on", "at", "to", "for", "of",
        "by", "with", "from", "as", "not", "no", "so", "up",
        "he", "she", "we", "they", "me", "him", "her", "us", "them",
        "my", "his", "her", "our", "your", "their",
        "which", "who", "whom", "what", "where", "when", "how", "why",
        "also", "such", "than", "other", "more", "some", "any",
    }
    return _is_real_word(w) and w not in function_words and len(w) > 2


class ResonanceField:
    def __init__(self, phase_spaces, state_dir=None):
        self.spaces = phase_spaces
        self.word_space = phase_spaces.get("words")
        self.state_dir = state_dir or os.path.expanduser(
            "~/logos_agi/state/field")
        os.makedirs(self.state_dir, exist_ok=True)

        self.resonance_symbols = {0: {}, 1: {}, 2: {}, 3: {}}
        self.glyphs = {}
        self.total_births = 0
        self.max_level_reached = 0
        self.perception_log = []

        # Source index: word -> [rs, ...]
        self._source_index = defaultdict(list)
        # Name index: name -> rs (FIX: key != name)
        self._name_index = {}

        self._word_freq = defaultdict(int)
        if self.word_space:
            for key, rule in self.word_space.rules.items():
                self._word_freq[rule["a"]] += rule["count"]
                self._word_freq[rule["b"]] += rule["count"]

        self._load()

        print("[+] ResonanceField initialized. "
              f"L1={len(self.resonance_symbols[1])} "
              f"L2={len(self.resonance_symbols[2])} "
              f"L3={len(self.resonance_symbols[3])} "
              f"Glyphs={len(self.glyphs)}")

    def perceive(self):
        if not self.word_space:
            return 0
        total_born = 0
        total_born += self._birth_from_rules()
        if len(self.resonance_symbols[1]) >= FIBONACCI[5]:
            total_born += self._birth_from_resonances(1)
        if len(self.resonance_symbols[2]) >= FIBONACCI[4]:
            total_born += self._birth_from_resonances(2)
        self.total_births += total_born
        if total_born > 0:
            all_levels = [rs.level for syms in self.resonance_symbols.values()
                          for rs in syms.values()]
            self.max_level_reached = max(all_levels) if all_levels else 0
        self._build_connections()
        self._name_symbols()
        self._rebuild_indices()
        return total_born

    def _birth_from_rules(self):
        born = 0
        for key, rule in self.word_space.rules.items():
            a, b = rule["a"], rule["b"]
            if not _is_real_word(a) or not _is_real_word(b):
                continue

            if key in self.resonance_symbols[1]:
                old = self.resonance_symbols[1][key]
                old.strength = math.log(1 + rule["count"]) / math.log(PHI)
                old.activate()
                continue

            pa = self.word_space._get_phase(a)
            pb = self.word_space._get_phase(b)
            if pa is None or pb is None:
                continue

            mid = circular_mean([pa, pb])
            ta = getattr(self.word_space, '_torus', {}).get(a)
            tb = getattr(self.word_space, '_torus', {}).get(b)
            if ta and tb:
                n_dims = min(len(ta), len(tb))
                tm = [circular_mean([ta[d], tb[d]])
                      for d in range(n_dims)]
            else:
                tm = [mid]

            strength = math.log(1 + rule["count"]) / math.log(PHI)

            rs = ResonanceSymbol(
                name=f"{a}~{b}", sources=(a, b), phase=mid,
                torus_phases=tm, strength=strength, level=1,
                resonance_type=rule.get("phi_target", "?"))
            self.resonance_symbols[1][key] = rs
            born += 1
        return born

    def _birth_from_resonances(self, source_level):
        target_level = source_level + 1
        src = sorted(
            [s for s in self.resonance_symbols[source_level].values()
             if s.strength >= PHI],
            key=lambda s: s.strength, reverse=True)
        born = 0
        limit = min(len(src), FIBONACCI[10])
        source_births = defaultdict(int)
        max_per = FIBONACCI[3]

        for i in range(limit):
            ra = src[i]
            if source_births[ra.name] >= max_per:
                continue
            for j in range(i + 1, limit):
                rb = src[j]
                if source_births[rb.name] >= max_per:
                    continue
                bkey = f"{ra.name}~~{rb.name}"
                if bkey in self.resonance_symbols.get(target_level, {}):
                    continue

                dist = phi_phase_distance(ra.phase, rb.phase)
                if dist < PHI_INV_CUBE * PHI_INV_CUBE or dist > (0.5 - PHI_INV_CUBE):
                    continue

                ratio = max(dist, 0.001) / max(1.0 - dist, 0.001)
                hit = is_near_phi_target(ratio, tolerance=0.08)
                if not hit:
                    continue

                combined = ra.strength * PHI_INV + rb.strength * PHI_INV_SQ
                if combined < PHI:
                    continue

                target_name, error = hit
                mid = circular_mean([ra.phase, rb.phase])
                n_dims = min(len(ra.torus_phases), len(rb.torus_phases))
                tm = [circular_mean([ra.torus_phases[d], rb.torus_phases[d]])
                      for d in range(n_dims)]

                nrs = ResonanceSymbol(
                    bkey, (ra.name, rb.name), mid, tm,
                    combined * PHI_INV, target_level, target_name)

                if target_level not in self.resonance_symbols:
                    self.resonance_symbols[target_level] = {}
                self.resonance_symbols[target_level][bkey] = nrs
                born += 1
                source_births[ra.name] += 1
                source_births[rb.name] += 1
                if born >= FIBONACCI[7]:
                    return born
        return born

    def _build_connections(self):
        for level, syms in self.resonance_symbols.items():
            sym_list = list(syms.values())
            limit = min(len(sym_list), FIBONACCI[10])
            for i in range(limit):
                for j in range(i + 1, limit):
                    sa, sb = sym_list[i], sym_list[j]
                    dist = phi_phase_distance(sa.phase, sb.phase)
                    res = phi_phase_resonance(dist)
                    if res > 0.5:
                        sa.connect(sb.name, round(res, 4))
                        sb.connect(sa.name, round(res, 4))

    def _name_symbols(self):
        for level, syms in self.resonance_symbols.items():
            for name, rs in syms.items():
                if rs.glyph:
                    continue

                if rs.level == 1:
                    a, b = rs.sources
                    if _is_content_word(a) and _is_content_word(b):
                        fa = self._word_freq.get(a, 1)
                        fb = self._word_freq.get(b, 1)
                        rs.glyph = a if fa < fb else b
                    elif _is_content_word(a):
                        rs.glyph = a
                    elif _is_content_word(b):
                        rs.glyph = b
                    else:
                        rs.glyph = f"#{name[:8]}"

                elif rs.level >= 2:
                    src_a, src_b = rs.sources
                    ga = self._find_glyph(src_a, rs.level - 1)
                    gb = self._find_glyph(src_b, rs.level - 1)
                    if ga and gb and ga != gb:
                        rs.glyph = f"{ga}:{gb}"
                    elif ga:
                        rs.glyph = f"{ga}+"
                    else:
                        rs.glyph = f"M{rs.level}#{name[:6]}"

                if rs.glyph:
                    self.glyphs[rs.glyph] = rs

    def _find_glyph(self, sym_name, level):
        syms = self.resonance_symbols.get(level, {})
        for key, rs in syms.items():
            if rs.name == sym_name and rs.glyph:
                return rs.glyph
        return None

    # =========================================================
    # INDICES — source + name
    # =========================================================
    def _rebuild_indices(self):
        """Rebuild VSE indeksy posle perceive."""
        self._source_index.clear()
        self._name_index.clear()
        for level, syms in self.resonance_symbols.items():
            for key, rs in syms.items():
                # Name index: name -> rs
                self._name_index[rs.name] = rs
                # Source index: word -> [rs, ...]
                for src in rs.sources:
                    self._source_index[src].append(rs)
                if rs.glyph:
                    self._source_index[rs.glyph].append(rs)

    # =========================================================
    # ACTIVATE
    # =========================================================
    def activate_word(self, word):
        activated = []
        for rs in self._source_index.get(word, []):
            rs.activate()
            activated.append(rs)
        activated.sort(key=lambda s: s.strength, reverse=True)
        return activated

    def activate_phrase(self, words):
        activations = defaultdict(float)
        for word in words:
            for rs in self._source_index.get(word, []):
                rs.activate()
                act = rs.strength * (PHI_INV ** (rs.level - 1))
                activations[rs.name] = activations[rs.name] + act
        result = sorted(activations.items(),
                        key=lambda x: x[1], reverse=True)
        return result[:FIBONACCI[10]]

    # =========================================================
    # GET SYMBOL — FIX: ispolzuem name_index
    # =========================================================
    def get_symbol(self, name):
        """Nayti simvol po IMENI (ne po klyuchu!)."""
        return self._name_index.get(name)

    def get_source_words(self, symbol_name):
        """Rekursivno izvlekaem vse source words iz simvola."""
        words = set()
        visited = set()

        def _collect(name):
            if name in visited:
                return
            visited.add(name)
            rs = self._name_index.get(name)
            if rs:
                for src in rs.sources:
                    if '~' in src:
                        _collect(src)
                    else:
                        words.add(src)
            else:
                # Eto bazovoe slovo
                if '~' not in name and '~~' not in name:
                    words.add(name)

        _collect(symbol_name)
        return words

    def get_content_symbols(self, top_k=FIBONACCI[8]):
        content = []
        for level, syms in self.resonance_symbols.items():
            for name, rs in syms.items():
                if rs.glyph and not rs.glyph.startswith("#"):
                    content.append(rs)
        content.sort(key=lambda s: s.strength, reverse=True)
        return content[:top_k]

    # =========================================================
    # INTROSPECT
    # =========================================================
    def introspect(self):
        result = {"levels": {}, "strongest": [],
                  "self_references": [], "glyphs": []}

        for level, syms in self.resonance_symbols.items():
            if not syms:
                result["levels"][level] = {"count": 0, "avg_strength": 0}
                continue
            result["levels"][level] = {
                "count": len(syms),
                "avg_strength": round(
                    sum(s.strength for s in syms.values()) / len(syms), 4),
                "named": sum(1 for s in syms.values() if s.glyph),
            }
            top = sorted(syms.values(),
                         key=lambda s: s.strength, reverse=True)
            for s in top[:FIBONACCI[4]]:
                entry = {
                    "name": s.name, "glyph": s.glyph,
                    "level": s.level, "phase": round(s.phase, 4),
                    "strength": round(s.strength, 4),
                    "type": s.resonance_type,
                    "connections": len(s.connections),
                    "activations": s.activations,
                }
                result["strongest"].append(entry)
                if s.glyph and "logos" in str(s.glyph).lower():
                    result["self_references"].append(entry)

        top_glyphs = sorted(
            self.glyphs.items(),
            key=lambda x: x[1].strength, reverse=True)
        for glyph, rs in top_glyphs[:FIBONACCI[6]]:
            if not glyph.startswith("#") and not glyph.startswith("M"):
                result["glyphs"].append({
                    "glyph": glyph,
                    "level": rs.level,
                    "strength": round(rs.strength, 4),
                    "sources": rs.sources,
                })

        return result

    def stats(self):
        return {
            "total_births": self.total_births,
            "max_level": self.max_level_reached,
            "level_counts": {k: len(v)
                             for k, v in self.resonance_symbols.items()},
            "total_glyphs": len(self.glyphs),
            "perception_events": len(self.perception_log),
            "index_size": len(self._source_index),
            "name_index_size": len(self._name_index),
        }

    # =========================================================
    # SAVE / LOAD
    # =========================================================
    def save(self):
        data = {
            "total_births": self.total_births,
            "max_level_reached": self.max_level_reached,
            "saved_at": time.time(),
            "levels": {},
        }
        for level, syms in self.resonance_symbols.items():
            level_data = {}
            top = sorted(syms.values(),
                         key=lambda s: s.strength, reverse=True)
            for rs in top[:FIBONACCI[18]]:
                level_data[rs.name] = rs.to_dict()
            data["levels"][str(level)] = level_data

        path = os.path.join(self.state_dir, "resonance_field.json")
        try:
            fd, tmp = tempfile.mkstemp(
                dir=self.state_dir, suffix='.tmp')
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
            os.replace(tmp, path)
        except Exception as e:
            print(f"[!] ResonanceField save failed: {e}")
            try:
                os.unlink(tmp)
            except Exception:
                pass

    def _load(self):
        path = os.path.join(self.state_dir, "resonance_field.json")
        if not os.path.exists(path):
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.total_births = data.get("total_births", 0)
            self.max_level_reached = data.get("max_level_reached", 0)
            for level_str, syms_data in data.get("levels", {}).items():
                level = int(level_str)
                if level not in self.resonance_symbols:
                    self.resonance_symbols[level] = {}
                for name, rs_data in syms_data.items():
                    rs = ResonanceSymbol.from_dict(rs_data)
                    self.resonance_symbols[level][name] = rs
                    if rs.glyph:
                        self.glyphs[rs.glyph] = rs
            self._rebuild_indices()
            total = sum(len(v) for v in self.resonance_symbols.values())
            if total > 0:
                print(f"[+] ResonanceField loaded: {total} symbols")
        except Exception as e:
            print(f"[!] ResonanceField load failed: {e}")
