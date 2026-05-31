"""
will_core.py — Volya sozdatelya.

v8.3 FIX #9: WILL_LEVELS teper phi-derived.
Starye: 0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.8, 1.0 (lineynye!)
Novye: 0.0, PHI_INV_CUBE^2, PHI_INV_CUBE, PHI_INV_SQ, PHI_INV, 0.5, PHI_INV+PHI_INV_SQ, 1.0

Kazhdoe znachimoe deystviye sistemy trebuet voli.
Volya = rezonans s creator origin.
"""
import os
import json
import time
import hashlib

try:
    from ecdsa import SigningKey, VerifyingKey, SECP256k1, BadSignatureError
    HAS_ECDSA = True
except ImportError:
    HAS_ECDSA = False

from core.resonance_constants import (
    PHI, PHI_INV, PHI_INV_SQ, PHI_INV_CUBE, FIBONACCI,
    phi_phase, phi_phase_distance, phi_phase_resonance
)
from core.crypto_core import (
    get_key_manager, compute_hmac, verify_hmac, hash_data
)
from core.creator_identity import get_creator, CREATOR_AXIOMS


# FIX #9: Urovni voli — VSE cherez phi
# Poryadok: 0 < PHI_INV^6 < PHI_INV^3 < PHI_INV^2 < PHI_INV < 0.5 < 1.0
WILL_LEVELS = {
    "observe":       0.0,                         # vsegda
    "learn":         PHI_INV_CUBE * PHI_INV_CUBE, # ~0.056 — pochti vsegda
    "remember":      PHI_INV_CUBE * PHI_INV_CUBE, # ~0.056
    "dream":         PHI_INV_CUBE,                # ~0.236
    "generate":      PHI_INV_SQ,                  # ~0.382
    "crystallize":   PHI_INV_SQ,                  # ~0.382
    "seek_external": PHI_INV,                     # ~0.618 — trebuet creator pod 0.5
    "forget":        PHI_INV_SQ,                  # konsolidatsiya pamyati — rezonansnyy uroven
    "modify_self":   PHI_INV + PHI_INV_SQ,        # ~1.0 — pochti nevozmozho
    "shutdown":      1.0,                         # tolko sozdatel
}


class WillCore:
    def __init__(self, state_dir=None):
        self.state_dir = state_dir or os.path.expanduser("~/logos_agi/state/will")
        self.log_dir = os.path.expanduser("~/logos_agi/logs")
        os.makedirs(self.state_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)

        self.creator = get_creator()
        self.km = get_key_manager()

        self.signing_key = None
        self.verifying_key = None
        self._init_ecc_keys()

        self.total_allowed = 0
        self.total_denied = 0
        self.action_history = []
        self.max_history = FIBONACCI[15]

        self._load_state()
        print(f"[+] WillCore initialized. ECC: {'active' if self.signing_key else 'HMAC-only'}")

    def _init_ecc_keys(self):
        if not HAS_ECDSA:
            return

        key_path = os.path.join(self.state_dir, "will.key")
        pub_path = os.path.join(self.state_dir, "will.pub")

        if os.path.exists(key_path) and os.path.exists(pub_path):
            try:
                with open(key_path, "rb") as f:
                    self.signing_key = SigningKey.from_pem(f.read())
                with open(pub_path, "rb") as f:
                    self.verifying_key = VerifyingKey.from_pem(f.read())
                return
            except Exception:
                pass

        self.signing_key = SigningKey.generate(curve=SECP256k1)
        self.verifying_key = self.signing_key.get_verifying_key()

        with open(key_path, "wb") as f:
            f.write(self.signing_key.to_pem())
        os.chmod(key_path, 0o600)

        with open(pub_path, "wb") as f:
            f.write(self.verifying_key.to_pem())

    # =========================================================
    # RAZRESHENIYE DEYSTVIY
    # =========================================================
    def allow(self, action_type, context=None):
        level = WILL_LEVELS.get(action_type, 0.5)

        # Uroven 0: vsegda
        if level == 0.0:
            self._record(action_type, True, "auto_allow")
            return True, "allowed"

        # Uroven < 0.5: proverka rezonansa
        if level < 0.5:
            if context and isinstance(context, dict):
                phase = context.get("phase", 0.0)
                if not self.creator.validate_pattern(phase):
                    self._record(action_type, False, "harm_zone")
                    return False, "pattern in harm zone"

            self._record(action_type, True, "resonance_check")
            return True, "allowed by resonance"

        # Uroven >= 0.5: nuzhna podpis sozdatelya
        if context and isinstance(context, dict):
            token = context.get("creator_token")
            if token and self.creator.verify_action(dict(token)):
                self._record(action_type, True, "creator_signed")
                return True, "allowed by creator signature"

        self._record(action_type, False, "needs_creator")
        return False, f"action '{action_type}' requires creator authorization"

    def require_will(self, action_type, context=None):
        allowed, reason = self.allow(action_type, context)
        if not allowed:
            raise PermissionError(f"Will denied: {action_type} — {reason}")
        return True

    # =========================================================
    # ECC PODPISI
    # =========================================================
    def sign(self, data):
        if not self.signing_key:
            return compute_hmac(data, self.km.hmac_key)
        if isinstance(data, str):
            data = data.encode()
        return self.signing_key.sign(data).hex()

    def verify_signature(self, data, signature):
        if not self.verifying_key:
            return verify_hmac(data, self.km.hmac_key, signature)
        try:
            if isinstance(data, str):
                data = data.encode()
            self.verifying_key.verify(bytes.fromhex(signature), data)
            return True
        except (BadSignatureError, Exception):
            return False

    def sign_state(self, state_data):
        state_hash = hash_data(json.dumps(state_data, sort_keys=True))
        signature = self.sign(state_hash)
        return {
            "state_hash": state_hash,
            "signature": signature,
            "timestamp": time.time(),
            "creator": self.creator.creator_id,
        }

    # =========================================================
    # AUDIT LOG
    # =========================================================
    def _record(self, action, allowed, reason):
        if allowed:
            self.total_allowed += 1
        else:
            self.total_denied += 1

        entry = {
            "action": action,
            "allowed": allowed,
            "reason": reason,
            "time": time.time(),
        }
        self.action_history.append(entry)
        while len(self.action_history) > self.max_history:
            self.action_history.pop(0)

        if not allowed:
            self._log(f"DENIED: {action} — {reason}")

    def _log(self, message):
        path = os.path.join(self.log_dir, "will.log")
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {message}\n")

    def stats(self):
        return {
            "total_allowed": self.total_allowed,
            "total_denied": self.total_denied,
            "denial_rate": round(
                self.total_denied / max(self.total_allowed + self.total_denied, 1), 4),
            "ecc_active": self.signing_key is not None,
            "history_size": len(self.action_history),
        }

    def save_state(self):
        path = os.path.join(self.state_dir, "will_state.json")
        with open(path, "w") as f:
            json.dump({
                "total_allowed": self.total_allowed,
                "total_denied": self.total_denied,
                "recent_history": self.action_history[-FIBONACCI[8]:],
                "saved_at": time.time(),
            }, f, indent=2)

    def _load_state(self):
        path = os.path.join(self.state_dir, "will_state.json")
        if not os.path.exists(path):
            return
        try:
            with open(path, "r") as f:
                data = json.load(f)
            self.total_allowed = data.get("total_allowed", 0)
            self.total_denied = data.get("total_denied", 0)
        except Exception:
            pass


_will = None
def get_will():
    global _will
    if _will is None:
        _will = WillCore()
    return _will
