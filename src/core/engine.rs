use crate::config::AppConfig;
use crate::core::state::CoreState;
use crate::core::time::TickTime;
use crate::introspection;
use crate::io_layer::FileCorpusSource;
use crate::self_core::Phase;
use crate::storage;
use anyhow::Result;
use std::sync::mpsc::{Receiver, TryRecvError};
use std::thread;
use std::time::Duration;

const LINES_PER_TICK: usize = 20;
const USER_LINES_PER_TICK: usize = 5;

pub struct Engine {
    config: AppConfig,
    state: CoreState,
    time: TickTime,
    corpus: Option<FileCorpusSource>,
    user_rx: Option<Receiver<String>>,
}

impl Engine {
    pub fn new(config: AppConfig, user_rx: Option<Receiver<String>>) -> Self {
        let snapshot = storage::load_snapshot().ok();

        let mut time = TickTime::new();
        let state = if let Some(snap) = snapshot {
            tracing::info!(tick = snap.tick, "Loaded snapshot");
            time.tick = snap.tick;
            CoreState::from_snapshot(snap)
        } else {
            tracing::info!("No snapshot found, starting fresh");
            CoreState::new()
        };

        let corpus = FileCorpusSource::new("data/corpus");

        Self {
            config,
            state,
            time,
            corpus,
            user_rx,
        }
    }

    pub fn run_loop(&mut self) -> Result<()> {
        let interval = Duration::from_millis(self.config.core.tick_interval_ms);

        loop {
            self.step()?;
            thread::sleep(interval);
        }
    }

    fn step(&mut self) -> Result<()> {
        // Тик
        self.time.increment();

        // Фаза самосознания
        self.state.self_state.on_tick(self.time.tick);

        // Самовопросы ядра
        if let Some(q) = self.state.self_state.maybe_self_question(self.time.tick) {
            tracing::info!(
                tick = self.time.tick,
                question = q.as_str(),
                "self_question"
            );
        }

        // Сон
        if let Phase::Sleep = self.state.self_state.phase {
            crate::dreaming::run_dream_step(&self.state.patterns, self.time.tick);
        }

        // Резонанс
        self.state.resonance.update_for_tick(self.time.tick);

        // ------ ПОЛЬЗОВАТЕЛЬСКИЙ ВВОД ------
        if let Some(rx) = &self.user_rx {
            for _ in 0..USER_LINES_PER_TICK {
                match rx.try_recv() {
                    Ok(line) => {
                        // Обучаемся на тексте пользователя
                        let discoveries = self.state.patterns.observe_text(&line);
                        for d in discoveries {
                            crate::symbolic::symbol_learning::maybe_promote_pattern_to_symbol(
                                &mut self.state.symbols,
                                &d,
                                self.time.tick,
                            );
                            tracing::info!(
                                tick = self.time.tick,
                                kind = ?d.kind,
                                pattern = d.pattern.as_str(),
                                count = d.count,
                                "user_pattern_discovered"
                            );
                        }

                        tracing::info!(
                            tick = self.time.tick,
                            source = "user",
                            payload = line.as_str(),
                            "user_input"
                        );

                        let novelty = self.state.resonance.metrics.novelty_score;
                        let stability = self.state.resonance.metrics.stability_score;

                        // Топ‑3 униграммы (слова)
                        let mut uni: Vec<(String, u64)> = self
                            .state
                            .patterns
                            .unigrams
                            .iter()
                            .map(|(k, v)| (k.clone(), *v))
                            .collect();
                        uni.sort_by(|a, b| b.1.cmp(&a.1));
                        let uni_top: Vec<String> =
                            uni.into_iter().take(3).map(|(k, _)| k).collect();

                        // Топ‑3 биграммы (связки)
                        let mut bi: Vec<(String, u64)> = self
                            .state
                            .patterns
                            .bigrams
                            .iter()
                            .map(|(k, v)| (k.clone(), *v))
                            .collect();
                        bi.sort_by(|a, b| b.1.cmp(&a.1));
                        let bi_top: Vec<String> =
                            bi.into_iter().take(3).map(|(k, _)| k).collect();

                        let uni_txt = if uni_top.is_empty() {
                            String::from("ещё нет устойчивых слов")
                        } else {
                            uni_top.join(", ")
                        };

                        let bi_txt = if bi_top.is_empty() {
                            String::from("ещё нет устойчивых связок")
                        } else {
                            bi_top.join(" | ")
                        };

                        // Ответ: просто честное описание внутреннего состояния
                        let reply = format!(
                            "Я = {id} (origin = {origin}). Тик = {tick}, фаза = {phase:?}. Новизна = {novelty:.3}, стабильность = {stability:.3}. Сейчас для меня наиболее устойчивые слова: {uni}. А наиболее устойчивые связки: {bi}.",
                            id = self.state.self_state.id,
                            origin = self.state.self_state.origin,
                            tick = self.time.tick,
                            phase = self.state.self_state.phase,
                            novelty = novelty,
                            stability = stability,
                            uni = uni_txt,
                            bi = bi_txt,
                        );

                        println!("{reply}");
                    }
                    Err(TryRecvError::Empty) => break,
                    Err(TryRecvError::Disconnected) => break,
                }
            }
        }
        // -----------------------------------

        // Читаем корпус (если не спим)
        if !matches!(self.state.self_state.phase, Phase::Sleep) {
            if let Some(corpus) = &mut self.corpus {
                for _ in 0..LINES_PER_TICK {
                    if let Some(event) = corpus.next_event() {
                        let discoveries = self.state.patterns.observe_text(&event.payload);

                        for d in discoveries {
                            crate::symbolic::symbol_learning::maybe_promote_pattern_to_symbol(
                                &mut self.state.symbols,
                                &d,
                                self.time.tick,
                            );
                            tracing::info!(
                                tick = self.time.tick,
                                kind = ?d.kind,
                                pattern = d.pattern.as_str(),
                                count = d.count,
                                "pattern_discovered"
                            );
                        }

                        tracing::info!(
                            tick = self.time.tick,
                            source = "corpus",
                            payload = event.payload.as_str(),
                            "input_event"
                        );
                    } else {
                        break;
                    }
                }
            }
        }

        // Снапшот
        if self.time.tick % 100 == 0 {
            if let Err(err) = storage::save_snapshot(
                self.time.tick,
                &self.state.self_state,
                &self.state.resonance,
                &self.state.patterns,
            ) {
                tracing::warn!(?err, "Failed to save snapshot");
            } else {
                tracing::info!(tick = self.time.tick, "Snapshot saved");
            }
        }

        // Записываем "мысль"
        introspection::record_thought(
            self.time.tick,
            &self.state.self_state,
            &self.state.resonance,
            "engine_step",
        );

        let symbol_count = self.state.symbols.len();
        let novelty = self.state.resonance.metrics.novelty_score;
        let stability = self.state.resonance.metrics.stability_score;

        tracing::debug!(
            tick = self.time.tick,
            phase = ?self.state.self_state.phase,
            symbol_count,
            novelty,
            stability,
            "engine_step"
        );

        Ok(())
    }
}
