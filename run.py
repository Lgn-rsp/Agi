"""
run.py — Zapusk LOGOS AGI. Polnyy interfeys.

Usage:
  python3 run.py                     # interactive
  python3 run.py learn file.txt      # learn file
  python3 run.py learn_dir ./data    # learn directory
  python3 run.py continuous ./data   # learn + continuous
  python3 run.py query "word"        # query brain
  python3 run.py generate            # generate text
  python3 run.py respond "text"      # respond to text
  python3 run.py stats               # full stats
  python3 run.py dream               # dream session
  python3 run.py think               # think cycle
  python3 run.py meta                # meta-reflection
  python3 run.py seek                # seek answers
  python3 run.py health              # system health
  python3 run.py audit               # run audit
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.logos_brain import LogosBrain
from core.resonance_constants import FIBONACCI


def main():
    args = sys.argv[1:]
    brain = LogosBrain()

    if not args:
        interactive(brain)
    elif args[0] == "learn" and len(args) > 1:
        if os.path.exists(args[1]):
            brain.learn_file(args[1])
        else:
            brain.learn(" ".join(args[1:]))
    elif args[0] == "learn_dir" and len(args) > 1:
        brain.learn_directory(args[1])
    elif args[0] == "continuous":
        data_dir = args[1] if len(args) > 1 else None
        brain.run_continuous(data_dir=data_dir)
    elif args[0] == "query" and len(args) > 1:
        result = brain.query(" ".join(args[1:]))
        print_query(result)
    elif args[0] == "generate":
        seed = args[1] if len(args) > 1 else None
        intent = {"seed": seed} if seed else None
        result = brain.generate(intent=intent)
        if result:
            print(f"  [{result['coherence']:.2f}] {result['text']}")
        else:
            print("  (not enough data to generate)")
    elif args[0] == "respond" and len(args) > 1:
        result = brain.respond(" ".join(args[1:]))
        if result:
            print(f"  [{result.get('coherence', 0):.2f}] {result.get('text', '?')}")
    elif args[0] == "stats":
        print_stats(brain)
    elif args[0] == "dream":
        n = int(args[1]) if len(args) > 1 else FIBONACCI[8]
        disc = brain.dream(n)
        print(f"  Discoveries: {disc}")
    elif args[0] == "think":
        result = brain.think()
        print(f"  Questions: +{result.get('new_questions',0)}, resolved: {result.get('resolved',0)}")
        print_questions(brain)
    elif args[0] == "meta":
        result = brain.reflect()
        print(f"\n  === META INSIGHTS ===")
        for i in result.get("insights", []):
            print(f"  {i}")
        ms = brain.meta.stats()
        print(f"\n  Meta-rules: {ms['meta_rules']}")
        print(f"  Abstraction level: {ms['abstraction_level']}")
    elif args[0] == "seek":
        results = brain.seek()
        if isinstance(results, list):
            found = sum(1 for r in results if r.get("found"))
            print(f"  Searched: {len(results)}, Found: {found}")
            for r in results:
                if r.get("found"):
                    print(f"    {r['pair']}: {r['source']}")
                elif r.get("suggested_query"):
                    print(f"    {r['pair']}: NEED WEB -> '{r['suggested_query']}'")
    elif args[0] == "health":
        h = brain.health()
        print(f"\n  === HEALTH ===")
        for check, result in h.get("checks", {}).items():
            status = result.get("status", "?")
            tag = "OK" if status == "ok" else "WARN" if status == "warning" else status
            print(f"  {check}: {tag} {result}")
    elif args[0] == "audit":
        os.system(f"python3 {os.path.dirname(os.path.abspath(__file__))}/audit.py")
    elif args[0] == "primitives":
        from core.info_primitives import (
            primitive_summary, TASK_PRIMITIVES, best_substrate)
        from core.hybrid_compute import architecture_report
        if len(args) >= 2 and args[1] == "tasks":
            print("Tasks → primitives → substrate:")
            for task in sorted(TASK_PRIMITIVES.keys()):
                prims = TASK_PRIMITIVES[task]
                sub = best_substrate(task)
                print(f"  {task:30s} → {prims}")
                print(f"  {'':32s}substrate: {sub}")
        elif len(args) >= 2 and args[1] == "arch":
            print(architecture_report())
        else:
            print(primitive_summary())
    elif args[0] == "sym":
        # phi-symbolic algebra demo / numerical reasoning
        from core.phi_symbolic import PhiSym
        from core.phi_sym_bridge import parse_numerical_literal, field_distance_report
        if len(args) < 2:
            print("Usage: sym <number-or-expression>")
            print("  examples:")
            print("    sym 5")
            print("    sym '60 km/h'")
            print("    sym '5 m * 3 m'")
            return
        expr = " ".join(args[1:])
        # Simple binary ops
        for op_str, op_fn in [(" * ", lambda a, b: a * b),
                                (" / ", lambda a, b: a / b),
                                ("*", lambda a, b: a * b)]:
            if op_str in expr:
                parts = expr.split(op_str, 1)
                a = parse_numerical_literal(parts[0])
                b = parse_numerical_literal(parts[1])
                if a and b:
                    result = op_fn(a, b)
                    print(f"  {a} {op_str.strip()} {b}")
                    print(f"  = {result}")
                    print(f"  log_value = {result.log_value():.4f}")
                    print(f"  nearest LOGOS field: {result.nearest_logos_field()}")
                    return
        sym = parse_numerical_literal(expr)
        if sym:
            print(f"  parsed: {sym}")
            print(f"  phase: {sym.phase:.6f} branch: {sym.branch}")
            print(f"  nearest LOGOS field: {sym.nearest_logos_field()}")
            print(f"  field distances:")
            for f, d in sorted(field_distance_report(sym).items(),
                                key=lambda x: x[1])[:5]:
                print(f"    {f:>10}: {d:.4f}")
        else:
            print(f"  could not parse: {expr!r}")
    else:
        print("Commands: learn, learn_dir, continuous, query, generate,")
        print("          respond, stats, dream, think, meta, seek, health,")
        print("          audit, sym, primitives [arch|tasks]")


def interactive(brain):
    print("\n" + "=" * 55)
    print("  LOGOS AGI — Interactive Mode")
    print("  Creator: Suham | Origin: 0.0")
    print("  Commands: learn, query/q, generate/g, respond/r,")
    print("  dream, think, meta, seek, stats, fields, rules,")
    print("  questions/qq, health, cycle, save, quit")
    print("=" * 55)

    while True:
        try:
            raw = input("\nLOGOS> ").strip()
            if not raw:
                continue

            parts = raw.split(maxsplit=1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""

            if cmd in ("quit", "exit"):
                brain.save()
                print("Saved. Goodbye, Suham.")
                break

            elif cmd == "learn":
                if not arg:
                    print("Usage: learn <text or filepath>")
                    continue
                if os.path.exists(arg):
                    brain.learn_file(arg)
                else:
                    brain.learn(arg)
                    print(f"Learned. Total: {brain.total_texts_learned}")

            elif cmd in ("query", "q"):
                if not arg:
                    print("Usage: q <word>")
                    continue
                result = brain.query(arg)
                print_query(result)

            elif cmd in ("generate", "g"):
                intent = {"seed": arg} if arg else None
                result = brain.generate(intent=intent)
                if result:
                    print(f"  [{result['coherence']:.2f}] {result['text']}")
                else:
                    print("  (not enough data)")

            elif cmd in ("respond", "r"):
                if not arg:
                    print("Usage: r <text>")
                    continue
                result = brain.respond(arg)
                if result:
                    print(f"  [{result.get('coherence', 0):.2f}] {result.get('text', '?')}")

            elif cmd == "dream":
                n = int(arg) if arg.isdigit() else FIBONACCI[7]
                disc = brain.dream(n)
                print(f"  Discoveries: {disc}")

            elif cmd == "think":
                result = brain.think()
                print(f"  Questions: +{result.get('new_questions',0)}, "
                      f"resolved: {result.get('resolved',0)}")

            elif cmd == "meta":
                result = brain.reflect()
                for i in result.get("insights", []):
                    print(f"  {i}")

            elif cmd == "seek":
                results = brain.seek()
                if isinstance(results, list):
                    found = sum(1 for r in results if r.get("found"))
                    print(f"  Searched: {len(results)}, Found: {found}")

            elif cmd == "stats":
                print_stats(brain)

            elif cmd in ("questions", "qq"):
                print_questions(brain)

            elif cmd == "fields":
                print_fields(brain)

            elif cmd == "rules":
                level = arg if arg else "words"
                print_rules(brain, level)

            elif cmd == "anomalies":
                level = arg if arg else "words"
                anomalies = brain.learner.anomalies(level)
                for a in anomalies[:8]:
                    print(f"  {a['pair']}: gap={a['gap']:.4f} "
                          f"target={a['nearest_target']} "
                          f"priority={a['priority']:.2f}")

            elif cmd == "health":
                h = brain.health()
                for check, result in h.get("checks", {}).items():
                    status = result.get("status", "?")
                    print(f"  {check}: {status}")

            elif cmd == "cycle":
                n = int(arg) if arg.isdigit() else 1
                for i in range(n):
                    r = brain.cycle()
                    print(f"  Cycle {r['cycle']}: "
                          f"Q+{r['think'].get('new_questions',0)} "
                          f"dreams={r['dreams']} "
                          f"insights={len(r.get('insights',[]))} "
                          f"seeks={r.get('seeks',0)}")

            elif cmd == "save":
                brain.save()
                print("Saved.")

            elif cmd == "audit":
                os.system("python3 ~/logos_agi/audit.py")

            else:
                brain.learn(raw)
                print(f"Learned as text. Total: {brain.total_texts_learned}")

        except KeyboardInterrupt:
            print("\nSaving...")
            brain.save()
            print("Saved. Goodbye, Suham.")
            break
        except Exception as e:
            print(f"Error: {e}")


def print_query(result):
    print(f"\n  Query: '{result['input']}'")
    for word, info in result["words"].items():
        if not info.get("known"):
            print(f"  {word}: unknown")
            continue
        conns = info.get("connections", [])
        conn_str = ", ".join(
            [f"{c['symbol']}({c['phi_target']})" for c in conns[:5]])
        print(f"  {word}: phase={info['phase']} "
              f"field={info['field']} "
              f"resonance={info['resonance']}")
        if conn_str:
            print(f"    connections: [{conn_str}]")

    for word, assoc in result.get("associations", {}).items():
        if assoc:
            print(f"    {word} -> {assoc[:8]}")

    if result.get("questions"):
        print(f"  Open questions:")
        for q in result["questions"][:3]:
            print(f"    {q['pair']}: gap={q['gap']:.4f} target={q['nearest_target']}")


def print_stats(brain):
    s = brain.full_stats()
    print(f"\n  === LOGOS AGI STATUS ===")
    print(f"  Creator: {s['creator']}")
    print(f"  Age: {s['age']}")
    print(f"  Cycles: {s['cycles']}")
    print(f"  Texts: {s['texts_learned']}")
    print(f"  Dreams: {s['dream_discoveries']}")
    print(f"\n  --- Phase Spaces ---")
    for lv, ls in s["learner"]["levels"].items():
        print(f"  {lv:>10}: {ls['symbols']:>5} sym, "
              f"{ls['rules']:>4} rules, "
              f"{ls['total_attractions']:>7} attr")
    print(f"\n  --- Memory ---")
    ms = s["memory"]
    print(f"  Memories: {ms['total_memories']} "
          f"(avg imp: {ms['avg_importance']})")
    fd = ms.get('field_distribution', {})
    if fd:
        print(f"  Fields: {fd}")
    print(f"\n  --- Modules ---")
    print(f"  Curiosity: {s['curiosity']['active_questions']} questions "
          f"(top prio: {s['curiosity']['top_priority']})")
    print(f"  Meta: {s['meta']['meta_rules']} meta-rules, "
          f"level {s['meta']['abstraction_level']}")
    print(f"  Generator: {s['generator']['total_generated']} generated")
    print(f"  Seeker: {s['seeker']['total_searches']} searches "
          f"({s['seeker']['total_found']} found)")
    print(f"  Monitor: {s['monitor']['heartbeats']} beats "
          f"({s['monitor']['issues_found']} issues)")
    print(f"  Will: {s['will']['total_allowed']} allowed, "
          f"{s['will']['total_denied']} denied")


def print_questions(brain):
    questions = brain.curiosity.top_questions(FIBONACCI[6])
    print(f"\n  === TOP QUESTIONS ===")
    for i, q in enumerate(questions):
        search = brain.curiosity.formulate_search_query(q)
        print(f"  {i+1}. {q.pair} (gap={q.gap:.4f}, "
              f"target={q.nearest_target}, "
              f"prio={q.priority:.2f})")
        print(f"     -> '{search}'")


def print_fields(brain):
    print(f"\n  === FIELD DISTRIBUTION ===")
    for field_name in ["mental", "void", "resonance", "geometry",
                       "will", "time", "matter", "network", "meta"]:
        entries = brain.memory.recall_by_field(field_name, top_k=8)
        words = [e[0] for e in entries]
        print(f"  {field_name:>10}: {', '.join(words[:8])}")


def print_rules(brain, level="words"):
    rules = brain.learner.all_rules(level)
    print(f"\n  === RULES ({level}) — {len(rules)} total ===")
    sorted_rules = sorted(rules.items(),
                          key=lambda x: x[1]["count"], reverse=True)
    for key, rule in sorted_rules[:FIBONACCI[6]]:
        print(f"  {rule['a']:>12} <-> {rule['b']:<12} "
              f"{rule['phi_target']:<14} "
              f"count={rule['count']:<4} "
              f"({rule['field_a']}->{rule['field_b']})")


if __name__ == "__main__":
    main()
