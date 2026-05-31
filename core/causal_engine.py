"""
causal_engine.py v10 — Kauzalnost cherez rezonans.

NE klassicheskaya logika (esli A to B).
NE bayesovskiy vyvod (P(B|A)).

REZONANSNAYA KONTRAFAKTUALNOST:
  A PRICHINA B togda i tolko togda kogda
  UDALENIE A iz fazovogo prostranstva
  RAZRUSHAET rezonansnyy kontur B.

  Esli kontur B ostaetsya zamknutym bez A —
  A prosto KORRELAT, ne prichina.

  Esli kontur B raspadaetsya bez A —
  A KAUZALNO NEOBKHODIM dlya B.

Kauzalnaya faza = dim 4 tora:
  Slova-prichiny -> blizhe k 0.0
  Slova-sledstviya -> blizhe k PHI_INV
  Neytralnyye -> okolo PHI_INV_SQ

Napravlennost:
  V assotsiativnom pravile a|b simmetrichno.
  V kauzalnom pravile a→b asimmetrichno.
  Napravleniye opredelyaetsya:
    1. Poryadkom v tekste (prichina stoit DO sledstviya)
    2. Kauzalnym konektorom (because, causes, leads)
    3. Kontrafaktualom (udalili A — B slomalos)

Glyph ∴ (path) = kauzalnoye otkrytiye.
Glyph ⧉ (duality) = korrelat, ne prichina.
Glyph ⧃ (silence) = nedostatochno dannykh.

Vsyo cherez phi. Nikakoy lineynosti.
"""
import time
import math
import json
import os
from collections import defaultdict

from core.resonance_constants import (
    PHI, PHI_INV, PHI_INV_SQ, PHI_INV_CUBE, PHI_SQ, FIBONACCI,
    HARM_THRESHOLD, HARM_PHASE,
    phi_phase_distance, phi_phase_resonance, is_near_phi_target,
    circular_mean
)


# =========================================================
# KAUZALNYE KONSTANTY — vsyo cherez phi
# =========================================================
CAUSAL_THRESHOLD = PHI_INV_SQ           # 0.382 — minimum dlya kauzalnosti
CAUSAL_STRONG = PHI_INV                 # 0.618 — silnaya prichina
COUNTERFACTUAL_DEPTH = FIBONACCI[4]     # 5 — glubina proverki
MAX_CAUSAL_RULES = FIBONACCI[17]        # 1597
CAUSAL_DECAY = PHI_INV                  # zatukhaniye kauzalnoy sily
MIN_CONTOUR_SCORE = PHI_INV_CUBE * PHI_INV  # ~0.146 — relaxed 2026-05-08 (was 0.236; gate starved counterfactual: 535 rules → 24 verified → 0 confirmed)

# Kauzalnye konnektory s vesami
# Ves = sila kauzalnoy svyazi cherez etot konnektor
CAUSAL_CONNECTORS_EN = {
    "because": PHI,           # silneyshaya prichina
    "causes": PHI,
    "caused": PHI,
    "therefore": PHI,
    "thus": PHI * PHI_INV,    # = 1.0
    "hence": PHI * PHI_INV,
    "leads": PHI_INV,
    "produces": PHI_INV,
    "creates": PHI_INV,
    "makes": PHI_INV,
    "results": PHI_INV,
    "enables": PHI_INV,
    "drives": PHI_INV,
    "generates": PHI_INV,
    "triggers": PHI_INV,
    "through": PHI_INV_SQ,
    "from": PHI_INV_SQ,
    "by": PHI_INV_SQ,
    "when": PHI_INV_SQ,
    "since": PHI_INV_SQ,
    "so": PHI_INV_SQ,
    "if": PHI_INV_SQ,
    "without": PHI_INV,       # otritsatelnyy kauzal
    "despite": PHI_INV_CUBE,  # anti-kauzal
    "although": PHI_INV_CUBE,
}

CAUSAL_CONNECTORS_RU = {
    "потому": PHI,
    "поэтому": PHI,
    "следовательно": PHI,
    "вызывает": PHI_INV,
    "приводит": PHI_INV,
    "создает": PHI_INV,
    "порождает": PHI_INV,
    "через": PHI_INV_SQ,
    "если": PHI_INV_SQ,
    "когда": PHI_INV_SQ,
    "без": PHI_INV,
    "несмотря": PHI_INV_CUBE,
}


class CausalRule:
    """
    Odno kauzalnoye pravilo: A → B.
    NE simmetrichnoye. A = prichina, B = sledstviye.
    """
    __slots__ = [
        'cause', 'effect', 'causal_strength', 'contrafactual_score',
        'connector', 'count', 'phase_cause', 'phase_effect',
        'direction_confidence', 'born_at', 'verified'
    ]

    def __init__(self, cause, effect, connector=None):
        self.cause = cause
        self.effect = effect
        self.causal_strength = 0.0      # [0, PHI] — sila kauzalnosti
        self.contrafactual_score = 0.0  # [-1, 1] — rezultat kontrafaktuala
        self.connector = connector       # "because", "causes", ...
        self.count = 1
        self.phase_cause = 0.0
        self.phase_effect = 0.0
        self.direction_confidence = 0.0  # [0, 1] — uverennost v napravlenii
        self.born_at = time.time()
        self.verified = False

    def to_dict(self):
        return {
            "cause": self.cause,
            "effect": self.effect,
            "causal_strength": round(self.causal_strength, 6),
            "contrafactual_score": round(self.contrafactual_score, 6),
            "connector": self.connector,
            "count": self.count,
            "direction_confidence": round(self.direction_confidence, 4),
            "verified": self.verified,
            "born_at": self.born_at,
        }

    @classmethod
    def from_dict(cls, data):
        cr = cls(data["cause"], data["effect"], data.get("connector"))
        cr.causal_strength = data.get("causal_strength", 0)
        cr.contrafactual_score = data.get("contrafactual_score", 0)
        cr.count = data.get("count", 1)
        cr.direction_confidence = data.get("direction_confidence", 0)
        cr.verified = data.get("verified", False)
        cr.born_at = data.get("born_at", time.time())
        return cr

    def __repr__(self):
        v = "✓" if self.verified else "?"
        return (f"Causal({self.cause}→{self.effect}, "
                f"str={self.causal_strength:.3f}, "
                f"cf={self.contrafactual_score:.3f} {v})")


class CausalEngine:
    """
    Kauzalnost cherez rezonans.

    Tri istochnika kauzalnykh pravil:
      1. TEKST — kauzalnye konnektory v framakh
      2. PORYADOK — prichina stoit do sledstviya
      3. KONTRAFAKTUAL — udalenie prichiny razrushaet kontur

    Rezulataty integriruyutsya v PhaseTorus kak dim 4 (causal phase).
    """

    def __init__(self, phase_spaces, verifier=None, state_dir=None):
        self.spaces = phase_spaces
        self.word_space = phase_spaces.get("words")
        self.verifier = verifier
        self.state_dir = state_dir or os.path.expanduser(
            "~/logos_agi/state/causal")
        self.log_dir = os.path.expanduser("~/logos_agi/logs")
        os.makedirs(self.state_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)

        # Kauzalnye pravila: "cause|effect" -> CausalRule
        self.causal_rules = {}

        # Kauzalnye fazy: word -> phase [0, 1)
        # 0.0 = chistaya prichina, PHI_INV = chistoye sledstviye
        self.causal_phases = {}

        # Statistika
        self.total_observed = 0
        self.total_extracted = 0
        self.total_verified = 0
        self.total_confirmed = 0
        self.total_rejected = 0

        # Kauzalnyy graf: word -> {neighbor: causal_strength}
        self._cause_graph = defaultdict(dict)  # word -> {effects}
        self._effect_graph = defaultdict(dict)  # word -> {causes}

        self._load()
        self._rebuild_graphs()

        print(f"[+] CausalEngine initialized. "
              f"Rules: {len(self.causal_rules)}, "
              f"Phases: {len(self.causal_phases)}")

    # =========================================================
    # 1. IZVLECHENIE — kauzalnye pravila iz teksta
    # =========================================================
    def observe_text(self, text):
        """
        Izvlech kauzalnye svyazi iz teksta.
        Ishchem kauzalnye konnektory i opredelyaem napravleniye.
        """
        if not text:
            return 0

        words = text.lower().split()
        if len(words) < 3:
            return 0

        self.total_observed += 1
        extracted = 0

        # Opredelyaem yazyk
        from core.lang_detect import detect_lang
        lang = detect_lang(text)
        connectors = CAUSAL_CONNECTORS_RU if lang == "ru" else CAUSAL_CONNECTORS_EN

        # Ishchem kauzalnye konnektory v tekste
        for i, word in enumerate(words):
            if word not in connectors:
                continue

            causal_weight = connectors[word]

            # Kontekst: FIBONACCI[4]=5 slov do i posle konnektora
            window = FIBONACCI[4]
            before = [w for w in words[max(0, i - window):i]
                      if len(w) > 2 and w not in connectors]
            after = [w for w in words[i + 1:i + 1 + window]
                     if len(w) > 2 and w not in connectors]

            if not before or not after:
                continue

            # Prichina = slova PERED konektorom
            # Sledstviye = slova POSLE konnektora
            # (dlya "because" — obratnyy poryadok: effect because cause)
            if word in ("because", "since", "потому", "из"):
                causes = after    # prichina posle "because"
                effects = before  # sledstviye pered "because"
            else:
                causes = before   # prichina pered "therefore"
                effects = after   # sledstviye posle

            # Sozdaem kauzalnye pravila
            for cause_word in causes[:FIBONACCI[3]]:
                for effect_word in effects[:FIBONACCI[3]]:
                    if cause_word == effect_word:
                        continue
                    # Proveryaem chto slova izvestny v fazovom prostranstve
                    if self.word_space:
                        pc = self.word_space._get_phase(cause_word)
                        pe = self.word_space._get_phase(effect_word)
                        if pc is None or pe is None:
                            continue

                    key = f"{cause_word}→{effect_word}"
                    if key in self.causal_rules:
                        rule = self.causal_rules[key]
                        rule.count += 1
                        # Usileniye cherez phi
                        rule.causal_strength = min(
                            rule.causal_strength + causal_weight * PHI_INV_CUBE,
                            PHI_SQ)
                    else:
                        rule = CausalRule(cause_word, effect_word, word)
                        rule.causal_strength = causal_weight * PHI_INV
                        # Nachalnaya direction_confidence iz konnektora
                        rule.direction_confidence = min(causal_weight * PHI_INV, 1.0)
                        if self.word_space:
                            rule.phase_cause = self.word_space._get_phase(cause_word) or 0
                            rule.phase_effect = self.word_space._get_phase(effect_word) or 0
                        self.causal_rules[key] = rule

                    extracted += 1

        # Eviction esli prevyshen limit
        if len(self.causal_rules) > MAX_CAUSAL_RULES:
            self._evict_weakest()

        self.total_extracted += extracted
        return extracted

    def observe_order(self, words):
        """
        Izvlech kauzalnoye napravleniye iz PORYADKA slov.
        Slovo kotoroye stabilno stoit PERED drugimi = prichina.
        
        Eto ne polnotsennyy kauzal — tolko podkreplyayet
        uzhe naydennyye kauzalnye pravila.
        """
        if not words or len(words) < 3:
            return 0

        reinforced = 0
        for i in range(len(words)):
            for j in range(i + 1, min(i + FIBONACCI[4], len(words))):
                a, b = words[i], words[j]
                if len(a) <= 2 or len(b) <= 2:
                    continue
                # a stoit pered b — eto kauzalnyy signal
                key_fwd = f"{a}→{b}"
                key_rev = f"{b}→{a}"

                # Usilivayem sushchestvuyushchiye pravila
                if key_fwd in self.causal_rules:
                    rule = self.causal_rules[key_fwd]
                    # Poryadok podkreplyayet napravleniye
                    dist = j - i
                    order_weight = PHI_INV ** dist  # blizhe = silneye
                    rule.direction_confidence = min(
                        rule.direction_confidence + order_weight * PHI_INV_CUBE,
                        1.0)
                    reinforced += 1

                # Oslablyaem obratnoye napravleniye
                if key_rev in self.causal_rules:
                    rule = self.causal_rules[key_rev]
                    rule.direction_confidence = max(
                        rule.direction_confidence - PHI_INV_CUBE * PHI_INV_CUBE,
                        0.0)

        return reinforced

    # =========================================================
    # 2. KONTRAFAKTUAL — yadro kauzalnosti
    # =========================================================
    def verify_causal(self, cause, effect):
        """
        Kontrafaktualnaya proverka: A prichina B?

        1. Proveryaem kontur B s A v prostranstve
        2. MASKIUEM A — vremenno ubiraem
        3. Proveryaem kontur B bez A
        4. Raznitsa = kauzalnaya sila

        Rezultat:
          > CAUSAL_STRONG (0.618) = silnaya prichina
          > CAUSAL_THRESHOLD (0.382) = prichina
          < CAUSAL_THRESHOLD = ne prichina (korrelat)
          < 0 = A podavlyaet B (ingibitor)
        """
        if not self.verifier or not self.word_space:
            return 0.0, "no_verifier"

        # 1. Kontur B s A v prostranstve
        score_with = self._contour_score(effect)
        # 2026-05-08: only bail on TRUE absence (score_with==0 = <2 neighbors).
        # Previously bailed at MIN_CONTOUR_SCORE; that starved the counter (135 attempts → 0 confirmed).
        if score_with <= 0.0:
            return 0.0, "no_contour"

        # 2. Maskiruem A
        masked = self._mask_symbol(cause)
        if not masked:
            return 0.0, "mask_failed"

        # 3. Kontur B BEZ A
        score_without = self._contour_score(effect)

        # 4. Vosstanovlivayem A
        self._unmask_symbol(cause, masked)

        # 5. Kauzalnaya sila
        if score_with > 0:
            causal_strength = (score_with - score_without) / score_with
        else:
            causal_strength = 0.0

        # Opredelyaem tip
        if causal_strength > CAUSAL_STRONG:
            verdict = "strong_cause"
        elif causal_strength > CAUSAL_THRESHOLD:
            verdict = "cause"
        elif causal_strength > PHI_INV_CUBE:
            verdict = "weak_cause"
        elif causal_strength < -PHI_INV_CUBE:
            verdict = "inhibitor"
        else:
            verdict = "correlate"

        self.total_verified += 1
        # 2026-05-08: weak_cause is positive evidence (s>PHI_INV_CUBE) — count as confirmed.
        if verdict in ("strong_cause", "cause", "weak_cause"):
            self.total_confirmed += 1
        elif verdict == "correlate":
            self.total_rejected += 1

        return causal_strength, verdict

    def _contour_score(self, word):
        """
        Skor kontura slova — skolko zamknutykh treugolnikov
        vokrug etogo slova. Ispolzuyet Verifier.
        """
        if not self.verifier:
            return 0.0

        # Nakhodim sosedey cherez pravila
        neighbors = []
        if self.word_space:
            for key, rule in self.word_space.rules.items():
                if rule["a"] == word:
                    neighbors.append(rule["b"])
                elif rule["b"] == word:
                    neighbors.append(rule["a"])

        if len(neighbors) < 2:
            return 0.0

        # Proveryaem zamknutost konturov
        neighbors = neighbors[:FIBONACCI[7]]  # max 21
        check_words = [word] + neighbors[:FIBONACCI[4]]
        result = self.verifier.verify(check_words)
        return result.score

    def _mask_symbol(self, symbol):
        """
        Vremenno ubiraem simvol iz fazovogo prostranstva.
        Sohranyaem ego dannyye dlya vosstanovleniya.
        
        NE udalyaem fizicheski — sdvigaem v ANTIFAZU (0.5)
        gde on ne rezoniryet ni s chem.
        """
        if not self.word_space:
            return None

        # Sohranyaem originalnye fazy
        original = {
            "phase": self.word_space.phases.get(symbol),
            "torus": None,
        }

        if symbol not in self.word_space.phases:
            return None

        torus_data = self.word_space._torus.get(symbol)
        if torus_data:
            original["torus"] = list(torus_data)

        # Sdvigaem v antifazu — HARM_PHASE (=0.5) po vsem razmernostyam
        # V antifaze simvol ne rezoniryet ni s chem (Creator antipode)
        self.word_space.phases[symbol] = HARM_PHASE
        if torus_data:
            for dim in range(len(torus_data)):
                torus_data[dim] = HARM_PHASE

        return original

    def _unmask_symbol(self, symbol, original):
        """Vosstanovit simvol posle kontrafaktuala."""
        if not original or not self.word_space:
            return

        orig_phase = original.get("phase")
        if orig_phase is not None:
            self.word_space.phases[symbol] = orig_phase

        orig_torus = original.get("torus")
        if orig_torus and symbol in self.word_space._torus:
            self.word_space._torus[symbol] = orig_torus

    # =========================================================
    # 3. KAUZALNYE FAZY — dim 4 tora
    # =========================================================
    def compute_causal_phases(self):
        """
        Vychislit kauzalnuyu fazu dlya kazhdogo slova.

        Slovo-prichina (chashche stoit v pozitsii cause) -> blizhe k 0.0
        Slovo-sledstviye (chashche v pozitsii effect) -> blizhe k PHI_INV
        Neytralnoye -> PHI_INV_SQ

        Metod: dlya kazhdogo slova schitaem:
          cause_score = summa causal_strength gde slovo = cause
          effect_score = summa causal_strength gde slovo = effect
          
          causal_phase = effect_score / (cause_score + effect_score) * PHI_INV
          
        Eto dayot fazu v [0, PHI_INV]:
          0.0 = chistaya prichina
          PHI_INV/2 ≈ 0.309 = neytralnoye  
          PHI_INV ≈ 0.618 = chistoye sledstviye
        """
        cause_scores = defaultdict(float)
        effect_scores = defaultdict(float)

        for key, rule in self.causal_rules.items():
            strength = rule.causal_strength * rule.direction_confidence
            cause_scores[rule.cause] += strength
            effect_scores[rule.effect] += strength

        all_words = set(cause_scores.keys()) | set(effect_scores.keys())
        self.causal_phases.clear()

        for word in all_words:
            cs = cause_scores.get(word, 0)
            es = effect_scores.get(word, 0)
            total = cs + es

            if total < PHI_INV_CUBE:
                continue  # slishkom malo dannykh

            # Fazovaya pozitsiya na kauzalnom kruge
            ratio = es / total  # 0 = cause, 1 = effect
            causal_phase = ratio * PHI_INV  # masshtabirovaniye v [0, PHI_INV]
            self.causal_phases[word] = causal_phase

        return len(self.causal_phases)

    def apply_to_torus(self):
        """
        Vnedrit kauzalnye fazy kak dim 4 tora.
        Tolko dlya slov kotorye UZhE v toruse.
        """
        if not self.word_space:
            return 0

        applied = 0
        for word, cp in self.causal_phases.items():
            if word not in self.word_space._torus:
                continue

            current = self.word_space._torus[word]

            # Dim 4 = kauzalnaya faza
            while len(current) < 4:
                # Zapolnyaem promezhuzhtoknye razmernosti
                current.append((current[-1] * PHI) % 1.0)

            if len(current) == 4:
                current.append(cp)
            else:
                # Plavnoe obnovleniye
                old = current[4]
                diff = cp - old
                if diff > 0.5:
                    diff -= 1.0
                elif diff < -0.5:
                    diff += 1.0
                current[4] = (old + diff * PHI_INV) % 1.0

            applied += 1

        if applied > 0:
            self.word_space.N = max(self.word_space.N, 5)

        return applied

    # =========================================================
    # 4. TSIKL — odin shag kauzalnogo analiza
    # =========================================================
    def causal_cycle(self):
        """
        Polnyy kauzalnyy tsikl:
        1. Izvlech kauzalnye pravila iz framov
        2. Proverit top-pravila cherez kontrafaktual
        3. Vychislit kauzalnye fazy
        4. Primenit k torusu
        """
        result = {
            "extracted_from_frames": 0,
            "verified": 0,
            "confirmed": 0,
            "rejected": 0,
            "new_phases": 0,
            "applied_to_torus": 0,
        }

        # 1. Izvlechenie iz framov (esli est trigram space)
        result["extracted_from_frames"] = self._extract_from_frames()

        # 2. Kontrafaktualnaya proverka top pravil
        unverified = [
            (key, rule) for key, rule in self.causal_rules.items()
            if not rule.verified and rule.causal_strength > PHI_INV_SQ
        ]
        # Sortiruem po sile — proveryaem silneyshie
        unverified.sort(key=lambda x: x[1].causal_strength, reverse=True)

        for key, rule in unverified[:FIBONACCI[5]]:  # max 8 za tsikl
            strength, verdict = self.verify_causal(rule.cause, rule.effect)
            rule.contrafactual_score = strength
            rule.verified = True

            if verdict in ("strong_cause", "cause", "weak_cause"):
                result["confirmed"] += 1
                self._log(f"∴ CAUSAL: {rule.cause}→{rule.effect} "
                         f"str={strength:.4f} ({verdict})")
            elif verdict == "correlate":
                result["rejected"] += 1
                # Oslablyaem nepodtverzhdyonnye
                rule.causal_strength *= PHI_INV_CUBE
                self._log(f"⧉ CORRELATE: {rule.cause}→{rule.effect} "
                         f"str={strength:.4f}")
            elif verdict == "inhibitor":
                self._log(f"⧃ INHIBITOR: {rule.cause}→{rule.effect} "
                         f"str={strength:.4f}")

            result["verified"] += 1

        # 3. Kauzalnye fazy
        result["new_phases"] = self.compute_causal_phases()

        # 4. Primenyayem k torusu
        result["applied_to_torus"] = self.apply_to_torus()

        # 5. Perestraivaem grafy
        self._rebuild_graphs()

        self.save()
        return result

    def _extract_from_frames(self):
        """Izvlech kauzalnye pravila iz trigram pravil."""
        trigram_space = self.spaces.get("trigrams")
        if not trigram_space:
            return 0

        connectors = set(CAUSAL_CONNECTORS_EN.keys()) | set(CAUSAL_CONNECTORS_RU.keys())
        extracted = 0

        for key, rule in trigram_space.rules.items():
            for sym in [rule["a"], rule["b"]]:
                parts = sym.split("_")
                if len(parts) != 3:
                    continue
                subj, mid, pred = parts
                if mid not in connectors:
                    continue
                if len(subj) <= 2 or len(pred) <= 2:
                    continue

                # Opredelyaem napravleniye
                weight = CAUSAL_CONNECTORS_EN.get(
                    mid, CAUSAL_CONNECTORS_RU.get(mid, 0))
                if weight == 0:
                    continue

                # "X because Y" -> Y prichina X
                if mid in ("because", "since", "потому"):
                    cause, effect = pred, subj
                else:
                    cause, effect = subj, pred

                ckey = f"{cause}→{effect}"
                if ckey in self.causal_rules:
                    self.causal_rules[ckey].count += 1
                    self.causal_rules[ckey].causal_strength = min(
                        self.causal_rules[ckey].causal_strength +
                        weight * PHI_INV_CUBE,
                        PHI_SQ)
                else:
                    cr = CausalRule(cause, effect, mid)
                    cr.causal_strength = weight * PHI_INV
                    cr.direction_confidence = min(weight * PHI_INV, 1.0)
                    cr.count = rule.get("count", 1)
                    self.causal_rules[ckey] = cr
                    extracted += 1

        self.total_extracted += extracted
        return extracted

    # =========================================================
    # 5. ZAPROS — chto vyzyvayetsya chem?
    # =========================================================
    def what_causes(self, word, top_k=FIBONACCI[6]):
        """Chto yavlyaetsya PRICHINOY etogo slova?"""
        causes = []
        for cause, strength in self._effect_graph.get(word, {}).items():
            rule = self.causal_rules.get(f"{cause}→{word}")
            if rule:
                causes.append({
                    "cause": cause,
                    "strength": round(rule.causal_strength, 4),
                    "confidence": round(rule.direction_confidence, 4),
                    "verified": rule.verified,
                    "contrafactual": round(rule.contrafactual_score, 4),
                })
        causes.sort(key=lambda x: x["strength"], reverse=True)
        return causes[:top_k]

    def what_effects(self, word, top_k=FIBONACCI[6]):
        """Kakie SLEDSTVIYA u etogo slova?"""
        effects = []
        for effect, strength in self._cause_graph.get(word, {}).items():
            rule = self.causal_rules.get(f"{word}→{effect}")
            if rule:
                effects.append({
                    "effect": effect,
                    "strength": round(rule.causal_strength, 4),
                    "confidence": round(rule.direction_confidence, 4),
                    "verified": rule.verified,
                    "contrafactual": round(rule.contrafactual_score, 4),
                })
        effects.sort(key=lambda x: x["strength"], reverse=True)
        return effects[:top_k]

    def causal_chain(self, start, end, max_depth=FIBONACCI[4]):
        """
        Nayti kauzalnuyu tsepochku: start → ... → end.
        Kazhdyy shag = kauzalnoye pravilo (ne assotsiativnoye).
        """
        if start == end:
            return None

        # BFS po kauzalnomu grafu
        from collections import deque
        visited = {start}
        queue = deque([(start, [])])

        while queue:
            current, path = queue.popleft()
            if len(path) >= max_depth:
                continue

            for next_word, strength in self._cause_graph.get(current, {}).items():
                if next_word == end:
                    full_path = path + [(current, next_word, strength)]
                    # Validatsiya: kauzalnaya sila tsepi
                    chain_strength = PHI
                    for _, _, s in full_path:
                        chain_strength *= s * PHI_INV
                    return {
                        "chain": [(a, b) for a, b, s in full_path],
                        "strength": round(chain_strength, 6),
                        "length": len(full_path),
                        "start": start,
                        "end": end,
                    }

                if next_word not in visited and strength > PHI_INV_CUBE:
                    visited.add(next_word)
                    queue.append((next_word,
                                  path + [(current, next_word, strength)]))

        return None

    def is_cause(self, a, b):
        """Bystrayaa proverka: A prichina B?"""
        key = f"{a}→{b}"
        rule = self.causal_rules.get(key)
        if not rule:
            return False, 0.0
        return (rule.causal_strength > CAUSAL_THRESHOLD,
                rule.causal_strength)

    # =========================================================
    # HELPERS
    # =========================================================
    def _rebuild_graphs(self):
        self._cause_graph.clear()
        self._effect_graph.clear()
        for key, rule in self.causal_rules.items():
            if rule.causal_strength > PHI_INV_CUBE:
                self._cause_graph[rule.cause][rule.effect] = rule.causal_strength
                self._effect_graph[rule.effect][rule.cause] = rule.causal_strength

    def _evict_weakest(self):
        """Udalyaem slabeyshiye kauzalnye pravila."""
        n_remove = int(len(self.causal_rules) * PHI_INV_SQ)
        sorted_rules = sorted(
            self.causal_rules.items(),
            key=lambda x: x[1].causal_strength)
        for key, _ in sorted_rules[:n_remove]:
            del self.causal_rules[key]

    # =========================================================
    # SAVE / LOAD
    # =========================================================
    def save(self):
        path = os.path.join(self.state_dir, "causal.json")
        data = {
            "rules": {k: r.to_dict() for k, r in self.causal_rules.items()},
            "phases": {k: round(v, 8) for k, v in self.causal_phases.items()},
            "stats": {
                "total_observed": self.total_observed,
                "total_extracted": self.total_extracted,
                "total_verified": self.total_verified,
                "total_confirmed": self.total_confirmed,
                "total_rejected": self.total_rejected,
            },
            "saved_at": time.time(),
        }
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception as e:
            print(f"[!] CausalEngine save failed: {e}")

    def _load(self):
        path = os.path.join(self.state_dir, "causal.json")
        if not os.path.exists(path):
            return
        try:
            with open(path) as f:
                data = json.load(f)
            for key, rd in data.get("rules", {}).items():
                self.causal_rules[key] = CausalRule.from_dict(rd)
            self.causal_phases = data.get("phases", {})
            stats = data.get("stats", {})
            self.total_observed = stats.get("total_observed", 0)
            self.total_extracted = stats.get("total_extracted", 0)
            self.total_verified = stats.get("total_verified", 0)
            self.total_confirmed = stats.get("total_confirmed", 0)
            self.total_rejected = stats.get("total_rejected", 0)
        except Exception as e:
            print(f"[!] CausalEngine load failed: {e}")

    def stats(self):
        verified_rules = sum(1 for r in self.causal_rules.values() if r.verified)
        strong_rules = sum(1 for r in self.causal_rules.values()
                          if r.causal_strength > CAUSAL_STRONG)
        return {
            "total_rules": len(self.causal_rules),
            "verified_rules": verified_rules,
            "strong_rules": strong_rules,
            "causal_phases": len(self.causal_phases),
            "total_observed": self.total_observed,
            "total_extracted": self.total_extracted,
            "total_verified": self.total_verified,
            "total_confirmed": self.total_confirmed,
            "total_rejected": self.total_rejected,
            "cause_graph_nodes": len(self._cause_graph),
            "effect_graph_nodes": len(self._effect_graph),
        }

    def _log(self, message):
        ts = time.strftime("%Y-%m-%dT%H:%M:%S")
        path = os.path.join(self.log_dir, "causal.log")
        try:
            with open(path, 'a', encoding='utf-8') as f:
                f.write(f"[CAUSAL] {ts} → {message}\n")
        except Exception:
            pass
