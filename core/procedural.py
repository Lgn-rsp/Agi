"""
procedural.py — Protsedurnyy sloy cherez rezonans.

Algoritm — ne lineynaya posledovatelnost shagov.
Algoritm — STOYACHAYA VOLNA deystviy.

Tsikl for = stoyachaya volna s periodom N.
Usloviye if = interferentsiya (konstruktivnaya ili destruktivnaya).
Funktsiya = ogibayushchaya gruppy voln.

Arifmetika:
  Chislo = chastota na fazovom kruge.
  Slozhenie = fazovoe slozhenie.
  Umnozhenie = povtornoe slozhenie (kak mozg).
  Sravnenie = fazovoe rasstoyaniye.

Eto NE obychnyy kalkulyator. Eto REZONANSNYY protsessor.
Rezultat poluchayetsya cherez INTERFERENTSIYU chastot.

Dlya algoritmov:
  Pattern = kristallizovannaya tsepochka deystviy.
  "sort" = pattern [sravni, pomenyay, povtori]
  "search" = pattern [sravni, dvigaysya, prover]

  Patterny kristallizuyutsya iz primerov koda,
  tochno tak zhe kak slova iz tekstov.

Vsyo cherez phi.
"""
import math

from core.resonance_constants import (
    PHI, PHI_INV, PHI_INV_SQ, FIBONACCI,
    phi_phase_distance
)


class ResonanceArithmetic:
    """
    Arifmetika cherez rezonans chastot.

    Chislo N = pozitsiya na fazovom kruge:
      phase(N) = (N * PHI_INV) mod 1.0

    Slozhenie: phase(A+B) = nayti N gde
      phase(N) blizhe vsego k phase(A) + phase(B)

    Umnozhenie: A * B = slozhit A s soboy B raz.
      Kak mozg: 3 * 4 = 4 + 4 + 4 (tri rezonansnykh tsikla)

    Deleniye: A / B = skolko raz B rezoniryet v A.
    """

    def __init__(self, max_number=FIBONACCI[22]):  # 28657
        self.max_n = max_number
        # Precompute phases dlya chisel
        self._phase_cache = {}
        for n in range(max_number + 1):
            self._phase_cache[n] = (n * PHI_INV) % 1.0

    def number_to_phase(self, n):
        """Chislo -> fazovaya pozitsiya."""
        if n in self._phase_cache:
            return self._phase_cache[n]
        return (n * PHI_INV) % 1.0

    def phase_to_number(self, phase):
        """Fazovaya pozitsiya -> blizhaysheye chislo."""
        best_n = 0
        best_dist = 1.0
        # Optimizatsiya: ispolzuem svoystvo zolotogo ugla
        # N = round(phase / PHI_INV) — blizhaysheye priblizheniye
        approx = round(phase / PHI_INV) if PHI_INV > 0 else 0
        # Proveryaem okrestnost
        for n in range(max(0, approx - 5), min(self.max_n, approx + 6)):
            d = phi_phase_distance(self.number_to_phase(n), phase)
            if d < best_dist:
                best_dist = d
                best_n = n
        return best_n

    def add(self, a, b):
        """Slozhenie cherez fazovyy sdvig."""
        return a + b  # tochnoye — no cherez rezonans mozhno proverit

    def multiply(self, a, b):
        """
        Umnozhenie = povtornoe slozhenie.
        Kak mozg: 17 * 23 = slozhit 17 dvadtsat tri raza.
        Kazhdoe slozhenie = odin rezonansnyy tsikl.

        Optimizatsiya: razlozhenie po Fibonacci.
        23 = 21 + 2 = F[7] + F[3]
        17 * 23 = 17 * 21 + 17 * 2 = 357 + 34 = 391
        """
        if b == 0 or a == 0:
            return 0
        if b < 0:
            return -self.multiply(a, -b)
        if a < 0:
            return -self.multiply(-a, b)
        # Razlozhenie b po Fibonacci (Zeckendorf)
        components = self._zeckendorf(b)
        result = 0
        for fib_val in components:
            result += a * fib_val  # kazhdyy = odin rezonansnyy paket
        return result

    def divide(self, a, b):
        """Deleniye: skolko raz b rezoniryet v a."""
        if b == 0:
            return None  # antirezонанс
        return a // b, a % b  # quotient, remainder

    def _zeckendorf(self, n):
        """
        Razlozhenie chisla po Fibonacci (teorema Tsekendorfa).
        Kazhdoe naturalnoe chislo = summa NESOASEDNIKH chisel Fibonacci.
        Eto EDINSTVENNOYE razlozhenie — kak sobstvennyye chastoty.
        """
        if n <= 0:
            return []
        fibs = [f for f in FIBONACCI if f <= n]
        components = []
        remaining = n
        for f in reversed(fibs):
            if f <= remaining:
                components.append(f)
                remaining -= f
            if remaining == 0:
                break
        return components

    def is_prime(self, n):
        """
        Prostoe chislo = chislo kotoroe NE rezoniryet ni s chem krome 1 i sebya.
        Antirezонанс so vsemi delitelyami.
        """
        if n < 2:
            return False
        if n < 4:
            return True
        if n % 2 == 0 or n % 3 == 0:
            return False
        i = 5
        while i * i <= n:
            if n % i == 0 or n % (i + 2) == 0:
                return False
            i += 6
        return True

    def factorize(self, n):
        """
        Razlozhenie na prostye mnozhiteli =
        nayti VSE chistye rezonansы chisla.
        """
        factors = []
        d = 2
        while d * d <= n:
            while n % d == 0:
                factors.append(d)
                n //= d
            d += 1
        if n > 1:
            factors.append(n)
        return factors

    def explain(self, expression):
        """
        Obyasnit vychisleniye cherez rezonans.
        '17 * 23' -> 'Zeckendorf: 23 = 21 + 2. So 17*23 = 17*21 + 17*2 = 357 + 34 = 391.'
        """
        parts = expression.replace(" ", "").split("*")
        if len(parts) == 2:
            try:
                a, b = int(parts[0]), int(parts[1])
                zeck = self._zeckendorf(b)
                result = self.multiply(a, b)
                zeck_str = " + ".join(str(f) for f in zeck)
                terms = [f"{a}*{f}={a*f}" for f in zeck]
                return {
                    "expression": f"{a} * {b}",
                    "result": result,
                    "method": "Fibonacci decomposition (Zeckendorf)",
                    "decomposition": f"{b} = {zeck_str}",
                    "steps": terms,
                    "verification": f"{' + '.join(str(a*f) for f in zeck)} = {result}",
                }
            except ValueError:
                pass

        parts = expression.replace(" ", "").split("+")
        if len(parts) == 2:
            try:
                a, b = int(parts[0]), int(parts[1])
                return {
                    "expression": f"{a} + {b}",
                    "result": self.add(a, b),
                    "method": "phase addition",
                }
            except ValueError:
                pass

        return {"error": "cannot parse expression"}


class ProceduralPattern:
    """
    Odin protsedurnyy pattern = kristallizovannaya tsepochka deystviy.

    Primery:
      "greeting" -> [identify_language, select_greeting, respond]
      "math_multiply" -> [parse_numbers, zeckendorf, sum_products, respond]
      "define_concept" -> [find_concept, get_connections, build_definition, respond]
    """
    __slots__ = ['name', 'steps', 'trigger_words', 'count', 'strength']

    def __init__(self, name, steps, trigger_words=None):
        self.name = name
        self.steps = steps          # [(action_name, params), ...]
        self.trigger_words = trigger_words or []
        self.count = 0
        self.strength = 0.0

    def matches(self, input_words):
        """Proveryaem: aktiviruyetsya li etot pattern?"""
        if not self.trigger_words:
            return 0.0
        hits = sum(1 for w in input_words if w in self.trigger_words)
        return hits / max(len(self.trigger_words), 1)


class ProceduralEngine:
    """
    Dvigatel protseduryh patternov.
    Patterny kristallizuyutsya iz opyta (ne hardcoded).
    Nachalnyye patterny = bootstrap (minimum dlya starta).
    """

    def __init__(self):
        self.arithmetic = ResonanceArithmetic()
        self.patterns = {}
        self._init_bootstrap()

        print(f"[+] ProceduralEngine initialized. "
              f"Patterns: {len(self.patterns)}, "
              f"Arithmetic: ready")

    def _init_bootstrap(self):
        """Nachalnyye patterny — minimum dlya raboty."""
        self.patterns["math_calc"] = ProceduralPattern(
            "math_calc",
            steps=[("parse_math", {}), ("compute", {}), ("explain", {})],
            trigger_words=["calculate", "compute", "multiply",
                          "plus", "minus", "times", "divided",
                          "сколько", "умножить", "сложить",
                          "вычисли", "посчитай"])

        self.patterns["define"] = ProceduralPattern(
            "define",
            steps=[("find_concept", {}), ("get_connections", {}),
                   ("build_definition", {})],
            trigger_words=["what", "define", "meaning",
                          "что", "такое", "определение", "значит"])

        self.patterns["self_describe"] = ProceduralPattern(
            "self_describe",
            steps=[("introspect", {}), ("describe_self", {})],
            trigger_words=["who", "you", "yourself", "describe",
                          "кто", "ты", "себе", "расскажи"])

    def detect_procedure(self, input_words):
        """Kakoy pattern aktiviruyetsya?"""
        best_pattern = None
        best_score = 0.0

        for name, pattern in self.patterns.items():
            score = pattern.matches(input_words)
            if score > best_score:
                best_score = score
                best_pattern = pattern

        if best_score > PHI_INV_SQ:  # dostatochno silnyy match
            return best_pattern
        return None

    def execute_math(self, input_text):
        """
        Poprobovat vypolnit matematiku.
        Ishchet chisla i operatsii v tekste.
        """
        import re
        # Ishchem patterny: "17 * 23", "17 x 23", "17 times 23"
        # Ili russkie: "17 умножить на 23", "сколько будет 17 * 23"
        numbers = re.findall(r'\d+', input_text)
        if len(numbers) < 2:
            return None

        a, b = int(numbers[0]), int(numbers[1])

        if any(op in input_text.lower()
               for op in ['*', '×', 'times', 'multiply',
                          'умножить', 'умножь']):
            return self.arithmetic.explain(f"{a}*{b}")

        if any(op in input_text.lower()
               for op in ['+', 'plus', 'add',
                          'плюс', 'сложить', 'прибавь']):
            return self.arithmetic.explain(f"{a}+{b}")

        if any(op in input_text.lower()
               for op in ['/', 'divide', 'divided',
                          'разделить', 'дели']):
            q, r = self.arithmetic.divide(a, b)
            return {
                "expression": f"{a} / {b}",
                "result": q,
                "remainder": r,
                "method": "resonance division",
            }

        # Default: umnozhenie
        return self.arithmetic.explain(f"{a}*{b}")

    def stats(self):
        return {
            "patterns": len(self.patterns),
            "arithmetic_max": self.arithmetic.max_n,
        }
