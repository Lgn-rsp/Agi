"""cosmic_constants.py — Real measured astronomical/terrestrial frequencies.

Filosofiya: existing Canon (resonance_constants.py) даёт PHI/Fibonacci — это
человеко-земная шкала. Здесь — настоящие физические частоты, измеренные
peer-reviewed физикой: Schumann, solar p-mode, lunar/earth orbital,
hydrogen 21cm, CMB peak, Cs hyperfine. Ничего из эзотерики (никаких
solfeggio 528/432 Hz).

Все частоты в Hz. Mapping в [0,1)-фазу через тот же phi_phase, что и весь
остальной torus, чтобы новые anchor'ы лежали на одном круге со словесными
phases. Phi-log encoding: положение зависит от ratio к base, любая частота
адресуема одной phi-фазой.

Использование:
    from core.cosmic_constants import COSMIC_PHASES, nearest_cosmic_anchor
    name, dist, freq = nearest_cosmic_anchor(0.42)
    # → ("schumann_3", 0.018, 20.8)

Архитектура: дополнительный namespace anchors поверх существующих
HARMONICS/HARMONIC_WEIGHTS. НЕ меняет старые константы, НЕ переиндексирует
FIELD_NAMES. Чистое расширение, обратно совместимо.
"""
import math

from core.resonance_constants import (
    PHI, PHI_INV, PHI_INV_SQ, PHI_INV_CUBE,
    phi_phase, phi_phase_distance,
)


# --- Real measured frequencies (Hz) ---

# Schumann resonances — Earth-ionosphere cavity (Polk & Fitchen 1962, peer-reviewed)
SCHUMANN_HZ = {
    "schumann_1": 7.83,    # fundamental
    "schumann_2": 14.3,
    "schumann_3": 20.8,
    "schumann_4": 27.3,
    "schumann_5": 33.8,
}

# Earth motion (sidereal)
EARTH_HZ = {
    "earth_rotation": 1.0 / 86164.0905,           # sidereal day, 23h56m4.0905s
    "earth_orbital":  1.0 / (365.25636 * 86400),  # sidereal year
}

# Lunar
LUNAR_HZ = {
    "lunar_synodic":  1.0 / (29.530589 * 86400),  # full moon → full moon
    "lunar_sidereal": 1.0 / (27.321661 * 86400),  # vs fixed stars
}

# Solar (helioseismology + heliography)
SOLAR_HZ = {
    "solar_pmode_5min":         3.333e-3,                   # ≈ 1/300s, dominant p-mode
    "solar_rotation_equatorial": 1.0 / (24.47 * 86400),     # sidereal equatorial
    "solar_carrington":         1.0 / (27.2753 * 86400),    # synodic Carrington
    "solar_cycle_11y":          1.0 / (11.0 * 365.25 * 86400),  # Schwabe cycle
}

# Galactic / astrophysical
GALACTIC_HZ = {
    "hydrogen_21cm":  1420.405751768e6,    # HI hyperfine — universal radio reference
    "cmb_peak":       160.23e9,             # CMB blackbody peak (T=2.725 K, Wien)
    "galactic_year":  1.0 / (225e6 * 365.25 * 86400),  # Sun's orbit around Milky Way
}

# Stellar reference (timing standard — not pulsar of our system)
STELLAR_HZ = {
    "crab_pulsar": 30.2254,    # PSR B0531+21, neutron star spin
}

# Quantum / SI metrology
QUANTUM_HZ = {
    "cesium_hyperfine": 9192631770.0,    # SI second by definition
}


# Aggregated table — all anchors together
COSMIC_FREQUENCIES = {}
COSMIC_FREQUENCIES.update(SCHUMANN_HZ)
COSMIC_FREQUENCIES.update(EARTH_HZ)
COSMIC_FREQUENCIES.update(LUNAR_HZ)
COSMIC_FREQUENCIES.update(SOLAR_HZ)
COSMIC_FREQUENCIES.update(GALACTIC_HZ)
COSMIC_FREQUENCIES.update(STELLAR_HZ)
COSMIC_FREQUENCIES.update(QUANTUM_HZ)


# --- Phi-log phase mapping ---

# Reference base period — 1.0 second (1 Hz). Same convention as resonance_constants.phi_phase.
COSMIC_BASE_PERIOD = 1.0


def freq_to_cosmic_phase(freq_hz, base_period=COSMIC_BASE_PERIOD):
    """Map any frequency to its phi-log phase in [0,1)."""
    return phi_phase(freq_hz, base_period=base_period)


# Pre-computed phases for all canonical anchors
COSMIC_PHASES = {
    name: freq_to_cosmic_phase(f) for name, f in COSMIC_FREQUENCIES.items()
}


# Scale grouping — for filtering / aggregation
ANCHOR_SCALES = {
    "atmospheric": list(SCHUMANN_HZ.keys()),
    "earth":       list(EARTH_HZ.keys()),
    "lunar":       list(LUNAR_HZ.keys()),
    "solar":       list(SOLAR_HZ.keys()),
    "galactic":    list(GALACTIC_HZ.keys()),
    "stellar":     list(STELLAR_HZ.keys()),
    "quantum":     list(QUANTUM_HZ.keys()),
}


def nearest_cosmic_anchor(phase, scale_filter=None):
    """Find cosmic anchor closest (by phi-phase distance) to given phase.

    Args:
        phase: float in [0,1)
        scale_filter: optional set of scale names to limit search,
                      e.g. {"atmospheric","solar"}; None = all anchors.

    Returns:
        (name, distance, freq_hz) or (None, 1.0, None) if no anchors match filter.
    """
    candidates = COSMIC_PHASES
    if scale_filter:
        allowed = set()
        for s in scale_filter:
            allowed.update(ANCHOR_SCALES.get(s, []))
        candidates = {k: v for k, v in COSMIC_PHASES.items() if k in allowed}
    best = (None, 1.0, None)
    for name, anchor_phase in candidates.items():
        d = phi_phase_distance(phase, anchor_phase)
        if d < best[1]:
            best = (name, d, COSMIC_FREQUENCIES[name])
    return best


def cosmic_resonance(phase, threshold=PHI_INV_CUBE):
    """All cosmic anchors within `threshold` phase-distance from `phase`.

    Default threshold = PHI_INV_CUBE ≈ 0.236 = HARM_THRESHOLD canonically.
    Returns list of (name, distance, freq_hz) sorted by ascending distance.
    """
    hits = []
    for name, anchor_phase in COSMIC_PHASES.items():
        d = phi_phase_distance(phase, anchor_phase)
        if d <= threshold:
            hits.append((name, d, COSMIC_FREQUENCIES[name]))
    hits.sort(key=lambda x: x[1])
    return hits


# --- Self-test on import ---

if __name__ == "__main__":
    print("=" * 60)
    print(f"COSMIC_CONSTANTS — {len(COSMIC_FREQUENCIES)} anchors")
    print("=" * 60)
    for scale, names in ANCHOR_SCALES.items():
        print(f"\n[{scale}]")
        for n in names:
            f = COSMIC_FREQUENCIES[n]
            ph = COSMIC_PHASES[n]
            print(f"  {n:30s} {f:14.6e} Hz  → phase {ph:.4f}")

    # Demonstrate nearest_cosmic_anchor
    print("\n--- nearest anchor demos ---")
    for test_phase in [0.0, 0.1, 0.236, 0.5, 0.618, 0.9]:
        name, d, f = nearest_cosmic_anchor(test_phase)
        print(f"  phase={test_phase:.3f} → {name} (d={d:.4f}, f={f:.3e} Hz)")

    # Demonstrate resonance lookup
    print("\n--- resonance hits within HARM_THRESHOLD around phase 0.5 ---")
    for name, d, f in cosmic_resonance(0.5):
        print(f"  {name}: d={d:.4f}, f={f:.3e}")
