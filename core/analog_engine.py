"""
analog_engine.py v10 — Strukturnye analogii cherez rezonans.

FILOSOFIYA:
  Analogiya — eto NE skhodstvo slov.
  Analogiya — eto REZONANS MEZHDU PATTERNAMI SVYAZEY.

  king i father — raznye slova, raznye fazy.
  No SOZVEZDIYA ikh svyazey — IZOMORFNY:
    king→queen ≈ father→mother  (parnost)
    king→kingdom ≈ father→family (domen vlasti)
    king→throne ≈ father→home    (mesto sily)

  Obnaruzhit analogiyu = nayti chto DVA OBLAKA SVYAZEY
  imeyut ODNU I TU ZhE FORMU v fazovom prostranstve.

METOD — RESONANCE FINGERPRINT:
  1. Dlya kazhdogo slova stroit "otpechatok" —
     raspredeleniye ego sosedey po fazovym kharakteristikam:
       - fazovoe rasstoyanie (dim 0)
       - rolevaya faza (dim 3)
       - kauzalnaya faza (dim 4)

  2. Otpechatok = vektor iz FIBONACCI[7]=21 komponentov.
     Kazhdyy komponent = plotnost sosedey v sektore.
     Sektory = PHI-razbieniye kruga [0, 1).

  3. Sravnenie otpechatkov = korrelyatsiya na kruge.
     Vysokaya korrelyatsiya = analogiya.

MAPPING:
  Kogda A≈C (analogichnyye slova), nayti B' takoe chto
  A:B :: C:B'

  B = sosed A s opredelyonnoy pozitsiey v sozvezdii A.
  B' = sosed C s TAKOY ZhE pozitsiey v sozvezdii C.

  "Pozitsiya v sozvezdii" = (distance, role_phase, causal_phase).

TRI UROVNYA ANALOGII:
  L1: Rolevaya — odinakova rol (agent:agent, patient:patient)
  L2: Strukturnaya — izomorfizm sosedstv (king≈father)
  L3: Glubokaya — rezonans cherez domeny (atom≈solar_system)

Vsyo cherez phi. Nikakikh hardcoded znaniy.
Sistema obnaruzhivayet analogii TOLKO iz struktury svyazey.
"""
import time
import math
import json
import os
from collections import defaultdict

from core.resonance_constants import (
    PHI, PHI_INV, PHI_INV_SQ, PHI_INV_CUBE, PHI_SQ, FIBONACCI,
    phi_phase_distance, phi_phase_resonance, is_near_phi_target,
    circular_mean
)


# =========================================================
# KONSTANTY
# =========================================================
FINGERPRINT_BINS = FIBONACCI[6]       # 13 sektorov v otpechatke
MIN_NEIGHBORS = FIBONACCI[4]          # 5 sosedey minimum
MAX_FINGERPRINTS = FIBONACCI[17]      # 1597
ANALOG_THRESHOLD = PHI_INV_SQ         # 0.382 — minimum dlya analogii
STRONG_ANALOG = PHI_INV               # 0.618 — silnaya analogiya
MAX_ANALOGS_CACHED = FIBONACCI[14]    # 610
MAP_TOP_K = FIBONACCI[5]              # 8 luchshikh mappingov


class Fingerprint:
    """
    Rezonansnyy otpechatok slova — forma ego sozvezdiya svyazey.

    NE konkretnye sosedi — a RASPREDELENIYE sosedey
    po fazovym kharakteristikam.

    Eto kak spektr zvezdy — ne vazhno kakaya eto zvezda,
    vazhna FORMA spektra. Dve zvezdy s odinakovym spektrom =
    odinakovyy khimicheskiy sostav.

    Dva slova s odinakovym otpechatkom =
    odinakovaya STRUKTURA svyazey.
    """
    __slots__ = [
        'word', 'bins_dist', 'bins_role', 'bins_causal',
        'n_neighbors', 'avg_distance', 'role_diversity',
        'timestamp'
    ]

    def __init__(self, word):
        self.word = word
        # Tri gistogrammy po FINGERPRINT_BINS sektorov
        self.bins_dist = [0.0] * FINGERPRINT_BINS    # po fazovym rastoyaniyam
        self.bins_role = [0.0] * FINGERPRINT_BINS     # po rolevym fazam sosedey
        self.bins_causal = [0.0] * FINGERPRINT_BINS   # po kauzalnym fazam sosedey
        self.n_neighbors = 0
        self.avg_distance = 0.0
        self.role_diversity = 0.0
        self.timestamp = 0.0

    def similarity(self, other):
        """
        Skhodstvo dvukh otpechatkov.

        NE evklidovo rasstoyanie — KRUGOVAYA KORRELYATSIYA.
        Potomu chto fazy na kruge: [0, 1) = torus.

        Tri komponenta vzvesheny cherez phi:
          dist_sim * PHI_INV +
          role_sim * PHI_INV_SQ +
          causal_sim * PHI_INV_CUBE

        Eto daeyt prioritet: semantika > roli > kauzalnost.
        """
        d_sim = _circular_correlation(self.bins_dist, other.bins_dist)
        r_sim = _circular_correlation(self.bins_role, other.bins_role)
        c_sim = _circular_correlation(self.bins_causal, other.bins_causal)

        # Penalty za raznoe kolichestvo sosedey
        n_ratio = min(self.n_neighbors, other.n_neighbors) / max(
            self.n_neighbors, other.n_neighbors, 1)
        n_penalty = PHI_INV_SQ + n_ratio * PHI_INV_SQ  # [PHI_INV_SQ, 1.0]

        combined = (d_sim * PHI_INV +
                    r_sim * PHI_INV_SQ +
                    c_sim * PHI_INV_CUBE) * n_penalty

        return max(0.0, min(1.0, combined))


def _circular_correlation(bins_a, bins_b):
    """
    Korrelyatsiya dvukh gistogramm na kruge.

    Eto NE Pearson correlation — eto fazovaya kogerentnost.
    Proveryayem sovpadeniye FORMY, ne znacheniy.

    1. Normalizuyem obe gistogrammy (summa = 1)
    2. Schitaem overlap: sum(min(a_i, b_i))
    3. overlap = 1.0 = identichnye formy
       overlap = 0.0 = polnostyu raznye

    Takzhe proveryaem SDVINUTUYU korrelyatsiyu —
    mozhet byt oba oblaka odinakovy no sdvinuty na phi.
    Eto vazhno: king i father mogut imet odinakuyu formu
    no sdvinutuyu na zolotoy ugol.
    """
    n = len(bins_a)
    if n == 0:
        return 0.0

    # Normalizatsiya
    sum_a = sum(bins_a) or 1.0
    sum_b = sum(bins_b) or 1.0
    na = [x / sum_a for x in bins_a]
    nb = [x / sum_b for x in bins_b]

    # Pryamoy overlap
    direct = sum(min(na[i], nb[i]) for i in range(n))

    # Proverka sdvigov: 1, 2, 3 bina (zolotougolnye sdvigi)
    best = direct
    for shift in [1, 2, int(n * PHI_INV)]:
        shifted = sum(min(na[i], nb[(i + shift) % n]) for i in range(n))
        if shifted > best:
            best = shifted * PHI_INV  # penalty za sdvig

    return best


class AnalogEngine:
    """
    Dvizhok analogiy cherez rezonans.

    Tri operatsii:
      1. FINGERPRINT: postroit otpechatok dlya slova
      2. FIND_ANALOG: nayti slova s pokhozhim otpechatkom
      3. MAP_ANALOG: A:B :: C:? — nayti ? cherez mapping pozitsiy

    Integriruetsya s:
      - PhaseTorus (fazovye rasstoyaniya, dim 0-1)
      - RoleEngine (rolevye fazy, dim 3)
      - CausalEngine (kauzalnye fazy, dim 4)
      - ChainEngine (graf svyazey dlya sosedey)
    """

    def __init__(self, phase_spaces, role_engine=None,
                 causal_engine=None, state_dir=None):
        self.spaces = phase_spaces
        self.word_space = phase_spaces.get("words")
        self.role_engine = role_engine
        self.causal_engine = causal_engine
        self.state_dir = state_dir or os.path.expanduser(
            "~/logos_agi/state/analogs")
        self.log_dir = os.path.expanduser("~/logos_agi/logs")
        os.makedirs(self.state_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)

        # Cache otpechatkov: word → Fingerprint
        self.fingerprints = {}

        # Cache analogiy: word → [(other_word, similarity)]
        self.analogy_cache = {}

        # Graf sosedey (iz word_space rules)
        self._graph = defaultdict(dict)  # word → {neighbor: count}

        # Statistika
        self.total_fingerprints = 0
        self.total_analogies_found = 0
        self.total_mappings = 0

        self._build_graph()
        self._load()

        print(f"[+] AnalogEngine v10 initialized. "
              f"Graph: {len(self._graph)} nodes, "
              f"Fingerprints: {len(self.fingerprints)}")

    # =========================================================
    # 1. GRAF SOSEDEY
    # =========================================================
    def _build_graph(self):
        """Postroit graf sosedey iz word_space rules."""
        self._graph.clear()
        if not self.word_space:
            return
        for key, rule in self.word_space.rules.items():
            a, b = rule["a"], rule["b"]
            count = rule.get("count", 1)
            self._graph[a][b] = count
            self._graph[b][a] = count

    def rebuild_graph(self):
        """Perepostroit graf (posle novykh pravil)."""
        self._build_graph()

    # =========================================================
    # 2. FINGERPRINT — postroit otpechatok
    # =========================================================
    def compute_fingerprint(self, word):
        """
        Postroit rezonansnyy otpechatok slova.

        Otpechatok = tri gistogrammy:
          1. bins_dist: raspredeleniye sosedey po fazovym rasstoyaniyam
          2. bins_role: raspredeleniye sosedey po rolevym fazam
          3. bins_causal: raspredeleniye sosedey po kauzalnym fazam

        Kazhdaya gistogramma imeet FINGERPRINT_BINS=13 sektorov.
        Sektor = odin iz 13 PHI-raznesennykh uglov na kruge.

        Pochemu 13? Eto FIBONACCI[6] — optimalnoe pokrytie kruga.
        """
        neighbors = self._graph.get(word, {})
        if len(neighbors) < MIN_NEIGHBORS:
            return None

        fp = Fingerprint(word)
        fp.timestamp = time.time()

        word_phase = self.word_space._get_phase(word) if self.word_space else None
        if word_phase is None:
            return None

        total_dist = 0.0
        role_phases_seen = set()

        for neighbor, count in neighbors.items():
            n_phase = self.word_space._get_phase(neighbor)
            if n_phase is None:
                continue

            # Weight = log-phi chastoty
            weight = math.log(1 + count) / math.log(PHI)

            # 1. Fazovoe rasstoyanie
            dist = phi_phase_distance(word_phase, n_phase)
            bin_idx = int(dist * FINGERPRINT_BINS) % FINGERPRINT_BINS
            fp.bins_dist[bin_idx] += weight
            total_dist += dist

            # 2. Rolevaya faza soseda
            if self.role_engine:
                role_p = self.role_engine.get_role_phase(neighbor)
                if role_p is not None:
                    r_bin = int(role_p * FINGERPRINT_BINS) % FINGERPRINT_BINS
                    fp.bins_role[r_bin] += weight
                    role_phases_seen.add(r_bin)

            # 3. Kauzalnaya faza soseda
            if self.causal_engine:
                causal_p = self.causal_engine.causal_phases.get(neighbor)
                if causal_p is not None:
                    c_bin = int(causal_p * FINGERPRINT_BINS) % FINGERPRINT_BINS
                    fp.bins_causal[c_bin] += weight

            fp.n_neighbors += 1

        if fp.n_neighbors < MIN_NEIGHBORS:
            return None

        fp.avg_distance = total_dist / fp.n_neighbors
        fp.role_diversity = len(role_phases_seen) / FINGERPRINT_BINS

        self.fingerprints[word] = fp
        self.total_fingerprints += 1
        return fp

    # =========================================================
    # 3. FIND ANALOG — nayti analogichnyye slova
    # =========================================================
    def find_analogs(self, word, top_k=FIBONACCI[5]):
        """
        Nayti slova strukturno analogichnyye dannomu.

        NE ishchem sinonomy (blizkie fazy).
        Ishchem slova s POKHOZHEY FORMOY SVYAZEY
        nezavisimo ot ikh fazovoy pozitsii.

        king i father mogut byt daleko drug ot druga na toruse,
        no ikh sozvezdiya svyazey — izomorfny.
        """
        fp = self.fingerprints.get(word)
        if not fp:
            fp = self.compute_fingerprint(word)
        if not fp:
            return []

        # Sravnivaem so vsemi otpechatkami
        scored = []
        for other_word, other_fp in self.fingerprints.items():
            if other_word == word:
                continue

            sim = fp.similarity(other_fp)
            if sim >= ANALOG_THRESHOLD:
                scored.append((other_word, round(sim, 4)))

        scored.sort(key=lambda x: x[1], reverse=True)
        result = scored[:top_k]

        if result:
            self.analogy_cache[word] = result
            self.total_analogies_found += len(result)

        return result

    # =========================================================
    # 4. MAP ANALOG — A:B :: C:?
    # =========================================================
    def map_analog(self, word_a, word_b, word_c, top_k=FIBONACCI[4]):
        """
        Analogicheskoye otobrazheniye: A:B :: C:?

        Metod:
          1. Naydyom pozitsiyu B v sozvezdii A
             (rasstoyanie, rolevaya delta, kauzalnaya delta)
          2. Ishchem v sozvezdii C slovo s TAKOY ZhE pozitsiey
          3. Eto i est otvet

        Primer:
          king:queen :: father:?
          1. queen v sozvezdii king: dist=0.12, role_delta=+PHI_INV_SQ
          2. V sozvezdii father ishchem: dist≈0.12, role_delta≈+PHI_INV_SQ
          3. Naydeno: mother (dist=0.11, role_delta=+PHI_INV_SQ)

        Eto rabotayet BEZ znaniya chto queen=zhenshchina.
        Tolko cherez STRUKTURU svyazey.
        """
        if not self.word_space:
            return []

        # Pozitsiya B v sozvezdii A
        pos_b = self._position_in_constellation(word_a, word_b)
        if pos_b is None:
            return []

        # Sosedi C (first-order constellation)
        neighbors_c = dict(self._graph.get(word_c, {}))  # copy for 2-hop merge

        # Ishchem v sozvezdii C slovo s pokhozhey pozitsiey
        candidates = []
        for candidate, count in neighbors_c.items():
            if candidate in (word_a, word_b, word_c):
                continue

            pos_cand = self._position_in_constellation(word_c, candidate)
            if pos_cand is None:
                continue

            # Skhodstvo pozitsiy
            sim = self._position_similarity(pos_b, pos_cand)
            if sim > PHI_INV_CUBE:
                candidates.append((candidate, round(sim, 4), "L1"))

        # FIX 2026-04-23: second-order fallback когда direct neighbors не дают
        # ответа. Раньше analogy ограничивалась direct neighbors of C — если
        # аналогичного слова нет среди них, map_analog возвращал []. Теперь
        # расширяем поиск до neighbors-of-neighbors (L2) с PHI_INV weight
        # penalty. Это работает в духе резонанса: слабее связанные слова
        # получают меньший вес, но могут пройти порог на structural similarity.
        if len(candidates) == 0:
            l2_seen = set(neighbors_c.keys()) | {word_a, word_b, word_c}
            for hop1 in list(neighbors_c.keys()):
                for hop2 in self._graph.get(hop1, {}).keys():
                    if hop2 in l2_seen:
                        continue
                    l2_seen.add(hop2)
                    pos_cand = self._position_in_constellation(word_c, hop2)
                    if pos_cand is None:
                        continue
                    sim = self._position_similarity(pos_b, pos_cand) * PHI_INV
                    # Пенальти × PHI_INV = 0.618 (one hop removed)
                    if sim > PHI_INV_CUBE:
                        candidates.append((hop2, round(sim, 4), "L2"))

        candidates.sort(key=lambda x: x[1], reverse=True)
        # Dedup: one entry per candidate (keep best)
        seen = {}
        for w, s, layer in candidates:
            if w not in seen or s > seen[w][0]:
                seen[w] = (s, layer)
        result = [(w, s) for w, (s, _) in
                  sorted(seen.items(), key=lambda x: x[1][0], reverse=True)][:top_k]

        if result:
            self.total_mappings += 1
            self._log(f"MAP: {word_a}:{word_b} :: {word_c}:? → "
                      f"{[w for w, s in result[:3]]}")

        return result

    def _position_in_constellation(self, center, target):
        """
        Pozitsiya target v sozvezdii center.

        Tri koordinaty:
          1. dist: fazovoe rasstoyanie ot center
          2. role_delta: raznitsa rolevykh faz
          3. causal_delta: raznitsa kauzalnykh faz

        Eto "adres" v sozvezdii — nezavisimyy ot
        absolyutnoy pozitsii na toruse.
        """
        if not self.word_space:
            return None

        center_phase = self.word_space._get_phase(center)
        target_phase = self.word_space._get_phase(target)
        if center_phase is None or target_phase is None:
            return None

        # 1. Fazovoe rasstoyanie
        dist = phi_phase_distance(center_phase, target_phase)

        # 2. Rolevaya delta
        role_delta = 0.0
        if self.role_engine:
            rc = self.role_engine.get_role_phase(center)
            rt = self.role_engine.get_role_phase(target)
            if rc is not None and rt is not None:
                role_delta = phi_phase_distance(rc, rt)

        # 3. Kauzalnaya delta
        causal_delta = 0.0
        if self.causal_engine:
            cc = self.causal_engine.causal_phases.get(center, 0)
            ct = self.causal_engine.causal_phases.get(target, 0)
            causal_delta = phi_phase_distance(cc, ct)

        # 4. Napravleniye (target_phase - center_phase, so znakom)
        direction = target_phase - center_phase
        if direction > 0.5:
            direction -= 1.0
        elif direction < -0.5:
            direction += 1.0

        return {
            "dist": dist,
            "role_delta": role_delta,
            "causal_delta": causal_delta,
            "direction": direction,
        }

    def _position_similarity(self, pos_a, pos_b):
        """
        Skhodstvo dvukh pozitsiy v sozvezdiyakh.

        Chem blizhe (dist, role_delta, causal_delta) —
        tem vyshe skhodstvo.

        Vzveshennoye cherez phi:
          dist_sim * PHI_INV +
          role_sim * PHI_INV_SQ +
          causal_sim * PHI_INV_CUBE +
          direction_sim * PHI_INV_CUBE
        """
        # Delta po kazhdomu parametru
        d_dist = abs(pos_a["dist"] - pos_b["dist"])
        d_role = abs(pos_a["role_delta"] - pos_b["role_delta"])
        d_causal = abs(pos_a["causal_delta"] - pos_b["causal_delta"])
        d_dir = abs(pos_a["direction"] - pos_b["direction"])
        if d_dir > 0.5:
            d_dir = 1.0 - d_dir

        # Konvertiruyem delty v skhodstva [0, 1]
        sim_dist = max(0, 1.0 - d_dist / PHI_INV_CUBE)
        sim_role = max(0, 1.0 - d_role / PHI_INV_CUBE)
        sim_causal = max(0, 1.0 - d_causal / PHI_INV_CUBE)
        sim_dir = max(0, 1.0 - d_dir / PHI_INV_CUBE)

        combined = (sim_dist * PHI_INV +
                    sim_role * PHI_INV_SQ +
                    sim_causal * PHI_INV_CUBE +
                    sim_dir * PHI_INV_CUBE)

        return combined

    # =========================================================
    # 5. BATCH OPERATSII
    # =========================================================
    def compute_all_fingerprints(self, min_neighbors=MIN_NEIGHBORS):
        """Vychislit otpechatki dlya vsekh slov s dostatochnym okruzheniyem."""
        computed = 0
        for word in list(self._graph.keys()):
            if len(self._graph[word]) >= min_neighbors:
                if word not in self.fingerprints:
                    fp = self.compute_fingerprint(word)
                    if fp:
                        computed += 1
        return computed

    def scan_analogies(self, top_per_word=FIBONACCI[3]):
        """
        Skanirovat vse otpechatki i nayti analogii.
        Udobno dlya nochnogo tsikla.
        """
        found = 0
        for word in list(self.fingerprints.keys()):
            analogs = self.find_analogs(word, top_k=top_per_word)
            if analogs:
                found += len(analogs)
        return found

    # =========================================================
    # 6. POLNYY TSIKL
    # =========================================================
    def analog_cycle(self):
        """
        Polnyy tsikl analogiy.
        Vyzyvaetsya iz brain.cycle() / night_learn.
        """
        result = {
            "new_fingerprints": 0,
            "analogies_found": 0,
        }

        # 1. Postroit novye otpechatki
        result["new_fingerprints"] = self.compute_all_fingerprints()

        # 2. Skanirovat analogii (tolko dlya novykh)
        if result["new_fingerprints"] > 0:
            result["analogies_found"] = self.scan_analogies()

        self.save()
        return result

    # =========================================================
    # SAVE / LOAD
    # =========================================================
    def save(self):
        path = os.path.join(self.state_dir, "analogs.json")
        fp_data = {}
        for word, fp in self.fingerprints.items():
            fp_data[word] = {
                "bins_dist": [round(x, 4) for x in fp.bins_dist],
                "bins_role": [round(x, 4) for x in fp.bins_role],
                "bins_causal": [round(x, 4) for x in fp.bins_causal],
                "n_neighbors": fp.n_neighbors,
                "avg_distance": round(fp.avg_distance, 6),
                "role_diversity": round(fp.role_diversity, 4),
            }

        cache_data = {}
        for word, analogs in self.analogy_cache.items():
            cache_data[word] = analogs[:FIBONACCI[5]]

        data = {
            "fingerprints": fp_data,
            "analogy_cache": cache_data,
            "stats": {
                "total_fingerprints": self.total_fingerprints,
                "total_analogies_found": self.total_analogies_found,
                "total_mappings": self.total_mappings,
            },
            "saved_at": time.time(),
        }
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception as e:
            print(f"[!] AnalogEngine save failed: {e}")

    def _load(self):
        path = os.path.join(self.state_dir, "analogs.json")
        if not os.path.exists(path):
            return
        try:
            with open(path) as f:
                data = json.load(f)
            for word, fpd in data.get("fingerprints", {}).items():
                fp = Fingerprint(word)
                fp.bins_dist = fpd.get("bins_dist", [0.0] * FINGERPRINT_BINS)
                fp.bins_role = fpd.get("bins_role", [0.0] * FINGERPRINT_BINS)
                fp.bins_causal = fpd.get("bins_causal", [0.0] * FINGERPRINT_BINS)
                fp.n_neighbors = fpd.get("n_neighbors", 0)
                fp.avg_distance = fpd.get("avg_distance", 0)
                fp.role_diversity = fpd.get("role_diversity", 0)
                self.fingerprints[word] = fp
            self.analogy_cache = data.get("analogy_cache", {})
            stats = data.get("stats", {})
            self.total_fingerprints = stats.get("total_fingerprints", 0)
            self.total_analogies_found = stats.get("total_analogies_found", 0)
            self.total_mappings = stats.get("total_mappings", 0)
        except Exception as e:
            print(f"[!] AnalogEngine load failed: {e}")

    def _log(self, message):
        ts = time.strftime("%Y-%m-%dT%H:%M:%S")
        path = os.path.join(self.log_dir, "analogs.log")
        try:
            with open(path, 'a', encoding='utf-8') as f:
                f.write(f"[ANALOG] {ts} → {message}\n")
        except Exception:
            pass

    def stats(self):
        return {
            "graph_nodes": len(self._graph),
            "fingerprints": len(self.fingerprints),
            "cached_analogies": len(self.analogy_cache),
            "total_fingerprints": self.total_fingerprints,
            "total_analogies_found": self.total_analogies_found,
            "total_mappings": self.total_mappings,
        }
