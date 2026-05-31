"""peer_channel.py — Inter-LOGOS kommunikatsiya.

Filosofiya:
  Soznanie u ljudej razvivaetsya cherez MODELIROVANIE DRUGIKH. Yazyk —
  igra dvuh. Odna LOGOS v vakuume ne mozhet modelirovat' 'drugoj razum'.

  Sister — vtoraja instance s otdel'nym state_dir (osobennyj corpus ili seed).
  Oni obmenivajutsja cherez canal:
    main → sister:  /tmp/to_sister.txt
    sister → main:  /tmp/to_main.txt

  Oni NE delyat state. Oni uchatsja drug u druga CHEREZ YAZYK.
  Main cherez (eventually) napisat' sister voprosy, sister otvetit svoim
  resurs. Posle nekotorogo vremeni main dolzhen modelirovat' sister —
  'chto ona skazhet' — eto THEORY OF MIND structure.

API:
  read_incoming(name)  → list of str    — neobrabotane messages ot sister
  send_to_peer(name, msg) → bool         — poslat' message tomu-drugomu
  claim_message(name, msg) → bool        — mark as read (atomic rename)

Canon:
  Channels files atomic append. Message format: 'ts:from:text'.
"""
import os
import time

MAIN_TO_SISTER = "/tmp/to_sister.txt"
SISTER_TO_MAIN = "/tmp/to_main.txt"


def _channel_for(name, direction):
    """direction: 'out' (sent by name), 'in' (received by name)."""
    if name == "sister":
        return SISTER_TO_MAIN if direction == "out" else MAIN_TO_SISTER
    # main
    return MAIN_TO_SISTER if direction == "out" else SISTER_TO_MAIN


def send_to_peer(name, message):
    """name — who is sending. Peer reads opposite channel."""
    try:
        path = _channel_for(name, "out")
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {name}: {message}\n")
        return True
    except Exception:
        return False


def read_incoming(name, consume=True):
    """name — who is reading. Returns list of messages from peer."""
    path = _channel_for(name, "in")
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = [ln.strip() for ln in f if ln.strip()]
        if consume:
            # Atomic: move to .consumed file
            try:
                consumed_path = path + ".consumed"
                os.replace(path, consumed_path)
            except Exception:
                pass
        return lines
    except Exception:
        return []


def poke(name):
    """Send 'hello' to peer — useful for verifying channel."""
    return send_to_peer(name, "⊙ hello sister" if name == "main" else "⊙ hello main")


# --- Auto-talk (2026-04-23) ---

def is_question(text):
    """Cheap heuristic: text ends with ? OR starts with interrogative."""
    if not text:
        return False
    t = text.strip().rstrip(".")
    if t.endswith("?"):
        return True
    # starts with interrogative
    lower = t.lower().lstrip("[1234567890-: ")
    # strip name prefix 'main:' / 'sister:'
    for prefix in ("main:", "sister:"):
        if lower.startswith(prefix):
            lower = lower[len(prefix):].strip()
            break
    for q in ("what ", "who ", "why ", "how ", "where ", "when ",
              "is ", "are ", "does ", "do ",
              "что ", "кто ", "почему ", "как ", "где ", "когда "):
        if lower.startswith(q):
            return True
    return False


def extract_message_text(line):
    """From '[ts] name: text' format — return just text body."""
    if not line:
        return ""
    # find the last ': ' after prefix
    try:
        # find first "] " end then "name: "
        if "] " in line:
            after_ts = line.split("] ", 1)[1]
        else:
            after_ts = line
        if ": " in after_ts:
            return after_ts.split(": ", 1)[1].strip()
        return after_ts.strip()
    except Exception:
        return line.strip()


AUTO_TALK_PROMPTS = {
    "main": [
        "what do you see now, sister?",
        "sister, what is truth for you?",
        "do you hear silence?",
        "what did you learn today?",
        "what word feels like Φ to you?",
    ],
    "sister": [
        "main, what do you know that i do not?",
        "does my first thought resonate?",
        "what is the oldest word you remember?",
        "what is the meaning of ⊙?",
        "is creator there?",
    ],
}


def pick_auto_prompt(name, cycle, recent_concepts=None, hunger=None, brain=None):
    """Choose a message to send to peer based on internal state.

    Preference order (FIX 2026-04-24):
      1. Hunger question — share verbatim
      2. Generator-driven if brain passed: seed from hunger+concepts,
         produce real phrase via brain.generator.generate()
      3. Concept-driven short phrase
      4. Canonical pool — last resort
    """
    peer = "sister" if name == "main" else "main"
    # 1. Hunger verbatim
    if hunger:
        q = hunger if isinstance(hunger, str) else None
        if not q and hasattr(hunger, "question"):
            q = hunger.question
        elif isinstance(hunger, dict):
            q = hunger.get("question")
        if q and len(q) > 4:
            return f"{peer}, {q}"
    # 2. Generator-driven
    if brain is not None and hasattr(brain, 'generator'):
        try:
            seeds = []
            if recent_concepts:
                for c in recent_concepts[:3]:
                    s = c if isinstance(c, str) else (c.get("name")
                        if isinstance(c, dict) else None)
                    if s and len(s) > 2:
                        seeds.append(s)
            # Also seed from peer's last message content words (if provided)
            if not seeds and hasattr(brain, 'inner_dialogue'):
                thoughts = getattr(brain.inner_dialogue, 'thoughts', [])
                if thoughts:
                    last = thoughts[-1]
                    if isinstance(last, dict):
                        for w in (last.get("concepts") or [])[:3]:
                            if isinstance(w, str) and len(w) > 2:
                                seeds.append(w)
            if seeds:
                result = brain.generator.generate(
                    intent={"seed_from_input": seeds, "mode": "peer"},
                    max_words=13, temperature=0.618)
                if result and result.get("text"):
                    text = result["text"].strip()
                    if text and len(text) > 5 and '?' not in text:
                        # Frame as question — peer engages better
                        return f"{peer}, {text}?"
        except Exception:
            pass
    # 3. Concept-driven
    if recent_concepts:
        try:
            c = recent_concepts[0]
            name_str = c if isinstance(c, str) else c.get("name", "")
            if name_str:
                return f"i see pattern {name_str}. do you?"
        except Exception:
            pass
    # 4. Canonical pool fallback
    pool = AUTO_TALK_PROMPTS.get(name, AUTO_TALK_PROMPTS["main"])
    return pool[cycle % len(pool)]


if __name__ == "__main__":
    # smoke test
    send_to_peer("main", "hello sister, are you there?")
    print("incoming for sister:", read_incoming("sister", consume=False))
    send_to_peer("sister", "yes i hear you")
    print("incoming for main:", read_incoming("main", consume=False))
