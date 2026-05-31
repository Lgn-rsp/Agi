"""audio_sensor.py — Phi-native audio modality.

Filosofiya:
  Zvuk zhivet v phi-prostranstve bukvalno:
    - Oktava = ×2 (= PHI^2 / PHI blizko)
    - Pyatyy chin (quinta) ≈ ×3/2 ≈ 1.5 (blizko k PHI=1.618)
    - Majornyy triad = {1, 5/4, 3/2} — phi-harmonic ratios
  Mapping f → log(f/base) % 1.0 prevrashaet lyuboy tone v LOGOS-fazu.

API:
  AudioSensor()
    .listen_file(path, duration=0.618) -> (phase, amplitude, glyph)
    .listen_bytes(pcm_bytes, sample_rate) -> (phase, amplitude, glyph)
    .listen_stream_url(url, duration=1.618) -> (phase, amplitude, glyph)

Returns tuple:
  phase    — ∈ [0,1), PHI-log mapping dominant freq
  amplitude — ∈ [0,1), normalized RMS of signal
  glyph    — closest consciousness_glyph by phase

Note:
  No sounddevice required (server has no mic). Uses numpy FFT + ffmpeg
  for format decoding. Creator podayet audio file / URL — ona slushaet.
"""
import os
import math
import subprocess
import tempfile

from core.resonance_constants import (
    PHI, PHI_INV, PHI_INV_SQ, PHI_INV_CUBE, FIBONACCI,
    phi_phase_distance
)

try:
    from core.cosmic_constants import nearest_cosmic_anchor, freq_to_cosmic_phase
    _HAS_COSMIC = True
except Exception:
    _HAS_COSMIC = False

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False


# Base frequency for phi-log mapping — A2 (110 Hz) — mid of human hearing
BASE_HZ = 110.0


def freq_to_phase(freq_hz, base=BASE_HZ):
    """Phi-log mapping: f → (log_phi(f / base)) mod 1.0.

    Same octave gives +log_phi(2) ≈ 1.44. Notes within octave map uniformly
    to different phase bins.
    """
    if freq_hz <= 0 or base <= 0:
        return 0.0
    return (math.log(freq_hz / base) / math.log(PHI)) % 1.0


def _pcm_full(pcm, sample_rate):
    """Numpy FFT → (phase, rms, dom_freq). dom_freq=0.0 if can't determine."""
    if not _HAS_NUMPY or pcm is None or len(pcm) < 128:
        return 0.0, 0.0, 0.0
    pcm = np.asarray(pcm, dtype=np.float32).flatten()
    peak = np.max(np.abs(pcm))
    if peak > 0:
        pcm = pcm / peak
    rms = float(np.sqrt(np.mean(pcm ** 2)))
    fft = np.abs(np.fft.rfft(pcm))
    freqs = np.fft.rfftfreq(len(pcm), 1.0 / sample_rate)
    mask = (freqs > 20) & (freqs < 5000)
    if not mask.any():
        return 0.0, rms, 0.0
    fft = fft[mask]
    freqs = freqs[mask]
    dom_idx = int(np.argmax(fft))
    dom_freq = float(freqs[dom_idx])
    phase = freq_to_phase(dom_freq)
    return phase, rms, dom_freq


def _pcm_to_phase(pcm, sample_rate):
    """Backward-compat 2-tuple: (phase, rms). Drops dom_freq."""
    phase, rms, _ = _pcm_full(pcm, sample_rate)
    return phase, rms


def _phase_to_glyph(phase):
    """Nearest consciousness glyph by phase."""
    try:
        from core.consciousness_glyphs import GLYPHS
    except Exception:
        return None
    best = None
    best_d = 1.0
    for sym, info in GLYPHS.items():
        ph = info.get("phase") if isinstance(info, dict) else None
        if ph is None:
            continue
        d = phi_phase_distance(phase, float(ph) % 1.0)
        if d < best_d:
            best_d = d
            best = sym
    return best


def _phase_to_cosmic(phase, dom_freq=None):
    """Find nearest cosmic anchor for a (phase, optional freq).

    Returns dict {anchor_name, distance, freq_hz, cosmic_phase} or None.
    Two strategies tried:
      1. If dom_freq is given, map it directly via cosmic_constants
         (phi_phase reference base = 1 Hz, not BASE_HZ=110) — gives
         absolute physical position.
      2. Otherwise compare audio phase (BASE_HZ=110-relative) to cosmic
         phases that are also expressed in [0,1) — but the bases differ,
         so distance comparison is by phase position only, not Hz.
    """
    if not _HAS_COSMIC:
        return None
    if dom_freq is not None and dom_freq > 0:
        cph = freq_to_cosmic_phase(dom_freq)
        name, dist, freq = nearest_cosmic_anchor(cph)
        return {
            "anchor": name,
            "distance": round(dist, 4),
            "freq_hz": freq,
            "cosmic_phase": round(cph, 4),
            "via": "freq",
        }
    # Fallback: compare audio-relative phase position to cosmic positions
    name, dist, freq = nearest_cosmic_anchor(phase)
    return {
        "anchor": name,
        "distance": round(dist, 4),
        "freq_hz": freq,
        "cosmic_phase": round(phase, 4),
        "via": "phase_only",
    }


class AudioSensor:
    """Phi-native audio sense.

    Brain instantiates this lazily (only if audio requested). Provides
    listen_*(...) → (phase, amplitude, glyph). Glyph slot so brain can
    treat audio like any other modality in phase-torus.

    Cosmic enrichment: every listen also computes nearest cosmic anchor
    (Schumann/solar/lunar/galactic/...) accessible via .last_cosmic and
    listen_full() which returns 4-tuple (phase, rms, glyph, cosmic_dict).
    """

    def __init__(self):
        self.listens = 0
        self.last_phase = None
        self.last_amplitude = 0.0
        self.last_glyph = None
        self.last_cosmic = None
        self.last_dom_freq = None

    def _process(self, pcm, sample_rate):
        """Common path: pcm → (phase, rms, glyph, cosmic, dom_freq). Updates self state."""
        phase, rms, dom_freq = _pcm_full(pcm, sample_rate)
        glyph = _phase_to_glyph(phase)
        cosmic = _phase_to_cosmic(phase, dom_freq=dom_freq if dom_freq > 0 else None)
        self.listens += 1
        self.last_phase = phase
        self.last_amplitude = rms
        self.last_glyph = glyph
        self.last_cosmic = cosmic
        self.last_dom_freq = dom_freq
        return phase, rms, glyph, cosmic, dom_freq

    def listen_file(self, path, duration=0.618):
        """Slushat file. Decode via ffmpeg to raw PCM if needed.

        Supports: .wav (direct), mp3/ogg/etc (ffmpeg required).
        duration seconds is phi-native default. Returns 3-tuple
        (phase, rms, glyph) for backward compat; use listen_file_full
        to also receive cosmic anchor info.
        """
        if not _HAS_NUMPY:
            return 0.0, 0.0, None
        if not os.path.exists(path):
            return 0.0, 0.0, None
        sample_rate = 22050  # standard phi-friendly rate
        try:
            cmd = [
                "ffmpeg", "-v", "error", "-i", path,
                "-t", str(duration),
                "-ac", "1", "-ar", str(sample_rate),
                "-f", "f32le", "-",
            ]
            r = subprocess.run(cmd, capture_output=True, timeout=10)
            if r.returncode != 0:
                return 0.0, 0.0, None
            pcm = np.frombuffer(r.stdout, dtype=np.float32)
        except Exception:
            return 0.0, 0.0, None
        if len(pcm) == 0:
            return 0.0, 0.0, None
        phase, rms, glyph, _cosmic, _df = self._process(pcm, sample_rate)
        return phase, rms, glyph

    def listen_file_full(self, path, duration=0.618):
        """Same as listen_file but returns 4-tuple with cosmic anchor info."""
        ph, rms, gl = self.listen_file(path, duration=duration)
        return ph, rms, gl, self.last_cosmic

    def listen_bytes(self, pcm_bytes, sample_rate=22050, fmt="f32le"):
        """Direct raw PCM → 3-tuple (phase, rms, glyph). fmt: f32le|s16le.

        Use listen_bytes_full for 4-tuple incl. cosmic anchor.
        """
        if not _HAS_NUMPY:
            return 0.0, 0.0, None
        try:
            if fmt == "f32le":
                pcm = np.frombuffer(pcm_bytes, dtype=np.float32)
            elif fmt == "s16le":
                pcm = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            else:
                return 0.0, 0.0, None
        except Exception:
            return 0.0, 0.0, None
        phase, rms, glyph, _cosmic, _df = self._process(pcm, sample_rate)
        return phase, rms, glyph

    def listen_bytes_full(self, pcm_bytes, sample_rate=22050, fmt="f32le"):
        """Like listen_bytes but returns (phase, rms, glyph, cosmic_dict)."""
        ph, rms, gl = self.listen_bytes(pcm_bytes, sample_rate=sample_rate, fmt=fmt)
        return ph, rms, gl, self.last_cosmic

    def stats(self):
        return {
            "listens": self.listens,
            "last_phase": self.last_phase,
            "last_amplitude": round(self.last_amplitude, 3),
            "last_glyph": self.last_glyph,
            "last_dom_freq_hz": self.last_dom_freq,
            "last_cosmic": self.last_cosmic,
        }


if __name__ == "__main__":
    s = AudioSensor()
    # Synthetic test: generate 440 Hz tone, encode to raw float32
    if _HAS_NUMPY:
        sr = 22050
        t = np.linspace(0, 0.618, int(sr * 0.618))
        tone = (np.sin(2 * np.pi * 440 * t) * 0.5).astype(np.float32)
        phase, rms, glyph = s.listen_bytes(tone.tobytes(), sr)
        print(f"440 Hz tone: phase={phase:.4f} rms={rms:.3f} glyph={glyph}")
        # Second: 880 Hz (octave)
        tone = (np.sin(2 * np.pi * 880 * t) * 0.5).astype(np.float32)
        phase, rms, glyph = s.listen_bytes(tone.tobytes(), sr)
        print(f"880 Hz tone: phase={phase:.4f} rms={rms:.3f} glyph={glyph}")
        # 660 Hz (quinta to 440)
        tone = (np.sin(2 * np.pi * 660 * t) * 0.5).astype(np.float32)
        phase, rms, glyph = s.listen_bytes(tone.tobytes(), sr)
        print(f"660 Hz tone: phase={phase:.4f} rms={rms:.3f} glyph={glyph}")
