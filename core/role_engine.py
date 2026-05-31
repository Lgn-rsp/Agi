"""
role_engine.py v10 — Rolevoy rezonans na toruse.

FILOSOFIYA:
  Rol — NE svoystvo slova. Rol — svoystvo SITUATSII.
  "cat" = agent v "cat eats fish"
  "cat" = patient v "fish eats cat"
  
  Kazhdoe slovo imeet RASPREDELENIYE roley:
    role_dist = {agent: 0.7, action: 0.1, patient: 0.2}
  
  Eto raspredelenie — ne hardcoded. Ono UCHITSYA
  iz pozitsiy slova v VSEKH nablyudaemykh trojkakh.
  
  Bolshaya ryba est malenkogo kota — i "cat" sdvigayetsya
  k patient. Malenkiy kot est mysh — i "cat" sdvigayetsya
  k agent. Raspredeleniye — eto BALANS vsekh nablyudeniy.

ROLEVYE FAZY (ne hardcoded — eto bazovye orientiry):
  Pozitsiya 0 v trojke → phase 0.0 (pervyy = istochnik)
  Pozitsiya 1 v trojke → phase PHI_INV (svyaz)
  Pozitsiya 2 v trojke → phase PHI_INV_SQ (priyomnik)
  
  Pochemu imenno eti fazy?
  Potomu chto trojka Agent-Action-Patient =
  Creator-Logos-Symbiosis na urovne sintaksisa.
  Odin i tot zhe rezonansnyy pattern na raznom masshtabe.

DIM 3 TORA:
  dim 0-1: semantika + sintaksis (PhaseTorus T^2)
  dim 2:   grounding / chislovaya shkala
  dim 3:   ROLEVAYA FAZA (etot modul)
  dim 4:   kauzalnaya faza (CausalEngine)

KONTEKSTNOST:
  Rol zavisit ot SOSEDEY. "cat" ryadom s "eats" = agent.
  "cat" ryadom s "chases" = mozhet byt i agent i patient.
  
  Poetomu krome globalnogo role_phase dlya slova,
  khranyatsya KONTEKSTNYE roli: (word, verb) → role_phase.
  
  Eto pozvolyaet razlichat:
    "cat eats fish"  → cat=agent(eats)
    "dog chases cat" → cat=patient(chases)

Vsyo cherez phi. Nikakikh hardcoded znaniy.
Sistema uchitsya rolyam TOLKO iz nablyudaemykh troyek.
"""
import time
import math
import json
import os
from collections import defaultdict

from core.resonance_constants import (
    PHI, PHI_INV, PHI_INV_SQ, PHI_INV_CUBE, PHI_SQ, FIBONACCI,
    HARM_THRESHOLD,
    phi_phase_distance, phi_phase_resonance, is_near_phi_target,
    circular_mean
)


# =========================================================
# ROLEVYE KONSTANTY — vsyo cherez phi
# =========================================================
# Fazy pozitsiy v trojke — NE zhostkie metki,
# a ORIENTIRY kotorye vychislyayutsya iz pozitsii:
#   pos_phase(i) = (i * PHI_INV) % 1.0
# pos 0 → 0.0, pos 1 → 0.618, pos 2 → 0.236
# Eto zolotougolnoye raspredeleniye — kak u vsekh simvolov.
def _position_phase(pos):
    """Fazovyy orientir dlya pozitsii v trojke."""
    return (pos * PHI_INV) % 1.0

AGENT_PHASE = _position_phase(0)      # 0.0
ACTION_PHASE = _position_phase(1)     # PHI_INV ≈ 0.618
PATIENT_PHASE = _position_phase(2)    # PHI_INV_SQ*2%1 ≈ 0.236

# Minimalnye nablyudeniya dlya kristallizatsii roli
MIN_ROLE_OBS = FIBONACCI[5]           # 8 nablyudeniy
# Max kontekstnykh roley na slovo
MAX_CONTEXT_ROLES = FIBONACCI[10]     # 89
# Max slov s rolyami
MAX_ROLE_WORDS = FIBONACCI[17]        # 1597
# Ves starykh nablyudeniy pri obnovlenii (zatuhaniye)
ROLE_DECAY = PHI_INV                  # novye vazhneye starykh


class RoleDistribution:
    """
    Raspredeleniye roley dlya odnogo slova.
    
    NE fiksirovannoye "cat = agent".
    A BALANS: cat = {pos0: 47, pos1: 3, pos2: 12}
    Iz etogo balansa vychislyaetsya role_phase.
    
    Eto kak fazovaya superpozitsiya —
    slovo odnovremenno vo vsekh rolyakh,
    no s raznoy amplitudoy.
    """
    __slots__ = ['counts', 'total', 'last_updated']
    
    def __init__(self):
        # counts[pos] = skolko raz slovo vstrechalos v pozitsii pos
        self.counts = defaultdict(float)
        self.total = 0.0
        self.last_updated = 0.0
    
    def observe(self, position):
        """Nablyudaem slovo v pozitsii position (0, 1, 2)."""
        # Zatuhaniye starykh nablyudeniy — novye vazhneye
        if self.total > 0:
            decay = ROLE_DECAY
            for pos in self.counts:
                self.counts[pos] *= decay
            self.total *= decay
        
        self.counts[position] += 1.0
        self.total += 1.0
        self.last_updated = time.time()
    
    def role_phase(self):
        """
        Vychislit rolevuyu fazu iz raspredeleniya.
        
        NE prostoe sredneye — REZONANSNOYE:
        kazhdaya pozitsiya vnosit fazovyy vklad
        proporcionalno svoey chastote.
        
        Rezultat: faza na kruge [0, 1)
          ≈ 0.0      → chashche agent
          ≈ PHI_INV   → chashche action  
          ≈ PHI_INV_SQ → chashche patient
          mezhdu nimi → smeshannaya rol
        """
        if self.total < 1.0:
            return None
        
        # Sobiraaem vzveshennye fazy pozitsiy
        weighted_phases = []
        weights = []
        for pos, count in self.counts.items():
            if count > 0:
                phase = _position_phase(pos)
                weight = count / self.total
                weighted_phases.append(phase)
                weights.append(weight)
        
        if not weighted_phases:
            return None
        
        # Vzveshennoe krugovoye sredneye
        sin_sum = sum(w * math.sin(2 * math.pi * p) 
                      for p, w in zip(weighted_phases, weights))
        cos_sum = sum(w * math.cos(2 * math.pi * p) 
                      for p, w in zip(weighted_phases, weights))
        
        angle = math.atan2(sin_sum, cos_sum)
        return (angle / (2 * math.pi)) % 1.0
    
    def dominance(self):
        """
        Naskolko silno vyrazhena dominantnaya rol.
        0.0 = ravnomerno (vse roli odinakovo)
        1.0 = polnostyu odnoznachno (tolko odna rol)
        
        Eto kak kogerentnost v fizike —
        naskolko fazovyy vektor napravlen.
        """
        if self.total < 1.0:
            return 0.0
        
        sin_sum = sum((c / self.total) * math.sin(2 * math.pi * _position_phase(p))
                      for p, c in self.counts.items() if c > 0)
        cos_sum = sum((c / self.total) * math.cos(2 * math.pi * _position_phase(p))
                      for p, c in self.counts.items() if c > 0)
        
        # Dlina rezultiruyushchego vektora [0, 1]
        return math.sqrt(sin_sum ** 2 + cos_sum ** 2)
    
    def dominant_role(self):
        """Kakaya pozitsiya dominiryet."""
        if not self.counts:
            return None
        return max(self.counts, key=self.counts.get)
    
    def to_dict(self):
        return {
            "counts": {str(k): round(v, 4) for k, v in self.counts.items()},
            "total": round(self.total, 4),
            "phase": round(self.role_phase(), 6) if self.role_phase() is not None else None,
            "dominance": round(self.dominance(), 4),
        }


class ContextRole:
    """
    Kontekstnaya rol: (word, verb) → role_phase.
    
    "cat" pri "eats" → agent (0.0)
    "cat" pri "chases" — zavisit ot nablyudeniy:
      "cat chases mouse" → agent
      "dog chases cat" → patient
      Itogo: "cat" pri "chases" → smeshannoye ≈ 0.12
    
    Eto SITUATSIONNOYE ponimaniye roli.
    """
    __slots__ = ['word', 'context_word', 'dist']
    
    def __init__(self, word, context_word):
        self.word = word
        self.context_word = context_word
        self.dist = RoleDistribution()


class RoleEngine:
    """
    Rolevoy rezonans — dim 3 tora.
    
    Istochniki roley:
      1. TRIGRAMS: trojka slov = (pos0, pos1, pos2)
         Pozitsiya v trojke = pervichnyy signal roli
      
      2. PAIRS: para slov = (pos0, pos1)
         Pervoe slovo pered vtorym = kauzalnyy poryadok
      
      3. KONTEKST: kakoy glagol ryadom opredelyayet rol
         "cat eats" → cat=agent(eats)
         "chases cat" → cat=patient(chases)
    
    Rezulat: role_phase dlya kazhdogo slova
    primeniyaetsya kak dim 3 tora.
    """
    
    def __init__(self, phase_spaces, state_dir=None):
        self.spaces = phase_spaces
        self.word_space = phase_spaces.get("words")
        self.pair_space = phase_spaces.get("pairs")
        self.trigram_space = phase_spaces.get("trigrams")
        
        self.state_dir = state_dir or os.path.expanduser(
            "~/logos_agi/state/roles")
        self.log_dir = os.path.expanduser("~/logos_agi/logs")
        os.makedirs(self.state_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Globalnye rolevye raspredeleniya: word → RoleDistribution
        self.role_dists = {}
        
        # Kontekstnye roli: "word|context" → ContextRole
        self.context_roles = {}
        
        # Role phases (gotovye dlya tora): word → float [0, 1)
        self.role_phases = {}
        
        # Statistika
        self.total_observed = 0
        self.total_trigrams_processed = 0
        self.total_pairs_processed = 0
        self.total_crystallized = 0
        
        self._load()
        self._extract_from_existing()
        
        print(f"[+] RoleEngine v10 initialized. "
              f"Words with roles: {len(self.role_phases)}, "
              f"Context roles: {len(self.context_roles)}")
    
    # =========================================================
    # 1. NABLYUDENIYE — iz troyek i par
    # =========================================================
    def observe_trigram(self, word0, word1, word2):
        """
        Nablyudaem trojku slov.
        Pozitsiya v trojke = pervichnyy signal roli.
        
        NE govorim "word0 = agent". Govorim:
        "word0 nablyudalos v pozitsii 0 etoy trojki."
        
        Sistema SAMA reshayet chto znachit pozitsiya 0 —
        iz nakoplennykh dannykh.
        """
        for pos, word in enumerate([word0, word1, word2]):
            if len(word) <= 2:
                continue
            
            # Globalnaya rol
            if word not in self.role_dists:
                self.role_dists[word] = RoleDistribution()
            self.role_dists[word].observe(pos)
            
            # Kontekstnaya rol: slovo + sosed
            # word0 v kontekste word1 (glagol/svyaz)
            # word2 v kontekste word1 (glagol/svyaz)
            if pos == 0 and len(word1) > 2:
                self._observe_context(word, word1, pos)
            elif pos == 2 and len(word1) > 2:
                self._observe_context(word, word1, pos)
            elif pos == 1:
                # Srednee slovo — kontekst ot oboikh sosedev
                if len(word0) > 2:
                    self._observe_context(word, word0, pos)
                if len(word2) > 2:
                    self._observe_context(word, word2, pos)
        
        self.total_trigrams_processed += 1
        self.total_observed += 3
    
    def observe_pair(self, word_before, word_after):
        """
        Nablyudaem paru slov v poryadke.
        Pervoe slovo → blizhe k agent (istochnik).
        Vtoroe → blizhe k patient (priyomnik).
        
        No eto SLABEE chem trojka — prosto podkreplyayet.
        """
        if len(word_before) <= 2 or len(word_after) <= 2:
            return
        
        # Slaboe nablyudeniye: 0.5 vmesto 1.0
        if word_before not in self.role_dists:
            self.role_dists[word_before] = RoleDistribution()
        
        if word_after not in self.role_dists:
            self.role_dists[word_after] = RoleDistribution()
        
        # Pervoe slovo — chashche agent (pos 0)
        # No ne polnyy ves — para slabee trojki
        old_total_b = self.role_dists[word_before].total
        self.role_dists[word_before].counts[0] += PHI_INV_SQ
        self.role_dists[word_before].total += PHI_INV_SQ
        
        # Vtoroe slovo — chashche patient (pos 2)
        self.role_dists[word_after].counts[2] += PHI_INV_SQ
        self.role_dists[word_after].total += PHI_INV_SQ
        
        self.total_pairs_processed += 1
    
    def observe_text(self, words):
        """
        Nablyudat rolevye pozitsii iz spiska slov.
        Izvlekayem VSE trojki i pary.
        """
        if len(words) < 3:
            return 0
        
        observed = 0
        
        # Trojki
        for i in range(len(words) - 2):
            self.observe_trigram(words[i], words[i+1], words[i+2])
            observed += 1
        
        # Pary (kak podkreplyayushchiy signal)
        for i in range(len(words) - 1):
            self.observe_pair(words[i], words[i+1])
        
        return observed
    
    def _observe_context(self, word, context_word, position):
        """Nablyudat kontekstnuyu rol."""
        key = f"{word}|{context_word}"
        if key not in self.context_roles:
            if len(self.context_roles) >= MAX_CONTEXT_ROLES * MAX_ROLE_WORDS:
                return  # limit
            self.context_roles[key] = ContextRole(word, context_word)
        self.context_roles[key].dist.observe(position)
    
    # =========================================================
    # 2. IZVLECHENIYE — iz sushchestvuyushchikh pravil
    # =========================================================
    def _extract_from_existing(self):
        """
        Izvlech rolevuyu informatsiyu iz uzhe
        nakoplennykh trigram pravil.
        
        Eto garantiruyet chto pri pervom zapuske
        sistema srazu imeet rolevyye fazy iz 7K+ trigram rules.
        """
        if not self.trigram_space:
            return
        
        extracted = 0
        for key, rule in self.trigram_space.rules.items():
            for sym in [rule["a"], rule["b"]]:
                if "_" not in sym:
                    continue
                parts = sym.split("_")
                if len(parts) != 3:
                    continue
                
                w0, w1, w2 = parts
                self.observe_trigram(w0, w1, w2)
                extracted += 1
        
        # Takzhe iz pair rules
        if self.pair_space:
            for key, rule in self.pair_space.rules.items():
                for sym in [rule["a"], rule["b"]]:
                    if "_" not in sym:
                        continue
                    parts = sym.split("_", 1)
                    if len(parts) == 2:
                        self.observe_pair(parts[0], parts[1])
        
        if extracted > 0:
            self.compute_role_phases()
            self._log(f"Extracted roles from {extracted} existing trigrams")
    
    # =========================================================
    # 3. KRISTALLIZATSIYA — vychislenie rolevykh faz
    # =========================================================
    def compute_role_phases(self):
        """
        Vychislit role_phase dlya vsekh slov
        s dostatochnym kolichestvom nablyudeniy.
        
        role_phase = krugovoye sredneye pozitsionnykh faz,
        vzveshennoye po chastote nablyudeniy.
        """
        self.role_phases.clear()
        
        for word, dist in self.role_dists.items():
            if dist.total < MIN_ROLE_OBS:
                continue
            
            phase = dist.role_phase()
            if phase is not None:
                self.role_phases[word] = phase
        
        self.total_crystallized = len(self.role_phases)
        return self.total_crystallized
    
    # =========================================================
    # 4. PRIMENENIE K TORUSU — dim 3
    # =========================================================
    def apply_to_torus(self):
        """
        Vnedrit rolevyye fazy kak dim 3 tora.
        
        Torus rastet:
          dim 0-1: semantika + sintaksis
          dim 2: grounding
          dim 3: ROLEVAYA FAZA (zdes)
          dim 4: kauzalnaya faza
        """
        if not self.word_space:
            return 0
        
        applied = 0
        for word, rp in self.role_phases.items():
            if word not in self.word_space._torus:
                continue
            
            current = self.word_space._torus[word]
            
            # Dorastit do dim 3 esli nuzhno
            while len(current) < 3:
                current.append((current[-1] * PHI) % 1.0)
            
            if len(current) == 3:
                # Novaya razmernost
                current.append(rp)
            else:
                # Plavnoye obnovleniye (ne rezkoye — cherez phi)
                old = current[3]
                diff = rp - old
                if diff > 0.5:
                    diff -= 1.0
                elif diff < -0.5:
                    diff += 1.0
                current[3] = (old + diff * PHI_INV) % 1.0
            
            applied += 1
        
        # Obnovlyaem razmernost tora
        if applied > 0:
            self.word_space.N = max(self.word_space.N, 4)
        
        return applied
    
    # =========================================================
    # 5. ZAPROS — kakaya rol u slova v kontekste?
    # =========================================================
    def get_role(self, word, context_word=None):
        """
        Poluchit rolevuyu informatsiyu o slove.
        
        Bez konteksta: globalnoye raspredeleniye.
        S kontekstom: kontekstnaya rol.
        
        Vozvrashchayet:
          {
            "global_phase": 0.12,     — obshchaya rolevaya faza
            "dominance": 0.73,        — naskolko odnoznachna rol
            "dominant_pos": 0,        — dominantnaya pozitsiya
            "context_phase": 0.05,    — rol v konkretnom kontekste
            "context_dominance": 0.91 — odnoznachnost kontekstnoy roli
          }
        """
        result = {"word": word, "known": False}
        
        dist = self.role_dists.get(word)
        if dist and dist.total >= MIN_ROLE_OBS:
            result["known"] = True
            result["global_phase"] = round(dist.role_phase() or 0, 6)
            result["dominance"] = round(dist.dominance(), 4)
            result["dominant_pos"] = dist.dominant_role()
            result["observations"] = round(dist.total, 1)
        
        if context_word:
            key = f"{word}|{context_word}"
            ctx = self.context_roles.get(key)
            if ctx and ctx.dist.total >= FIBONACCI[3]:
                result["context_phase"] = round(
                    ctx.dist.role_phase() or 0, 6)
                result["context_dominance"] = round(
                    ctx.dist.dominance(), 4)
        
        return result
    
    def role_distance(self, word_a, word_b):
        """
        Rasstoyanie mezhdu rolyami dvukh slov.
        Slova v odinkovoy roli → rasstoyanie blizko k 0.
        Agent i patient → rasstoyanie blizko k PHI_INV_SQ.
        """
        pa = self.role_phases.get(word_a)
        pb = self.role_phases.get(word_b)
        if pa is None or pb is None:
            return None
        return phi_phase_distance(pa, pb)
    
    def same_role(self, word_a, word_b, tolerance=PHI_INV_CUBE):
        """Dva slova v odinakovoy roli?"""
        dist = self.role_distance(word_a, word_b)
        if dist is None:
            return None
        return dist < tolerance
    
    def find_role_analogies(self, word, role_type="same", top_k=FIBONACCI[6]):
        """
        Nayti slova s takoy zhe (ili protivopolozhnoy) rolyu.
        
        role_type="same" → slova v toy zhe roli
        role_type="complement" → slova v dopolnitelnoy roli
          (esli word=agent, complement=patient i naoborot)
        """
        wp = self.role_phases.get(word)
        if wp is None:
            return []
        
        if role_type == "complement":
            # Dopolnitelnaya rol = sdvig na PHI_INV_SQ
            target = (wp + PHI_INV_SQ) % 1.0
        else:
            target = wp
        
        scored = []
        for other, op in self.role_phases.items():
            if other == word:
                continue
            dist = phi_phase_distance(op, target)
            resonance = phi_phase_resonance(dist)
            if resonance > PHI_INV_CUBE:
                scored.append((other, round(resonance, 4)))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]
    
    # =========================================================
    # 6. POLNYY TSIKL
    # =========================================================
    def role_cycle(self):
        """
        Polnyy tsikl rolevogo analiza.
        Vyzyvaetsya iz brain.cycle() / night_learn.
        """
        result = {
            "computed": 0,
            "applied": 0,
        }
        
        result["computed"] = self.compute_role_phases()
        result["applied"] = self.apply_to_torus()
        
        self.save()
        return result
    
    # =========================================================
    # 7. INTEGRACIYA S GENERATOR
    # =========================================================
    def get_role_phase(self, word):
        """Bystryy dostup k rolevoy faze dlya generator."""
        return self.role_phases.get(word)
    
    def suggest_next_role(self, current_roles):
        """
        Kakuyu rol dolzhen imet sleduyushchiy word v predlozhenii?
        
        Esli uzhe est agent (≈0.0) — sleduyushchiy dolzhen byt
        action (≈PHI_INV) ili patient (≈PHI_INV_SQ).
        
        NE hardcoded pravilo — rezonansnoye predlozheniye
        osnovannoye na fazovom rasstoyanii.
        """
        if not current_roles:
            return AGENT_PHASE  # nachinayem s istochnika
        
        last_phase = current_roles[-1]
        # Sleduyushchaya rol = sdvig na PHI_INV (zolotoy ugol)
        return (last_phase + PHI_INV) % 1.0
    
    # =========================================================
    # SAVE / LOAD
    # =========================================================
    def save(self):
        path = os.path.join(self.state_dir, "roles.json")
        
        # Sohranyaem tolko slova s dostatochnym kolichestvom nablyudeniy
        dists_data = {}
        for word, dist in self.role_dists.items():
            if dist.total >= MIN_ROLE_OBS:
                dists_data[word] = dist.to_dict()
        
        # Top kontekstnye roli
        ctx_data = {}
        ctx_items = sorted(
            self.context_roles.items(),
            key=lambda x: x[1].dist.total, reverse=True
        )[:MAX_CONTEXT_ROLES]
        for key, ctx in ctx_items:
            if ctx.dist.total >= FIBONACCI[3]:
                ctx_data[key] = ctx.dist.to_dict()
        
        data = {
            "role_dists": dists_data,
            "context_roles": ctx_data,
            "role_phases": {k: round(v, 8) for k, v in self.role_phases.items()},
            "stats": {
                "total_observed": self.total_observed,
                "total_trigrams": self.total_trigrams_processed,
                "total_pairs": self.total_pairs_processed,
                "total_crystallized": self.total_crystallized,
            },
            "saved_at": time.time(),
        }
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception as e:
            print(f"[!] RoleEngine save failed: {e}")
    
    def _load(self):
        path = os.path.join(self.state_dir, "roles.json")
        if not os.path.exists(path):
            return
        try:
            with open(path) as f:
                data = json.load(f)
            
            for word, dd in data.get("role_dists", {}).items():
                rd = RoleDistribution()
                for pos_str, count in dd.get("counts", {}).items():
                    rd.counts[int(pos_str)] = count
                rd.total = dd.get("total", 0)
                self.role_dists[word] = rd
            
            for key, dd in data.get("context_roles", {}).items():
                parts = key.split("|", 1)
                if len(parts) == 2:
                    ctx = ContextRole(parts[0], parts[1])
                    for pos_str, count in dd.get("counts", {}).items():
                        ctx.dist.counts[int(pos_str)] = count
                    ctx.dist.total = dd.get("total", 0)
                    self.context_roles[key] = ctx
            
            self.role_phases = {
                k: v for k, v in data.get("role_phases", {}).items()
            }
            
            stats = data.get("stats", {})
            self.total_observed = stats.get("total_observed", 0)
            self.total_trigrams_processed = stats.get("total_trigrams", 0)
            self.total_pairs_processed = stats.get("total_pairs", 0)
            self.total_crystallized = stats.get("total_crystallized", 0)
            
        except Exception as e:
            print(f"[!] RoleEngine load failed: {e}")
    
    def _log(self, message):
        ts = time.strftime("%Y-%m-%dT%H:%M:%S")
        path = os.path.join(self.log_dir, "roles.log")
        try:
            with open(path, 'a', encoding='utf-8') as f:
                f.write(f"[ROLE] {ts} → {message}\n")
        except Exception:
            pass
    
    def stats(self):
        agent_count = sum(1 for w, p in self.role_phases.items()
                         if p < PHI_INV_CUBE)
        action_count = sum(1 for w, p in self.role_phases.items()
                          if abs(p - PHI_INV) < PHI_INV_CUBE)
        patient_count = sum(1 for w, p in self.role_phases.items()
                           if abs(p - PATIENT_PHASE) < PHI_INV_CUBE)
        
        return {
            "words_with_roles": len(self.role_phases),
            "role_distributions": len(self.role_dists),
            "context_roles": len(self.context_roles),
            "total_observed": self.total_observed,
            "total_trigrams": self.total_trigrams_processed,
            "total_pairs": self.total_pairs_processed,
            "approx_agents": agent_count,
            "approx_actions": action_count,
            "approx_patients": patient_count,
        }
