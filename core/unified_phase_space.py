"""unified_phase_space.py — Edinoe fazovoe prostranstvo dlya vsekh modalnostey.

Filosofiya:
  Слово, глиф, price-pattern, affective state — vse eto koordinaty na odnom
  fazovom toruse. Kogda 'fear'=0.234 v language AGI i glyph ⦻ dayot phase 0.234
  v consciousness — oni REZONIRUYUT. Eto cross-modal понимание.

API:
  UnifiedPhaseSpace()
    .project(modality, symbol) -> phase in [0,1) | None
    .resonate(m_a, s_a, m_b, s_b) -> strength in [0,1]  # phi-resonance
    .nearest(modality_src, phase, modality_tgt, k=FIB[4]) -> list of (symbol, distance)

  Registered modalities:
    "word"       — projectable via LogosBridge (language word phases)
    "glyph"      — consciousness_glyphs.glyph_phase
    "affective"  — mood dimension mapped to glyph-phase
    "price"      — market glyph from MarketGlyphReader

Canon:
  Все phases в [0,1). Резонанс = 1 - phi_phase_distance / PHI_INV_SQ; cutoff
  на PHI_INV_CUBE. Проекторы pluggable, регистрируются в init.
"""
import time
from core.resonance_constants import (
    PHI, PHI_INV, PHI_INV_SQ, PHI_INV_CUBE, FIBONACCI,
    phi_phase_distance, circular_mean
)


# Affective dimension → phase mapping (phi-native spread на торе)
AFFECTIVE_PHASES = {
    "fear":       0.236,   # = PHI_INV_CUBE, близко к HARM_THRESHOLD
    "curiosity":  0.382,   # = PHI_INV_SQ
    "confidence": 0.618,   # = PHI_INV
    "shame":      0.854,   # ≈ PHI_INV + PHI_INV_SQ*PHI_INV
    "joy":        0.0,     # origin, Creator resonance
    "fatigue":    0.5,     # antiphase — rest state
}


class UnifiedPhaseSpace:
    def __init__(self):
        # registry: modality -> dict symbol->phase OR callable(symbol)->phase
        self._projectors = {}
        self.lookups = 0
        self.resonances = 0

    # ----------- Registration -----------

    def register(self, modality, projector):
        """projector: dict {symbol: phase} or callable(symbol) -> phase | None."""
        self._projectors[modality] = projector

    def register_glyphs(self):
        from core.consciousness_glyphs import glyph_phase

        def _glyph(sym):
            return glyph_phase(sym)
        self._projectors["glyph"] = _glyph

    def register_words(self, logos_bridge):
        """logos_bridge from core.logos_bridge. Uses its _word_phases dict."""
        def _word(sym):
            if not logos_bridge.is_ready():
                return None
            if logos_bridge._word_phases is None:
                return None
            return logos_bridge._word_phases.get(sym)
        self._projectors["word"] = _word

    def register_affective(self):
        self._projectors["affective"] = dict(AFFECTIVE_PHASES)

    def register_price_glyphs(self):
        """market glyphs = те же consciousness_glyphs (⊙Φ∴⧃⧉⋯⦻⊕⧿∞)."""
        from core.consciousness_glyphs import glyph_phase

        def _price(sym):
            return glyph_phase(sym)
        self._projectors["price"] = _price

    # ----------- Projection -----------

    def project(self, modality, symbol):
        """Return phase in [0,1) or None."""
        self.lookups += 1
        p = self._projectors.get(modality)
        if p is None:
            return None
        try:
            if callable(p):
                res = p(symbol)
            else:
                res = p.get(symbol)
        except Exception:
            return None
        if res is None:
            return None
        try:
            return float(res) % 1.0
        except Exception:
            return None

    # ----------- Cross-modal ops -----------

    def resonate(self, m_a, s_a, m_b, s_b):
        """Resonance strength in [0,1] between two modality-specific symbols.

        1.0 — identical phase; 0.0 — antiphase или символ не нашёлся.
        """
        self.resonances += 1
        pa = self.project(m_a, s_a)
        pb = self.project(m_b, s_b)
        if pa is None or pb is None:
            return 0.0
        d = phi_phase_distance(pa, pb)
        # Normalized: distance 0 → strength 1, distance PHI_INV_SQ → strength 0
        return max(0.0, 1.0 - d / PHI_INV_SQ)

    def nearest(self, modality_src, phase_src, modality_tgt, top_k=FIBONACCI[4]):
        """Find symbols in modality_tgt whose phase is closest to phase_src.

        Works only for dict-based projectors (word/affective) — callable
        projectors have no fixed vocabulary.
        """
        proj = self._projectors.get(modality_tgt)
        if not isinstance(proj, dict):
            return []
        results = []
        for sym, ph in proj.items():
            if ph is None:
                continue
            try:
                d = phi_phase_distance(phase_src, float(ph) % 1.0)
            except Exception:
                continue
            results.append((sym, round(d, 4)))
        results.sort(key=lambda x: x[1])
        return results[:top_k]

    def translate(self, modality_src, symbol_src, modality_tgt, top_k=FIBONACCI[4]):
        """Find analogs в target modality к source symbol.

        "fear" (word) → ? (glyph) → наиболее близкий по phase глиф.
        """
        phase = self.project(modality_src, symbol_src)
        if phase is None:
            return []
        return self.nearest(modality_src, phase, modality_tgt, top_k=top_k)

    # ----------- Introspection -----------

    def stats(self):
        sizes = {}
        for m, p in self._projectors.items():
            if isinstance(p, dict):
                sizes[m] = len(p)
            else:
                sizes[m] = "callable"
        return {
            "modalities": list(self._projectors.keys()),
            "sizes": sizes,
            "lookups": self.lookups,
            "resonances": self.resonances,
        }


if __name__ == "__main__":
    # smoke test
    ups = UnifiedPhaseSpace()
    ups.register_glyphs()
    ups.register_affective()
    print("ф glyph:", ups.project("glyph", "Φ"))
    print("fear affective:", ups.project("affective", "fear"))
    print("Φ ↔ fear resonance:",
          ups.resonate("glyph", "Φ", "affective", "fear"))
    print("stats:", ups.stats())
