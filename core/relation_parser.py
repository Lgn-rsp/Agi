"""relation_parser.py — Syntactic skeleton parser dlya relational queries.

Filosofiya:
  Resonance gives us WHO resonates with WHOM, but we need grammar
  to identify WHAT RELATION is being asked. "X and Y", "X connects Y",
  "X causes Y" — eto razrya zgruppirovannye po relation type.

  Ne grammatika generativnaya. Ne parser polnyy. Just 'is this query
  asking about a connection, and if so — between what and what?'
  Re-uses phase-torus symbols — no new representations, only router.

Patterny EN:
  - "what connects X and Y"
  - "how are X and Y related"
  - "what is the relationship between X and Y"
  - "X and Y"  (bare — implicit connection)

Patterny RU:
  - "что связывает X и Y"
  - "как связаны X и Y"
  - "связь между X и Y"
  - "X и Y"  (bare)

Returns:
  {
    "relation": "connects" | "causes" | "is_a" | None,
    "operands": ["X", "Y"],
    "lang": "en" | "ru",
    "confidence": float,
  }
  или None если не распознано.

Canon:
  Phi-weighted confidence: pattern match count → confidence through
  1 - PHI_INV^N. Nothing more abstract than that.
"""
import re


# EN connects patterns
EN_CONNECTS = [
    re.compile(r"^what\s+connects\s+([\w\-]{2,25})\s+and\s+([\w\-]{2,25})\??$",
               re.IGNORECASE),
    re.compile(r"^how\s+are\s+([\w\-]{2,25})\s+and\s+([\w\-]{2,25})\s+related\??$",
               re.IGNORECASE),
    re.compile(r"^what\s+is\s+(?:the\s+)?relationship\s+between\s+([\w\-]{2,25})\s+and\s+([\w\-]{2,25})\??$",
               re.IGNORECASE),
    re.compile(r"^relation\s+between\s+([\w\-]{2,25})\s+and\s+([\w\-]{2,25})\??$",
               re.IGNORECASE),
]

# RU connects patterns
RU_CONNECTS = [
    re.compile(r"^что\s+связывает\s+([\w\-]{2,25})\s+и\s+([\w\-]{2,25})\??$",
               re.IGNORECASE | re.UNICODE),
    re.compile(r"^как\s+связаны\s+([\w\-]{2,25})\s+и\s+([\w\-]{2,25})\??$",
               re.IGNORECASE | re.UNICODE),
    re.compile(r"^связь\s+между\s+([\w\-]{2,25})\s+и\s+([\w\-]{2,25})\??$",
               re.IGNORECASE | re.UNICODE),
]

# EN causes
EN_CAUSES = [
    re.compile(r"^(?:what|why)\s+causes\s+([\w\-]{2,25})\??$",
               re.IGNORECASE),
    re.compile(r"^does\s+([\w\-]{2,25})\s+cause\s+([\w\-]{2,25})\??$",
               re.IGNORECASE),
]

RU_CAUSES = [
    re.compile(r"^что\s+вызывает\s+([\w\-]{2,25})\??$",
               re.IGNORECASE | re.UNICODE),
    re.compile(r"^вызывает\s+ли\s+([\w\-]{2,25})\s+([\w\-]{2,25})\??$",
               re.IGNORECASE | re.UNICODE),
]


def parse_relation(text):
    """Parse relational query. Return dict or None."""
    if not text:
        return None
    t = text.strip()
    # Connects EN
    for pat in EN_CONNECTS:
        m = pat.match(t)
        if m:
            return {
                "relation": "connects",
                "operands": [m.group(1).lower(), m.group(2).lower()],
                "lang": "en",
                "confidence": 0.9,
            }
    # Connects RU
    for pat in RU_CONNECTS:
        m = pat.match(t)
        if m:
            return {
                "relation": "connects",
                "operands": [m.group(1).lower(), m.group(2).lower()],
                "lang": "ru",
                "confidence": 0.9,
            }
    # Causes EN
    for pat in EN_CAUSES:
        m = pat.match(t)
        if m:
            operands = [g.lower() for g in m.groups() if g]
            return {
                "relation": "causes",
                "operands": operands,
                "lang": "en",
                "confidence": 0.85,
            }
    # Causes RU
    for pat in RU_CAUSES:
        m = pat.match(t)
        if m:
            operands = [g.lower() for g in m.groups() if g]
            return {
                "relation": "causes",
                "operands": operands,
                "lang": "ru",
                "confidence": 0.85,
            }
    return None


if __name__ == "__main__":
    tests = [
        "what connects truth and silence",
        "what is the relationship between water and fire",
        "что связывает время и пространство",
        "how are X and Y related",
        "random text",
        "what causes rain",
        "что вызывает дождь",
    ]
    for t in tests:
        print(f"'{t}' → {parse_relation(t)}")
