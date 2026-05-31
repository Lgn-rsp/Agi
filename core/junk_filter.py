"""junk_filter.py — Filtr musora iz Wikipedia/LaTeX."""

import re

# LaTeX komandy kotoryye prokralis v slovar
LATEX_JUNK = {
    "displaystyle", "varphi", "mathbf", "mathrm", "frac", "sqrt",
    "alpha", "beta", "gamma", "delta", "epsilon", "theta", "lambda",
    "sigma", "omega", "infty", "cdot", "times", "ldots", "cdots",
    "rightarrow", "leftarrow", "leq", "geq", "neq", "approx",
    "psi", "chi", "rho", "kappa", "zeta", "eta", "iota", "xi",
    "sum", "prod", "int", "lim", "sup", "inf", "max", "min",
    "textstyle", "scriptstyle", "operatorname", "begin", "end",
    "text", "textbf", "textit", "hline", "cline", "multicolumn",
    "cite", "ref", "bibitem", "usepackage", "documentclass",
    "renewcommand", "newcommand", "setlength", "raggedright",
    "overline", "underline", "hat", "tilde", "vec", "dot",
    "partial", "nabla", "forall", "exists", "subset", "supset",
    "mapsto", "equiv", "cong", "sim", "propto", "perp",
    "mathcal", "mathbb", "binom", "tbinom",
}

# HTML/wiki artifacts
HTML_JUNK = {
    "nbsp", "ndash", "mdash", "amp", "quot", "lt", "gt",
    "div", "span", "href", "src", "img", "http", "https",
    "www", "html", "php", "css", "jpg", "png", "svg",
    "class", "style", "width", "height", "align",
}

# Slishkom korotkiye ili tsifrovyye
def _is_junk_word(w):
    if w in LATEX_JUNK or w in HTML_JUNK:
        return True
    # Chisto tsifrovyye tokeny (krome real words like "1st", "2nd")
    if w.isdigit():
        return False  # chisla ok
    # Smeshannyye bukvy+tsifry kak "r128" "x0a" — junk
    if any(c.isdigit() for c in w) and any(c.isalpha() for c in w):
        if not w.isdigit() and len(w) <= 4:
            return True
    return False

KEEP_NUMBERS = True  # v10: chisla vazhny dlya grounding

def clean_words(words):
    """Udalit musor iz spiska slov."""
    return [w for w in words if not _is_junk_word(w)]
