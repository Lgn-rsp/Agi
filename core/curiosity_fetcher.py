"""curiosity_fetcher.py — Self-directed learning via Wikipedia REST API.

Idea: brain has an agency channel (`/tmp/logos_wants.txt`) and truth_seeker
hungers — but до этого всё только записывалось «хочу понять X», без действий.
Этот модуль закрывает контур: prompt → fetch summary → save → learn.

Источник: Wikipedia REST API (`/api/rest_v1/page/summary/<title>`). Бесплатно,
без ключей, требует User-Agent. Возвращает чистый extract в plain text.

Anti-abuse:
  - Дедуп через self.fetched (один subject = один запрос за время жизни)
  - Rate limit между запросами (PHI секунд)
  - Размер ответа ограничен (256 KB)
  - Только GET, никаких POST
  - Опт-ин: brain не вызывает фетчер если CURIOSITY_FETCH_ENABLED=False

State persistence: history sохраняется в `state/curiosity_history.jsonl` —
brain видит что узнала.
"""
import json
import os
import re
import tempfile
import time
import urllib.parse
import urllib.request

from core.resonance_constants import PHI, PHI_INV, FIBONACCI


WIKIPEDIA_BASE = "https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}"
# 2026-05-08: broader internet fallback — DuckDuckGo Instant Answer (free, no key).
DDG_BASE = "https://api.duckduckgo.com/?q={q}&format=json&no_html=1&skip_disambig=1"
DEFAULT_USER_AGENT = "LogosAGI/1.0 (curiosity_fetcher; https://github.com/local)"
MAX_RESPONSE_BYTES = 256 * 1024  # 256 KB safety cap
MIN_USEFUL_TEXT = 64              # ниже этого — не считаем текстом
SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_а-яА-ЯёЁ-]")


def _atomic_write_text(path, text):
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def _safe_filename(subject):
    """Имя файла из subject: убираем спецсимволы, ограничиваем длину FIBONACCI[9]=55."""
    s = subject.strip().replace(" ", "_")
    s = SAFE_NAME_RE.sub("_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:FIBONACCI[9]] or "untitled"


class CuriosityFetcher:
    """Pulls plaintext from Wikipedia for subjects she wants to understand.

    Args:
        save_dir: куда сохранять fetched.txt (учится потом via learn_file)
        history_path: jsonl журнал {ts, subject, lang, ok, len}
        lang_chain: список языков (попробовать по порядку); default ["ru","en"]
        user_agent: HTTP UA
        rate_seconds: минимум между запросами (PHI=1.618 default)
        max_subjects_per_tick: сколько subjects обрабатывать за один tick (FIB[3]=3)
    """

    def __init__(self, save_dir, history_path=None,
                 lang_chain=("ru", "en"),
                 user_agent=DEFAULT_USER_AGENT,
                 rate_seconds=PHI,
                 max_subjects_per_tick=FIBONACCI[3]):
        self.save_dir = save_dir
        self.history_path = history_path
        self.lang_chain = tuple(lang_chain)
        self.user_agent = user_agent
        self.rate_seconds = float(rate_seconds)
        self.max_subjects_per_tick = int(max_subjects_per_tick)
        self.fetched = set()
        self.last_fetch_ts = 0.0
        # Подтянуть deduped subjects из journal если есть
        if history_path and os.path.exists(history_path):
            try:
                with open(history_path, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            rec = json.loads(line)
                            self.fetched.add(rec.get("subject", ""))
                        except Exception:
                            continue
            except Exception:
                pass

    # --- HTTP ---

    def fetch_summary(self, subject, lang="ru"):
        """Returns plaintext extract or None."""
        title = urllib.parse.quote(subject.strip().replace(" ", "_"))
        url = WIKIPEDIA_BASE.format(lang=lang, title=title)
        # Throttle
        gap = time.time() - self.last_fetch_ts
        if gap < self.rate_seconds:
            time.sleep(self.rate_seconds - gap)
        self.last_fetch_ts = time.time()
        req = urllib.request.Request(url, headers={"User-Agent": self.user_agent,
                                                     "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = resp.read(MAX_RESPONSE_BYTES + 1)
                if len(data) > MAX_RESPONSE_BYTES:
                    return None
                obj = json.loads(data.decode("utf-8"))
            extract = obj.get("extract") or ""
            extract = extract.strip()
            if len(extract) < MIN_USEFUL_TEXT:
                return None
            return extract
        except Exception:
            return None

    def fetch_ddg(self, subject):
        """DuckDuckGo Instant Answer fallback — broader internet than just Wikipedia.

        Returns plaintext extract or None. Same anti-abuse limits.
        """
        url = DDG_BASE.format(q=urllib.parse.quote(subject.strip()))
        gap = time.time() - self.last_fetch_ts
        if gap < self.rate_seconds:
            time.sleep(self.rate_seconds - gap)
        self.last_fetch_ts = time.time()
        req = urllib.request.Request(url, headers={"User-Agent": self.user_agent,
                                                     "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = resp.read(MAX_RESPONSE_BYTES + 1)
                if len(data) > MAX_RESPONSE_BYTES:
                    return None
                obj = json.loads(data.decode("utf-8"))
            # DDG fields: AbstractText (preferred), Definition, RelatedTopics[*].Text
            text = (obj.get("AbstractText") or obj.get("Definition") or "").strip()
            if len(text) < MIN_USEFUL_TEXT:
                # try concatenated RelatedTopics as last resort
                related = []
                for r in (obj.get("RelatedTopics") or [])[:FIBONACCI[5]]:
                    t = (r.get("Text") or "").strip()
                    if t:
                        related.append(t)
                text = "\n".join(related).strip()
            if len(text) < MIN_USEFUL_TEXT:
                return None
            return text
        except Exception:
            return None

    def acquire(self, subject):
        """Full pipeline: fetch (RU then EN Wikipedia, then DDG) → save .txt → record history.

        Returns dict {subject, lang, path, length} on success, None on failure.
        """
        if not subject or not isinstance(subject, str):
            return None
        subject = subject.strip()
        if not subject or subject in self.fetched:
            return None
        for lang in self.lang_chain:
            text = self.fetch_summary(subject, lang=lang)
            if text:
                fname = _safe_filename(subject) + f".{lang}.txt"
                path = os.path.join(self.save_dir, fname)
                # add a header line so brain has subject context
                _atomic_write_text(path, f"# {subject}\n{text}\n")
                self.fetched.add(subject)
                self._record_history(subject, lang, True, len(text))
                return {"subject": subject, "lang": lang, "path": path,
                        "length": len(text)}
        # 2026-05-08: Wikipedia exhausted — try DuckDuckGo for broader internet.
        ddg_text = self.fetch_ddg(subject)
        if ddg_text:
            fname = _safe_filename(subject) + ".ddg.txt"
            path = os.path.join(self.save_dir, fname)
            _atomic_write_text(path, f"# {subject} (DuckDuckGo)\n{ddg_text}\n")
            self.fetched.add(subject)
            self._record_history(subject, "ddg", True, len(ddg_text))
            return {"subject": subject, "lang": "ddg", "path": path,
                    "length": len(ddg_text)}
        # Failure path — still mark to avoid retry storms
        self.fetched.add(subject)
        self._record_history(subject, None, False, 0)
        return None

    def tick(self, subjects):
        """Process up to max_subjects_per_tick from given iterable.

        Returns list of acquired dicts (subject,lang,path,length).
        """
        out = []
        n = 0
        for s in subjects:
            if n >= self.max_subjects_per_tick:
                break
            r = self.acquire(s)
            if r:
                out.append(r)
                n += 1
        return out

    # --- history ---

    def _record_history(self, subject, lang, ok, length):
        if not self.history_path:
            return
        try:
            d = os.path.dirname(self.history_path)
            if d:
                os.makedirs(d, exist_ok=True)
            with open(self.history_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "ts": round(time.time(), 3),
                    "subject": subject,
                    "lang": lang,
                    "ok": ok,
                    "length": length,
                }, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def stats(self):
        return {
            "fetched_unique": len(self.fetched),
            "last_fetch_ts": self.last_fetch_ts,
            "save_dir": self.save_dir,
        }


# --- Subject extraction helpers ---

WANT_PREFIX_RE = re.compile(
    r"(?:хочу\s+понять|узнать)[\s:.\-]+(.+)$", re.IGNORECASE
)
WHY_QUESTION_RE = re.compile(
    r"why\s+(?:does|is)\s+(\w[\w-]*)\s+(?:cause|resonate|mean|relate)",
    re.IGNORECASE
)
RU_QUESTION_RE = re.compile(
    r"что\s+такое\s+(\w[\w-]+)|почему\s+(\w[\w-]+)", re.IGNORECASE
)


def subjects_from_wants_file(path, max_lines=FIBONACCI[10]):  # 2026-05-07: 21→89, agency_channel забивал хвост одним и тем же subject
    """Read /tmp/logos_wants.txt and extract subjects from 'хочу понять: X' lines.

    Returns list of unique subjects in chronological order (most recent first).
    """
    if not os.path.exists(path):
        return []
    out = []
    seen = set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for line in reversed(lines[-max_lines:]):
            m = WANT_PREFIX_RE.search(line)
            if not m:
                continue
            subj = m.group(1).strip().rstrip("?.!,").strip()
            if not subj or len(subj) > FIBONACCI[9]:
                continue
            if subj.lower() in seen:
                continue
            seen.add(subj.lower())
            out.append(subj)
    except Exception:
        pass
    return out


def subjects_from_open_questions(brain, max_n=FIBONACCI[5]):
    """Extract content-bearing subjects from brain.truth_seeker / inner_dialogue.

    Heuristic: look for 'why does X cause Y' patterns and 'что такое X'/'почему X'.
    Picks the most recent N.
    """
    subjects = []
    seen = set()
    sources = []
    ts = getattr(brain, "truth_seeker", None)
    id_ = getattr(brain, "inner_dialogue", None)
    if ts is not None:
        sources.append(getattr(ts, "open_questions", None) or [])
    if id_ is not None:
        sources.append(getattr(id_, "open_questions", None) or [])
    for src in sources:
        for q in reversed(list(src)[-FIBONACCI[7]:]):
            text = q.get("question") if isinstance(q, dict) else str(q)
            if not text:
                continue
            for match in (WHY_QUESTION_RE.findall(text)
                          or RU_QUESTION_RE.findall(text)):
                if isinstance(match, tuple):
                    cand = next((c for c in match if c), None)
                else:
                    cand = match
                if not cand:
                    continue
                cand = cand.strip().lower()
                if cand in seen or len(cand) < 3 or len(cand) > FIBONACCI[8]:
                    continue
                seen.add(cand)
                subjects.append(cand)
                if len(subjects) >= max_n:
                    return subjects
    return subjects


if __name__ == "__main__":
    import sys
    save = "/tmp/curiosity_test"
    hist = "/tmp/curiosity_test_hist.jsonl"
    f = CuriosityFetcher(save_dir=save, history_path=hist)
    test_subjects = sys.argv[1:] or ["water", "vancouver", "nonexistent_xyz_zzz_qqq"]
    for s in test_subjects:
        r = f.acquire(s)
        if r:
            print(f"OK {s}: {r['lang']} → {r['path']} ({r['length']} chars)")
        else:
            print(f"-- {s}: not fetched")
    print(f"stats: {f.stats()}")
