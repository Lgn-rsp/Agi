"""
learner.py — Rezonansnoe obuchenie.
Beret tekst -> simboliziruet -> kormit PhaseTorus na vsekh urovnyakh.
Potokovo, ne gruzit vse v pamyat.

v8.2: PhaseTorus T^2 vmesto PhaseSpace.
Kazhdyy uroven — dvukhmernyy fazovyy tor.
Obratna sovmestimost: .phases = {sym: float} kak ranshe.
"""
import os
import time
import json
from core.resonance_constants import (
    FIBONACCI, SAVE_INTERVAL, PHI, phi_phase
)
# Block migration 2026-04-26: opt-in dynamic substrate via env var.
# LOGOS_DYNAMIC_SUBSTRATE=1 → use phi_resonance.DynamicPhaseTorus
# (oscillator-backed; phases evolve in continuous time, not stored floats).
# Default (unset/0) keeps the legacy PhaseTorus, so existing brains run
# unchanged. See PHI_RESONANCE.md for migration plan.
if os.environ.get("LOGOS_DYNAMIC_SUBSTRATE", "0") == "1":
    from phi_resonance.phase_torus_dynamic import (
        DynamicPhaseTorus as PhaseTorus,
    )
    print("[+] ResonanceLearner using DYNAMIC oscillator substrate")
else:
    from core.phase_torus import PhaseTorus
from core.symbolizer import (
    symbolize_multilevel, stream_file, text_to_words
)

# Skolko razmernostey tora dlya kazhdogo urovnya
# Chars: 1D (dostatochno dlya bukv)
# Words: 2D (semantika + sintaksis)
# Pairs: 2D
# Trigrams: 2D
TORUS_DIMS = {
    "chars": 1,
    "words": 2,
    "pairs": 2,
    "trigrams": 2,
}


class ResonanceLearner:
    """
    Uchitsya cherez rezonans, ne cherez gradient.
    v8.2: PhaseTorus — kazhdyy simvol na fazovom tore.
    """

    def __init__(self, state_dir=None):
        self.state_dir = state_dir or os.path.expanduser("~/logos_agi/state")
        self.log_dir = os.path.expanduser("~/logos_agi/logs")
        os.makedirs(self.log_dir, exist_ok=True)

        # 4 fazovykh tora — po odnomu na uroven
        self.spaces = {}
        for name in ["chars", "words", "pairs", "trigrams"]:
            dims = TORUS_DIMS.get(name, 1)
            self.spaces[name] = PhaseTorus(
                dimensions=dims,
                creator_id="creator",
                state_dir=os.path.join(self.state_dir, name),
            )

        # Block migration 2026-04-26: under dynamic substrate, DPTs are
        # created with autostart=False (default env). We start their
        # integration loops LAZILY — on first learn_text() call. By then
        # LogosBrain.__init__ has finished its heavy init phases
        # (GroundingTorus._recompute_phases, AnalogEngine fingerprints
        # etc.) so the 4 phi_brain threads don't compete for CPU during
        # those single-threaded computations.
        self._brains_started = False

        self.chunks_processed = 0
        self.last_save = time.time()
        self.start_time = None

        dims_str = " ".join(f"{n}=T^{TORUS_DIMS[n]}" for n in self.spaces)
        print(f"[+] ResonanceLearner initialized. {dims_str}")

    def learn_text(self, text):
        # Lazy-start dynamic substrate brains on first learn (see __init__)
        if not self._brains_started:
            for sp in self.spaces.values():
                if hasattr(sp, "start"):
                    sp.start()
            self._brains_started = True
        levels = symbolize_multilevel(text)
        for level_name, sequence in levels.items():
            if sequence and level_name in self.spaces:
                self.spaces[level_name].observe(sequence)
        self.chunks_processed += 1

    def learn_file(self, filepath, report_every=FIBONACCI[7]):
        print(f"\n[*] Learning from: {filepath}")
        self.start_time = time.time()
        chunk_count = 0
        for text_chunk in stream_file(filepath):
            self.learn_text(text_chunk)
            chunk_count += 1
            if chunk_count % report_every == 0:
                self._report(chunk_count)
            if time.time() - self.last_save > SAVE_INTERVAL:
                self.save()
        self._report(chunk_count, final=True)
        self.save()
        print(f"[+] File complete: {chunk_count} chunks\n")

    def learn_directory(self, dirpath, extension=".txt"):
        if not os.path.isdir(dirpath):
            print(f"[!] Not a directory: {dirpath}")
            return
        files = sorted([f for f in os.listdir(dirpath)
                       if f.endswith(extension)])
        print(f"[*] Found {len(files)} {extension} files in {dirpath}")
        for i, fname in enumerate(files):
            print(f"\n--- File {i+1}/{len(files)}: {fname} ---")
            self.learn_file(os.path.join(dirpath, fname))

    def learn_string(self, text, repeat=1):
        for _ in range(repeat):
            self.learn_text(text)

    def stats(self):
        result = {
            "chunks_processed": self.chunks_processed,
            "levels": {}
        }
        for name, space in self.spaces.items():
            result["levels"][name] = space.stats()
        return result

    def anomalies(self, level="words", top_k=FIBONACCI[6]):
        return self.spaces[level].find_anomalies(top_k)

    def query(self, symbol, level="words"):
        return self.spaces[level].query(symbol)

    def all_rules(self, level="words"):
        return self.spaces[level].rules

    def save(self):
        for name, space in self.spaces.items():
            space.save_state()
        self.last_save = time.time()
        meta_path = os.path.join(self.state_dir, "learner_meta.json")
        with open(meta_path, "w") as f:
            json.dump({
                "chunks_processed": self.chunks_processed,
                "torus_dims": TORUS_DIMS,
                "saved_at": self.last_save,
            }, f, indent=2)

    def _report(self, chunk_count, final=False):
        elapsed = time.time() - (self.start_time or time.time())
        speed = chunk_count / max(elapsed, 0.001)
        tag = "FINAL" if final else "progress"
        stats = self.stats()
        total_symbols = sum(
            s["symbols"] for s in stats["levels"].values())
        total_rules = sum(
            s["rules"] for s in stats["levels"].values())
        total_attractions = sum(
            s["total_attractions"] for s in stats["levels"].values())
        print(f"  [{tag}] chunks={chunk_count} "
              f"time={elapsed:.1f}s "
              f"speed={speed:.1f}ch/s "
              f"symbols={total_symbols} "
              f"rules={total_rules} "
              f"attractions={total_attractions}")

    def _log(self, message):
        log_path = os.path.join(self.log_dir, "learner.log")
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {message}\n")
