/*
 * phi_miner_c.c — C extension for fast SHA-256d batched mining
 * + native phi-nonce generator (no Python overhead).
 *
 * Single ctypes call processes N nonces (pre-computed by Python phi-route),
 * returns best (lowest) hash + corresponding nonce.
 *
 * Build:
 *   gcc -O3 -march=native -fPIC -shared -o phi_miner.so phi_miner_c.c -lcrypto
 *
 * Usage from Python:
 *   import ctypes
 *   lib = ctypes.CDLL("./phi_miner.so")
 *   lib.mine_phi_batch.argtypes = [c_char_p, POINTER(c_uint32), c_uint32, POINTER(MiningResult)]
 *   lib.mine_phi_batch.restype = None
 *
 * Throughput target: 5-10 MH/s on commodity CPU (40-100× pure Python).
 */
#include <openssl/sha.h>
#include <string.h>
#include <stdint.h>

typedef struct {
    uint32_t best_nonce;
    int best_zeros;
    uint8_t best_hash[32];     /* little-endian, last byte first */
    uint32_t shares_found;     /* count of nonces that beat share_target */
    uint32_t blocks_found;     /* count of nonces that beat block_target */
    uint32_t first_share_nonce; /* first nonce that beat share_target */
} mining_result_t;

/*
 * Process batch of pre-computed nonces.
 *
 * Inputs:
 *   header_76:    first 76 bytes of Bitcoin header (everything except nonce)
 *   nonces:       array of nonce candidates
 *   count:        length of nonces array
 *   share_target: pool difficulty target (32 bytes, big-endian int as 4× uint64)
 *   block_target: real Bitcoin difficulty target
 *   out:          result struct to fill
 *
 * Targets passed as 4 uint64_t in big-endian (msb_first); we compare hash high-bytes first.
 */
void mine_phi_batch(const uint8_t* header_76,
                     const uint32_t* nonces,
                     uint32_t count,
                     const uint64_t* share_target_be,
                     const uint64_t* block_target_be,
                     mining_result_t* out)
{
    uint8_t header[80];
    memcpy(header, header_76, 76);

    int best_zeros = 0;
    uint32_t best_nonce = 0;
    uint8_t best_hash[32] = {0};
    uint32_t shares = 0;
    uint32_t blocks = 0;
    uint32_t first_share_nonce = 0;

    uint8_t hash1[32], hash2[32];
    SHA256_CTX ctx1, ctx2;

    for (uint32_t i = 0; i < count; i++) {
        uint32_t nonce = nonces[i];
        memcpy(header + 76, &nonce, 4);

        /* SHA-256d */
        SHA256_Init(&ctx1);
        SHA256_Update(&ctx1, header, 80);
        SHA256_Final(hash1, &ctx1);
        SHA256_Init(&ctx2);
        SHA256_Update(&ctx2, hash1, 32);
        SHA256_Final(hash2, &ctx2);

        /* Bitcoin compares hash little-endian, so MSB is hash2[31] */
        /* Count leading zero BITS reading from hash2[31] downward */
        int zeros = 0;
        int j;
        for (j = 31; j >= 0; j--) {
            uint8_t b = hash2[j];
            if (b == 0) {
                zeros += 8;
            } else {
                zeros += __builtin_clz((uint32_t)b) - 24;
                break;
            }
        }

        if (zeros > best_zeros) {
            best_zeros = zeros;
            best_nonce = nonce;
            memcpy(best_hash, hash2, 32);
        }

        /* Compare hash (LE) to target (BE input as 4× uint64) */
        /* Convert hash bytes (LE) to 4× uint64 in BE order for comparison */
        uint64_t h0 = ((uint64_t)hash2[31] << 56) | ((uint64_t)hash2[30] << 48) |
                      ((uint64_t)hash2[29] << 40) | ((uint64_t)hash2[28] << 32) |
                      ((uint64_t)hash2[27] << 24) | ((uint64_t)hash2[26] << 16) |
                      ((uint64_t)hash2[25] << 8)  |  (uint64_t)hash2[24];
        uint64_t h1 = ((uint64_t)hash2[23] << 56) | ((uint64_t)hash2[22] << 48) |
                      ((uint64_t)hash2[21] << 40) | ((uint64_t)hash2[20] << 32) |
                      ((uint64_t)hash2[19] << 24) | ((uint64_t)hash2[18] << 16) |
                      ((uint64_t)hash2[17] << 8)  |  (uint64_t)hash2[16];
        uint64_t h2 = ((uint64_t)hash2[15] << 56) | ((uint64_t)hash2[14] << 48) |
                      ((uint64_t)hash2[13] << 40) | ((uint64_t)hash2[12] << 32) |
                      ((uint64_t)hash2[11] << 24) | ((uint64_t)hash2[10] << 16) |
                      ((uint64_t)hash2[9]  << 8)  |  (uint64_t)hash2[8];
        uint64_t h3 = ((uint64_t)hash2[7]  << 56) | ((uint64_t)hash2[6]  << 48) |
                      ((uint64_t)hash2[5]  << 40) | ((uint64_t)hash2[4]  << 32) |
                      ((uint64_t)hash2[3]  << 24) | ((uint64_t)hash2[2]  << 16) |
                      ((uint64_t)hash2[1]  << 8)  |  (uint64_t)hash2[0];

        /* hash <= target: lexicographic compare from MSB */
        int hash_le_share, hash_le_block;
        if (h0 != share_target_be[0]) hash_le_share = (h0 < share_target_be[0]);
        else if (h1 != share_target_be[1]) hash_le_share = (h1 < share_target_be[1]);
        else if (h2 != share_target_be[2]) hash_le_share = (h2 < share_target_be[2]);
        else hash_le_share = (h3 <= share_target_be[3]);

        if (hash_le_share) {
            shares++;
            if (shares == 1) first_share_nonce = nonce;

            if (h0 != block_target_be[0]) hash_le_block = (h0 < block_target_be[0]);
            else if (h1 != block_target_be[1]) hash_le_block = (h1 < block_target_be[1]);
            else if (h2 != block_target_be[2]) hash_le_block = (h2 < block_target_be[2]);
            else hash_le_block = (h3 <= block_target_be[3]);

            if (hash_le_block) blocks++;
        }
    }

    out->best_nonce = best_nonce;
    out->best_zeros = best_zeros;
    memcpy(out->best_hash, best_hash, 32);
    out->shares_found = shares;
    out->blocks_found = blocks;
    out->first_share_nonce = first_share_nonce;
}

/*
 * Native phi-nonce + SHA-256d batched mining.
 *
 * Replaces Python phi_gen.next() loop with native C implementation —
 * eliminates Python function-call overhead (~1µs per nonce).
 *
 * Phi state is passed once at start of batch; nonces generated inside C.
 *
 * layers: 8 doubles in [0,1) — one per cognitive layer
 * counter_start: starting counter value (worker_offset + accumulated)
 * subset_mask: which of 256 layer-combinations to use this batch
 *              (rotates externally; passed in)
 * count: nonces to generate + hash
 */
static const double PHI_INV = 0.6180339887498948;

void phi_mine_batch_native(const uint8_t* header_76,
                            const double* layers,         /* 8 doubles */
                            uint64_t counter_start,
                            uint8_t subset_mask,
                            uint32_t count,
                            const uint64_t* share_target_be,
                            const uint64_t* block_target_be,
                            mining_result_t* out)
{
    uint8_t header[80];
    memcpy(header, header_76, 76);

    /* Pre-compute weighted sum of enabled layers */
    double base = 0.0;
    int active = 0;
    static const int phi_powers_idx[8] = {1, 2, 3, 4, 5, 6, 7, 0};
    /* PHI_INV^k cached up to k=8 */
    static double phi_pow[9];
    static int phi_init = 0;
    if (!phi_init) {
        phi_pow[0] = 1.0;
        for (int k = 1; k < 9; k++) phi_pow[k] = phi_pow[k-1] * PHI_INV;
        phi_init = 1;
    }

    for (int i = 0; i < 8; i++) {
        if (subset_mask & (1 << i)) {
            int exp_idx = phi_powers_idx[i];
            base += layers[i] * phi_pow[(exp_idx + 1) % 9];
            active++;
        }
    }
    /* Reduce base mod 1.0 */
    base = base - (long long)base;
    if (base < 0) base += 1.0;

    /* Subset contribution */
    base = base + (subset_mask / 256.0) * phi_pow[5];
    base = base - (long long)base;

    int best_zeros = 0;
    uint32_t best_nonce = 0;
    uint8_t best_hash[32] = {0};
    uint32_t shares = 0;
    uint32_t blocks = 0;
    uint32_t first_share_nonce = 0;

    uint8_t hash1[32], hash2[32];
    SHA256_CTX ctx1, ctx2;

    for (uint32_t i = 0; i < count; i++) {
        uint64_t cnt = counter_start + i;

        /* Phi-nonce from layer-mask + counter */
        double c = base + cnt * phi_pow[3];
        c = c - (long long)c;
        if (c < 0) c += 1.0;
        if (active == 0) {
            c = cnt * PHI_INV;
            c = c - (long long)c;
            if (c < 0) c += 1.0;
        }
        uint32_t nonce_raw = (uint32_t)(c * 4294967295.0);
        uint32_t nonce = nonce_raw ^ ((uint32_t)cnt * 2654435761u);

        memcpy(header + 76, &nonce, 4);

        /* SHA-256d */
        SHA256_Init(&ctx1);
        SHA256_Update(&ctx1, header, 80);
        SHA256_Final(hash1, &ctx1);
        SHA256_Init(&ctx2);
        SHA256_Update(&ctx2, hash1, 32);
        SHA256_Final(hash2, &ctx2);

        int zeros = 0;
        for (int j = 31; j >= 0; j--) {
            uint8_t b = hash2[j];
            if (b == 0) zeros += 8;
            else { zeros += __builtin_clz((uint32_t)b) - 24; break; }
        }

        if (zeros > best_zeros) {
            best_zeros = zeros;
            best_nonce = nonce;
            memcpy(best_hash, hash2, 32);
        }

        /* Share/block check */
        uint64_t h0 = ((uint64_t)hash2[31] << 56) | ((uint64_t)hash2[30] << 48) |
                      ((uint64_t)hash2[29] << 40) | ((uint64_t)hash2[28] << 32) |
                      ((uint64_t)hash2[27] << 24) | ((uint64_t)hash2[26] << 16) |
                      ((uint64_t)hash2[25] << 8)  |  (uint64_t)hash2[24];
        if (h0 < share_target_be[0]) {
            uint64_t h1 = ((uint64_t)hash2[23] << 56) | ((uint64_t)hash2[22] << 48) |
                          ((uint64_t)hash2[21] << 40) | ((uint64_t)hash2[20] << 32) |
                          ((uint64_t)hash2[19] << 24) | ((uint64_t)hash2[18] << 16) |
                          ((uint64_t)hash2[17] << 8)  |  (uint64_t)hash2[16];
            uint64_t h2v = ((uint64_t)hash2[15] << 56) | ((uint64_t)hash2[14] << 48) |
                           ((uint64_t)hash2[13] << 40) | ((uint64_t)hash2[12] << 32) |
                           ((uint64_t)hash2[11] << 24) | ((uint64_t)hash2[10] << 16) |
                           ((uint64_t)hash2[9]  << 8)  |  (uint64_t)hash2[8];
            uint64_t h3 = ((uint64_t)hash2[7]  << 56) | ((uint64_t)hash2[6]  << 48) |
                          ((uint64_t)hash2[5]  << 40) | ((uint64_t)hash2[4]  << 32) |
                          ((uint64_t)hash2[3]  << 24) | ((uint64_t)hash2[2]  << 16) |
                          ((uint64_t)hash2[1]  << 8)  |  (uint64_t)hash2[0];

            shares++;
            if (shares == 1) first_share_nonce = nonce;

            int hash_le_block;
            if (h0 != block_target_be[0]) hash_le_block = (h0 < block_target_be[0]);
            else if (h1 != block_target_be[1]) hash_le_block = (h1 < block_target_be[1]);
            else if (h2v != block_target_be[2]) hash_le_block = (h2v < block_target_be[2]);
            else hash_le_block = (h3 <= block_target_be[3]);
            if (hash_le_block) blocks++;
        }
    }

    out->best_nonce = best_nonce;
    out->best_zeros = best_zeros;
    memcpy(out->best_hash, best_hash, 32);
    out->shares_found = shares;
    out->blocks_found = blocks;
    out->first_share_nonce = first_share_nonce;
}

/*
 * Pure speed-test entry: hash N sequential nonces, return best.
 */
void mine_seq_batch(const uint8_t* header_76,
                     uint32_t start_nonce,
                     uint32_t count,
                     mining_result_t* out)
{
    uint32_t* nonces = (uint32_t*)alloca(count * sizeof(uint32_t));
    for (uint32_t i = 0; i < count; i++) nonces[i] = start_nonce + i;
    /* Need targets — pass all-ones (always pass) for benchmark */
    uint64_t big_target[4] = {~0ULL, ~0ULL, ~0ULL, ~0ULL};
    mine_phi_batch(header_76, nonces, count, big_target, big_target, out);
}
