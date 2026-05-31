"""peer_crypto.py — ed25519 sign/verify for federation messages.

Block 6.2 of hardening. Without signing, any internet host can POST to
`/peer/inbox` and inject text into the brain's training pipeline (per
Block 6.4 quarantine that's now blocked, but signing is still wanted as
defence-in-depth and to enable LATER reopening of auto-learn under
trusted peers only).

Keys live in `/root/logos_agi/keys/peer/`:
  ed25519_private.bin   — this node's private key (32 bytes)
  ed25519_public.bin    — this node's public key (32 bytes)
  pubkeys.json          — map {peer_name: base64(public_key)} for
                          known peers

Run `python3 -m core.peer_crypto generate` once to create local keypair.
Distribute public key to other nodes manually (SSH mesh exists).

Wire format addition: signed messages get a `sig` field with
base64(ed25519_signature_of_canonical_json_without_sig). Verifier checks
sig against pubkeys.json[from]. Default is **warn-only**: log invalid
sigs but accept the message. Set `LOGOS_PEER_REQUIRE_SIG=1` to enforce.
"""
from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path
from typing import Optional

KEY_DIR = Path("/root/logos_agi/keys/peer")
PRIV_PATH = KEY_DIR / "ed25519_private.bin"
PUB_PATH = KEY_DIR / "ed25519_public.bin"
PUBKEYS_PATH = KEY_DIR / "pubkeys.json"


def _ensure_dir() -> None:
    KEY_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(KEY_DIR, 0o700)


def generate_keypair(force: bool = False) -> tuple[bytes, bytes]:
    """Create ed25519 keypair if not already present. Returns
    (private_bytes, public_bytes)."""
    from nacl.signing import SigningKey
    _ensure_dir()
    if PRIV_PATH.exists() and not force:
        priv_bytes = PRIV_PATH.read_bytes()
        pub_bytes = PUB_PATH.read_bytes()
        return priv_bytes, pub_bytes
    sk = SigningKey.generate()
    priv_bytes = bytes(sk)
    pub_bytes = bytes(sk.verify_key)
    PRIV_PATH.write_bytes(priv_bytes)
    PUB_PATH.write_bytes(pub_bytes)
    os.chmod(PRIV_PATH, 0o600)
    os.chmod(PUB_PATH, 0o644)
    return priv_bytes, pub_bytes


def load_signing_key() -> Optional["SigningKey"]:
    """Load this node's signing key. Returns None if no key present."""
    if not PRIV_PATH.exists():
        return None
    try:
        from nacl.signing import SigningKey
        return SigningKey(PRIV_PATH.read_bytes())
    except Exception:
        return None


def load_pubkeys() -> dict:
    """Load known-peer public keys from pubkeys.json."""
    if not PUBKEYS_PATH.exists():
        return {}
    try:
        d = json.loads(PUBKEYS_PATH.read_text())
        if isinstance(d, dict):
            return d
    except Exception:
        pass
    return {}


def save_pubkeys(d: dict) -> None:
    _ensure_dir()
    tmp = PUBKEYS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, indent=2, ensure_ascii=False))
    os.replace(tmp, PUBKEYS_PATH)
    os.chmod(PUBKEYS_PATH, 0o644)


def _canonical_bytes(msg: dict) -> bytes:
    """Canonical JSON for signing — sort keys, ensure_ascii=False, exclude
    the sig field itself."""
    payload = {k: v for k, v in msg.items() if k != "sig"}
    return json.dumps(payload, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def sign_outgoing(msg: dict, signing_key: Optional["SigningKey"] = None) -> dict:
    """Add `sig` field to msg. Returns the same dict mutated."""
    if signing_key is None:
        signing_key = load_signing_key()
    if signing_key is None:
        return msg  # no key, leave unsigned
    canonical = _canonical_bytes(msg)
    signed = signing_key.sign(canonical)
    msg["sig"] = base64.b64encode(signed.signature).decode("ascii")
    return msg


def verify_incoming(msg: dict, pubkeys: Optional[dict] = None) -> tuple[bool, str]:
    """Verify msg's `sig` against pubkeys[msg['from']].

    Returns (is_valid, reason). reason is empty on success or describes
    why verification failed.
    """
    if pubkeys is None:
        pubkeys = load_pubkeys()
    sender = msg.get("from")
    if not sender:
        return False, "missing from field"
    if sender not in pubkeys:
        return False, f"unknown sender {sender!r}"
    sig_b64 = msg.get("sig")
    if not sig_b64:
        return False, "missing sig"
    try:
        sig = base64.b64decode(sig_b64)
    except Exception:
        return False, "sig not base64"
    try:
        pub_bytes = base64.b64decode(pubkeys[sender])
    except Exception:
        return False, f"pubkey for {sender} not base64"
    canonical = _canonical_bytes(msg)
    try:
        from nacl.signing import VerifyKey
        VerifyKey(pub_bytes).verify(canonical, sig)
        return True, ""
    except Exception as e:
        return False, f"verify failed: {e!s}"


def my_public_key_b64() -> Optional[str]:
    """Returns this node's public key in base64, for pasting into other
    nodes' pubkeys.json."""
    if not PUB_PATH.exists():
        return None
    return base64.b64encode(PUB_PATH.read_bytes()).decode("ascii")


# CLI
def _main() -> int:
    if len(sys.argv) < 2:
        print("usage: peer_crypto.py {generate|pubkey|list-peers|"
              "add-peer NAME B64_KEY|remove-peer NAME}")
        return 1
    cmd = sys.argv[1]
    if cmd == "generate":
        force = "--force" in sys.argv
        priv, pub = generate_keypair(force=force)
        print(f"keypair at {KEY_DIR}")
        print(f"public (base64): {base64.b64encode(pub).decode('ascii')}")
        return 0
    if cmd == "pubkey":
        pk = my_public_key_b64()
        if pk is None:
            print("no key; run `generate` first")
            return 1
        print(pk)
        return 0
    if cmd == "list-peers":
        d = load_pubkeys()
        for name in sorted(d):
            print(f"  {name}: {d[name][:24]}...")
        if not d:
            print("(no peers configured)")
        return 0
    if cmd == "add-peer" and len(sys.argv) >= 4:
        name, b64 = sys.argv[2], sys.argv[3]
        d = load_pubkeys()
        d[name] = b64
        save_pubkeys(d)
        print(f"added peer {name}")
        return 0
    if cmd == "remove-peer" and len(sys.argv) >= 3:
        name = sys.argv[2]
        d = load_pubkeys()
        if name in d:
            del d[name]
            save_pubkeys(d)
            print(f"removed peer {name}")
        else:
            print(f"peer {name} not in pubkeys.json")
        return 0
    print(f"unknown command: {cmd}")
    return 1


if __name__ == "__main__":
    sys.exit(_main())
