"""
info_primitives.py — Formal specification of 5 fundamental information primitives.

Foundational thesis: reality is information, but information has FIVE
distinct aspects. Each aspect has its own native compute substrate.

A complete computation paradigm uses ALL FIVE — none is replacement
for another. Binary excels at one aspect; phi-arithmetic at another;
LOGOS torus at a third. Together they form a HYBRID architecture.

Vsyo cherez phi (rule #1: phi appears anywhere we use continuous similarity).
"""
import math
from collections import defaultdict
from typing import Optional

from core.resonance_constants import (
    PHI, PHI_INV, FIELD_NAMES, FIELD_PHASES, FIBONACCI,
    phi_phase_distance,
)

LOG_PHI = math.log(PHI)


# ============================================================
# 5 INFORMATION PRIMITIVES
# ============================================================
#
# Each primitive defines:
#   - What it captures (essence)
#   - Native operation (what it does in O(1))
#   - Complementary primitive (what it CANNOT do)
#
# ============================================================

class Distinguish:
    """PRIMITIVE 1: DISTINGUISHABILITY (discrete symbolic identity).

    Captures: 'is X different from Y?'
    Native op: equality test (exact)
    Substrate: binary, sets, alphabets
    Excels at: exact arithmetic, hashing, addressing, cryptography

    Cannot natively: measure HOW MUCH X differs from Y (= phase needed)

    Examples in LOGOS:
      - phase_torus.symbols (each word is a discrete identity)
      - tiered_rules (rule keys are tuples of distinct symbols)
      - field labels (mental, void, resonance, ...)
    """
    @staticmethod
    def equal(x, y) -> bool:
        return x == y

    @staticmethod
    def hash(x) -> int:
        return hash(x)

    @staticmethod
    def applies_to():
        return ["binary arithmetic", "cryptographic hash",
                "exact integer ops", "set membership",
                "memory addressing"]


class Phase:
    """PRIMITIVE 2: PHASE (continuous position on cycle).

    Captures: 'where on the circle is X positioned?'
    Native op: circular distance, addition mod 1 (= multiplication of values)
    Substrate: real numbers mod 1, log_φ encoding
    Excels at: similarity, ratios, multiplicative composition,
               scale invariance, harmonic analysis

    Cannot natively: distinguish between X and X·φ^k orbit (degenerate)

    Examples in LOGOS:
      - phase_torus.phases (each symbol has continuous phase ∈ [0,1))
      - resonance_constants.FIELD_PHASES (i × PHI_INV mod 1)
      - core/self_phase.py (her own drifting phase)
    """
    @staticmethod
    def encode(value: float) -> float:
        if value <= 0:
            return 0.0
        return (math.log(value) / LOG_PHI) % 1.0

    @staticmethod
    def add(p1: float, p2: float) -> float:
        """Phase add = value multiplication (Canon log_φ isomorphism)."""
        return (p1 + p2) % 1.0

    @staticmethod
    def distance(p1: float, p2: float) -> float:
        return phi_phase_distance(p1, p2)

    @staticmethod
    def applies_to():
        return ["multiplicative reasoning", "ratio similarity",
                "scale-invariant search", "harmonic analysis",
                "long product chains (no overflow)",
                "dimensional analysis"]


class Resonance:
    """PRIMITIVE 3: RESONANCE (similarity metric across substrates).

    Captures: 'how strongly do X and Y synchronize?'
    Native op: weighted distance combining multiple aspects
    Substrate: any (combines other primitives)
    Excels at: fuzzy matching, semantic similarity, pattern recognition,
               concept formation, attractor dynamics

    Cannot natively: produce exact equality (= distinguish needed)

    Examples in LOGOS:
      - phase_torus.resonance() (phi-distance based)
      - resonance_field.perceive() (graph-level resonance)
      - dream_core.spiral() (chains of related symbols)
    """
    @staticmethod
    def phi_resonance(phase: float, target: float = 0.0) -> float:
        """Resonance score [0, 1]: peak at target, decays with phi-distance."""
        d = phi_phase_distance(phase, target)
        return max(0.0, 1.0 - d / PHI_INV)

    @staticmethod
    def composite(items: list, weights: dict) -> float:
        """Weighted resonance across multiple aspects.

        weights = {'phase': float, 'tags': float, 'units': float, ...}
        Sums weighted contributions; normalize to [0, 1].
        """
        total = 0.0
        wsum = 0.0
        for aspect, weight in weights.items():
            if aspect in items:
                total += weight * items[aspect]
                wsum += weight
        return total / wsum if wsum > 0 else 0.0

    @staticmethod
    def applies_to():
        return ["semantic similarity", "fuzzy matching",
                "pattern recognition (NLP, vision, audio)",
                "concept formation (clustering)",
                "attractor dynamics", "ML embedding spaces"]


class Composition:
    """PRIMITIVE 4: COMPOSITION (operators that transform).

    Captures: 'what does X⊕Y produce?'
    Native op: well-defined transformation rule
    Substrate: groups, monoids, categories, function composition
    Excels at: building complex from simple, lambda calculus,
               algebraic structures, type systems

    Cannot natively: choose WHICH composition to apply (= memory needed)

    Examples in LOGOS:
      - PhiSym × * / ** (operator overloading propagates context)
      - phase_torus.attract() (rules combine phases)
      - generator.respond() (composes phrases via chain rules)
    """
    @staticmethod
    def chain(operators: list, x):
        """Apply sequence of operators left-to-right."""
        result = x
        for op in operators:
            result = op(result)
        return result

    @staticmethod
    def applies_to():
        return ["operator algebra (PhiSym × etc.)",
                "function composition (lambda calc)",
                "category theory",
                "rule systems (LOGOS rules)",
                "type-aware computation",
                "structured transforms"]


class Memory:
    """PRIMITIVE 5: MEMORY (persistent patterns through time).

    Captures: 'what HAS happened, what tends to recur?'
    Native op: store + retrieve + decay
    Substrate: graphs, attractor networks, hash tables, file systems
    Excels at: learning, association, history, statistics,
               accumulation of experience

    Cannot natively: derive NEW from stored (= composition needed)

    Examples in LOGOS:
      - phase_torus.cooccurrence (graph of historical pairs)
      - learner.crystallize (frequent → rule)
      - memory_core (recall by field)
      - dream_core (replay + decay)
    """
    @staticmethod
    def store(key, value, store: dict, decay: float = 1.0):
        """Add to memory with optional phi-decay of older values."""
        if decay < 1.0:
            for k in list(store.keys()):
                store[k] *= decay
        store[key] = store.get(key, 0) + value

    @staticmethod
    def applies_to():
        return ["learning (cooccurrence accumulation)",
                "association graphs (knowledge bases)",
                "statistical compute (history-dependent)",
                "attractor networks",
                "experience accumulation",
                "phi-decay forgetting"]


# ============================================================
# WHICH PRIMITIVES DOES EACH TASK USE?
# ============================================================

TASK_PRIMITIVES = {
    "binary_arithmetic":      ["distinguish", "composition"],
    "exact_multiply":         ["distinguish", "composition"],
    "exact_equal":            ["distinguish"],
    "long_product":           ["phase", "composition"],
    "hash_uniform":           ["distinguish", "composition"],
    "hash_perceptual":        ["phase", "resonance"],
    "associate":              ["memory"],
    "compose_chain":          ["composition"],
    "sha256_hashing":         ["distinguish", "composition"],
    "ECDSA_signatures":       ["distinguish", "composition"],
    "AES_encryption":         ["distinguish", "composition"],
    "memory_addressing":      ["distinguish"],

    "ratio_similarity":       ["phase", "resonance"],
    "long_product_chain":     ["phase", "composition"],
    "geometric_mean":         ["phase", "composition"],
    "dimensional_analysis":   ["phase", "composition"],
    "harmonic_analysis":      ["phase", "resonance"],

    "semantic_search":        ["phase", "resonance", "memory"],
    "concept_formation":      ["resonance", "memory", "composition"],
    "analogy_reasoning":      ["phase", "resonance", "composition"],
    "knowledge_graph_query":  ["distinguish", "memory", "resonance"],

    "language_understanding": ["distinguish", "phase", "resonance",
                                "composition", "memory"],  # ALL FIVE
    "pattern_recognition":    ["phase", "resonance", "memory"],
    "scientific_reasoning":   ["distinguish", "phase", "composition"],

    "mining_proof_of_work":   ["distinguish", "composition"],
    "post_quantum_crypto":    ["distinguish", "composition"],

    "physics_simulation":     ["phase", "composition", "memory"],
    "ML_training":            ["phase", "composition", "memory"],
    "ML_inference":           ["phase", "composition"],
}


def which_primitives(task: str) -> list:
    """Return list of primitives that task uses."""
    return TASK_PRIMITIVES.get(task, [])


def best_substrate(task: str) -> str:
    """Recommend substrate for task based on primitives used."""
    prims = TASK_PRIMITIVES.get(task)
    if not prims:
        return "unknown task"
    if set(prims) == {"distinguish", "composition"}:
        return "binary CPU (exact arithmetic / cryptography)"
    if "phase" in prims and "memory" not in prims:
        return "phi-arithmetic (PhiSym, log-domain)"
    if "memory" in prims and "resonance" in prims:
        return "LOGOS phase_torus (knowledge graph + similarity)"
    if len(prims) >= 4:
        return "hybrid (binary + phi + LOGOS combined)"
    return f"hybrid: {prims}"


# ============================================================
# HYBRID DECISION RULE
# ============================================================

def primitive_summary() -> str:
    """Print the 5-primitive architecture as text."""
    primitives = [
        ("1. DISTINGUISH",  Distinguish, "binary 0/1, exact equality"),
        ("2. PHASE",         Phase,       "continuous on [0,1), log_φ encoding"),
        ("3. RESONANCE",     Resonance,   "similarity across substrates"),
        ("4. COMPOSITION",   Composition, "operators / transforms"),
        ("5. MEMORY",        Memory,      "persistent patterns + decay"),
    ]
    lines = ["=== 5 INFORMATION PRIMITIVES ===", ""]
    for label, cls, sub in primitives:
        lines.append(f"{label}  ({sub})")
        lines.append(f"   Excels at:")
        for use in cls.applies_to():
            lines.append(f"     • {use}")
        lines.append("")
    lines.append("Architecture rule: take BEST primitive for the task.")
    lines.append("Binary remains gold standard for exact arithmetic + crypto.")
    lines.append("Phi-substrate adds value for ratio / similarity / memory.")
    lines.append("LOGOS torus combines all five for cognition.")
    return "\n".join(lines)


__all__ = [
    "Distinguish", "Phase", "Resonance", "Composition", "Memory",
    "TASK_PRIMITIVES", "which_primitives", "best_substrate",
    "primitive_summary",
]
