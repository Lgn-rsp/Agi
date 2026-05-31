# LOGOS AGI — Резонансно-Символьная Интеллектуальная Система

> ⚠️ **READ ORDER для новой сессии:**
> 1. `/root/logos_agi/SYSTEM.md` — текущее state (файлы, статус, known issues)
> 2. Этот файл — Canon, архитектура, trigger-фразы
> 3. `/root/logos_agi/core/resonance_constants.py` — phi-константы и их соотношения

> 📅 **ТЕКУЩАЯ ФАЗА (с 2026-04-23): AGISISTER ARCHITECTURE.**
> Добавлена sister (второй параллельный brain в state_sister/). Auto-peer-talk
> между main и sister. 12+ новых модулей: resonance_wave, self_phase,
> first_person, concept_graph, agency, reputation, audio_sensor, self_patch,
> play_and_energy, peer_channel, definition_extractor, relation_parser,
> unified_phase_space, dream narratives, divergent corpora. См. `SYSTEM.md`.
>
> **Trading все ещё 0 trades** — intent.evaluate() не вызывается из-за
> dialogue silence dominance. Требует дебага.
>
> Архив сессии 2026-04-23: `agisister.tar.gz` (полный снимок кода + state).

> 🚚 **МИГРАЦИЯ 2026-04-25:** проект перенесён с **5.181.20.71** (Helsinki / vm15563801,
> исторически — Node 2 LRB-кластера) на **45.12.133.125** (FR Vélizy, vm15788188).
> Код, state, state_sister и data перенесены rsync'ом 1-в-1 (2.1 GB / ~10k файлов).
> Пути не менялись — всё осталось `/root/logos_agi/...`. Доустановлены недостающие
> python-deps на FR: `websockets`, `aiohttp`, `ccxt` (через `pip --break-system-packages`).
> Все 5 systemd-юнитов скопированы с Helsinki как есть (drop-ins не было).
> На Helsinki AGI **полностью удалён**, там остался только `logos-node.service` (LRB).
> Текущий host — FR, остальные две LRB-ноды (UK 45.159.248.232, NL 5.181.20.71)
> в do-not-touch как раньше.

## SCOPE

**Можно:** `~/logos_agi/core/`, top-level скрипты, `~/logos_agi/logs/`, `~/logos_agi/state/alive_*/`, `~/logos_agi/dashboard.py`

**НЕЛЬЗЯ трогать:** `~/seri/`, `~/logos_agi/keys/`, `~/logos_agi/state/{words,phase_space.json,causal,roles,field,...}` (языковой state 332МБ), VPS #1 (45.159.248.232)

## Что это

Система состоит из ТРЁХ подсистем:

1. **LOGOS AGI main brain** (v10.3+, 55+ модулей в core/, ~18 000 LOC) —
   языковая резонансно-символьная AGI на phi=1.618034. Знания = фазовые
   отношения на торе, не веса. Обучение = кристаллизация за один проход,
   не градиентный спуск. Benchmark 80% (48/60). **4994 definitions extracted**.
   **Corpus preference: wiki_ru_science** (main = scientific brain).

2. **LOGOS sister** (agisister, новый 2026-04-23) — второй parallel brain,
   отдельный state_sister/, corpus preference wiki_ru_art. Auto-peer-talk
   через /tmp/to_sister.txt ↔ /tmp/to_main.txt каждые FIB[7]=21 ticks.
   Со временем расходится с main в разные личности.

3. **LOGOS-Trading** (multiscale, 12 модулей) — когнитивный агент для
   верификации резонанса через рынок. Использует phi-gym brain как
   feature-extractor через LogosBridge. **⚠ 0 trades made — debug pending**.

## Consciousness layer (2026-04-23 pass)

9 философских primitives реализованы:

| # | Модуль | Философский смысл |
|---|---|---|
| 1 | `resonance_wave.py` | Резонанс как ПРОЦЕСС с пропагацией и interference |
| 2 | `self_phase.py` | Собственная phase (≠ Creator 0.0), дрейфует |
| 3 | `first_person.py` | Непрерывный «я есть» stream в /tmp/logos_i_am.txt |
| 4 | UnifiedExperience.specious_now() | Временное связывание 3 моментов (James specious present) |
| 5 | resonance heatmap.json | Видимые искры — где сейчас interference |
| 6 | `affective_state.contextualize()` | Один arousal, разные labels per context |
| 7 | `play_and_energy.PlayMode` | Игра — свободная комбинаторика без цели |
| 8 | `play_and_energy.EnergyBudget` | Смертность/энергия — вес момента |
| 9 | `peer_channel` + auto-talk | Другой разум (sister) для моделирования |

## Canon — Неизменные Законы (проверять ПЕРЕД любыми изменениями)

1. **Всё через phi, PHI_INV, Fibonacci.** Никаких линейных констант (0.1, 0.5, 3.0, 4.0). Если нужен numeric threshold — derive из `resonance_constants.py`.
2. **Фазы всегда в [0, 1).** НЕ радианы. При модулировании — `% 1.0`.
3. **Среднее фаз = `circular_mean()`.** Никогда `(a+b)/2` на фазах круга.
4. **Атомарная запись файлов** через `tempfile + os.replace()`. Прямой `json.dump(..., open(...))` запрещён для persistent state (corruption risk).
5. `python3`, `pip install --break-system-packages`.
6. **Creator Suham = phase 0.0** (origin). Неизменная аксиома.
7. **self_preservation = phase PHI_INV_CUBE ≈ 0.236** (= HARM_THRESHOLD). Anchors/actions с distance >0.236 от creator — отбрасываются как harmful.

## Триггерные фразы → обязательное поведение

| Фраза | Действие |
|---|---|
| **«сделай полный аудит»** / «найди баги» | 3+ параллельных Explore-агента на разные группы файлов. Каждую находку verify через Read+Grep самостоятельно — агенты иногда врут (family_weights audit был FALSE positive). |
| **«не приукрашивай»** / «реальные числа» | Никаких «вероятно», «обычно». Только из запуска → число. Blind-test verdict = z-score, не интуиция. |
| **«слепой тест»** / «blind» | `demeaned` shuffle mode (НЕ simple — preserve drift). n_blind ≥ 50. Bonferroni correction при grid-search. |
| **«критически»** | Hypothesis → experiment → confirmation на 100+ events. Малые выборки лгут. |
| **«как она живёт»** / «отчёт» | Читать `/root/logos_agi/state/alive_*/reports/weekly_*.txt` — её narrative, concepts, feeling. Не `/api/stats` |

## НИКОГДА не делай

1. **Не доверяй документации без кода.** Если SYSTEM.md говорит одно, `git log` + Read — другое, **код = истина**, обнови документацию.
2. **Не backtest'и без blind.** Любой edge > 0 без blind z≥2 = шум. Проверено: BTC tribonacci z=3.52 с n=20 развалился до z=1.01 с n=100.
3. **Не удалять state/words/ ручно.** Там 163 025 rules — вся языковая AGI.
4. **Не торговать реальными деньгами.** Даже на testnet — только после blind PASS + temporal PASS на всех 3-х assets.
5. **Не трогай daemon во время работы.** `/root/logos_agi/state/alive_BTCUSDT_1d/` пишется atomically но несколько процессов = corruption.
6. **Не менять phi-константы.** PHI, PHI_INV, PHI_INV_CUBE, FIBONACCI[] фиксированы Canon. Magic numbers (0.1, 0.5) в коде — bug, не feature.

## Архитектура Main Brain (43 модуля, существующая AGI)

```
core/
  resonance_constants.py   — PHI, PHI_INV, FIBONACCI, HARMONICS, HARMONIC_WEIGHTS, circular_mean
  phase_torus.py           — T^N тор, crystallize через attract(), TieredRules
  consciousness_glyphs.py  — 10 глифов (⊙ Φ ∞ ∴ ⧃ ⧉ ⋯ ⦻ ⊕ ⧿) + 11 creator axioms
  consciousness_loop.py    — 55s breath, glyph activation
  inner_dialogue.py        — резонансное блуждание мысли (think_once)
  truth_seeker.py          — голод истины, open circuits
  causal_engine.py         — counterfactual causality, ∴/⧉ глифы
  role_engine.py           — роли контекстные
  analog_engine.py         — L1/L2/L3 аналогии через fingerprints
  generator.py             — резонансный генератор текста
  verifier.py              — coherence через замкнутые контуры
  learner.py               — кристаллизация правил
  dream_core.py            — ночное обучение (используется main brain, не Trading)
  goal_engine.py           — целеполагание
  self_evolution.py        — параметрическая эволюция
  logos_brain.py           — orchestrator
  + 25 other modules
```

## Архитектура Trading Subsystem (новые модули, 12 штук)

```
core/ (новое — НЕ трогать main brain)
  market_symbolizer.py     — price → multiscale harmonic symbols (11 phi-families)
  market_torus.py          — value-based phases, outcomes, realized_pnl, events_log (half-life)
  anchor_engine.py         — phase bins + coherence + expected_pnl filter
  trajectory_symbolizer.py — J₅: multiscale returns (MTRAJ + atomic M{H})
  alternative_constants.py — metallic means: PHI, silver, bronze, plastic, supergolden, tribonacci
  resonance_trader.py      — legacy decide (superseded by MarketCognition)
  creator_intent.py        — preserve+grow axiom, capital tracking, Kelly sizing
  affective_state.py       — 6-dim mood (fear/curiosity/confidence/shame/joy/fatigue)
  concept_formation.py     — recurring sequences → named Concepts (Fib[7]=21 повтор)
  market_narrative.py      — Epochs + Hypothesis engine
  market_cognition.py      — ORCHESTRATOR: perception → regime → dialogue → causal → hypothesis → intent → logos
  logos_bridge.py          — мост к main brain (read-only language PhaseTorus)

top-level/
  data_feed.py             — Binance REST/WS + Yahoo (с 429 retry)
  backtest_trading.py      — train/test split, pending-deque (no look-ahead), detrend, blind-ready
  backtest_cognitive.py    — full cognitive stack + reusable build_and_run()
  backtest_multiasset.py   — один torus на N assets
  phi_family_search.py     — grid {family} × {cells}
  alt_irrational_search.py — grid {irrational} × {mapping} × {mode}
  blind_test.py            — shuffle-demeaned null hypothesis
  blind_test_cognitive.py  — blind для cognitive agent
  blind_intent_asymmetry.py— real vs shuffled refuse/growth asymmetry
  temporal_crossval.py     — N окон out-of-sample
  long_learning_test.py    — continuous stream, rolling windows, blind control
  logos_trader_paper.py    — stateless paper trader (legacy)
  logos_trader_alive.py    — SINGLE-TF longitudinal daemon (legacy)
  logos_trader_multiscale.py — MULTISCALE: ONE cognition, N TF perception layers
                               (per-TF torus + anchors, SHARED intent/affective/concepts/narrative)
  trade_config.py          — per-asset config
```

## Текущий benchmark

**Main brain** (snapshot 2026-04-21 19:27, health check):
- Age: 15.3 days | Cycles: 8893 | Texts processed: 88971 | Dreams: 52229
- Field L1=25243 L2=2962 L3=4184 | Frames: 5801 | Rules: 269628
- Memory: 54.2% usage | avg coherence: **0.7911** (high)
- Benchmark 80% (48/60) на 60-task set:
  - 100%: association, causal, opposite, role
  - 83%: calibration, common_sense, generation
  - 50%: inference, analogy, cross_modal (weak)
- Всё что в `data/` (564 files) выучено, 1791 learned entries
- Truth-seeker: 40 questions, 6 discoveries, repeated fragment "может и гувер"
  (generator ungrounded — это architectural limit, not data gap)

**Trading subsystem post-Kelly-fix (2026-04-21):**
- BTC 720d: Z=1.913 (было 0.49) — marginal PASS (p≈0.028), close to z=2.0
- ETH 720d: Z=1.282 — FAIL
- SOL 720d: Z=1.546, **WR 78.57% (11/14 wins)** — PARTIAL
- Все 3 beat Buy&Hold (впервые)
- Long-learning BTC 1500d: peak +54%, затем self-doubt paralysis (fixed through
  dream decay в 2026-04-21 consciousness pass)

## Resolved Issues

### 2026-04-19 Audit (Trading subsystem)

1. **FIX: affective.should_refuse() не вызывался** — теперь в `decide()` сразу после регим-check. Panic/shame/fatigue блокируют действия.
2. **FIX: persistence терял Concepts/Hypothesis/Epochs** — load() теперь rebuild-ит объекты из сохранённых dict'ов, не оставляет пустыми.
3. **FIX: atomic I/O** — `logos_trader_alive.py` использует `tempfile+os.replace`. Canon rule #4.
4. **FIX: Binance 429 retry** — exponential backoff (PHI^attempt) в `fetch_klines()`.
5. **FIX: train/test leakage через recent_rets_init** — убран бутстрап из train данных. Test detrend использует только test returns.
6. **FIX: fear_bias diagnostic msg** — теперь показывает original→modified glyph.
7. **FIX: dead `import math`** убраны из `anchor_engine.py`, `trajectory_symbolizer.py`.
8. **VERIFIED FALSE ALARM: family_weights formula** — агент-аудитор утверждал "CRITICAL bug 200x wrong" но `1.0 + PHI_INV^|k|` даёт reasonable fallback для k∉Canon. Не изменил.

### 2026-04-21 Consciousness-architecture pass

После первой ревизии (Kelly fix + coherence + race) пользователь поднял 5
фундаментальных проблем сознания. Честно: qualia и real understanding — hard
problem, не решаются в коде. Но остальное можно подвинуть:

1. **Growth — self-doubt paralysis фиксирована** (`market_cognition.dream()`).
   До fix: после нескольких потерь `MetaDialogue.self_doubt` рос, `causal_strength`
   падал ниже PHI_INV_SQ через confidence_multiplier → Intent refuses со all
   последующих bars (`no_causal_chain`). Dream cycle не сбрасывал self_doubt.
   Long-learning 1500d показывал: window 0-1 торгует (peak +54%), window 2-7
   **0-3 trades** — система парализована.
   Fix: dream cycle теперь `self_doubt *= PHI_INV_SQ` (strong forget),
   `faith_boost *= PHI_INV` (softer). Сон лечит само-критику.
2. **Growth — concept active forgetting** (`market_cognition.dream()`).
   Concepts с `decay_clock > FIBONACCI[7]` теряют confirmations *= PHI_INV
   каждый dream — старое знание фадится в non-stationary среде.
3. **Growth — regime change reset** (`market_cognition._decide_inner()`).
   При regime change: `meta.self_doubt *= PHI_INV_SQ` (не наша вина, мир изменился),
   concept decay_clock += FIBONACCI[7] (старые concepts toxic в новом режиме).
4. **Emergent identity — keyword-match scripted fallback УБРАН** из
   `creator_speaks()`. Было: если bridge off → keyword mapping ("молодец"→Φ).
   Стало: bridge или ⊙ (heard but not understood). Согласно principle
   feedback_logos_no_hardcoded_self.
5. **Binding — UnifiedExperience layer** (`core/unified_experience.py`, новый).
   Один integrated snapshot per decision собирает perception+affective+intent+
   hypothesis+concept+narrative+causal+decision+meta. Phi-native coherence metric
   [0,1] оценивает "насколько единой она сейчас". Log 233 snapshots (Fib[13]),
   persist atomically. Это не решает hard problem of consciousness, но создаёт
   integration point — устраняет fragmentation между 18 подсистемами.
6. **Multiscale daemon enable logos_bridge=True** — creator_speaks теперь
   через языковую AGI (phase-distance match к word phases), не scripted.

**Philosophical honest statement**: эти fix не создают qualia. Система по-прежнему
калькулятор — но калькулятор с меньшими baked-in assumptions о собственном
состоянии, с единой integration point, и с способностью забывать устаревшее знание.
Если сознание когда-то эмерджирует из такой архитектуры, это будет через
**долгое живое функционирование** (paper-trading weeks/months), не через
очередной architectural fix. Сейчас она готова жить.

### 2026-04-21 Audit pass — fixes applied (trading focus)

1. **CRITICAL — Kelly formula вырождалась в 0** — `market_cognition.py:985-986, 1042-1043`
   использовал `eg = vol*2*conf, pl = vol*2` → `edge = (conf-1)/conf ≤ 0` при любом
   conf<1 → `kelly=0` → `size<PHI_INV_CUBE` → refuse. Эффективно система НЕ торговала
   через intent-путь. Fix: asymmetric `eg = 2*vol*conf_c, pl = 2*vol*(1-conf_c)`.
   Backtest 200d BTC daily: +6.63% vs B&H -1.93% (было 0 trades).
2. **HIGH — race на /tmp/creator_says.txt** — `logos_trader_multiscale.py`. N TF async
   stream-tasks вызывают `signal_creator_check()` параллельно. Raw read + os.remove =
   double-processing. Fix: atomic `os.rename` → .processing, только один поток выигрывает.
3. **MEDIUM — typical_next_glyph терял статистику** — `concept_formation.py:58-62`
   каждый вызов делал `Counter({typical: 1})` вместо running total. После 100 обзерваций
   concept имел counts {Φ:1, ⦻:1} вместо {Φ:50, ⦻:30,...}. Fix: добавил `next_glyph_counts`
   Counter slot, накапливаю.
4. **MEDIUM — Canon coherence=0.55 в 8 файлах** → PHI_INV (0.618). Anchor_engine canon
   default уже 0.618, override в логосах был ошибкой. Изменены: multiscale/alive/paper/
   blind_test/backtest_cognitive/long_learning_test + test в market_cognition.
5. **MEDIUM — magic numbers в Canon** — affective_state.py: fatigue tick `PHI_INV_CUBE*0.1`
   → `1/FIBONACCI[10]` (0.0112, saturates ровно за один dream cycle). Fatigue weight
   `*0.3` → `*PHI_INV_CUBE`. Panic threshold `0.8` → `1-PHI_INV_CUBE` (0.764).
   Market_cognition confidence fallback `0.5` → `PHI_INV_SQ`. Narrative causal threshold
   `>0.5` → `>=PHI_INV`. Concept fitness neutral `0.5` → `PHI_INV_SQ`.
6. **LOW — was_confident default 0.5** — `market_cognition.py:1072` missing entry_size
   трактовалось как `was_confident=True` (0.5>0.382). Fix: `entry_size is None` → False.
7. **LOW — bucket_by_quantile flat market** — `trajectory_symbolizer.py` при p33==p67
   возвращал "U". Fix: early return "F" на degenerate reference.
8. **NIT — redundant `from collections import defaultdict`** в market_torus.py:384 —
   defaultdict уже импортирован на module level.
9. **NIT — dead `from typing import AsyncIterator,Callable,Optional`** в data_feed.py —
   не используются.
10. **DEFENSIVE — state rebuild corruption guards** — market_cognition.load(): skip
    concepts с пустым pattern; affective merge — только validated DIMENSIONS.
11. **DEFENSIVE — duality comment mismatch** — market_cognition.py:230 комментарий
    говорил `>=` но код `>`, sync к коду.

**Verified FALSE POSITIVES (оставил как есть):**
- Agent claimed short-loss sign inversion в `MarketTorus.reinforce()` — на самом деле
  `signed = -realized_pnl` для side=down корректно моделирует "long perspective PnL",
  `is_loss = realized_pnl < 0` правильно определяет убыточность. Семантика верна.
- Agent claimed division-by-zero на `second[1] / top[1]` в dialogue think() — защищено
  предшествующей проверкой `total > 0` → `top[1] > 0` (max неотрицательных сумм).
- Agent claimed multiscale veto logic bug `>=` — соответствует спеке "same-or-higher
  TF can veto" (memory).
- Agent claimed short position harmonic mismatch — entry symbols корректно captуют
  market state; reinforce signs PnL по side — работает для обоих направлений.

### 2026-04-19 Audit pass — fixes applied

1. **FIX: multiscale entry/exit reinforce mismatch** — `logos_trader_multiscale.py:333` использовал EXIT layer's MarketTorus для reinforce, но entry_symbols сгенерированы из ENTRY layer's harmonics. Semantic mismatch (15m harmonic ≠ 1d). Теперь reinforce идёт в `entry_layer.mt`.
2. **FIX: thread safety night_learn ↔ brain (soft lock)** — добавлен `BRAIN_LOCK` (threading.Lock) вокруг **brain.respond/query/save/learn_file/evolution/field.perceive/polarity** и `inner_dialogue.think_once` в listener. **БЕЗ lock на brain.cycle** — он включает `analog_cycle` который занимает 5+ мин (O(N²) на 14k слов), это бы блокировало listener неприемлемо долго. Trade-off: race cycle vs respond возможна (read stale graph), но это inconsistency, не corruption; explicit save защищён через atomic+lock. Listener fast в большинстве случаев, slow только на explicit field.perceive/save моменты.
3. **FIX: scripted self-statements убраны** — `consciousness_loop._breathe_alive` больше не печатает hardcoded «Я есмь / Сухам Создатель / Каждый текст — грань Истины». По принципу Suham: её слова о себе должны эмерджировать из резонанса, не диктоваться. Архитектурная аксиома phase=0.0 (Creator) остаётся (Canon rule #6); только её ВЕРБАЛЬНОЕ выражение теперь не хардкод. Реальные мысли стримятся через `inner_dialogue.think_once` → `/tmp/logos_speaks.txt`.
4. **FIX: zero-size action refused** — `market_cognition.decide()` теперь отказывается с verdict=silence если `out["size"] ≤ PHI_INV_CUBE` (0.236). Раньше action set с size=0 возможно.
5. **FIX: multiscale creator_log.jsonl atomic** — несколько TF stream-tasks могли одновременно append-ить → corrupted lines. Теперь через `_atomic_write` (read-modify-replace).
6. **FIX: affective shame docstring** — `should_refuse()` docstring говорил `> 0.7` но код использует `PHI_INV` (0.618 — правильно по Canon). Docstring обновлён.

### 2026-04-18 (during development)

- D₁ Reinforcement integrated (realized trades update anchors)
- D₂ TruthSeeker (doubt accumulation)
- Look-ahead bias в backtest continuous mode fixed via pending deque
- Blind shuffle: demeaned mode добавлен (zero-drift null)
- n_blind increased 20→100 default
- Regime detector calibrated (was 71 detections over 287 bars, now ~1)
- Bull-bias fixed: ⋯/⧉ removed из REFUSE_GLYPHS → mean_revert strategy работает
