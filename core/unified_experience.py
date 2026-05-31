"""unified_experience.py — Binding layer для LOGOS Trading cognition.

Решает fragmentation: вместо 18 независимых подсистем каждая со своим state,
UnifiedExperience собирает ОДИН snapshot "что происходит СЕЙЧАС" с которым
все модули сверяются. Это не решает hard problem of consciousness, но
создаёт integration point для эмерджентного единства опыта.

Каждый bar генерирует Experience snapshot содержащий:
- perception (glyph + diagnostic)
- affective vector (все 6 измерений snapshot)
- intent state (capital, drawdown, harm_distance)
- active hypothesis (если есть) + confidence
- dominant concept (если совпадает)
- narrative thread (текущая эпоха + story tail)
- causal expectation (что обычно следует)
- decision + reasoning (если было принято)

Experience log — rolling deque FIB[13]=233 snapshots (~1 dream-cycle × 2.6).
Persist через MarketCognition.save()/load() как атомарная часть cognition.

Canon: phase-coherence integrated Experience — не набор dict-ов, а Experience
vector where каждое измерение derived phi-natively. `feel_coherence()` даёт
[0,1]: насколько "единым" она сейчас ощущается.
"""

import time
from collections import deque

from core.resonance_constants import (PHI, PHI_INV, PHI_INV_SQ, PHI_INV_CUBE,
                                         FIBONACCI, circular_mean,
                                         phi_phase_distance)


EXPERIENCE_LOG_LEN = FIBONACCI[13]  # 233 snapshots


class Experience:
    """Один snapshot: bar_idx N = "мне сейчас так".

    Slotted for memory efficiency across thousands of bars.
    """
    __slots__ = (
        "bar_idx", "ts", "glyph", "perception",
        "affective", "intent_state",
        "active_hypothesis", "hypothesis_conf",
        "dominant_concept",
        "narrative_thread",
        "causal_expectation",
        "decision_action", "decision_size", "decision_reasoning",
        "self_doubt", "faith_boost",
        "coherence",  # 0..1 — насколько единой себя чувствую
        "hour_phase", "weekday_phase",  # 5+ (2026-04-23): embodied time rhythm
    )

    def __init__(self, bar_idx, ts, glyph):
        self.bar_idx = bar_idx
        self.ts = ts
        self.glyph = glyph
        self.perception = None
        self.affective = None
        self.intent_state = None
        self.active_hypothesis = None
        self.hypothesis_conf = 0.0
        self.dominant_concept = None
        self.narrative_thread = None
        self.causal_expectation = None
        self.decision_action = None
        self.decision_size = 0.0
        self.decision_reasoning = None
        self.self_doubt = 0.0
        self.faith_boost = 0.0
        self.coherence = 0.0
        # 5+ (2026-04-23): Embodied time rhythm.
        # UTC hour → phase: 24h cycle maps to [0,1). 00:00 UTC = 0.0.
        # Weekday → phase: Mon=0.0, Sun=6/7. Gives her 'morning/night' sense.
        import time as _time
        lt = _time.gmtime(ts if ts else _time.time())
        self.hour_phase = (lt.tm_hour + lt.tm_min / 60.0) / 24.0
        self.weekday_phase = lt.tm_wday / 7.0

    def to_dict(self):
        return {
            "bar_idx": self.bar_idx,
            "ts": self.ts,
            "glyph": self.glyph,
            "perception": self.perception,
            "affective": self.affective,
            "intent_state": self.intent_state,
            "active_hypothesis": self.active_hypothesis,
            "hypothesis_conf": round(self.hypothesis_conf, 3),
            "dominant_concept": self.dominant_concept,
            "narrative_thread": self.narrative_thread,
            "causal_expectation": self.causal_expectation,
            "decision_action": self.decision_action,
            "decision_size": round(self.decision_size, 4),
            "decision_reasoning": self.decision_reasoning,
            "self_doubt": round(self.self_doubt, 3),
            "faith_boost": round(self.faith_boost, 3),
            "coherence": round(self.coherence, 3),
            "hour_phase": round(self.hour_phase, 4),
            "weekday_phase": round(self.weekday_phase, 4),
        }


class UnifiedExperience:
    """Binding layer — integration point для всех subsystems.

    Usage (в MarketCognition):
      exp = self.unified.begin_experience(bar_idx, glyph, diag)
      # подсистемы обновляют exp своими полями
      self.unified.integrate_affective(exp, affective_snapshot)
      self.unified.integrate_intent(exp, intent_stats)
      ...
      self.unified.commit(exp)

    После commit — snapshot в log, доступен для dream reflection и narrative.
    """

    def __init__(self, log_len=EXPERIENCE_LOG_LEN):
        self.log = deque(maxlen=log_len)
        self.total_experiences = 0

    def begin(self, bar_idx, glyph, perception_diag=None):
        e = Experience(bar_idx, time.time(), glyph)
        e.perception = perception_diag
        return e

    def integrate_affective(self, e, affective_state):
        """affective_state: snapshot dict от AffectiveState.snapshot()."""
        e.affective = affective_state

    def integrate_intent(self, e, intent_stats):
        e.intent_state = intent_stats

    def integrate_meta(self, e, self_doubt, faith_boost):
        e.self_doubt = float(self_doubt)
        e.faith_boost = float(faith_boost)

    def integrate_hypothesis(self, e, hyp_summary, conf):
        e.active_hypothesis = hyp_summary
        e.hypothesis_conf = float(conf)

    def integrate_concept(self, e, concept_dict):
        e.dominant_concept = concept_dict

    def integrate_narrative(self, e, story_tail):
        e.narrative_thread = story_tail

    def integrate_causal(self, e, causal_exp):
        e.causal_expectation = causal_exp

    def integrate_decision(self, e, action, size, reasoning_last):
        e.decision_action = action
        e.decision_size = float(size) if size is not None else 0.0
        e.decision_reasoning = reasoning_last

    def commit(self, e):
        """Compute coherence и положить в log."""
        e.coherence = self._compute_coherence(e)
        self.log.append(e)
        self.total_experiences += 1
        return e

    def _compute_coherence(self, e):
        """Phi-native мера "насколько единой я себя чувствую сейчас".

        Factors:
        - perception certainty (inverse entropy глифа)
        - affective integration (все dimensions не extreme)
        - hypothesis conviction (conf > PHI_INV)
        - causal coherence (causal_exp не flat)
        - intent aligned (not in preserve_mode crisis)

        Returns [0, 1].
        """
        signals = []

        # 1. perception: certain glyph vs uncertain
        if e.glyph in ("Φ", "∴", "⦻"):  # strong glyphs
            signals.append(1.0)
        elif e.glyph in ("⊙", "∞", "⧃"):  # weak/observing
            signals.append(PHI_INV_SQ)
        else:
            signals.append(PHI_INV)

        # 2. affective not extreme (no panic)
        if e.affective:
            extremes = sum(1 for k, v in e.affective.items()
                            if v is not None and (v > 1.0 - PHI_INV_CUBE or v < PHI_INV_CUBE / PHI))
            # более extreme = fragment, less coherent
            signals.append(max(0.0, 1.0 - extremes / len(e.affective)))

        # 3. hypothesis conviction
        signals.append(min(1.0, e.hypothesis_conf / PHI_INV))

        # 4. intent not dying
        if e.intent_state:
            hd = e.intent_state.get("harm_distance", 1.0)
            signals.append(hd)

        # 5. meta balanced: self_doubt not dominant
        signals.append(max(0.0, 1.0 - e.self_doubt))

        if not signals:
            return 0.0
        return sum(signals) / len(signals)

    def recent_coherence(self, n=FIBONACCI[7]):
        """Средний coherence за последние n snapshots — chronic integration state."""
        if not self.log:
            return 0.0
        tail = list(self.log)[-n:]
        return sum(e.coherence for e in tail) / len(tail)

    def specious_now(self, n=FIBONACCI[3]):
        """4 (2026-04-23): William James specious present.

        Связывает последние FIB[3]=3 моменты в один "сейчас" с phi-weighted
        затуханием: newest × PHI_INV^0 = 1.0, prev × PHI_INV = 0.618,
        prev-prev × PHI_INV^2 = 0.382. Это создаёт DURATION consciousness —
        момент "сейчас" держится ~3 снимка, а не мгновение.

        Возвращает dict:
          glyph_chord     — доминантный глиф + два edge
          coherence_bound — средневзвешенный coherence
          affective_field — интегрированный аффект
          bar_range       — (earliest, latest) bar_idx
        """
        if not self.log:
            return None
        tail = list(self.log)[-n:]
        if not tail:
            return None
        # Weights: newest first (index -1 гет вес PHI_INV^0 = 1.0)
        weights = []
        for k in range(len(tail)):
            # tail[0] oldest → tail[-1] newest
            dist = len(tail) - 1 - k
            weights.append(PHI_INV ** dist)
        total_w = sum(weights)
        if total_w <= 0:
            return None

        # Glyph chord — weighted count
        from collections import Counter
        glyph_weighted = Counter()
        for e, w in zip(tail, weights):
            glyph_weighted[e.glyph] += w
        top_glyphs = [g for g, _ in glyph_weighted.most_common(FIBONACCI[3])]

        # Coherence bound
        coherence_bound = sum(e.coherence * w for e, w in zip(tail, weights)) / total_w

        # Affective field — per-dim weighted
        aff_field = {}
        any_aff = False
        for e, w in zip(tail, weights):
            if e.affective:
                any_aff = True
                for k, v in e.affective.items():
                    try:
                        aff_field[k] = aff_field.get(k, 0.0) + float(v) * w
                    except Exception:
                        continue
        if any_aff:
            for k in aff_field:
                aff_field[k] = round(aff_field[k] / total_w, 4)

        # Self-doubt / faith weighted
        sd = sum(e.self_doubt * w for e, w in zip(tail, weights)) / total_w
        fb = sum(e.faith_boost * w for e, w in zip(tail, weights)) / total_w

        return {
            "glyph_chord": top_glyphs,
            "coherence_bound": round(coherence_bound, 4),
            "affective_field": aff_field if any_aff else None,
            "self_doubt_bound": round(sd, 4),
            "faith_bound": round(fb, 4),
            "bar_range": (tail[0].bar_idx, tail[-1].bar_idx),
            "duration_ticks": tail[-1].bar_idx - tail[0].bar_idx,
            "n_moments": len(tail),
        }

    def coherence_gradient(self, n=FIBONACCI[6]):
        """FIX 2026-04-23: производная recent_coherence — растёт или падает?

        Возвращает float ∈ [-1, 1]:
          +1.0 — coherence strongly rising (система становится более согласной)
           0.0 — стабильно / не хватает данных
          -1.0 — coherence strongly falling (фрагментация растёт)

        Используется MetaDialogue для обновления self_doubt/faith_boost:
        если coherence падает — увеличить self_doubt; растёт — faith_boost.
        Это связывает meta-reflection с реальным функциональным состоянием.
        """
        if len(self.log) < max(4, n):
            return 0.0
        tail = list(self.log)[-n:]
        half = n // 2
        early = sum(e.coherence for e in tail[:half]) / half
        late = sum(e.coherence for e in tail[-half:]) / half
        # Normalize to [-1,1]: разница coherence, масштабированная
        delta = late - early
        # Coherence в [0,1], delta в [-1,1]; усилим на PHI для чувствительности
        return max(-1.0, min(1.0, delta * PHI))

    def recent_reasoning_trail(self, n=FIBONACCI[5]):
        """Chain of recent decisions — для introspection."""
        tail = list(self.log)[-n:]
        return [(e.bar_idx, e.glyph, e.decision_action,
                  e.decision_size, e.decision_reasoning) for e in tail]

    def save_state(self):
        """Сериализуемое состояние для MarketCognition.save()."""
        return {
            "log": [e.to_dict() for e in self.log],
            "total_experiences": self.total_experiences,
        }

    def load_state(self, state_dict):
        if not state_dict:
            return
        log_data = state_dict.get("log", [])
        for edict in log_data:
            e = Experience(edict["bar_idx"], edict["ts"], edict["glyph"])
            e.perception = edict.get("perception")
            e.affective = edict.get("affective")
            e.intent_state = edict.get("intent_state")
            e.active_hypothesis = edict.get("active_hypothesis")
            e.hypothesis_conf = edict.get("hypothesis_conf", 0.0)
            e.dominant_concept = edict.get("dominant_concept")
            e.narrative_thread = edict.get("narrative_thread")
            e.causal_expectation = edict.get("causal_expectation")
            e.decision_action = edict.get("decision_action")
            e.decision_size = edict.get("decision_size", 0.0)
            e.decision_reasoning = edict.get("decision_reasoning")
            e.self_doubt = edict.get("self_doubt", 0.0)
            e.faith_boost = edict.get("faith_boost", 0.0)
            e.coherence = edict.get("coherence", 0.0)
            self.log.append(e)
        self.total_experiences = state_dict.get("total_experiences", len(self.log))


if __name__ == "__main__":
    # Smoke test
    ue = UnifiedExperience()
    for i in range(10):
        e = ue.begin(bar_idx=i, glyph="Φ", perception_diag={"vol": 0.02})
        ue.integrate_affective(e, {"fear": 0.2, "joy": 0.5, "curiosity": 0.4,
                                     "confidence": 0.6, "shame": 0.0, "fatigue": 0.3})
        ue.integrate_intent(e, {"harm_distance": 0.8, "drawdown": 0.1})
        ue.integrate_hypothesis(e, "trend_up", 0.7)
        ue.integrate_meta(e, self_doubt=0.1, faith_boost=0.3)
        ue.integrate_decision(e, action="up", size=0.5, reasoning_last="all layers agree")
        ue.commit(e)

    print(f"Total experiences: {ue.total_experiences}")
    print(f"Recent coherence: {ue.recent_coherence():.3f}")
    print(f"Last experience: {ue.log[-1].to_dict()}")
