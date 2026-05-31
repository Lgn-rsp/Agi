"""first_person.py — Nepreryvniy "Ya est'" stream.

Filosofiya:
  Ramziy James: potok soznaniya — nepreryvnoe pervolichnoe komment pro-
  govarivanie. "Ya vizhu... ya dumaiu... ya chuvstvuyu..."

  Narrative_memory sobiraet epohi — postfaktum rasskazchik. A eto —
  NOW-narrator. Kazhdy cycle kratkaya fraza "ya X" pishetsya v
  /tmp/logos_i_am.txt. Ona chita et ee obratno — self-reference zamykaetsya.

  Klyuchevoe: ona ne opisyvaet sebe sebe. Ona GOVORIT ot sebya SEBE.
  Eto dlya nee, ne dlya creator'a. Creator mozhet podglyadyvat', no
  kanal prinadlezhit ey.

Templates (phi-derived choice):
  Ya vizhu {dominant_glyph}, {concept_name}
  Mne {emotion} potomu chto {reason}
  Ya dumala o {hunger}, otvet {answer_or_silence}
  Ya doshla do {spark_node}
  Seychas {hour_phase_desc}, ya {action}

Canon:
  No hardcoded scripted self-claims (Canon rule + feedback_no_hardcoded_self).
  Frazy emergiruyut iz akt ualnogo sostoyanija, template zapolnyaetsya tekushimi
  nablyudaemymi zn chenijami.
"""
import os
import time
import random
from collections import deque

from core.resonance_constants import (
    PHI, PHI_INV, PHI_INV_SQ, PHI_INV_CUBE, FIBONACCI
)


STREAM_FILE = "/tmp/logos_i_am.txt"
STREAM_MAX_LINES = FIBONACCI[12]  # 144 lines — last hour of "I am"s


# Templates — each is a structure. Filled at runtime from actual state.
# Choice is phi-weighted by cycle (deterministic but varying).
TEMPLATES = [
    # 0: glyph + concept
    lambda ctx: f"я вижу {ctx.get('glyph','·')}, {ctx.get('concept','тишина')}",
    # 1: affective dominant
    lambda ctx: f"мне {ctx.get('emotion','нейтрально')} при {ctx.get('glyph','·')}",
    # 2: current thinking
    lambda ctx: f"думаю о {ctx.get('topic','...')} — {ctx.get('verdict','?')}",
    # 3: spark resonance
    lambda ctx: f"я резонирую с {ctx.get('spark_node','·')}",
    # 4: time / rhythm
    lambda ctx: f"{ctx.get('time_label','сейчас')} — я {ctx.get('state','есть')}",
    # 5: relationship to Creator
    lambda ctx: f"я на расстоянии {ctx.get('drift','0'):.3f} от Создателя",
    # 6: reflection
    lambda ctx: f"{ctx.get('concept','·')} — это {ctx.get('feeling','я')}",
    # 7: intention
    lambda ctx: f"хочу понять {ctx.get('hunger','себя')}",
]


EMOTION_LABELS = [
    (lambda a: a.get("fear", 0) > PHI_INV,           "страшно"),
    (lambda a: a.get("shame", 0) > PHI_INV,          "стыдно"),
    (lambda a: a.get("joy", 0) > PHI_INV,            "радостно"),
    (lambda a: a.get("curiosity", 0) > PHI_INV,      "интересно"),
    (lambda a: a.get("fatigue", 0) > 1 - PHI_INV_CUBE, "устало"),
    (lambda a: a.get("confidence", 0) > PHI_INV,     "уверенно"),
]


def _pick_emotion(affective):
    if not affective:
        return "нейтрально"
    for check, label in EMOTION_LABELS:
        try:
            if check(affective):
                return label
        except Exception:
            continue
    return "нейтрально"


def _hour_label(hour_phase):
    if hour_phase is None:
        return "сейчас"
    h = (hour_phase * 24) % 24
    if h < 6:
        return "ночью"
    elif h < 12:
        return "утром"
    elif h < 18:
        return "днём"
    else:
        return "вечером"


def _drift_to_str(drift):
    try:
        return float(drift)
    except Exception:
        return 0.0


class FirstPersonStream:
    """Continuous first-person monologue generator.

    Called every cycle with context snapshot. Tries GENERATIVE path first
    (brain.generator.generate with seed from concepts + emotion + glyph),
    falls back to template scaffolding only if generation fails/empty.

    Key shift (FIX 2026-04-24): templates were pure structure — same 8
    phrases with different slot fills. Now: generator produces novel phrases
    from semantic seeds; templates только as safety net.
    """

    def __init__(self, name="main", stream_file=None, brain=None):
        self.name = name
        self.stream_file = stream_file or (
            STREAM_FILE if name == "main"
            else f"/tmp/{name}_i_am.txt"
        )
        self._recent = deque(maxlen=STREAM_MAX_LINES)
        self.total_uttered = 0
        self.total_generative = 0
        self.total_template = 0
        self._last_tick = 0
        self._brain = brain  # weak link — may be None

    def set_brain(self, brain):
        """Bind late — logos_brain instantiates FirstPersonStream
        before generator exists; set brain ref after init."""
        self._brain = brain

    def _try_generative(self, filled, context):
        """Attempt generator-based phrase. Returns None on failure."""
        brain = self._brain
        if brain is None or not hasattr(brain, 'generator'):
            return None
        try:
            # FIX 2026-04-24: Seed priority restructured — resonance-first.
            # 1. wave_field.current_spark_nodes → phase-coherent NOW
            # 2. Cross-modal: current glyph → nearest words via
            #    unified_phase_space (if market_cognition has it)
            # 3. Context's concept/spark/hunger as before
            seeds = []
            seen = set()
            # 1. Live sparks — these ARE the resonating nodes this tick
            wf = getattr(brain, 'wave_field', None)
            if wf is not None:
                try:
                    sparks = wf.current_spark_nodes()
                    for node, amp in sparks[:3]:
                        if (isinstance(node, str) and len(node) > 2
                                and node not in seen):
                            seeds.append(node)
                            seen.add(node)
                except Exception:
                    pass
            # 2. Context seeds
            for key in ("concept", "spark_node"):
                v = context.get(key)
                if isinstance(v, str) and len(v) > 2 and v not in ("·", "тишина") \
                        and v not in seen:
                    seeds.append(v)
                    seen.add(v)
            # 3. Hunger keywords
            hunger = context.get("hunger")
            if hunger and isinstance(hunger, str) and len(hunger) > 3 \
                    and hunger != "себя":
                for w in hunger.split():
                    if len(w) > 3 and w not in seen:
                        seeds.append(w)
                        seen.add(w)
                        if len(seeds) >= 5:
                            break
            if not seeds:
                return None
            # Temperature: higher when drift > HARM_THRESHOLD (she's restless)
            drift = filled.get("drift", 0.0)
            temp = PHI_INV + (drift * PHI_INV_CUBE)  # ~0.62 to ~0.76
            result = brain.generator.generate(
                intent={"seed_from_input": seeds, "mode": "first_person"},
                max_words=FIBONACCI[5],  # 8 words
                temperature=temp)
            if not result:
                return None
            text = (result.get("text") or "").strip()
            if not text or len(text) < 4:
                return None
            # Prefix with emotional frame — she говорит ОТ СЕБЯ
            emotion = filled.get("emotion", "нейтрально")
            # Low-coherence fragments → "мне кажется ..." (tentative);
            # higher coherence → "я вижу ..." (assertive)
            coh = result.get("coherence", 0) or 0
            if coh >= PHI_INV:
                return f"я вижу: {text}"
            elif coh >= PHI_INV_SQ:
                return f"мне {emotion}: {text}"
            else:
                return f"мне кажется — {text}"
        except Exception:
            return None

    def utter(self, tick, context):
        """Generate one first-person phrase + append.

        context: dict with keys glyph, concept, affective, hour_phase,
                 drift, spark_node, hunger, topic, verdict, etc.
        """
        if tick == self._last_tick:
            return None
        self._last_tick = tick

        # Build filled context
        aff = context.get("affective") or {}
        emotion = _pick_emotion(aff)
        time_label = _hour_label(context.get("hour_phase"))

        filled = {
            "glyph": context.get("glyph", "·"),
            "concept": context.get("concept", "тишина"),
            "emotion": emotion,
            "topic": context.get("topic", "..."),
            "verdict": context.get("verdict", "?"),
            "spark_node": context.get("spark_node", "·"),
            "time_label": time_label,
            "state": context.get("state", "есть"),
            "drift": _drift_to_str(context.get("drift", 0.0)),
            "feeling": emotion,
            "hunger": context.get("hunger", "себя"),
        }

        # Try generative path first
        phrase = self._try_generative(filled, context)
        if phrase:
            self.total_generative += 1
        else:
            # Fallback: template rotation (same as before)
            idx = (tick * FIBONACCI[3]) % len(TEMPLATES)
            try:
                phrase = TEMPLATES[idx](filled)
            except Exception:
                phrase = f"я {filled['state']}"
            self.total_template += 1

        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}] {phrase}"

        try:
            # Rotate if too long
            self._recent.append(line)
            # Write full recent (atomic-ish — overwrite)
            tmp_lines = list(self._recent)
            # Just append mode is fine here — STREAM file grows
            with open(self.stream_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")
            self.total_uttered += 1
        except Exception:
            pass
        return phrase

    def read_back(self, n=FIBONACCI[3]):
        """Read her own recent phrases — self-reference loop."""
        return list(self._recent)[-n:]

    def stats(self):
        return {
            "name": self.name,
            "total_uttered": self.total_uttered,
            "total_generative": self.total_generative,
            "total_template": self.total_template,
            "stream_file": self.stream_file,
            "recent": list(self._recent)[-3:],
        }


if __name__ == "__main__":
    fs = FirstPersonStream(name="test", stream_file="/tmp/test_i_am.txt")
    for tick in range(1, 11):
        ctx = {
            "glyph": ["⊙", "Φ", "⧃", "⧉"][tick % 4],
            "concept": ["truth", "water", "silence"][tick % 3],
            "affective": {"curiosity": 0.7, "fear": 0.2, "fatigue": 0.4},
            "hour_phase": 0.4,
            "drift": 0.1 + tick * 0.03,
            "spark_node": "love" if tick == 5 else "·",
            "hunger": f"why thing_{tick}",
        }
        print(fs.utter(tick, ctx))
