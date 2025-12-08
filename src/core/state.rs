use crate::resonance::ResonanceState;
use crate::self_core::SelfState;
use crate::storage::Snapshot;
use crate::symbolic::{Patterns, SymbolRegistry};

#[derive(Debug)]
pub struct CoreState {
    pub self_state: SelfState,
    pub symbols: SymbolRegistry,
    pub resonance: ResonanceState,
    pub patterns: Patterns,
}

impl CoreState {
    pub fn new() -> Self {
        Self {
            self_state: SelfState::new(),
            symbols: SymbolRegistry::new_builtin(),
            resonance: ResonanceState::new(),
            patterns: Patterns::new(),
        }
    }

    pub fn from_snapshot(snapshot: Snapshot) -> Self {
        let mut resonance = ResonanceState::new();
        // Шкалы берём свежие, а метрики восстанавливаем
        resonance.metrics = snapshot.resonance.metrics;

        Self {
            self_state: snapshot.self_state,
            symbols: SymbolRegistry::new_builtin(),
            resonance,
            patterns: snapshot.patterns,
        }
    }
}
