use crate::symbolic::{PatternDiscovery, PatternKind, Symbol, SymbolRegistry, SymbolResonance};
use serde::Serialize;
use std::fs::OpenOptions;
use std::io::Write;
use std::path::Path;

#[derive(Debug, Serialize)]
struct SymbolCreationEvent<'a> {
    tick: u64,
    pattern: &'a str,
    kind: &'a str,
    symbol_id: String,
}

/// Безопасная очистка строки паттерна для использования в id символа.
/// Работает по char, а не по байтам, никаких truncate.
fn sanitize_pattern_for_id(pattern: &str) -> String {
    let mut out = String::new();

    // Строим строку по символам
    for ch in pattern.chars() {
        if ch.is_alphanumeric() {
            out.push(ch.to_ascii_lowercase());
        } else if !out.ends_with('_') {
            out.push('_');
        }

        // Ограничиваем длину по количеству символов, а не байт
        if out.chars().count() >= 32 {
            break;
        }
    }

    // Снимаем хвостовые подчёркивания
    while out.ends_with('_') {
        out.pop();
    }

    out
}

/// Попытка "поднять" паттерн до нового символа.
pub fn maybe_promote_pattern_to_symbol(
    registry: &mut SymbolRegistry,
    d: &PatternDiscovery,
    tick: u64,
) {
    let (min_count, kind_str, prefix) = match d.kind {
        PatternKind::Unigram => (20, "unigram", "AUTO_U_"),
        PatternKind::Bigram => (10, "bigram", "AUTO_B_"),
    };

    if d.count < min_count {
        return;
    }

    let core = sanitize_pattern_for_id(&d.pattern);
    if core.is_empty() {
        return;
    }

    let id = format!("{}{}", prefix, core);
    if registry.exists(&id) {
        return;
    }

    let sym = Symbol {
        id: id.clone(),
        glyph: "◊".into(),
        name: format!("auto {}", d.pattern),
        category: "auto_pattern".into(),
        resonance: Some(SymbolResonance {
            scales: vec![],
            expected_per_1000_ticks: None,
        }),
    };

    registry.insert(sym);

    let event = SymbolCreationEvent {
        tick,
        pattern: &d.pattern,
        kind: kind_str,
        symbol_id: id,
    };

    if let Ok(json) = serde_json::to_string(&event) {
        let path = Path::new("data/symbols_dynamic.ndjson");
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
