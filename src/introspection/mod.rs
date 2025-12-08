use crate::resonance::ResonanceState;
use crate::self_core::{Phase, SelfState};
use serde::Serialize;
use std::fs::OpenOptions;
use std::io::Write;
use std::path::Path;

#[derive(Debug, Serialize)]
struct SelfSummary<'a> {
    id: &'a str,
    origin: &'a str,
    phase: &'a Phase,
}

#[derive(Debug, Serialize)]
struct ThoughtTrace<'a> {
    tick: u64,
    self_state: SelfSummary<'a>,
    novelty: f64,
    stability: f64,
    label: &'a str,
}

pub fn record_thought(
    tick: u64,
    self_state: &SelfState,
    resonance: &ResonanceState,
    label: &str,
) {
    let summary = SelfSummary {
        id: &self_state.id,
        origin: &self_state.origin,
        phase: &self_state.phase,
    };

    let trace = ThoughtTrace {
        tick,
        self_state: summary,
        novelty: resonance.metrics.novelty_score,
        stability: resonance.metrics.stability_score,
        label,
    };

    if let Ok(json) = serde_json::to_string(&trace) {
        let path = Path::new("data/thought_traces/current.ndjson");
        if let Some(parent) = path.parent() {
            let _ = std::fs::create_dir_all(parent);
        }

        if let Ok(mut file) = OpenOptions::new()
            .create(true)
            .append(true)
            .open(path)
        {
            let _ = file.write_all(json.as_bytes());
            let _ = file.write_all(b"\n");
        }
    }
}
