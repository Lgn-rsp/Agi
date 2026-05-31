#!/usr/bin/env python3
"""
audit.py — Polnaya proverka LOGOS AGI.
Nahodit bagi, mertvyy kod, rassoglasovaniya, propushchennye svyazi.
"""
import sys, os, importlib, inspect, ast, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS = 0
FAIL = 0
WARN = 0

def test(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")

def warn(name, detail=""):
    global WARN
    WARN += 1
    print(f"  WARN  {name}  {detail}")

print("=" * 60)
print("LOGOS AGI — FULL SYSTEM AUDIT")
print("=" * 60)

# ============================================================
print("\n--- 1. MODULE IMPORTS ---")
# ============================================================
modules = {}
module_names = [
    "core.resonance_constants",
    "core.phase_space",
    "core.symbolizer",
    "core.learner",
    "core.dream_core",
    "core.curiosity",
    "core.memory_core",
    "core.crypto_core",
    "core.creator_identity",
    "core.will_core",
    "core.meta_core",
    "core.generator",
    "core.seeker",
    "core.self_monitor",
    "core.logos_brain",
]

for name in module_names:
    try:
        mod = importlib.import_module(name)
        modules[name] = mod
        test(f"import {name}", True)
    except Exception as e:
        test(f"import {name}", False, str(e)[:80])

# ============================================================
print("\n--- 2. RESONANCE CONSTANTS ---")
# ============================================================
rc = modules.get("core.resonance_constants")
if rc:
    test("PHI value", abs(rc.PHI - 1.6180339887498948) < 1e-10)
    test("PHI_INV value", abs(rc.PHI_INV - 0.6180339887498948) < 1e-10)
    test("FIBONACCI length >= 19", len(rc.FIBONACCI) >= 19)
    test("FIBONACCI[9]=55", rc.FIBONACCI[9] == 55)
    test("HARMONICS", rc.HARMONICS == [0, 1, 2, 4, 5, 6, 11])
    # FIELD_NAMES: structural checks only — no hardcoded names anywhere.
    # Canon: phases derive from index × PHI_INV % 1.0; first phase = 0 (Creator).
    test("FIELD_NAMES non-empty", len(rc.FIELD_NAMES) >= 1)
    test("FIELD_NAMES unique", len(set(rc.FIELD_NAMES)) == len(rc.FIELD_NAMES))
    test("FIELD_PHASES count matches FIELD_NAMES",
         len(rc.FIELD_PHASES) == len(rc.FIELD_NAMES))
    test("FIELD_PHASES[name=index_0] is Creator phase 0.0",
         rc.FIELD_PHASES[rc.FIELD_NAMES[0]] == 0.0)
    # All phases derived correctly: phase[i] == (i*PHI_INV) % 1.0
    derived_ok = all(
        abs(rc.FIELD_PHASES[name] - (i * rc.PHI_INV) % 1.0) < 1e-12
        for i, name in enumerate(rc.FIELD_NAMES)
    )
    test("FIELD_PHASES = i × PHI_INV mod 1 for all", derived_ok)
    test("phi_phase(1.0) works", rc.phi_phase(1.0) >= 0)
    test("phi_phase_distance symmetric",
         abs(rc.phi_phase_distance(0.2, 0.8) - rc.phi_phase_distance(0.8, 0.2)) < 1e-10)
    test("is_near_phi_target(1.618)", rc.is_near_phi_target(1.618) is not None)
    test("CRYSTALLIZE_THRESHOLD=8", rc.CRYSTALLIZE_THRESHOLD == 8)
    test("CO_OCCURRENCE_WINDOW=8", rc.CO_OCCURRENCE_WINDOW == 8)

    # No linear constants check
    for attr in ['CRYSTALLIZE_THRESHOLD', 'DREAM_INTERVAL', 'SAVE_INTERVAL',
                 'MAX_RULES', 'CACHE_SIZE', 'CO_OCCURRENCE_WINDOW']:
        val = getattr(rc, attr, None)
        if val is not None:
            is_fib = val in rc.FIBONACCI
            is_phi_power = any(abs(val - round(rc.PHI**n)) < 1 for n in range(1, 20))
            test(f"{attr}={val} resonant", is_fib or is_phi_power,
                 f"value {val} is not fibonacci or phi-power")

# ============================================================
print("\n--- 3. PHASE SPACE ---")
# ============================================================
ps_mod = modules.get("core.phase_space")
if ps_mod:
    ps = ps_mod.PhaseSpace(state_dir="/tmp/audit_ps")

    test("PhaseSpace created", ps is not None)
    test("has axioms", len(ps.axioms) >= 4)
    test("creator axiom phase=0.0", ps.axioms.get("creator", {}).get("phase") == 0.0)
    test("harm axiom phase=0.5", ps.axioms.get("harm", {}).get("phase") == 0.5)
    test("axioms immutable", all(a.get("immutable") for a in ps.axioms.values()))

    # Observe test
    ps.observe(["a", "b", "c", "a", "b", "c"] * 10)
    test("observe creates symbols", len(ps.phases) >= 3)
    test("observe creates cooccurrence", len(ps.cooccurrence) > 0)

    # Query test
    q = ps.query("a")
    test("query returns dict", isinstance(q, dict))
    test("query has phase", "phase" in q)

    # Save/load test
    ps.save_state()
    test("save_state works", os.path.exists("/tmp/audit_ps/phase_space.json"))

    # Anomalies
    anomalies = ps.find_anomalies()
    test("find_anomalies returns list", isinstance(anomalies, list))

# ============================================================
print("\n--- 4. AXIOM CONSISTENCY ---")
# ============================================================
ci_mod = modules.get("core.creator_identity")
ps_mod2 = modules.get("core.phase_space")
if ci_mod and ps_mod2:
    # Check: phase_space axioms vs creator_identity axioms
    ps_test = ps_mod2.PhaseSpace(state_dir="/tmp/audit_axiom")
    ci_axioms = ci_mod.CREATOR_AXIOMS

    ps_axiom_names = set(ps_test.axioms.keys())
    ci_axiom_names = set(ci_axioms.keys())

    # Both modules now use unified short names: creator / harm
    ps_has_creator = "creator" in ps_axiom_names
    ci_has_creator = "creator" in ci_axiom_names
    test("both have creator axiom", ps_has_creator and ci_has_creator)

    ps_has_harm = "harm" in ps_axiom_names
    ci_has_harm = "harm" in ci_axiom_names
    test("both have harm axiom", ps_has_harm and ci_has_harm)

    # Check phase values match
    if ps_has_creator and ci_has_creator:
        ps_phase = ps_test.axioms["creator"]["phase"]
        ci_phase = ci_axioms["creator"]["phase"]
        test("creator phase match", ps_phase == ci_phase,
             f"PS={ps_phase} vs CI={ci_phase}")

    if ps_has_harm and ci_has_harm:
        ps_phase = ps_test.axioms["harm"]["phase"]
        ci_phase = ci_axioms["harm"]["phase"]
        test("harm phase match", ps_phase == ci_phase,
             f"PS={ps_phase} vs CI={ci_phase}")

    # Creator has symbiosis, does PhaseSpace?
    ci_has_symbiosis = "symbiosis" in ci_axiom_names
    ps_has_symbiosis = any("symbiosis" in k or "symbio" in k
                          for k in ps_axiom_names)
    if ci_has_symbiosis and not ps_has_symbiosis:
        warn("PhaseSpace missing 'symbiosis' axiom",
             "creator_identity has it but PhaseSpace does not")

    # Count difference
    if len(ps_axiom_names) != len(ci_axiom_names):
        warn(f"Axiom count mismatch",
             f"PhaseSpace has {len(ps_axiom_names)}, "
             f"CreatorIdentity has {len(ci_axiom_names)}")

# ============================================================
print("\n--- 5. CRYPTO INTEGRATION ---")
# ============================================================
crypto_mod = modules.get("core.crypto_core")
if crypto_mod:
    km = crypto_mod.get_key_manager()
    test("KeyManager created", km is not None)
    test("master_key exists", km.master_key is not None and len(km.master_key) == 32)
    test("hmac_key exists", km.hmac_key is not None and len(km.hmac_key) == 32)

    # Test encrypt/decrypt
    test_data = {"test": True, "phi": 1.618}
    blob = crypto_mod.encrypt_json(test_data, km.master_key)
    result = crypto_mod.decrypt_json(blob, km.master_key)
    test("encrypt/decrypt JSON", result == test_data)

    # Check: who uses crypto?
    core_dir = os.path.expanduser("~/logos_agi/core")
    crypto_users = []
    for fname in os.listdir(core_dir):
        if not fname.endswith(".py") or fname == "crypto_core.py":
            continue
        fpath = os.path.join(core_dir, fname)
        with open(fpath, "r") as f:
            content = f.read()
        if "encrypt" in content or "decrypt" in content or "crypto_core" in content:
            crypto_users.append(fname)

    test("crypto used in other modules", len(crypto_users) > 0,
         f"only used in: {crypto_users}" if crypto_users else "NOBODY imports crypto!")

    # Check: state files are encrypted?
    state_dir = os.path.expanduser("~/logos_agi/state")
    json_files = []
    enc_files = []
    for root, dirs, files in os.walk(state_dir):
        for f in files:
            if f.endswith(".json"):
                json_files.append(f)
            elif f.endswith(".enc"):
                enc_files.append(f)

    if json_files:
        warn(f"Unencrypted state files",
             f"{len(json_files)} .json files: {json_files[:5]}")
    if enc_files:
        test(f"Encrypted state files exist", True)

# ============================================================
print("\n--- 6. WILL ENFORCEMENT ---")
# ============================================================
will_mod = modules.get("core.will_core")
if will_mod:
    will = will_mod.get_will()
    test("WillCore created", will is not None)

    # Check: who calls will.allow()?
    core_dir = os.path.expanduser("~/logos_agi/core")
    will_callers = []
    for fname in os.listdir(core_dir):
        if not fname.endswith(".py") or fname in ("will_core.py", "__init__.py"):
            continue
        fpath = os.path.join(core_dir, fname)
        with open(fpath, "r") as f:
            content = f.read()
        if "will" in content.lower() and ("allow" in content or "require_will" in content):
            if "will_core" in content or "get_will" in content:
                will_callers.append(fname)

    if not will_callers:
        warn("NOBODY calls will.allow()",
             "Will is defined but never enforced in any module")
    else:
        test("will enforced in modules", True,
             f"callers: {will_callers}")

# ============================================================
print("\n--- 7. DREAM SAFETY ---")
# ============================================================
dream_mod = modules.get("core.dream_core")
ci_mod2 = modules.get("core.creator_identity")
if dream_mod and ci_mod2:
    # Check: does dream_core call validate_dream?
    core_dir = os.path.expanduser("~/logos_agi/core")
    dream_path = os.path.join(core_dir, "dream_core.py")
    with open(dream_path, "r") as f:
        dream_code = f.read()

    has_validate = "validate_dream" in dream_code
    has_creator_import = "creator_identity" in dream_code
    test("dream imports creator_identity", has_creator_import,
         "dreams not checked against creator axioms!")
    test("dream calls validate_dream", has_validate,
         "dream results not validated!")

# ============================================================
print("\n--- 8. BRAIN INTEGRATION ---")
# ============================================================
brain_mod = modules.get("core.logos_brain")
if brain_mod:
    brain_path = os.path.join(os.path.expanduser("~/logos_agi/core"),
                               "logos_brain.py")
    with open(brain_path, "r") as f:
        brain_code = f.read()

    expected_imports = {
        "creator_identity": "CreatorIdentity / get_creator",
        "will_core": "WillCore / get_will",
        "crypto_core": "encryption",
        "meta_core": "MetaCore / self-reflection",
        "generator": "ResonanceGenerator / speech",
        "seeker": "Seeker / answer finding",
        "self_monitor": "SelfMonitor / health",
    }

    for module, purpose in expected_imports.items():
        found = module in brain_code
        if not found:
            warn(f"brain missing {module}", f"({purpose}) not integrated")
        else:
            test(f"brain has {module}", True)

# ============================================================
print("\n--- 9. SYMBOLIZER COVERAGE ---")
# ============================================================
sym_mod = modules.get("core.symbolizer")
if sym_mod:
    # Latin
    latin = sym_mod.text_to_words("The cat sat on the mat")
    test("latin text works", len(latin) == 6)

    # Numbers
    nums = sym_mod.text_to_words("2 plus 3 equals 5")
    test("numbers preserved", "plus" in nums,
         f"got: {nums}")

    # Check if numbers are stripped
    chars = sym_mod.text_to_chars("abc 123 def")
    has_digits = any(c.isdigit() for c in chars)
    if not has_digits:
        warn("symbolizer strips digits",
             "numbers will be lost during learning")

    # Cyrillic
    cyrillic = sym_mod.text_to_words("Кот сидит на мате")
    if len(cyrillic) == 0:
        warn("symbolizer strips cyrillic",
             "Russian text produces empty output")
    else:
        test("cyrillic works", len(cyrillic) > 0)

    # Special chars
    special = sym_mod.text_to_words("φ = 1.618 → golden ratio")
    if not special:
        warn("symbolizer strips special chars",
             "phi symbol and arrows lost")

# ============================================================
print("\n--- 10. RUN.PY COMPLETENESS ---")
# ============================================================
run_path = os.path.expanduser("~/logos_agi/run.py")
if os.path.exists(run_path):
    with open(run_path, "r") as f:
        run_code = f.read()

    expected_commands = {
        "generate": "text generation",
        "respond": "response to input",
        "meta": "self-reflection",
        "seek": "answer seeking",
        "health": "system health",
        "fields": "field distribution",
        "rules": "show rules",
    }

    for cmd, purpose in expected_commands.items():
        found = f'"{cmd}"' in run_code or f"'{cmd}'" in run_code
        if not found:
            warn(f"run.py missing '{cmd}' command", f"({purpose})")
        else:
            test(f"run.py has '{cmd}'", True)

# ============================================================
print("\n--- 11. PHASE_SPACE CRYSTALLIZE LOGIC ---")
# ============================================================
if ps_mod:
    ps_path = os.path.join(os.path.expanduser("~/logos_agi/core"),
                            "phase_space.py")
    with open(ps_path, "r") as f:
        ps_code = f.read()

    # Scope check to _try_crystallize body only (two legal call sites in
    # whole file: crystallize + find_anomalies — different functions).
    import re as _re
    m = _re.search(
        r"def _try_crystallize\(.*?\n(.*?)(?=\n    def |\nclass |\Z)",
        ps_code, _re.DOTALL)
    body = m.group(1) if m else ""
    count_in_fn = body.count("is_near_phi_target")
    if count_in_fn > 1:
        warn("_try_crystallize has double phi_target check",
             f"is_near_phi_target appears {count_in_fn} times inside "
             f"_try_crystallize — first call result may be overwritten")

# ============================================================
print("\n--- 12. STATE PERSISTENCE ---")
# ============================================================
state_dir = os.path.expanduser("~/logos_agi/state")
if os.path.isdir(state_dir):
    state_files = []
    for root, dirs, files in os.walk(state_dir):
        for f in files:
            fpath = os.path.join(root, f)
            size = os.path.getsize(fpath)
            rel = os.path.relpath(fpath, state_dir)
            state_files.append((rel, size))

    print(f"  State files found: {len(state_files)}")
    for name, size in sorted(state_files):
        enc_tag = " [ENCRYPTED]" if name.endswith(".enc") else ""
        print(f"    {name}: {size/1024:.1f}KB{enc_tag}")

    # Only creator identity.enc is encrypted
    encrypted = [n for n, _ in state_files if n.endswith(".enc")]
    unencrypted = [n for n, _ in state_files if n.endswith(".json")]
    test("has encrypted files", len(encrypted) > 0)
    if unencrypted:
        warn(f"{len(unencrypted)} unencrypted state files",
             ", ".join(unencrypted[:5]))

# ============================================================
print("\n--- 13. FUNCTIONAL TEST ---")
# ============================================================
try:
    brain = brain_mod.LogosBrain(
        state_dir=os.path.expanduser("~/logos_agi/state"))

    # Learn
    brain.learn("the cat sat on the mat")
    brain.learn("the dog ran in the park")
    test("brain.learn works", brain.total_texts_learned > 0)

    # Think
    think = brain.think()
    test("brain.think works", isinstance(think, dict))

    # Dream
    dreams = brain.dream(5)
    test("brain.dream works", isinstance(dreams, int))

    # Query
    q = brain.query("cat")
    test("brain.query works", "words" in q)

    # Cycle
    c = brain.cycle()
    test("brain.cycle works", "cycle" in c)

    # Stats
    s = brain.full_stats()
    test("brain.full_stats works", "learner" in s)

except Exception as e:
    test("brain functional test", False, str(e)[:100])

# ============================================================
# SUMMARY
# ============================================================
print("\n" + "=" * 60)
total = PASS + FAIL
print(f"RESULTS: {PASS}/{total} passed, {FAIL} failed, {WARN} warnings")

if FAIL == 0 and WARN == 0:
    print("ALL CLEAR — system ready")
elif FAIL == 0:
    print(f"NO FAILURES but {WARN} warnings — review above")
else:
    print(f"ATTENTION: {FAIL} failures need fixing")

print("\n=== CRITICAL FIXES NEEDED ===")
if WARN > 0 or FAIL > 0:
    print("  1. Integrate ALL modules into logos_brain.py")
    print("  2. Encrypt state files with crypto_core")
    print("  3. Enforce will_core.allow() in critical paths")
    print("  4. Unify axioms between PhaseSpace and CreatorIdentity")
    print("  5. Add validate_dream() call in dream_core")
    print("  6. Fix symbolizer to support digits + cyrillic")
    print("  7. Add missing commands to run.py")

print("=" * 60)
