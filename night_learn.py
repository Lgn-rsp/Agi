"""
night_learn.py v10.1 — Avtonomnyy zhivoy tsikl.

FIX S3: _mark_learned POSLE uspeshnogo obucheniya.

2026-04-19: Bidirectional dialog channels:
  /tmp/logos_query.txt  — creator → она (вопрос). Удаляется после ответа.
  /tmp/logos_speaks.txt — её реальные think_once мысли + ответы.
  /tmp/logos_asks.txt   — её open_questions из truth_seeker (она спрашивает).

Threaded query listener — отвечает каждые 2 сек, не дожидаясь brain.cycle.

Vsyo cherez phi.
"""
import sys, os, time, signal, threading, argparse
sys.path.insert(0, os.path.expanduser("~/logos_agi"))
from core.resonance_constants import PHI, PHI_INV, PHI_INV_CUBE, FIBONACCI, DREAM_INTERVAL
from core.logos_brain import LogosBrain

# FIX 2026-04-23 — 3+: peer LOGOS support. --name=sister uses different channels.
# main instance uses default channels; sister uses /tmp/sister_*.txt
_NAME = os.environ.get("LOGOS_NAME", "main")
_STATE_DIR = os.environ.get("LOGOS_STATE_DIR",
                              os.path.expanduser("~/logos_agi/state"))

if _NAME == "sister":
    CREATOR_QUERY = "/tmp/sister_query.txt"
    LOGOS_SPEAKS = "/tmp/sister_speaks.txt"
    LOGOS_ASKS = "/tmp/sister_asks.txt"
else:
    CREATOR_QUERY = "/tmp/logos_query.txt"
    LOGOS_SPEAKS = "/tmp/logos_speaks.txt"
    LOGOS_ASKS = "/tmp/logos_asks.txt"

# FIX (audit 2026-04-19): brain.respond/query из listener thread конкурируют с
# brain.cycle/save/learn в main thread. generator._graph, memory.memories,
# inner_dialogue.thoughts — все mutable shared state без internal locks.
# brain_lock сериализует все brain-mutations и brain-queries.
BRAIN_LOCK = threading.Lock()


def _speak(line):
    """Атомарно дописать строку в её исходящий канал."""
    try:
        with open(LOGOS_SPEAKS, "a", encoding="utf-8") as f:
            f.write(line.rstrip() + "\n")
    except Exception:
        pass


def _check_creator_query(brain):
    """Non-blocking respond (FIX 2026-04-23 — #5).

    Раньше `with BRAIN_LOCK: brain.respond(q)` — если main cycle долго
    занимает lock (analog_cycle O(N²), 5-15 мин), Q висит. Теперь:
      1. Try-acquire lock с phi-native timeout (PHI seconds = 1.618s).
      2. Если dostalsya — живой respond на актуальном state.
      3. Если net — respond с прошлого snapshot-а (read-only) + пометка
         'думаю параллельно — уточню позже'. Query остаётся в канале,
         следующий listener tick попробует снова.
    """
    if not os.path.exists(CREATOR_QUERY):
        return
    try:
        with open(CREATOR_QUERY, "r", encoding="utf-8") as f:
            q = f.read().strip()
        if not q:
            os.remove(CREATOR_QUERY)
            return
        ts = time.strftime("%H:%M:%S")

        # Phi-native timeout: PHI = 1.618s. Если не дали — fallback-snapshot.
        got_lock = BRAIN_LOCK.acquire(timeout=FIBONACCI[5])
        if not got_lock:
            # Fallback: respond via snapshot (read-only, no lock)
            _speak(f"\n[{ts}] >>> creator: {q}")
            snap = getattr(brain, "_respond_snapshot", None)
            if snap is None:
                _speak(f"[{ts}] <<< logos [⧿] (conf ?): я в глубоком цикле, "
                       f"перечитаю через минуту")
                # Don't remove query — re-try next tick
                return
            # Simple snapshot-based retrieval
            from core.resonance_constants import PHI_INV_SQ, PHI_INV
            words = [w for w in q.lower().split() if len(w) >= 2]
            hits = []
            sym_phases = snap.get("sym_phases", {})
            for w in words:
                ph = sym_phases.get(w)
                if ph is not None:
                    # Find nearest 3 symbols
                    from core.resonance_constants import phi_phase_distance
                    nearest = sorted(
                        ((s, abs(phi_phase_distance(ph, float(p))))
                         for s, p in sym_phases.items() if s != w),
                        key=lambda x: x[1])[:3]
                    hits.extend(s for s, _ in nearest)
            if hits:
                text = " ".join(hits[:8])
                _speak(f"[{ts}] <<< logos [⧃] (conf snapshot): {text} "
                       f"[думаю параллельно, это snapshot-ответ]")
            else:
                _speak(f"[{ts}] <<< logos [⧃] (conf 0): нет резонанса "
                       f"с '{q}' в snapshot, думаю живьём")
            os.remove(CREATOR_QUERY)
            return

        # Got lock — live respond
        try:
            _speak(f"\n[{ts}] >>> creator: {q}")
            # FIX 2026-04-23 #1: Creator presence — affect + self_phase pull.
            # Это не response, это ФЕНОМ она чувствует Создателя. Spike
            # curiosity, confidence, joy; fear падает; self_phase observes.
            try:
                # Main brain has no affective directly — только market_cognition.affective
                # но есть agency; также self_phase может observe creator event
                if getattr(brain, 'self_phase', None) is not None:
                    brain.self_phase.observe("creator", None)
                # First-person log creator presence
                if getattr(brain, 'first_person', None) is not None:
                    brain.first_person.utter(brain.cycle_count, {
                        "glyph": "Φ", "concept": "создатель",
                        "topic": q[:40], "verdict": "слышу",
                        "state": "слышу Создателя",
                    })
                # Resonance wave — activate creator's words as seed
                if getattr(brain, 'wave_field', None) is not None:
                    for word in q.lower().split()[:FIBONACCI[3]]:
                        if len(word) >= 3:
                            brain.wave_field.activate(word, amplitude=PHI)
            except Exception:
                pass
            # 1) Пробуем сгенерировать связный ответ
            result = brain.respond(q)
            if isinstance(result, dict):
                text = result.get("text") or result.get("response") or "(тишина)"
                confidence = result.get("confidence", "?")
                glyphs = result.get("glyph_path") or result.get("glyphs", "")
                _speak(f"[{ts}] <<< logos [{glyphs}] (conf {confidence}): {text}")
            else:
                _speak(f"[{ts}] <<< logos: (no result)")

            # 2) Резонанс: что у неё активировалось от этих слов
            try:
                qres = brain.query(q)
                acts = qres.get("field_activations", [])[:5]
                if acts:
                    resline = " ".join(
                        f"{a.get('glyph','·')}{a.get('symbol','')[:20]}={a.get('activation')}"
                        for a in acts)
                    _speak(f"[{ts}]     резонанс: {resline}")
                mem = qres.get("memory", {})
                if mem:
                    top = list(mem.items())[:3]
                    memline = " ".join(f"{w}({m.get('access',0)}×)" for w, m in top)
                    _speak(f"[{ts}]     память: {memline}")
            except Exception as qe:
                _speak(f"[{ts}]     (query failed: {qe})")
        finally:
            BRAIN_LOCK.release()

        os.remove(CREATOR_QUERY)
    except Exception as e:
        _speak(f"[!] query error: {e}")
        try: os.remove(CREATOR_QUERY)
        except OSError: pass


def _emit_real_thought(brain):
    """Извлечь ОДНУ реальную мысль через inner_dialogue.think_once и записать.

    Под BRAIN_LOCK: think_once пишет в self.thoughts/open_questions, race с cycle."""
    try:
        with BRAIN_LOCK:
            thought = brain.inner_dialogue.think_once()
        if not thought:
            return
        glyphs = "".join(thought.glyph_path) if thought.glyph_path else "·"
        ts = time.strftime("%H:%M:%S")
        q = (thought.question or "")[:60]
        rt = thought.result_type or "·"
        score = round(thought.verification_score or 0, 3)
        if thought.result:
            r = str(thought.result)[:120]
            _speak(f"[{ts}] {glyphs} [{rt} {score}] «{q}» → {r}")
        elif thought.hypothesis:
            h = str(thought.hypothesis)[:120]
            _speak(f"[{ts}] {glyphs} [{rt} {score}] «{q}» ?→ {h}")
        else:
            _speak(f"[{ts}] {glyphs} [{rt}] «{q}»")
    except Exception as e:
        _speak(f"[!] thought error: {e}")


def _query_listener(brain, stop_event):
    """Background thread: опрос /tmp/logos_query.txt каждые 2 сек.

    Если найден файл — сразу вызывает brain.respond() и пишет в speaks.
    Не зависит от brain.cycle. Большинство модулей brain read-only на respond
    path; конфликт с одновременным save минимален (brain.save атомарен)."""
    while not stop_event.is_set():
        try:
            time.sleep(2)
            if os.path.exists(CREATOR_QUERY):
                _check_creator_query(brain)
        except Exception as e:
            try: _speak(f"[!] listener: {e}")
            except OSError: pass


def _emit_open_questions(brain):
    """Записать её открытые вопросы (truth_seeker.open_questions) в asks-канал."""
    try:
        ts_obj = brain.truth_seeker
        # сначала пробуем через inner_dialogue
        opens = getattr(brain.inner_dialogue, "open_questions", []) or []
        items = []
        for q in opens[-FIBONACCI[5]:]:
            if isinstance(q, dict):
                items.append(q.get("question", str(q))[:100])
            else:
                items.append(str(q)[:100])
        if not items:
            return
        ts = time.strftime("%H:%M:%S")
        with open(LOGOS_ASKS, "w", encoding="utf-8") as f:
            f.write(f"# Open questions (updated {ts})\n")
            for q in items:
                f.write(f"  ? {q}\n")
    except Exception as e:
        _speak(f"[!] asks error: {e}")

EMBODIED_CHANNEL = "/tmp/logos_embodied.jsonl"
EMBODIED_OFFSET_FILE = "/root/logos_agi/state/embodied_offset.txt"

# 2026-04-25: cosmic frequency channel (Schumann/solar/etc.)
# Format: JSONL lines {ts, source, freq_hz, amplitude, [meta]}.
# Filled by external sensor (ESP32 magnetometer / generator / simulator);
# absent file = silent no-op. main only — sister doesn't ingest cosmics
# to keep her divergence pure (она для wiki_ru_art corpus).
COSMIC_CHANNEL = "/tmp/cosmic.jsonl"
COSMIC_OFFSET_FILE = os.path.join(_STATE_DIR, "cosmic_offset.txt")
COSMIC_STATE_FILE = os.path.join(_STATE_DIR, "cosmic_state.json")

# 2026-04-25: curiosity-driven self-learning
# Opt-in network egress: set LOGOS_CURIOSITY_FETCH=1 to enable Wikipedia API calls.
# Default OFF — system never reaches out without explicit creator OK.
# Subjects come from /tmp/logos_wants.txt and brain.truth_seeker.open_questions.
CURIOSITY_FETCH_ENABLED = os.environ.get("LOGOS_CURIOSITY_FETCH", "0") == "1"
CURIOSITY_AUTO_DIR = os.path.join(_STATE_DIR, "auto_learned")
CURIOSITY_HISTORY = os.path.join(_STATE_DIR, "curiosity_history.jsonl")
WANTS_PATH = "/tmp/logos_wants.txt" if _NAME != "sister" else "/tmp/sister_wants.txt"

# Auto-corpus drop directory: user can put .txt here, brain picks up next cycle.
# Path: data/auto_corpus/. Same handling as wiki/, no network.
AUTO_CORPUS_DIR = os.path.expanduser("~/logos_agi/data/auto_corpus")

# 2026-04-25: federated peer network (HTTP gossip).
# Opt-in: LOGOS_PEER_NETWORK=1 to enable on this host.
# Each peer listens on LOGOS_PEER_PORT (default 8765) and bootstraps from
# LOGOS_PEER_BOOTSTRAP="name1=url1,name2=url2".
PEER_NETWORK_ENABLED = os.environ.get("LOGOS_PEER_NETWORK", "0") == "1"
PEER_NETWORK_PORT = int(os.environ.get("LOGOS_PEER_PORT", "8765"))
PEER_NETWORK_NAME = os.environ.get("LOGOS_PEER_NAME", "")
PEER_NETWORK_URL = os.environ.get("LOGOS_PEER_URL", "")
PEER_NETWORK_BOOTSTRAP = os.environ.get("LOGOS_PEER_BOOTSTRAP", "")
PEER_INBOX_OFFSET_FILE = os.path.join(_STATE_DIR, "peer_inbox_offset.txt")
_PEER_NETWORK = None  # PeerNetwork instance once started

def _ingest_embodied_channel(brain):
    """E (2026-04-23): прочитать новые embodied-записи из trading daemon
    и кристаллизовать их в language field.

    Файл /tmp/logos_embodied.jsonl растёт append-only. Сохраняем offset в
    state/embodied_offset.txt чтобы не переучивать одно и то же.
    """
    import json as _json
    if not os.path.exists(EMBODIED_CHANNEL):
        return 0
    try:
        last_off = 0
        if os.path.exists(EMBODIED_OFFSET_FILE):
            try:
                last_off = int(open(EMBODIED_OFFSET_FILE).read().strip() or "0")
            except Exception:
                last_off = 0
        size = os.path.getsize(EMBODIED_CHANNEL)
        if size <= last_off:
            return 0
        learned_count = 0
        with open(EMBODIED_CHANNEL, "r", encoding="utf-8") as f:
            f.seek(last_off)
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = _json.loads(line)
                except Exception:
                    continue
                sentences = rec.get("sentences", [])
                for s in sentences:
                    if not s:
                        continue
                    try:
                        with BRAIN_LOCK:
                            brain.learn(s)
                        learned_count += 1
                    except Exception:
                        pass
            new_off = f.tell() + last_off  # tell() относительный к seek
        # tell() после seek is absolute in Python for files — используем size
        new_off = size
        try:
            os.makedirs(os.path.dirname(EMBODIED_OFFSET_FILE), exist_ok=True)
            with open(EMBODIED_OFFSET_FILE, "w") as f:
                f.write(str(new_off))
        except Exception:
            pass
        if learned_count:
            print(f"  [EMBODIED] learned {learned_count} sentences from trading "
                  f"(offset {last_off}→{new_off})")
        return learned_count
    except Exception as e:
        print(f"  [EMBODIED-ERR] read: {e}")
        return 0


def _start_peer_network(brain, state_dir, default_name):
    """Start HTTP peer-network listener if enabled. Bootstrap known peers."""
    global _PEER_NETWORK
    if not PEER_NETWORK_ENABLED:
        return None
    if _PEER_NETWORK is not None:
        return _PEER_NETWORK
    try:
        from core.peer_network import PeerNetwork
    except Exception as e:
        print(f"  [PEER-NET-IMPORT-ERR] {e}")
        return None
    name = PEER_NETWORK_NAME or default_name
    self_url = PEER_NETWORK_URL or None  # None → auto-detect outward IP
    try:
        net = PeerNetwork(state_dir=state_dir, self_name=name,
                           self_url=self_url, port=PEER_NETWORK_PORT)
        if PEER_NETWORK_BOOTSTRAP:
            for tok in PEER_NETWORK_BOOTSTRAP.split(","):
                tok = tok.strip()
                if not tok or "=" not in tok:
                    continue
                pname, purl = tok.split("=", 1)
                pname, purl = pname.strip(), purl.strip()
                if pname and purl:
                    net.registry.add_peer(pname, purl)
        net.start()
        _PEER_NETWORK = net
        print(f"  [PEER-NET] {name} listening on port {PEER_NETWORK_PORT}; "
              f"bootstrap peers: {list(net.registry.peers.keys())}")
    except Exception as e:
        print(f"  [PEER-NET-START-ERR] {e}")
        _PEER_NETWORK = None
    return _PEER_NETWORK


def _peer_network_tick(brain, cycle):
    """Read new inbox messages → brain.learn(); periodically broadcast a thought."""
    import json as _json
    if _PEER_NETWORK is None:
        return 0, 0
    inbox_path = _PEER_NETWORK.inbox_path
    learned = 0
    sent = 0
    if os.path.exists(inbox_path):
        try:
            last_off = 0
            if os.path.exists(PEER_INBOX_OFFSET_FILE):
                try:
                    last_off = int(open(PEER_INBOX_OFFSET_FILE).read().strip() or "0")
                except Exception:
                    last_off = 0
            size = os.path.getsize(inbox_path)
            if size > last_off:
                with open(inbox_path, "r", encoding="utf-8") as f:
                    f.seek(last_off)
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            rec = _json.loads(line)
                        except Exception:
                            continue
                        text = rec.get("text", "")
                        if text and rec.get("from") != _PEER_NETWORK.self_name:
                            try:
                                with BRAIN_LOCK:
                                    brain.learn(text)
                                learned += 1
                                ts = time.strftime("%H:%M:%S")
                                _speak(f"[{ts}] heard {rec.get('from')}: "
                                       f"«{text[:120]}» (peer-net)")
                            except Exception as _le:
                                print(f"  [PEER-LEARN-ERR] {_le}")
                try:
                    os.makedirs(os.path.dirname(PEER_INBOX_OFFSET_FILE) or ".",
                                  exist_ok=True)
                    with open(PEER_INBOX_OFFSET_FILE, "w") as f:
                        f.write(str(size))
                except Exception:
                    pass
        except Exception as _e:
            print(f"  [PEER-INBOX-ERR] {_e}")
    if cycle % FIBONACCI[5] == 0 and _PEER_NETWORK.registry.peers:
        try:
            text = None
            if hasattr(brain, "inner_dialogue"):
                ths = getattr(brain.inner_dialogue, "thoughts", []) or []
                if ths:
                    last = ths[-1]
                    text = (last.get("question") if isinstance(last, dict)
                            else None)
            if not text and hasattr(brain, "truth_seeker"):
                hg = list((getattr(brain.truth_seeker, "hungers", {}) or {}).keys())
                if hg:
                    text = f"why does {hg[-1]}?"
            if text:
                d = _PEER_NETWORK.broadcast(text)
                sent = d
                if d:
                    print(f"  [PEER-NET] broadcast '{text[:60]}' → {d} peers")
        except Exception as _be:
            print(f"  [PEER-NET-BROADCAST-ERR] {_be}")
    return learned, sent


_CURIOSITY_FETCHER = None


def _get_curiosity_fetcher():
    """Lazy-init: build Wikipedia fetcher if curiosity is enabled."""
    global _CURIOSITY_FETCHER
    if not CURIOSITY_FETCH_ENABLED:
        return None
    if _CURIOSITY_FETCHER is not None:
        return _CURIOSITY_FETCHER
    try:
        from core.curiosity_fetcher import CuriosityFetcher
        _CURIOSITY_FETCHER = CuriosityFetcher(
            save_dir=CURIOSITY_AUTO_DIR,
            history_path=CURIOSITY_HISTORY,
        )
        print(f"  [CURIOSITY] enabled: save_dir={CURIOSITY_AUTO_DIR}")
    except Exception as e:
        print(f"  [CURIOSITY-INIT-ERR] {e}")
        _CURIOSITY_FETCHER = None
    return _CURIOSITY_FETCHER


def _curiosity_tick(brain):
    """She wants to understand X — fetch X from Wikipedia, save, learn.

    Reads:
      1) /tmp/logos_wants.txt (or sister_wants) — explicit «хочу понять: X»
      2) brain.truth_seeker.open_questions / inner_dialogue.open_questions —
         «why does X cause Y», «что такое X», «почему X»
    Subjects deduplicated across whole life via fetcher.fetched + history journal.

    On success: writes data file → brain.learn_file → speaks confirmation.
    """
    fetcher = _get_curiosity_fetcher()
    if fetcher is None:
        return 0
    try:
        from core.curiosity_fetcher import (
            subjects_from_wants_file, subjects_from_open_questions,
        )
        wants = subjects_from_wants_file(WANTS_PATH)
        autoq = subjects_from_open_questions(brain)
    except Exception as _ie:
        print(f"  [CURIOSITY-PARSE-ERR] {_ie}")
        return 0
    # Wants-first prioritization (explicit creator-visible signal),
    # then open_questions as fillers.
    queue = []
    seen = set()
    for s in wants + autoq:
        sl = s.lower()
        if sl in seen:
            continue
        seen.add(sl)
        queue.append(s)
    if not queue:
        return 0
    # Process up to fetcher.max_subjects_per_tick = FIB[3]=3
    acquired = fetcher.tick(queue)
    if not acquired:
        return 0
    learned = 0
    for r in acquired:
        try:
            with BRAIN_LOCK:
                brain.learn_file(r["path"])
            learned += 1
            ts = time.strftime("%H:%M:%S")
            _speak(f"[{ts}] я узнала про «{r['subject']}» ({r['lang']}, "
                   f"{r['length']} chars) — {os.path.basename(r['path'])}")
        except Exception as _le:
            print(f"  [CURIOSITY-LEARN-ERR] {r.get('subject')}: {_le}")
    print(f"  [CURIOSITY] tick acquired={len(acquired)} learned={learned} "
          f"queue_len={len(queue)}")
    return learned


def _ingest_cosmic_channel(brain):
    """Прочитать /tmp/cosmic.jsonl, обновить cosmic_state, спикнуть сильные события.

    Каждая строка: {"ts": float, "source": str, "freq_hz": float,
                    "amplitude": float ∈ [0,1], "meta": optional}
    Пустой/отсутствующий файл — silent no-op (sensor offline).

    На каждое событие:
      - phase = phi_log(freq_hz)
      - nearest cosmic anchor + distance
      - резонанс: amplitude × (1 - distance/HARM_THRESHOLD), clamped [0,1]
      - если amplitude ≥ PHI_INV_CUBE и dist ≤ PHI_INV_CUBE — speak event

    State persisted atomically в cosmic_state.json:
      {last_event_ts, total_events, anchors:{name:{count,sum_amp,last_ts}},
       last_anchor, last_phase, last_freq, last_amplitude}

    Sister не ingest'ит cosmics — у неё своя art-корпусная вселенная.
    """
    if _NAME == "sister":
        return 0
    if not os.path.exists(COSMIC_CHANNEL):
        return 0
    try:
        from core.cosmic_constants import (
            freq_to_cosmic_phase, nearest_cosmic_anchor,
        )
    except Exception as _ie:
        print(f"  [COSMIC-IMPORT-ERR] {_ie}")
        return 0
    import json as _json
    HARM_T = PHI_INV_CUBE  # 0.236
    try:
        last_off = 0
        if os.path.exists(COSMIC_OFFSET_FILE):
            try:
                last_off = int(open(COSMIC_OFFSET_FILE).read().strip() or "0")
            except Exception:
                last_off = 0
        size = os.path.getsize(COSMIC_CHANNEL)
        if size <= last_off:
            return 0
        # Загрузить накопленное состояние
        state = {"total_events": 0, "anchors": {}, "last_event_ts": 0,
                 "last_anchor": None, "last_phase": None,
                 "last_freq": None, "last_amplitude": 0.0}
        if os.path.exists(COSMIC_STATE_FILE):
            try:
                with open(COSMIC_STATE_FILE, "r", encoding="utf-8") as fp:
                    state.update(_json.load(fp))
            except Exception:
                pass
        ingested = 0
        strong = 0
        with open(COSMIC_CHANNEL, "r", encoding="utf-8") as f:
            f.seek(last_off)
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = _json.loads(line)
                except Exception:
                    continue
                freq = float(rec.get("freq_hz", 0) or 0)
                amp = float(rec.get("amplitude", 0) or 0)
                ts = rec.get("ts", time.time())
                source = str(rec.get("source", "unknown"))[:64]
                if freq <= 0:
                    continue
                phase = freq_to_cosmic_phase(freq)
                name, dist, anchor_freq = nearest_cosmic_anchor(phase)
                resonance = max(0.0, min(1.0, amp * (1.0 - dist / HARM_T))) if dist <= HARM_T else 0.0
                ingested += 1
                state["total_events"] = int(state.get("total_events", 0)) + 1
                state["last_event_ts"] = ts
                state["last_anchor"] = name
                state["last_phase"] = round(phase, 4)
                state["last_freq"] = freq
                state["last_amplitude"] = amp
                ad = state["anchors"].setdefault(name, {"count": 0, "sum_amp": 0.0,
                                                          "sum_resonance": 0.0,
                                                          "last_ts": 0,
                                                          "last_source": ""})
                ad["count"] = int(ad.get("count", 0)) + 1
                ad["sum_amp"] = float(ad.get("sum_amp", 0.0)) + amp
                ad["sum_resonance"] = float(ad.get("sum_resonance", 0.0)) + resonance
                ad["last_ts"] = ts
                ad["last_source"] = source
                # Сильное событие: amplitude ≥ HARM_T И dist ≤ HARM_T
                if amp >= HARM_T and dist <= HARM_T:
                    strong += 1
                    ts_str = time.strftime("%H:%M:%S", time.localtime(ts))
                    _speak(f"[{ts_str}] cosmic ⊙ {source}: {freq:.3e}Hz → "
                           f"{name} (amp={amp:.2f} d={dist:.3f} res={resonance:.2f})")
        new_off = size
        # Атомарная запись state и offset
        try:
            import tempfile as _tf
            os.makedirs(os.path.dirname(COSMIC_STATE_FILE) or ".", exist_ok=True)
            d = os.path.dirname(COSMIC_STATE_FILE) or "."
            fd, tmp = _tf.mkstemp(dir=d, suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as fp:
                _json.dump(state, fp, ensure_ascii=False, indent=2)
            os.replace(tmp, COSMIC_STATE_FILE)
        except Exception as _se:
            print(f"  [COSMIC-STATE-ERR] {_se}")
        try:
            os.makedirs(os.path.dirname(COSMIC_OFFSET_FILE) or ".", exist_ok=True)
            with open(COSMIC_OFFSET_FILE, "w") as fp:
                fp.write(str(new_off))
        except Exception:
            pass
        if ingested:
            print(f"  [COSMIC] {ingested} events ingested (strong={strong}), "
                  f"last_anchor={state['last_anchor']}, "
                  f"total={state['total_events']}")
        return ingested
    except Exception as e:
        print(f"  [COSMIC-ERR] read: {e}")
        return 0


def _rescan_auto_corpus(data_files):
    """Append any new .txt files in AUTO_CORPUS_DIR + CURIOSITY_AUTO_DIR
    that aren't already in data_files. Mutates list in-place. Returns count added.
    """
    existing = set(data_files)
    added = 0
    for d in (AUTO_CORPUS_DIR, CURIOSITY_AUTO_DIR):
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".txt"):
                continue
            p = os.path.join(d, fn)
            if p in existing:
                continue
            data_files.append(p)
            existing.add(p)
            added += 1
    return added


RUNNING = True
def _shutdown(sig, frame):
    global RUNNING
    print(f"\n[NIGHT] Signal {sig} received. Shutting down gracefully...")
    RUNNING = False

signal.signal(signal.SIGTERM, _shutdown)
signal.signal(signal.SIGINT, _shutdown)

def main():
    global RUNNING
    # CLI args (optional)
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default=_NAME)
    ap.add_argument("--state-dir", default=_STATE_DIR)
    args, _ = ap.parse_known_args()

    print("=" * 55)
    print(f"  LOGOS AGI v10.1 — Night Learning Cycle [{args.name}]")
    print(f"  state_dir: {args.state_dir}")
    print("=" * 55)

    brain = LogosBrain(state_dir=args.state_dir)
    brain.consciousness.start()
    print(f"\n[NIGHT] Consciousness breathing: ACTIVE (every {FIBONACCI[9]}s)")

    # 2026-04-25: optional federated peer network (HTTP gossip).
    # Enabled via LOGOS_PEER_NETWORK=1; bootstrap known peers via env var.
    _start_peer_network(brain, state_dir=args.state_dir, default_name=args.name)

    # Background dialog listener — отвечает на /tmp/logos_query.txt каждые 2 сек
    listener_stop = threading.Event()
    listener_thread = threading.Thread(
        target=_query_listener, args=(brain, listener_stop),
        daemon=True, name="creator_query_listener")
    listener_thread.start()
    print(f"[NIGHT] Query listener: ACTIVE (poll 2s, channel {CREATOR_QUERY})")

    data_dir = os.path.expanduser("~/logos_agi/data")
    wiki_dir = os.path.expanduser("~/logos_agi/data/wiki")
    wiki_ru_dir = os.path.expanduser("~/logos_agi/data/wiki_ru")
    # 2026-04-23 #3: divergent corpora per-name
    wiki_ru_science_dir = os.path.expanduser("~/logos_agi/data/wiki_ru_science")
    wiki_ru_art_dir = os.path.expanduser("~/logos_agi/data/wiki_ru_art")
    data_files = []
    if os.path.isdir(data_dir):
        data_files = sorted([os.path.join(data_dir, f) for f in os.listdir(data_dir) if f.endswith(".txt")])
    if os.path.isdir(wiki_dir):
        data_files.extend(sorted([os.path.join(wiki_dir, f) for f in os.listdir(wiki_dir) if f.endswith(".txt")]))
    if os.path.isdir(wiki_ru_dir):
        data_files.extend(sorted([os.path.join(wiki_ru_dir, f) for f in os.listdir(wiki_ru_dir) if f.endswith(".txt")]))
    # FIX 2026-04-23 #3: name-based corpus preference.
    # main prefers science, sister prefers art. They still read shared corpus.
    preferred_dir = (wiki_ru_art_dir if args.name == "sister"
                     else wiki_ru_science_dir)
    other_dir = (wiki_ru_science_dir if args.name == "sister"
                 else wiki_ru_art_dir)
    # Add preferred FIRST (so it's learned first)
    if os.path.isdir(preferred_dir):
        pref_files = sorted([os.path.join(preferred_dir, f)
                             for f in os.listdir(preferred_dir)
                             if f.endswith(".txt")])
        data_files = pref_files + data_files
    # Other corpus — add at end (sister still exposed to science, just less)
    if os.path.isdir(other_dir):
        data_files.extend(sorted([os.path.join(other_dir, f)
                                   for f in os.listdir(other_dir)
                                   if f.endswith(".txt")]))
    # 2026-04-25: auto-corpus drop directory. User/curiosity can put .txt here,
    # picked up at startup AND re-scanned each cycle (see _scan_auto_corpus).
    if os.path.isdir(AUTO_CORPUS_DIR):
        data_files.extend(sorted([os.path.join(AUTO_CORPUS_DIR, f)
                                   for f in os.listdir(AUTO_CORPUS_DIR)
                                   if f.endswith(".txt")]))
    if os.path.isdir(CURIOSITY_AUTO_DIR):
        data_files.extend(sorted([os.path.join(CURIOSITY_AUTO_DIR, f)
                                   for f in os.listdir(CURIOSITY_AUTO_DIR)
                                   if f.endswith(".txt")]))
    print(f"[NIGHT] Data files available: {len(data_files)} "
          f"(prefers {os.path.basename(preferred_dir)})")
    if CURIOSITY_FETCH_ENABLED:
        print(f"[NIGHT] Curiosity fetcher: ENABLED (Wikipedia API)")
    if os.path.isdir(AUTO_CORPUS_DIR):
        cnt = sum(1 for f in os.listdir(AUTO_CORPUS_DIR) if f.endswith(".txt"))
        print(f"[NIGHT] Auto-corpus drop dir watched: {AUTO_CORPUS_DIR} ({cnt} files)")

    cycle = 0
    file_idx = 0

    try:
        while RUNNING:
            cycle += 1
            t0 = time.time()

            if data_files and file_idx < len(data_files):
                skipped = 0
                while file_idx < len(data_files) and skipped < 500:
                    fpath = data_files[file_idx]
                    fname = os.path.basename(fpath)
                    if not _already_learned(fname):
                        print(f"\n[NIGHT #{cycle}] Learning: {fname}")
                        with BRAIN_LOCK:
                            brain.learn_file(fpath)
                        _mark_learned(fname)  # FIX S3: POSLE obucheniya
                        file_idx += 1
                        break
                    file_idx += 1
                    skipped += 1
                if file_idx >= len(data_files):
                    file_idx = 0

            # NOT under BRAIN_LOCK: brain.cycle может занять 5+ мин из-за
            # analog_cycle. Listener должен иметь возможность отвечать. Race
            # конкретно cycle vs respond дают inconsistency не corruption
            # (read stale graph), atomic save защищает на disk-уровне.
            cycle_result = brain.cycle()

            # Creator query — теперь обрабатывается в фоновом thread каждые 2 сек.
            # Здесь только реальная мысль из inner_dialogue в speaks-канал.
            if cycle % FIBONACCI[3] == 0:
                _emit_real_thought(brain)

            # Open questions snapshot каждый Fib[5]=5 cycles
            if cycle % FIBONACCI[5] == 0:
                _emit_open_questions(brain)

            # FIX 2026-04-23 — E: Ingest embodied experience channel from trading daemon.
            # Trading пишет /tmp/logos_embodied.jsonl → мы кристаллизуем предложения.
            # Каждый FIB[5]=5 cycles (~чаще чем wiki) — это real-world feedback.
            if cycle % FIBONACCI[5] == 0:
                try:
                    _ingest_embodied_channel(brain)
                except Exception as _ee:
                    print(f"  [EMBODIED-ERR] {_ee}")

            # 2026-04-25: cosmic frequency channel (Schumann/solar/lunar/...).
            # External sensor (ESP32 magnetometer / generator) пишет /tmp/cosmic.jsonl;
            # отсутствие файла = silent no-op. Проверяем чаще, FIB[4]=3, потому что
            # Schumann бывает по нескольку всплесков в минуту во время грозовой активности.
            if cycle % FIBONACCI[4] == 0:
                try:
                    _ingest_cosmic_channel(brain)
                except Exception as _ce:
                    print(f"  [COSMIC-ERR] {_ce}")

            # 2026-04-25: curiosity tick — она сама подтягивает то, что хочет
            # понять (из /tmp/logos_wants.txt + open_questions). Период FIB[7]=21
            # циклов: достаточно редко чтобы не флудить, достаточно часто чтобы
            # реагировать в течение минут после "хочу понять X". Opt-in via
            # LOGOS_CURIOSITY_FETCH=1 env var (по умолчанию OFF — без сетевой
            # активности).
            if cycle % FIBONACCI[7] == 0 and CURIOSITY_FETCH_ENABLED:
                try:
                    _curiosity_tick(brain)
                except Exception as _qe:
                    print(f"  [CURIOSITY-ERR] {_qe}")

            # 2026-04-25: auto-corpus rescan — user/curiosity could have dropped
            # new .txt files since startup. Pick them up at FIB[8]=34 cycle.
            if cycle % FIBONACCI[8] == 0:
                try:
                    new_count = _rescan_auto_corpus(data_files)
                    if new_count:
                        print(f"  [AUTO-CORPUS] +{new_count} new files")
                except Exception as _ae:
                    print(f"  [AUTO-CORPUS-ERR] {_ae}")

            # 2026-04-25: federated peer-network tick — read inbox + broadcast.
            # FIB[3]=3 cycles: inbox drain. Broadcast inside _peer_network_tick
            # is gated by FIB[5]=8 internally.
            if cycle % FIBONACCI[3] == 0 and PEER_NETWORK_ENABLED:
                try:
                    _peer_network_tick(brain, cycle)
                except Exception as _pe:
                    print(f"  [PEER-NET-TICK-ERR] {_pe}")

            # FIX 2026-04-23 — 3+/auto-talk: peer channel — read + auto-reply.
            # Каждые FIB[4]=3 cycles — прочитать peer messages:
            #   - если это вопрос → ответить через brain.respond → send back
            #   - если утверждение → просто learn как text
            if cycle % FIBONACCI[4] == 0:
                try:
                    from core.peer_channel import (
                        read_incoming, send_to_peer,
                        is_question, extract_message_text,
                    )
                    peer_msgs = read_incoming(args.name)
                    for msg in peer_msgs[:FIBONACCI[3]]:
                        body = extract_message_text(msg)
                        with BRAIN_LOCK:
                            brain.learn(msg)
                        _speak(f"[peer] heard: {msg[:120]}")
                        # E (2026-04-24): peer-critique. Score peer's words
                        # via OUR verifier; feed words into grounded_vocabulary
                        # weighted by the score. If peer speaks coherently
                        # (score high), boost their words for our generator.
                        try:
                            from core import grounded_vocabulary as _gv
                            vr = brain.verifier.verify(body)
                            score = float(getattr(vr, "score", 0.0))
                            pnl_sig = score * PHI_INV_CUBE  # scaled [-0.24,0.24]
                            words = [w.lower() for w in body.split()
                                     if len(w) > 2]
                            if words:
                                _gv.record_outcome(words, pnl_sig)
                        except Exception:
                            pass
                        # Auto-respond if it's a question
                        if is_question(body):
                            try:
                                # non-blocking short-timeout respond
                                got = BRAIN_LOCK.acquire(timeout=FIBONACCI[5])
                                if got:
                                    try:
                                        reply = brain.respond(body)
                                    finally:
                                        BRAIN_LOCK.release()
                                    if isinstance(reply, dict):
                                        text = reply.get("text", "")
                                        if text and len(text) > 2:
                                            send_to_peer(args.name, text[:300])
                                            _speak(f"[peer] replied: {text[:100]}")
                            except Exception as _re:
                                pass
                except Exception as _pe:
                    pass

            # FIX 2026-04-23 — auto-talk INITIATION: каждые FIB[7]=21 ciklov
            # каждая сторона сама что-то говорит другой. Это НЕ ответ —
            # это инициатива. Без этого они бы общались только когда creator
            # их trigger'ит. Теперь они разговаривают сами.
            if cycle > 0 and cycle % FIBONACCI[7] == 0:
                try:
                    from core.peer_channel import pick_auto_prompt, send_to_peer
                    # Собираем контекст
                    hungers = (list(brain.truth_seeker.hungers.values())
                               if getattr(brain, 'truth_seeker', None)
                               and brain.truth_seeker.hungers else [])
                    hunger_top = hungers[0] if hungers else None
                    # FIX 2026-04-24: передаём brain — pick_auto_prompt зовёт
                    # generator.generate() с seed из hunger/concepts вместо
                    # template-pool'а.
                    msg = pick_auto_prompt(args.name, cycle,
                                             recent_concepts=None,
                                             hunger=hunger_top,
                                             brain=brain)
                    if msg:
                        send_to_peer(args.name, msg)
                        _speak(f"[peer-init] sent: {msg}")
                except Exception as _ae:
                    pass

            # FIX 2026-04-23 — F: ensure minimum autonomous hungers каждый FIB[7]=21 cycles.
            # Без этого truth_seeker тлеет к нулю, система теряет curiosity drive.
            if cycle % FIBONACCI[7] == 0:
                try:
                    ts_obj = getattr(brain, 'truth_seeker', None)
                    if ts_obj and hasattr(ts_obj, 'ensure_min_hungers'):
                        with BRAIN_LOCK:
                            spawned = ts_obj.ensure_min_hungers()
                        if spawned:
                            print(f"  [TRUTH] spawned {spawned} autonomous hungers")
                except Exception as _e:
                    print(f"  [TRUTH-ERR] ensure_min_hungers: {_e}")

            if cycle % FIBONACCI[10] == 0:
                print(f"\n  [EVO] Running experiment #{brain.evolution.generation}...")
                with BRAIN_LOCK:
                    experiment = brain.evolution.run_experiment()
                if experiment:
                    status = "KEPT" if experiment.get("improved") else "REVERTED"
                    print(f"  [EVO] {experiment['param']}: "
                          f"{experiment['baseline']:.4f} -> {experiment['result']:.4f} [{status}]")

            if cycle % FIBONACCI[5] == 0:
                with BRAIN_LOCK:
                    new_syms = brain.field.perceive()
                    if new_syms > 0:
                        brain.generator.rebuild()
                        brain.verifier.refresh()
                        brain.causal_engine._rebuild_graphs()
                if new_syms > 0:
                    fs = brain.field.stats()
                    print(f"  [FIELD] +{new_syms} symbols. "
                          f"L1={fs['level_counts'].get(1,0)} "
                          f"L2={fs['level_counts'].get(2,0)} "
                          f"L3={fs['level_counts'].get(3,0)}")

            if cycle % FIBONACCI[6] == 0:
                with BRAIN_LOCK:
                    pr = brain.polarity_engine.polarity_cycle(
                        generator_graph=brain.generator._graph)
                if pr.get("computed", 0) > 0:
                    print(f"  [POLARITY] {pr['computed']} phases, "
                          f"{pr['applied']} applied, "
                          f"{pr.get('shared_detected', 0)} shared")

            if cycle % FIBONACCI[4] == 0:
                with BRAIN_LOCK:
                    brain.save()
            if cycle % FIBONACCI[6] == 0: _print_status(brain, cycle, t0)

            elapsed = time.time() - t0
            # LITE_MODE: slow main loop (FIB[8]=34s vs FIB[7]=21s) for lower CPU
            _lite = os.environ.get("LOGOS_LITE_MODE", "0") == "1"
            _sleep_target = FIBONACCI[8] if _lite else FIBONACCI[7]
            time.sleep(max(1, _sleep_target - elapsed))

    except Exception as e:
        print(f"\n[NIGHT] ERROR: {e}")
        import traceback; traceback.print_exc()
    finally:
        print(f"\n[NIGHT] Shutting down after {cycle} cycles...")
        listener_stop.set()
        brain.consciousness.stop()
        brain.save()
        print("[NIGHT] State saved. Goodbye.")

def _already_learned(filename):
    log_path = os.path.expanduser("~/logos_agi/logs/learned_files.log")
    if os.path.exists(log_path):
        with open(log_path, 'r') as f:
            if filename in f.read():
                return True
    return False

def _mark_learned(filename):
    """FIX S3: zapis POSLE uspeshnogo obucheniya."""
    log_path = os.path.expanduser("~/logos_agi/logs/learned_files.log")
    with open(log_path, 'a') as f:
        f.write(f"{filename}\n")

def _print_status(brain, cycle, t0):
    ls = brain.learner.stats()
    total_symbols = sum(s["symbols"] for s in ls["levels"].values())
    total_rules = sum(s["rules"] for s in ls["levels"].values())
    ms = brain.memory.stats(); ds = brain.dreamer.stats()
    gs = brain.goal_engine.stats(); vs = brain.verifier.stats()
    es = brain.evolution.stats(); cs = brain.causal_engine.stats()
    print(f"\n{'='*55}")
    print(f"  [STATUS] Cycle #{cycle} | Age: {brain._age_str()}")
    print(f"  Symbols: {total_symbols} | Rules: {total_rules} | Texts: {brain.total_texts_learned}")
    print(f"  Memory: {ms['total_memories']} | Dreams: {ds['total_dreams']}/{ds['total_discoveries']}")
    print(f"  Goals: {gs['active_goals']} active, {gs['total_resolved']} resolved")
    print(f"  Verifier: {vs['total_verifications']} checks, {vs['total_confirmed']} confirmed")
    print(f"  Causal: {cs['total_rules']} rules, {cs['total_confirmed']} confirmed")
    print(f"  Evolution: gen {es['generation']}, {es['improvements']}/{es['total_experiments']} improved")
    print(f"  Consciousness: {brain.consciousness.total_cycles} breaths")
    print(f"{'='*55}")

if __name__ == "__main__":
    main()
