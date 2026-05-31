"""
dialogue_context.py v10.1 — Rabochaya pamyat dialoga.

FIX S2: get_recent_output_words teper korrektno izvlekayet
poslednie slova iz buffera dlya anti-attractor penalty.

Vsyo cherez phi.
"""
import time
from collections import OrderedDict

from core.resonance_constants import (
    PHI, PHI_INV, PHI_INV_SQ, PHI_INV_CUBE, FIBONACCI,
    phi_phase_distance, phi_phase_resonance
)


class DialogueContext:
    def __init__(self, max_size=FIBONACCI[8]):  # 34
        self.buffer = OrderedDict()
        self.max_size = max_size
        self.turn_count = 0
        self.history = []
        self.max_history = FIBONACCI[7]

        # FIX S2: otdelnyy bufer dlya poslednih output slov
        self._recent_output = set()

        print(f"[+] DialogueContext v10.1 initialized. "
              f"Buffer size: {max_size}")

    def new_turn(self, activated_concepts):
        self.turn_count += 1

        # 1. ZATUKHANIYE
        for sym in list(self.buffer.keys()):
            self.buffer[sym] *= PHI_INV

        # 2. DOBAVLENIYE
        for word, strength in activated_concepts:
            if word in self.buffer:
                self.buffer[word] = self.buffer[word] + strength
            else:
                self.buffer[word] = strength

        # 3. SMERT
        dead = [sym for sym, act in self.buffer.items()
                if act < PHI_INV_CUBE]
        for sym in dead:
            del self.buffer[sym]

        # 4. TRIM
        if len(self.buffer) > self.max_size:
            sorted_items = sorted(self.buffer.items(),
                                  key=lambda x: x[1], reverse=True)
            self.buffer = OrderedDict(sorted_items[:self.max_size])

        # 5. ISTORIYA
        top = self.get_top(FIBONACCI[4])
        self.history.append({
            "turn": self.turn_count,
            "time": time.time(),
            "top": [(w, round(a, 3)) for w, a in top],
            "buffer_size": len(self.buffer),
        })
        while len(self.history) > self.max_history:
            self.history.pop(0)

        # FIX S2: zapomnim output slova etogo khoda
        self._recent_output = set(
            w for w, s in activated_concepts if len(str(w)) > 2)

    def get_top(self, n=FIBONACCI[6]):
        sorted_items = sorted(self.buffer.items(),
                              key=lambda x: x[1], reverse=True)
        return sorted_items[:n]

    def get_context_bonus(self):
        return dict(self.buffer)

    def get_topic_continuity(self):
        if self.turn_count < 2:
            return []
        persistent = [(sym, act) for sym, act in self.buffer.items()
                      if act > PHI_INV]
        persistent.sort(key=lambda x: x[1], reverse=True)
        return persistent

    def get_recent_output_words(self):
        """FIX S2: vozvrashchayet slova iz predydushchego otveta."""
        return self._recent_output

    def reset(self):
        self.buffer.clear()
        self.turn_count = 0
        self.history.clear()
        self._recent_output = set()

    def stats(self):
        return {
            "turn_count": self.turn_count,
            "buffer_size": len(self.buffer),
            "total_activation": round(
                sum(self.buffer.values()), 2) if self.buffer else 0,
            "history_length": len(self.history),
            "persistent_topics": len(self.get_topic_continuity()),
            "recent_output_words": len(self._recent_output),
        }
