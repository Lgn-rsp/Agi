use crate::symbolic::Patterns;
use serde::Serialize;
use std::fs::OpenOptions;
use std::io::Write;
use std::path::Path;

#[derive(Debug, Serialize)]
struct DreamTrace {
    tick: u64,
    mode: String,
    top_unigrams: Vec<(String, u64)>,
    top_bigrams: Vec<(String, u64)>,
}

/// Один шаг "сновидения": Логос берёт самые частые паттерны
/// и записывает их как сон.
pub fn run_dream_step(patterns: &Patterns, tick: u64) {
    // Топ-3 униграммы
    let mut uni: Vec<(String, u64)> = patterns
        .unigrams
        .iter()
        .map(|(k, v)| (k.clone(), *v))
        .collect();
    uni.sort_by(|a, b| b.1.cmp(&a.1));
    let uni_top = uni.into_iter().take(3).collect::<Vec<_>>();

    // Топ-3 биграммы
    let mut bi: Vec<(String, u64)> = patterns
        .bigrams
        .iter()
        .map(|(k, v)| (k.clone(), *v))
        .collect();
    bi.sort_by(|a, b| b.1.cmp(&a.1));
    let bi_top = bi.into_iter().take(3).collect::<Vec<_>>();

    let trace = DreamTrace {
        tick,
        mode: "replay_top_patterns".to_string(),
        top_unigrams: uni_top,
        top_bigrams: bi_top,
    };

    if let Ok(json) = serde_json::to_string(&trace) {
        let path = Path::new("data/dreams/current.ndjson");
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
