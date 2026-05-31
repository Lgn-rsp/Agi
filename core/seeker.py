"""
seeker.py — Poisk otvetov na voprosy sistemy.
v8.1: realnyy web search cherez Wikipedia API + DuckDuckGo.
"""
import os
import time
import json
import re

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    import wikipediaapi
    HAS_WIKI = True
except ImportError:
    HAS_WIKI = False

from core.resonance_constants import (
    PHI, FIBONACCI,
    phi_phase_distance, phi_phase_resonance
)


class Seeker:
    def __init__(self, memory, learner, curiosity, state_dir=None):
        self.memory = memory
        self.learner = learner
        self.curiosity = curiosity
        self.state_dir = state_dir or os.path.expanduser("~/logos_agi/state")
        self.log_dir = os.path.expanduser("~/logos_agi/logs")
        os.makedirs(self.log_dir, exist_ok=True)

        self.total_searches = 0
        self.total_found = 0
        self.total_web_queries = 0
        self.total_web_found = 0

        # Wikipedia API
        self.wiki = None
        if HAS_WIKI:
            self.wiki = wikipediaapi.Wikipedia(
                user_agent='LOGOS_AGI/1.0 (resonance learning system)',
                language='en'
            )

        web_status = "Wikipedia" if HAS_WIKI else "NO WEB"
        print(f"[+] Seeker initialized ({web_status})")

    def seek_answer(self, question):
        self.total_searches += 1

        # 1. Vnutrennyaya pamyat
        result = self._seek_in_memory(question)
        if result:
            self.total_found += 1
            self._log(f"FOUND IN MEMORY: {question.pair}")
            return result

        # 2. Neizuchennye dannye
        result = self._seek_in_data(question)
        if result:
            self.total_found += 1
            self._log(f"FOUND IN DATA: {question.pair}")
            return result

        # 3. Web — realnyy poisk
        result = self._seek_web(question)
        if result:
            self.total_found += 1
            self.total_web_found += 1
            self._log(f"FOUND ON WEB: {question.pair}")
            return result

        web_query = self.curiosity.formulate_search_query(question)
        self._log(f"NOT FOUND: '{web_query}' for {question.pair}")

        return {
            "found": False,
            "source": "none",
            "suggested_query": web_query,
            "pair": question.pair,
        }

    def _seek_in_memory(self, question):
        a, b = question.pair

        assoc_a = self.memory.recall_associated(a)
        assoc_b = self.memory.recall_associated(b)

        set_a = {x[0] for x in assoc_a}
        set_b = {x[0] for x in assoc_b}
        shared = set_a & set_b

        if shared:
            return {
                "found": True,
                "source": "memory_association",
                "pair": question.pair,
                "bridge_symbols": list(shared),
                "suggestion": f"{a} and {b} share connections through: {', '.join(list(shared)[:5])}",
            }

        mem_a = self.memory.recall(a)
        mem_b = self.memory.recall(b)
        if mem_a and mem_b:
            traces_a = set()
            for t in mem_a.get("traces", []):
                traces_a.update(t.get("context", []))
            traces_b = set()
            for t in mem_b.get("traces", []):
                traces_b.update(t.get("context", []))
            shared_ctx = traces_a & traces_b
            if shared_ctx:
                return {
                    "found": True,
                    "source": "memory_context",
                    "pair": question.pair,
                    "shared_context": list(shared_ctx)[:8],
                }

        return None

    def _seek_in_data(self, question):
        data_dir = os.path.expanduser("~/logos_agi/data")
        if not os.path.isdir(data_dir):
            return None

        a, b = question.pair
        search_terms = {a.lower(), b.lower()}

        for fname in os.listdir(data_dir):
            if not fname.endswith(".txt"):
                continue
            fpath = os.path.join(data_dir, fname)
            try:
                with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                    for line_num, line in enumerate(f):
                        lower_line = line.lower()
                        if all(term in lower_line for term in search_terms):
                            self.learner.learn_text(line.strip())
                            return {
                                "found": True,
                                "source": "data_file",
                                "file": fname,
                                "line": line_num,
                                "pair": question.pair,
                                "text": line.strip()[:200],
                            }
            except Exception:
                continue

        return None

    def _seek_web(self, question):
        """Realnyy poisk v Wikipedia."""
        if not HAS_WIKI and not HAS_REQUESTS:
            return None

        query = self.curiosity.formulate_search_query(question)
        self.total_web_queries += 1
        self._log(f"WEB SEARCH: '{query}'")

        # Wikipedia poisk
        text = self._search_wikipedia(query)
        if text:
            # Uchim naydennoye
            # Ogranichivaem dlinu — ne bolshe 500 slov za raz
            words = text.split()
            chunk_size = FIBONACCI[12]  # 233 slov na chunk
            chunks_learned = 0
            for i in range(0, min(len(words), chunk_size * 3), chunk_size):
                chunk = ' '.join(words[i:i+chunk_size])
                if chunk.strip():
                    self.learner.learn_text(chunk)
                    chunks_learned += 1

            return {
                "found": True,
                "source": "wikipedia",
                "pair": question.pair,
                "query": query,
                "text_length": len(text),
                "chunks_learned": chunks_learned,
            }

        # DuckDuckGo instant answers (fallback)
        text = self._search_ddg(query)
        if text:
            self.learner.learn_text(text)
            return {
                "found": True,
                "source": "duckduckgo",
                "pair": question.pair,
                "query": query,
                "text": text[:200],
            }

        return None

    def _search_wikipedia(self, query):
        """Ishchem v Wikipedia — vozvrashchaem tekst stati."""
        if not self.wiki:
            return None

        try:
            # Probuyem naiti statyu
            page = self.wiki.page(query)
            if page.exists():
                text = page.summary
                if len(text) > 100:
                    self._log(f"WIKI HIT: '{query}' -> {len(text)} chars")
                    return text

            # Probuyem otdelnye slova iz zaprosa
            words = query.split()
            for word in words:
                if len(word) < 3:
                    continue
                page = self.wiki.page(word)
                if page.exists():
                    text = page.summary
                    if len(text) > 100:
                        self._log(f"WIKI HIT (word): '{word}' -> {len(text)} chars")
                        return text

        except Exception as e:
            self._log(f"WIKI ERROR: {e}")

        return None

    def _search_ddg(self, query):
        """DuckDuckGo instant answers API — bez klyucha."""
        if not HAS_REQUESTS:
            return None

        try:
            resp = requests.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": 1},
                timeout=FIBONACCI[6],  # 13 sekund
                headers={"User-Agent": "LOGOS_AGI/1.0"}
            )
            if resp.status_code == 200:
                data = resp.json()
                # Abstract
                text = data.get("AbstractText", "")
                if not text:
                    text = data.get("Answer", "")
                if not text:
                    # Related topics
                    topics = data.get("RelatedTopics", [])
                    parts = []
                    for t in topics[:FIBONACCI[4]]:
                        if isinstance(t, dict) and "Text" in t:
                            parts.append(t["Text"])
                    text = ". ".join(parts)

                if text and len(text) > 50:
                    self._log(f"DDG HIT: '{query}' -> {len(text)} chars")
                    return text

        except Exception as e:
            self._log(f"DDG ERROR: {e}")

        return None

    def seek_batch(self, n=FIBONACCI[5]):
        questions = self.curiosity.top_questions(n)
        results = []
        for q in questions:
            result = self.seek_answer(q)
            results.append(result)
            if result.get("found"):
                q.attempts += 1
            # Ne flodit web — pauza mezhdu zaprosami
            if result.get("source") in ("wikipedia", "duckduckgo"):
                time.sleep(1)
        return results

    def search_and_learn(self, query):
        """
        Pryamoy poisk po zaprosu — dlya dashboard.
        Vozvrashchaet naydennyi tekst.
        """
        self.total_web_queries += 1
        text = self._search_wikipedia(query)
        if text:
            words = text.split()
            chunk_size = FIBONACCI[12]
            for i in range(0, min(len(words), chunk_size * 3), chunk_size):
                chunk = ' '.join(words[i:i+chunk_size])
                if chunk.strip():
                    self.learner.learn_text(chunk)
            self.total_web_found += 1
            return {"found": True, "source": "wikipedia", "text": text}

        text = self._search_ddg(query)
        if text:
            self.learner.learn_text(text)
            self.total_web_found += 1
            return {"found": True, "source": "duckduckgo", "text": text}

        return {"found": False, "query": query}

    def stats(self):
        return {
            "total_searches": self.total_searches,
            "total_found": self.total_found,
            "total_web_queries": self.total_web_queries,
            "total_web_found": self.total_web_found,
            "hit_rate": round(
                self.total_found / max(self.total_searches, 1), 4),
            "web_available": HAS_WIKI or HAS_REQUESTS,
        }

    def _log(self, message):
        path = os.path.join(self.log_dir, "seeker.log")
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {message}\n")


print("[+] seeker module loaded")
