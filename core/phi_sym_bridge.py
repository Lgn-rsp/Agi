"""
phi_sym_bridge.py — Bridge between PhiSym (numerical+context) and
PhaseTorus (linguistic). Allows numerical concepts to be added to
LOGOS knowledge graph and queried via phase resonance.

Two directions:
  symbol_to_torus(sym, torus, level)  — register PhiSym as a torus symbol
  torus_to_sym(symbol_str, torus)     — wrap torus symbol as PhiSym

Use cases:
  - Numerical literals appearing in text get encoded with phase
  - PhiSym concepts (units, ratios) become queryable via phase_torus
  - Math-aware respond: "5 apples × 3" returns 15 apples via PhiSym path

Vsyo cherez phi.
"""
import math
from typing import Optional

from core.resonance_constants import PHI, PHI_INV, FIELD_PHASES, FIELD_NAMES
from core.phi_symbolic import PhiSym


def symbol_to_torus(sym: PhiSym, torus, level: str = "words") -> bool:
    """Register PhiSym as a phase_torus symbol (read-only torus does nothing).

    Side effects: torus.phases[name] = sym.phase, axiom-style tagging.
    Returns True if added, False if name conflict or torus invalid.
    """
    if not torus or not hasattr(torus, "phases"):
        return False
    name = sym.name or sym._auto_name(sym.to_value())
    if name in torus.phases:
        return False  # don't overwrite existing
    torus.phases[name] = sym.phase
    # Optionally store tags as field associations — skip for safety
    return True


def torus_to_sym(name: str, torus) -> Optional[PhiSym]:
    """Wrap an existing torus symbol as PhiSym for arithmetic.

    PhiSym branch is reconstructed from ascii-encoded magnitude.
    Returns None if symbol not in torus.
    """
    if not torus or not hasattr(torus, "phases"):
        return None
    if name not in torus.phases:
        return None
    phase = torus.phases[name]
    # Try to parse magnitude from name itself (numeric strings)
    branch = 0
    try:
        v = float(name)
        if v > 0:
            return PhiSym(value=v, name=name)
    except (ValueError, TypeError):
        pass
    return PhiSym(phase=phase, branch=branch, name=name)


def parse_numerical_literal(text: str) -> Optional[PhiSym]:
    """Detect '5', '3.14', '5 m', '60 km/h' — return PhiSym if numeric.

    Lightweight regex-style parser, no full grammar.
    """
    import re
    text = text.strip()
    # Bare number
    m = re.match(r"^(\d+\.?\d*|\.\d+)$", text)
    if m:
        v = float(m.group(1))
        if v > 0:
            return PhiSym(value=v)
    # Number with single unit: "5 m", "60 kg"
    m = re.match(r"^(\d+\.?\d*|\.\d+)\s*([a-zA-Z]+)$", text)
    if m:
        v = float(m.group(1))
        u = m.group(2)
        if v > 0:
            return PhiSym(value=v, units={u: 1}, name=text)
    # Number with compound unit: "60 km/h", "5 m/s"
    m = re.match(r"^(\d+\.?\d*|\.\d+)\s*([a-zA-Z]+)/([a-zA-Z]+)$", text)
    if m:
        v = float(m.group(1))
        num_unit = m.group(2)
        denom_unit = m.group(3)
        if v > 0:
            return PhiSym(value=v,
                          units={num_unit: 1, denom_unit: -1},
                          name=text)
    return None


def field_distance_report(sym: PhiSym) -> dict:
    """Distances from sym.phase to each LOGOS field."""
    from core.resonance_constants import phi_phase_distance
    return {fname: phi_phase_distance(sym.phase, fphase)
            for fname, fphase in FIELD_PHASES.items()}


__all__ = [
    "symbol_to_torus", "torus_to_sym",
    "parse_numerical_literal", "field_distance_report",
]
