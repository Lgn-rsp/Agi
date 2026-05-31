"""
hybrid_compute.py — Routing layer that picks best primitive for task.

Decision rule:
  task → primitives → best substrate

Hybrid principle: take the best from each.
  - exact arithmetic, crypto, hashing → BINARY
  - ratio, similarity, multiplicative → PHI
  - persistent association → LOGOS torus / memory_core
  - composition / typed ops → PhiSym (phi + tags + units)
  - resonance / fuzzy match → phi_phase_distance + tag overlap

Vsyo cherez phi (where phi is right primitive).
"""
import math
import hashlib
from typing import Any, Optional

from core.resonance_constants import PHI, PHI_INV, phi_phase_distance
from core.info_primitives import (
    Distinguish, Phase, Resonance, Composition, Memory,
    TASK_PRIMITIVES, which_primitives, best_substrate,
)
from core.phi_symbolic import PhiSym


# ============================================================
# DECISION TABLE: routing tasks to primitives
# ============================================================

def compute(task: str, *args, **kwargs) -> Any:
    """High-level dispatch: pick substrate for task."""
    if task == "exact_multiply":
        # Binary wins for small ints
        a, b = args
        return a * b

    if task == "long_product":
        # Phi wins for chains (no overflow)
        values = args[0]
        result = PhiSym(value=1.0)
        for v in values:
            result = result * PhiSym(value=v)
        return result

    if task == "ratio_similarity":
        # Phase wins
        a, b = args
        pa = Phase.encode(a)
        pb = Phase.encode(b)
        return Phase.distance(pa, pb)

    if task == "exact_equal":
        # Distinguish wins
        a, b = args
        return Distinguish.equal(a, b)

    if task == "hash_uniform":
        # Binary (SHA) wins for crypto-strength uniformity
        x = args[0]
        return hashlib.sha256(str(x).encode()).hexdigest()

    if task == "hash_perceptual":
        # Phi wins for similarity-preserving hash
        x = args[0]
        return Phase.encode(float(x))

    if task == "associate":
        # Memory wins
        store, key, value = args
        Memory.store(key, value, store)
        return store

    if task == "compose_chain":
        # Composition wins
        ops = args[0]
        x = args[1]
        return Composition.chain(ops, x)

    raise ValueError(f"unknown task: {task}")


# ============================================================
# COGNITIVE ROUTER: how a request flows through primitives
# ============================================================

def cognitive_route(query: dict) -> dict:
    """Demo of how a complex cognitive query routes through primitives.

    Example: 'find me concepts related to "5 meters" by ratio'
    Steps:
      1. Distinguish: parse the literal "5 meters" → exact tokens
      2. Phase: encode 5 → phi_phase = 0.345
      3. Memory: lookup phase_torus for nearby symbols
      4. Resonance: rank by combined phase + tag distance
      5. Composition: optionally apply operator (×, /) to extend

    This is what LOGOS does at high level.
    """
    primitives_used = []
    trace = []

    # Step 1: Distinguish — parse identity
    target = query.get("target")
    if target is None:
        return {"error": "missing target"}
    primitives_used.append("distinguish")
    trace.append(f"DISTINGUISH: parsed target = {target!r}")

    # Step 2: Phase — encode if numeric
    if isinstance(target, (int, float)) and target > 0:
        target_phase = Phase.encode(target)
        primitives_used.append("phase")
        trace.append(f"PHASE: encode({target}) = {target_phase:.4f}")
    elif isinstance(target, PhiSym):
        target_phase = target.phase
        trace.append(f"PHASE: from PhiSym = {target_phase:.4f}")
    else:
        target_phase = None

    # Step 3: Memory — lookup similar
    candidates = query.get("candidates", [])
    primitives_used.append("memory")
    trace.append(f"MEMORY: searched {len(candidates)} candidates")

    # Step 4: Resonance — rank
    if target_phase is not None and candidates:
        scored = []
        for c in candidates:
            if isinstance(c, PhiSym):
                d = Phase.distance(c.phase, target_phase)
                scored.append((d, c))
            elif isinstance(c, (int, float)) and c > 0:
                cp = Phase.encode(c)
                d = Phase.distance(cp, target_phase)
                scored.append((d, c))
        scored.sort(key=lambda x: x[0])
        primitives_used.append("resonance")
        trace.append(f"RESONANCE: ranked by phi-distance, top-3:")
        for d, c in scored[:3]:
            trace.append(f"           dist={d:.4f}  {c}")
    else:
        scored = []

    # Step 5: Composition — optional transform
    operator = query.get("apply_operator")
    if operator and scored:
        best = scored[0][1]
        if isinstance(best, PhiSym) and isinstance(operator, PhiSym):
            transformed = best * operator
            primitives_used.append("composition")
            trace.append(f"COMPOSITION: {best} × {operator} = {transformed}")
            return {
                "primitives_used": primitives_used,
                "trace": trace,
                "result": transformed,
            }

    return {
        "primitives_used": primitives_used,
        "trace": trace,
        "top_matches": [c for _, c in scored[:5]],
    }


# ============================================================
# REPORT
# ============================================================

def architecture_report() -> str:
    """Show LOGOS architecture in 5-primitive terms."""
    lines = [
        "=== LOGOS HYBRID ARCHITECTURE ===",
        "",
        "Foundation: 5 information primitives — none replaces another.",
        "Each LOGOS module maps to one or more primitives:",
        "",
        "DISTINGUISH (binary substrate):",
        "  - core/symbolizer.py        (text → discrete tokens)",
        "  - core/crypto_core.py       (HMAC, AES — exact bit ops)",
        "  - core/will_core.py         (boolean allow/deny)",
        "  - tiered_rules.py           (rule-key tuples)",
        "",
        "PHASE (phi substrate):",
        "  - core/resonance_constants.py (FIELD_PHASES = i × PHI_INV mod 1)",
        "  - core/self_phase.py          (her own drifting phase)",
        "  - core/phi_symbolic.py        (PhiSym values as phases)",
        "  - phi_phase() everywhere",
        "",
        "RESONANCE (phi-distance + multi-aspect):",
        "  - core/phase_torus.py:resonance()  (phi-distance graph)",
        "  - core/resonance_field.py          (graph perceive)",
        "  - core/resonance_wave.py           (sparks propagation)",
        "  - PhiSym.resonance()  (phase + tags + units)",
        "",
        "COMPOSITION (operators with context):",
        "  - PhiSym.__mul__/__truediv__ (units propagate)",
        "  - core/learner.py:crystallize  (rules emerge)",
        "  - core/generator.py:respond   (chain rules)",
        "  - core/causal_engine.py       (operator chains)",
        "",
        "MEMORY (persistent patterns):",
        "  - core/memory_core.py        (recall by field)",
        "  - core/phase_torus.py:cooccurrence (graph history)",
        "  - core/dream_core.py         (replay + decay)",
        "  - core/concept_graph.py      (frequent → concept)",
        "",
        "=== ROUTING RULE ===",
        "Task uses primitives P ⊆ {1,2,3,4,5}",
        "  - if P == {1,4}: binary CPU (exact, crypto)",
        "  - if 2 ∈ P, 5 ∉ P: phi-arithmetic (PhiSym)",
        "  - if {3,5} ⊂ P: LOGOS torus (knowledge graph)",
        "  - if |P| >= 4: hybrid (combine substrates)",
        "",
        "Binary stays for what binary does best.",
        "Phi adds where binary is silent.",
        "LOGOS unifies all five.",
    ]
    return "\n".join(lines)


__all__ = ["compute", "cognitive_route", "architecture_report"]
