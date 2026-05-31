"""
phi_symbolic.py — PhiSym: numbers + context as one type.

Extension of LOGOS phase_torus pattern from linguistic to numerical
domain. Each PhiSym carries:
  - phase ∈ [0,1) (Canon rule #2)
  - branch ∈ ℤ (magnitude tracking)
  - name (symbolic identity)
  - tags (semantic classification, set)
  - units (dimensional exponents, dict)
  - associations (related-concept graph)

Operations propagate context:
  × (multiplication) — phase add + tag union + units add + assoc merge
                       (foreign assoc decayed by PHI_INV — Canon rule #1)
  / (division)       — phase sub + units sub
  ** k (power)       — phase × k + units × k

Bridges to LOGOS:
  - phase compatible with phase_torus.phases storage
  - field assignment via phi-distance to FIELD_PHASES
  - tag overlap mirrors phase_torus rule.field semantics

Vsyo cherez phi.
"""
import math
from typing import Optional

from core.resonance_constants import (
    PHI, PHI_INV, FIELD_NAMES, FIELD_PHASES,
    phi_phase_distance,
)

LOG_PHI = math.log(PHI)


def _phi_phase(value: float) -> float:
    """log_φ(value) % 1.0. Group hom (R+, ×) → (R/Z, +)."""
    if value <= 0:
        return 0.0
    return (math.log(value) / LOG_PHI) % 1.0


class PhiSym:
    """Phi-encoded number with attached symbolic context.

    Examples:
        five = PhiSym(value=5)
        meter = PhiSym(value=1, units={"m": 1})
        length5m = PhiSym(value=5, units={"m": 1}, name="5m")
        area = length5m * length5m  # → 25 m²
    """
    __slots__ = ("phase", "branch", "name", "tags", "units",
                 "associations", "is_operator")

    def __init__(self, value: float = None, *,
                 name: str = None,
                 phase: float = None, branch: int = None,
                 tags: set = None, units: dict = None,
                 associations: dict = None,
                 is_operator: bool = False):
        if value is not None:
            if value <= 0:
                raise ValueError("PhiSym requires positive value")
            log_phi = math.log(value) / LOG_PHI
            self.branch = int(log_phi)
            self.phase = log_phi - self.branch
            if name is None:
                name = self._auto_name(value)
        else:
            self.phase = (phase or 0.0) % 1.0
            self.branch = branch if branch is not None else 0
        self.name = name
        self.tags = set(tags) if tags else set()
        self.units = dict(units) if units else {}
        self.associations = dict(associations) if associations else {}
        self.is_operator = is_operator

    @staticmethod
    def _auto_name(value):
        if value == int(value):
            return str(int(value))
        return f"{value:.4g}"

    def to_value(self) -> float:
        try:
            return PHI ** (self.phase + self.branch)
        except OverflowError:
            return float("inf")

    def log_value(self) -> float:
        """log_φ(value) — no overflow risk."""
        return self.phase + self.branch

    # === arithmetic ===

    def __mul__(self, other):
        if not isinstance(other, PhiSym):
            return self * PhiSym(value=other)

        new_phase = self.phase + other.phase
        new_branch = self.branch + other.branch
        while new_phase >= 1.0:
            new_phase -= 1.0
            new_branch += 1

        new_tags = (self.tags | other.tags) - {"operator"}

        new_units = {}
        for k, v in self.units.items():
            new_units[k] = new_units.get(k, 0) + v
        for k, v in other.units.items():
            new_units[k] = new_units.get(k, 0) + v
        new_units = {k: v for k, v in new_units.items() if v != 0}

        new_assoc = {}
        for k, v in self.associations.items():
            new_assoc[k] = new_assoc.get(k, 0) + v
        for k, v in other.associations.items():
            new_assoc[k] = new_assoc.get(k, 0) + v * PHI_INV  # phi-decay

        if self.is_operator and not other.is_operator:
            new_name = other.name
        elif other.is_operator and not self.is_operator:
            new_name = self.name
        else:
            new_name = None

        return PhiSym(name=new_name, phase=new_phase, branch=new_branch,
                       tags=new_tags, units=new_units,
                       associations=new_assoc, is_operator=False)

    def __truediv__(self, other):
        if not isinstance(other, PhiSym):
            return self / PhiSym(value=other)
        new_phase = self.phase - other.phase
        new_branch = self.branch - other.branch
        while new_phase < 0:
            new_phase += 1.0
            new_branch -= 1
        new_tags = self.tags - other.tags
        new_units = dict(self.units)
        for k, v in other.units.items():
            new_units[k] = new_units.get(k, 0) - v
        new_units = {k: v for k, v in new_units.items() if v != 0}
        return PhiSym(name=self.name, phase=new_phase, branch=new_branch,
                       tags=new_tags, units=new_units)

    def __pow__(self, k):
        log_total = (self.phase + self.branch) * k
        new_branch = int(log_total)
        new_phase = (log_total - new_branch) % 1.0
        if new_phase < 0:
            new_phase += 1.0
            new_branch -= 1
        new_units = {kk: v * k for kk, v in self.units.items()}
        new_units = {kk: v for kk, v in new_units.items() if v != 0}
        return PhiSym(phase=new_phase, branch=new_branch,
                       tags=set(self.tags), units=new_units)

    # === semantics ===

    def resonance(self, other: "PhiSym") -> float:
        """Phi-resonance between two symbols ∈ [0, 1]."""
        d = phi_phase_distance(self.phase, other.phase)
        tag_overlap = (len(self.tags & other.tags) /
                       max(len(self.tags | other.tags), 1)
                       if (self.tags or other.tags) else 0)
        unit_match = 1.0 if self.units == other.units else 0.5
        return (1 - d) * 0.5 + tag_overlap * 0.3 + unit_match * 0.2

    def nearest_logos_field(self) -> tuple:
        """Find closest LOGOS semantic field (Canon rule #1).

        Returns (field_name, distance).
        """
        nearest = min(FIELD_PHASES.items(),
                      key=lambda kv: phi_phase_distance(kv[1], self.phase))
        d = phi_phase_distance(nearest[1], self.phase)
        return nearest[0], d

    def units_str(self) -> str:
        if not self.units:
            return ""
        parts = []
        for k, v in sorted(self.units.items()):
            if v == 1:
                parts.append(k)
            else:
                parts.append(f"{k}^{v}")
        return "·".join(parts)

    def __repr__(self):
        v = self.to_value()
        u = self.units_str()
        u = f" {u}" if u else ""
        n = self.name if self.name else "?"
        t = f" tags={sorted(self.tags)}" if self.tags else ""
        return f"PhiSym({n}={v:.4g}{u}{t})"


__all__ = ["PhiSym"]
