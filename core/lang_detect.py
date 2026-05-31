"""
lang_detect.py — Opredeleniye yazyka cherez fazovyy analiz.
Ni kakikh bibliotek — tolko simvoly.
Russkiy = kirillicheskie bukvy. Angliyskiy = latinskie.
Smeshannyy = oba.
"""

_CYR = set("абвгдеёжзийклмнопрстуфхцчшщъыьэюя")
_LAT = set("abcdefghijklmnopqrstuvwxyz")

def detect_lang(text):
    """Vozvrashchaet 'ru', 'en', ili 'mix'."""
    text = text.lower()
    cyr = sum(1 for c in text if c in _CYR)
    lat = sum(1 for c in text if c in _LAT)
    total = cyr + lat
    if total == 0:
        return "en"
    ratio = cyr / total
    if ratio > 0.618:  # PHI_INV — bolshe poloviny kirillicheskikh
        return "ru"
    elif ratio < 0.382:  # PHI_INV_SQ
        return "en"
    return "mix"

def filter_by_lang(words, lang):
    """Ostavit tolko slova nuzhnogo yazyka."""
    if lang == "mix":
        return words
    result = []
    for w in words:
        w_low = w.lower()
        has_cyr = any(c in _CYR for c in w_low)
        has_lat = any(c in _LAT for c in w_low)
        if lang == "ru" and has_cyr:
            result.append(w)
        elif lang == "en" and has_lat and not has_cyr:
            result.append(w)
        elif lang == "mix":
            result.append(w)
    return result
