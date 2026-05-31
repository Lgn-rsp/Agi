"""definition_extractor.py — Izvlechenie definicii pri learn-time.

Filosofiya:
  Vikipediya napisana tak: "Water is a transparent liquid." "Время — это..."
  Eti patterny opredeleniy — ZOLOTO dlya 'what is X' zaprosov.

  Do etogo fix'a brain na zapros 'what is water' delal sheer retrieval
  (tikh bazhe+vyazhe+schast'e), vyduvaya wiki-chunks po phase-proximity.
  Teper my sohranyaem realnye definicii i mozhem otvechat kratko i tochno.

Structura:
  definitions: {subject: [(predicate, confidence, count)]}
    "water" -> [("liquid", 0.93, 47), ("substance", 0.72, 12), ...]

Patterny EN:
  "X is a/an/the Y"
  "X are Y"
  "X means Y"
  "X refers to Y"

Patterny RU:
  "X — это Y"
  "X является Y"
  "X это Y" (без тире)

Canon:
  Confidence = phi-weighted kolichestvo podverzhenij:
    conf = 1 - PHI_INV ** count  (saturates k 1.0 pri ~10 podverzhdenii)
  Storage atomic (tempfile + os.replace).
"""
import os
import re
import json
import tempfile
import time
from collections import defaultdict

from core.resonance_constants import (
    PHI, PHI_INV, PHI_INV_SQ, PHI_INV_CUBE, FIBONACCI
)


# EN patterns — capture head noun (skip leading adjective)
# "X is a/an/the [adj]? Y" — capture both [adj] Y as predicate
EN_PATTERNS = [
    # "X is a transparent liquid" → predicate="transparent liquid" (up to 2 words after article)
    re.compile(r"\b(\w{3,20})\s+is\s+(?:a |an |the )?((?:\w{3,20}\s+){0,1}\w{3,25})\b", re.IGNORECASE),
    re.compile(r"\b(\w{3,20})\s+are\s+(?:a |an |the )?((?:\w{3,20}\s+){0,1}\w{3,25})\b", re.IGNORECASE),
    re.compile(r"\b(\w{3,20})\s+means\s+(\w{3,25})\b", re.IGNORECASE),
    re.compile(r"\b(\w{3,20})\s+refers\s+to\s+(\w{3,25})\b", re.IGNORECASE),
]

RU_PATTERNS = [
    re.compile(r"\b(\w{3,20})\s+[—-]\s*это\s+((?:\w{3,20}\s+){0,1}\w{3,25})\b", re.IGNORECASE | re.UNICODE),
    re.compile(r"\b(\w{3,20})\s+является\s+((?:\w{3,20}\s+){0,1}\w{3,25})\b", re.IGNORECASE | re.UNICODE),
    re.compile(r"\b(\w{4,20})\s+—\s+(\w{4,25})\b", re.UNICODE),
]

# Stopwords (articles, aux verbs etc.) that shouldn't be definitions
STOP_DEFINERS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "this", "that", "these", "those", "it", "its",
    "of", "in", "on", "at", "to", "for", "by", "with",
    "этот", "это", "тот", "один", "два", "этой", "так",
    "the", "of", "one", "or", "for",
}


class DefinitionExtractor:
    """Izvlekaet i khranit X is-a Y definicii iz tekstov."""

    def __init__(self, state_path=None):
        self.state_path = state_path
        # subject -> Counter({predicate: count})
        self.defs = defaultdict(lambda: defaultdict(int))
        self.total_extracted = 0
        self.total_texts = 0

    def extract(self, text):
        """Na kusok teksta — izvlekaet opredelenia.

        Vozvrashchaet list of (subject, predicate, pattern_source).
        """
        if not text:
            return []
        out = []
        # Limit text scan (wiki texts can be huge — cost O(N))
        max_chars = FIBONACCI[15]  # ~987 chars per pass
        if len(text) > max_chars:
            text = text[:max_chars]
        for pat in EN_PATTERNS + RU_PATTERNS:
            for m in pat.finditer(text):
                subj, pred = m.group(1).lower(), m.group(2).lower()
                if subj == pred:
                    continue
                if subj in STOP_DEFINERS or pred in STOP_DEFINERS:
                    continue
                if len(subj) < 3 or len(pred) < 3:
                    continue
                self.defs[subj][pred] += 1
                out.append((subj, pred, pat.pattern[:40]))
                self.total_extracted += 1
        if out:
            self.total_texts += 1
        return out

    def define(self, subject, top_k=FIBONACCI[3]):
        """Vernut naibolee uverennye opredelenia dlya subject.

        Vozvrashchaet list of dict {predicate, confidence, count}.
        """
        subject = subject.lower().strip()
        if subject not in self.defs:
            return []
        preds = self.defs[subject]
        if not preds:
            return []
        out = []
        for pred, count in preds.items():
            # phi-weighted confidence: saturates pri ~10 podverzhdenii
            conf = 1.0 - (PHI_INV ** min(count, 20))
            out.append({
                "predicate": pred,
                "confidence": round(conf, 3),
                "count": count,
            })
        out.sort(key=lambda x: (-x["count"], -x["confidence"]))
        return out[:top_k]

    def format_answer(self, subject, lang="auto"):
        """Return natural language answer 'subject is X' or None if unknown."""
        definitions = self.define(subject)
        if not definitions:
            return None
        top = definitions[0]
        preds = [d["predicate"] for d in definitions]
        if lang == "ru":
            if len(preds) == 1:
                return f"{subject} — это {preds[0]}"
            return f"{subject} — это {preds[0]} (также: {', '.join(preds[1:])})"
        # default EN
        if len(preds) == 1:
            return f"{subject} is {preds[0]}"
        return f"{subject} is {preds[0]} (also: {', '.join(preds[1:])})"

    def save(self):
        if not self.state_path:
            return
        try:
            os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
            data = {
                "defs": {k: dict(v) for k, v in self.defs.items()},
                "total_extracted": self.total_extracted,
                "total_texts": self.total_texts,
                "saved_at": time.time(),
            }
            # Canon #4: atomic write
            fd, tmp = tempfile.mkstemp(dir=os.path.dirname(self.state_path),
                                         suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False)
                os.replace(tmp, self.state_path)
            except Exception:
                try: os.unlink(tmp)
                except Exception: pass
                raise
        except Exception:
            pass

    def load(self):
        if not self.state_path or not os.path.exists(self.state_path):
            return
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for subj, preds in data.get("defs", {}).items():
                self.defs[subj] = defaultdict(int, preds)
            self.total_extracted = data.get("total_extracted", 0)
            self.total_texts = data.get("total_texts", 0)
        except Exception:
            pass

    def stats(self):
        return {
            "subjects": len(self.defs),
            "total_extracted": self.total_extracted,
            "total_texts": self.total_texts,
            "top_subjects": [
                (s, sum(p.values()))
                for s in list(self.defs.keys())[:10]
                for p in [self.defs[s]]
            ][:10],
        }


if __name__ == "__main__":
    de = DefinitionExtractor()
    test_texts = [
        "Water is a transparent liquid. Water is the chemical substance.",
        "Time is a fundamental quantity. Time means passage of events.",
        "Вода — это прозрачная жидкость. Вода является веществом.",
    ]
    for t in test_texts:
        res = de.extract(t)
        print(f"'{t[:40]}...' → {res}")
    print()
    print("define('water'):", de.define("water"))
    print("answer water:", de.format_answer("water"))
    print("answer вода:", de.format_answer("вода", lang="ru"))
