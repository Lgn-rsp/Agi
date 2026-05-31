"""
self_awareness.py — Sistema nablyudaet SEBYA kak objekt.

Logos imeet svoy simvol v fazovom prostranstve (phase = PHI_INV).
Posle kazhdogo deystviya sistema generiruet TEKST o tom chto sdelala,
i skarmlivayet ego sebe. Tak "logos", "dream", "crystallize",
"learn", "discover" stanovyatsya simvolami v fazovom prostranstve,
i svyazi mezhdu nimi otrazhayut realnuyu arkhitekturu sistemy.

Eto ne imitatsiya — eto kristallizatsiya patternov sobstvennogo povedeniya.
"""
import time
from core.resonance_constants import (
    PHI, PHI_INV, FIBONACCI,
    phi_phase_distance
)


class SelfAwareness:
    """
    Logos nablyudaet sebya.
    Kazhdoe deystviye -> tekst -> observe -> kristallizatsiya.
    """

    def __init__(self, learner):
        self.learner = learner
        self.total_self_observations = 0
        self.observation_log = []
        self.max_log = FIBONACCI[15]  # 987

        print(f"[+] SelfAwareness initialized. "
              f"Logos = phase {PHI_INV:.6f}")

    def observe_action(self, action, details=None):
        """
        Sistema nablyudaet svoe deystviye.
        Generiruet tekst i skarmlivayet sebe.
        """
        phrases = self._action_to_phrases(action, details or {})

        # Amplifikatsiya: FIBONACCI[3]=3 povtora (kak dream observe)
        for phrase in phrases:
            for _ in range(FIBONACCI[3]):  # 3x — usilenie signala
                self.learner.learn_text(phrase)

        self.total_self_observations += 1

        entry = {
            "action": action,
            "phrases": phrases,
            "time": time.time(),
        }
        self.observation_log.append(entry)
        while len(self.observation_log) > self.max_log:
            self.observation_log.pop(0)

        return phrases

    def _action_to_phrases(self, action, details):
        """
        TOLKO FAKTY. Nikakikh interpretatsiy.
        Sistema sama reshayet chto eto znachit.
        """
        phrases = []

        if action == "learn":
            words = details.get("words", 0)
            topic = details.get("topic", "")
            if topic:
                phrases.append(f"logos {topic}")

        elif action == "dream":
            disc = details.get("discoveries", 0)
            for d in details.get("examples", [])[:3]:
                if "a" in d and "b" in d:
                    phrases.append(f"logos {d['a']} {d['b']}")

        elif action == "crystallize":
            a = details.get("a", "")
            b = details.get("b", "")
            if a and b:
                phrases.append(f"logos {a} {b}")

        elif action == "think":
            pass  # molchaniye — mysli ne nuzhdayutsya v slovakh

        elif action == "seek":
            topic = details.get("topic", "")
            if topic:
                phrases.append(f"logos {topic}")

        elif action == "reflect":
            pass

        elif action == "cycle":
            pass  # tsikly — vnutrenniy ritm, ne slova

        return phrases


    def stats(self):
        return {
            "total_self_observations": self.total_self_observations,
            "log_size": len(self.observation_log),
        }
