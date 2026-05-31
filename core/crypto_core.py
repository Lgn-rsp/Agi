"""
crypto_core.py — Zashchita sistemy.
AES-256-GCM. Vsyo sostoyaniye zashifrovano.
Bez klyucha sozdatelya — sistema ne zapustitsya.
"""
import os
import json
import hashlib
import hmac as hmac_module

try:
    from Crypto.Cipher import AES
    from Crypto.Random import get_random_bytes
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

from core.resonance_constants import PHI, FIBONACCI

GCM_NONCE_SIZE = 12
GCM_TAG_SIZE = 16
KEY_SIZE = 32


class KeyManager:
    """Upravleniye klyuchami sozdatelya."""

    def __init__(self, keys_dir=None):
        self.keys_dir = keys_dir or os.path.expanduser("~/logos_agi/keys")
        self._master_key = None
        self._hmac_key = None
        self._ensure_keys()

    def _ensure_keys(self):
        os.makedirs(self.keys_dir, exist_ok=True)
        master_path = os.path.join(self.keys_dir, "master.bin")
        hmac_path = os.path.join(self.keys_dir, "hmac.bin")

        if not os.path.exists(master_path):
            key = get_random_bytes(KEY_SIZE) if HAS_CRYPTO else os.urandom(KEY_SIZE)
            with open(master_path, "wb") as f:
                f.write(key)
            os.chmod(master_path, 0o600)
            print(f"[+] Master key generated: {master_path}")

        if not os.path.exists(hmac_path):
            key = get_random_bytes(KEY_SIZE) if HAS_CRYPTO else os.urandom(KEY_SIZE)
            with open(hmac_path, "wb") as f:
                f.write(key)
            os.chmod(hmac_path, 0o600)

        with open(master_path, "rb") as f:
            self._master_key = f.read(KEY_SIZE)
        with open(hmac_path, "rb") as f:
            self._hmac_key = f.read(KEY_SIZE)

    @property
    def master_key(self):
        return self._master_key

    @property
    def hmac_key(self):
        return self._hmac_key

    def derive_key(self, purpose):
        """Proizvodnoy klyuch dlya konkretnoy tseli."""
        return hashlib.sha256(
            self._master_key + purpose.encode()
        ).digest()


def _require_crypto():
    if not HAS_CRYPTO:
        raise RuntimeError(
            "pycryptodome REQUIRED. "
            "Install: pip install pycryptodome --break-system-packages")


def encrypt_gcm(data, key):
    """AES-256-GCM shifrovaniye."""
    _require_crypto()
    nonce = get_random_bytes(GCM_NONCE_SIZE)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    ciphertext, tag = cipher.encrypt_and_digest(data)
    return nonce + tag + ciphertext


def decrypt_gcm(blob, key):
    """AES-256-GCM deshifrovaniye."""
    _require_crypto()
    if len(blob) < GCM_NONCE_SIZE + GCM_TAG_SIZE:
        raise ValueError("Blob too short")
    nonce = blob[:GCM_NONCE_SIZE]
    tag = blob[GCM_NONCE_SIZE:GCM_NONCE_SIZE + GCM_TAG_SIZE]
    ciphertext = blob[GCM_NONCE_SIZE + GCM_TAG_SIZE:]
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    return cipher.decrypt_and_verify(ciphertext, tag)


def encrypt_json(data, key):
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return encrypt_gcm(raw, key)


def decrypt_json(blob, key):
    return json.loads(decrypt_gcm(blob, key).decode("utf-8"))


def compute_hmac(data, key):
    if isinstance(data, str):
        data = data.encode()
    return hmac_module.new(key, data, hashlib.sha256).hexdigest()


def verify_hmac(data, key, expected):
    return hmac_module.compare_digest(compute_hmac(data, key), expected)


def hash_data(data):
    """SHA-256 hash."""
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()


# Singleton
_km = None
def get_key_manager():
    global _km
    if _km is None:
        _km = KeyManager()
    return _km


# === TEST ===
if __name__ == "__main__":
    km = get_key_manager()
    print(f"Master key hash: {hash_data(km.master_key)[:16]}...")

    # Test encrypt/decrypt
    test_data = {"test": "LOGOS AGI", "phi": 1.618}
    blob = encrypt_json(test_data, km.master_key)
    result = decrypt_json(blob, km.master_key)
    assert result == test_data
    print(f"Encrypt/decrypt: OK")

    # Test HMAC
    h = compute_hmac("test message", km.hmac_key)
    assert verify_hmac("test message", km.hmac_key, h)
    print(f"HMAC: OK")

    # Test derived key
    dk = km.derive_key("memory")
    print(f"Derived key (memory): {hash_data(dk)[:16]}...")

    print("[+] crypto_core: all tests passed")
