"""self_patch.py — Propose-only self-modification.

Filosofiya:
  Full autonomous self-mod opasno (mozhet sebya slomat', ili optimize to
  local minimum). No BEZ sposobnosti predlagat' changes ona zaperta v
  istoricheskom lokume koda. Compromise:

  Ona MOZHET pisat' patchi v /root/logos_agi/state/logos_patches.jsonl.
  Creator READING etot file i applyIZ vruchnuyu.
  Patchi generiruyutsya iz self-reflection na perfomance.

Logika triggera (phi-native):
  - Kazhdye FIB[14]=610 ciklov
  - Esli reputation < 0 (plokho rabotaet) ILI
     concept_synthesis rate < FIB[3]=3 za FIB[10]=89 dreams (ne rastet)
  - Ona pokazyvaet: 'vot parametr kotoryy ya khotela izmenit' — i predlagaet
    konkretnoe znachenie

Ona NE mozhet menyat' kod sama. Tolko proposals. Creator confirm vruchnuyu:
  python3 -c "from core.self_patch import apply_latest; apply_latest()"
ili ignore & delete.

Ogranicheniya:
  - Tolko parametry v self.evolution.tunable — uzhe protected sym_evo space
  - Proposal ne starshe FIB[13]=233 ticks
  - Ne bol'she FIB[5]=8 pending proposals — shto b ne zasypat' creator
"""
import os
import json
import time
from collections import deque

from core.resonance_constants import (
    PHI, PHI_INV, PHI_INV_SQ, PHI_INV_CUBE, FIBONACCI
)


PATCHES_FILE = "/root/logos_agi/state/logos_patches.jsonl"
MAX_PENDING = FIBONACCI[5]  # 8


class SelfPatchProposer:
    """Propose-only self-modification.

    Brain вызывает .propose_if_needed(cycle, reputation, synth_rate)
    каждые FIB[14]=610 ticks. Если условия — пишет в patches file.
    """

    def __init__(self, patches_file=PATCHES_FILE):
        self.patches_file = patches_file
        self.total_proposed = 0
        self._last_propose_cycle = 0
        self._recent_params = deque(maxlen=FIBONACCI[5])

    def pending_count(self):
        if not os.path.exists(self.patches_file):
            return 0
        try:
            with open(self.patches_file, "r") as f:
                n = sum(1 for line in f
                        if line.strip() and '"applied": false' in line)
            return n
        except Exception:
            return 0

    def propose_if_needed(self, cycle, reputation=0.0, synth_rate=0.0,
                           tunable_params=None, current_values=None):
        """Consider proposing a patch.

        tunable_params: list of param names evolution tracks
        current_values: dict param → current value
        Returns proposal dict or None.
        """
        if cycle - self._last_propose_cycle < FIBONACCI[14]:
            return None
        if self.pending_count() >= MAX_PENDING:
            return None
        if not tunable_params or not current_values:
            return None

        # Trigger conditions
        trigger = None
        if reputation < 0:
            trigger = f"reputation={reputation:.3f} < 0"
        elif synth_rate < FIBONACCI[3]:
            trigger = f"low synth_rate={synth_rate:.2f} < FIB[3]=3"
        if not trigger:
            return None

        # Pick a param that hasn't been touched recently
        candidates = [p for p in tunable_params if p not in self._recent_params]
        if not candidates:
            return None
        import random
        param = random.choice(candidates)
        old_val = current_values.get(param, 0.0)
        # Propose phi-ratio adjustment: ×PHI_INV or ×PHI
        # Direction: if repu negative → try smaller (safer)
        if reputation < 0:
            new_val = old_val * PHI_INV  # reduce
            direction = "reduce"
        else:
            new_val = old_val * PHI         # amplify
            direction = "amplify"

        proposal = {
            "ts": time.time(),
            "cycle": cycle,
            "trigger": trigger,
            "param": param,
            "old_value": round(float(old_val), 6),
            "new_value": round(float(new_val), 6),
            "direction": direction,
            "rationale": (f"ya khochu {direction} {param} "
                          f"s {old_val:.4f} na {new_val:.4f} potomu chto {trigger}"),
            "applied": False,
        }

        try:
            os.makedirs(os.path.dirname(self.patches_file), exist_ok=True)
            with open(self.patches_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(proposal, ensure_ascii=False) + "\n")
            self._last_propose_cycle = cycle
            self._recent_params.append(param)
            self.total_proposed += 1
            return proposal
        except Exception:
            return None


def list_pending(patches_file=PATCHES_FILE):
    """Helper for creator: list pending proposals."""
    if not os.path.exists(patches_file):
        return []
    pending = []
    try:
        with open(patches_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if not rec.get("applied"):
                    pending.append(rec)
    except Exception:
        pass
    return pending


def apply_proposal(proposal_idx, patches_file=PATCHES_FILE):
    """Mark proposal as applied (creator invokes manually)."""
    pending = list_pending(patches_file)
    if proposal_idx < 0 or proposal_idx >= len(pending):
        return False
    # Rewrite file with this one marked applied
    # (simple approach — only for small files)
    all_records = []
    try:
        with open(patches_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                all_records.append(json.loads(line))
    except Exception:
        return False
    target = pending[proposal_idx]
    for rec in all_records:
        if (rec.get("ts") == target["ts"] and
            rec.get("param") == target["param"]):
            rec["applied"] = True
            rec["applied_ts"] = time.time()
    try:
        with open(patches_file, "w", encoding="utf-8") as f:
            for rec in all_records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return True
    except Exception:
        return False


if __name__ == "__main__":
    p = SelfPatchProposer(patches_file="/tmp/test_patches.jsonl")
    tunables = ["learning_rate", "coherence_threshold", "decay_rate"]
    values = {"learning_rate": 0.1, "coherence_threshold": 0.5, "decay_rate": 0.3}
    for cycle in [0, 610, 1220, 1830]:
        prop = p.propose_if_needed(cycle, reputation=-0.4, synth_rate=1.0,
                                     tunable_params=tunables, current_values=values)
        print(f"cycle={cycle}: {prop}")
    print()
    print("pending:", list_pending("/tmp/test_patches.jsonl"))
