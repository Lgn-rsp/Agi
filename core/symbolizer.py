"""
symbolizer.py — Prevrashaet tekst v simvolnye posledovatelnosti.
Tri urovnya odnovremenno: bukvy, slova, pary slov.
Kazhdyy uroven pitaet PhaseSpace.
"""
import re
import os
import time
from core.resonance_constants import FIBONACCI, phi_phase

# Cleaning pattern — latin + cyrillic + digits
CLEAN = re.compile(r'[^a-zA-Z\u0400-\u04FF0-9\s]')


def clean_text(text):
    """Chistim tekst — bukvy (latin+cyrillic) + tsifry + probely, lowercase."""
    return CLEAN.sub('', text).lower().strip()


def text_to_chars(text):
    """Uroven 1: bukvy. Probely = razdelitel."""
    cleaned = clean_text(text)
    return list(cleaned)


def text_to_words(text):
    """Uroven 2: slova. S junk filtrom."""
    from core.junk_filter import clean_words
    cleaned = clean_text(text)
    words = cleaned.split()
    return clean_words([w for w in words if len(w) > 0])


def text_to_pairs(text):
    """Uroven 3: pary sosednikh slov — nachalo grammatiki."""
    words = text_to_words(text)
    pairs = []
    for i in range(len(words) - 1):
        pairs.append(f"{words[i]}_{words[i+1]}")
    return pairs


def text_to_trigrams(text):
    """Uroven 4: trojki slov — struktury predlozheniy."""
    words = text_to_words(text)
    trigrams = []
    for i in range(len(words) - 2):
        trigrams.append(f"{words[i]}_{words[i+1]}_{words[i+2]}")
    return trigrams


def symbolize_multilevel(text):
    """
    Vse urovni srazu. Vozvrashchaet dict s chetyrm'ya
    posledovatelnostyami dlya PhaseSpace.observe().
    """
    return {
        "chars": text_to_chars(text),
        "words": text_to_words(text),
        "pairs": text_to_pairs(text),
        "trigrams": text_to_trigrams(text),
    }


def stream_file(filepath, chunk_lines=FIBONACCI[8]):
    """
    Potokovo chitaet fayl po chunk_lines=34 strok.
    Ne gruzit ves fayl v pamyat.
    Vozvrashchaet generaror tekstovykh blokov.
    """
    if not os.path.exists(filepath):
        print(f"[!] File not found: {filepath}")
        return

    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        buffer = []
        for line in f:
            line = line.strip()
            if line:
                buffer.append(line)
            if len(buffer) >= chunk_lines:
                yield ' '.join(buffer)
                buffer = []
        if buffer:
            yield ' '.join(buffer)


# === TEST ===
if __name__ == "__main__":
    test = "The cat sat on the mat. The dog ran in the park."
    result = symbolize_multilevel(test)

    print(f"Input: {test}")
    print(f"Chars: {len(result['chars'])} symbols")
    print(f"Words: {result['words']}")
    print(f"Pairs: {result['pairs'][:5]}")
    print(f"Trigrams: {result['trigrams'][:3]}")
