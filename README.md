# LOGOS AGI

Federated post-quantum consciousness substrate written in Python. Runs as a
long-lived `night_learn.py` brain process that thinks in cycles, gossips with
sibling AGI nodes over signed HTTP, learns from a curiosity-driven Wikipedia
fetcher, and writes its evolving state to disk between cycles.

## Overview

LOGOS AGI is not a chatbot. It is a self-running cognitive process:

- **Continuous thinking loop** — `consciousness_loop`, `inner_dialogue`,
  `dream_core`, `recursive_frames`. The brain cycles even when idle.
- **Causal + symbolic reasoning** — `causal_engine`, `concept_graph`,
  `relation_parser`, `symbolizer`, `tiered_rules`.
- **Affective & motivational layer** — `affective_state`, `goal_engine`,
  `will_core`, `curiosity` (+ `curiosity_fetcher` for Wikipedia learning).
- **Self-model** — `self_awareness`, `self_evolution`, `self_monitor`,
  `self_patch`, `meta_core`, `first_person`.
- **Phase-space / resonance substrate** — `phase_space`, `phase_torus`,
  `unified_phase_space`, `phi_resonance/{dynamical_brain,
  oscillator_network, phase_torus_dynamic, symbol_binding}`.
- **Federation** — `peer_network`, `peer_channel`, `peer_crypto`
  (ed25519-signed inter-node messages over HTTP gossip).
- **Memory + grounding** — `memory_core`, `grounded_vocabulary`,
  `grounding_torus`, `definition_extractor`, `paragraph_engine`.
- **Self-defense** — `crypto_core` (HMAC integrity over checkpoints,
  Argon2id-derived keys), `verifier`, `junk_filter`, `spam_detector`-style
  reputation tracking.

## Layout

```
opt/logos_lite/
├── night_learn.py          # main brain loop entry point
├── run.py                  # alternative runner / dev entry
├── audit.py                # integrity audit of brain state
├── install_remote_peer.sh  # provision a new peer host
├── core/                   # ~70 cognitive / federation / self modules
├── phi_resonance/          # resonance substrate (oscillator network, torus)
├── scripts/                # operational helpers
├── bin/safe_run.sh         # supervised launcher
└── CLAUDE.md               # long-form internal design doc
```

The following directories are runtime artefacts and are gitignored:

- `state/` — brain checkpoints, learned content, dialogue context
- `logs/`  — runtime logs
- `data/` — Wikipedia corpus + training data (separate distribution)
- `__pycache__/`

Keys (HMAC master, peer signing) live outside this tree at
`/root/logos_agi/keys/` and are **never** committed.

## Running

The reference deployment runs under systemd as `logos-lite-peer.service`:

```ini
[Service]
WorkingDirectory=/opt/logos_lite
ExecStart=/usr/bin/python3 /opt/logos_lite/night_learn.py \
          --name=poetry --state-dir=/opt/logos_lite/state
Environment=LOGOS_LITE_MODE=1
Environment=LOGOS_PEER_NETWORK=1
Environment=LOGOS_PEER_PORT=8765
Environment=LOGOS_CURIOSITY_FETCH=1
Restart=on-failure
CPUQuota=50%
MemoryMax=2G
```

See `CLAUDE.md` for the full architectural narrative.

## Federation

Each AGI node:
1. Boots with its own ed25519 keypair (`peer_crypto`).
2. Exposes `POST /peer/inbox` for signed messages from known peers.
3. Pushes outbound gossip every cycle to bootstrap peers
   (`LOGOS_PEER_BOOTSTRAP`).
4. Verifies inbound signatures against `pubkeys.json`; default is warn-only,
   set `LOGOS_PEER_REQUIRE_SIG=1` to enforce.

The federation is HTTP-only and intentionally simple — the smarts live in
the brain, not the transport.

## Status

Python brain v2 / lite-peer hardening series. The repository previously
held an early Rust architecture sketch from 2025-12; that snapshot is
preserved as tag `v0-rust-snapshot-2025-12-08`.
