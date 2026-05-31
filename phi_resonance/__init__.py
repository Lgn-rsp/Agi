"""phi_resonance — coupled oscillator network substrate.

Replaces "stored phase floats in hash tables" (current LOGOS phase_torus)
with continuous-time integrated dynamics (Kuramoto / Stuart-Landau form).

Standalone package. Does NOT modify core/. Integration with existing LOGOS
modules is a separate, gated step that happens after this substrate passes
its own tests.

Why a new package: changing core/phase_torus.py in place would break every
running brain. Building the substrate alongside lets it be developed and
verified independently.

What this is NOT:
- A claim that running coupled oscillators produces consciousness.
- A "consciousness primitive". It's a dynamical system with measurable
  invariants (order parameter, cluster count, mean field power spectrum).
- A drop-in replacement for phase_torus. The integration adapter
  (symbol_binding.py, future) is a separate concern.
"""
from .oscillator_network import KuramotoNetwork, StuartLandauNetwork
from .observables import (
    order_parameter,
    cluster_phases,
    chimera_index,
    mean_field,
)

__version__ = "0.1.0"
__all__ = [
    "KuramotoNetwork",
    "StuartLandauNetwork",
    "order_parameter",
    "cluster_phases",
    "chimera_index",
    "mean_field",
]
