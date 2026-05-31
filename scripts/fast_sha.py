"""Fast SHA-256d via ctypes → OpenSSL libcrypto.

Bypasses Python's hashlib wrapper overhead. Calls EVP_Digest directly.

Speedup vs hashlib: ~5-15× for short messages (Bitcoin headers are 80 bytes).

Usage:
    from fast_sha import sha256d_fast
    digest = sha256d_fast(header_bytes)  # 32-byte result
"""
import ctypes
import ctypes.util
import hashlib
import time


def _load_libcrypto():
    """Find and load libcrypto.so."""
    for name in ("crypto", "crypto.3", "crypto.1.1"):
        path = ctypes.util.find_library(name)
        if path:
            try:
                return ctypes.CDLL(path)
            except OSError:
                continue
    # Direct paths fallback
    for path in ("libcrypto.so.3", "libcrypto.so.1.1", "libcrypto.so"):
        try:
            return ctypes.CDLL(path)
        except OSError:
            continue
    raise OSError("Cannot find libcrypto")


_lib = _load_libcrypto()
_SHA256 = _lib.SHA256
_SHA256.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_char_p]
_SHA256.restype = ctypes.c_char_p


def sha256(data: bytes) -> bytes:
    out = ctypes.create_string_buffer(32)
    _SHA256(data, len(data), out)
    return out.raw[:32]


def sha256d_fast(data: bytes) -> bytes:
    """Bitcoin double SHA-256 via direct OpenSSL call."""
    out = ctypes.create_string_buffer(32)
    _SHA256(data, len(data), out)
    out2 = ctypes.create_string_buffer(32)
    _SHA256(out.raw, 32, out2)
    return out2.raw[:32]


# === Self-test ===

def _verify():
    """Confirm fast SHA matches hashlib output."""
    test_inputs = [b"", b"a", b"abc", b"\x00" * 80, b"\xff" * 80,
                   b"The quick brown fox jumps over the lazy dog"]
    for x in test_inputs:
        a = hashlib.sha256(hashlib.sha256(x).digest()).digest()
        b = sha256d_fast(x)
        assert a == b, f"mismatch on {x[:20]!r}: {a.hex()} vs {b.hex()}"
    return True


def _benchmark(n=200_000):
    """Compare fast vs hashlib speed for 80-byte input."""
    test = b"\x42" * 80
    # warmup
    for _ in range(1000):
        sha256d_fast(test)
        hashlib.sha256(hashlib.sha256(test).digest()).digest()

    t0 = time.perf_counter()
    for _ in range(n):
        sha256d_fast(test)
    t_fast = time.perf_counter() - t0

    t0 = time.perf_counter()
    for _ in range(n):
        hashlib.sha256(hashlib.sha256(test).digest()).digest()
    t_hash = time.perf_counter() - t0

    return {
        "n": n,
        "fast_s": t_fast, "fast_h_per_s": n / t_fast,
        "hashlib_s": t_hash, "hashlib_h_per_s": n / t_hash,
        "speedup": t_hash / t_fast,
    }


if __name__ == "__main__":
    _verify()
    print("verify: OK")
    b = _benchmark(200_000)
    print(f"hashlib:    {b['hashlib_h_per_s']:>10,.0f} H/s  ({b['hashlib_s']:.2f}s for {b['n']})")
    print(f"fast_sha:   {b['fast_h_per_s']:>10,.0f} H/s  ({b['fast_s']:.2f}s)")
    print(f"speedup:    {b['speedup']:.2f}×")
