pub mod patterns;
pub mod symbol_learning;

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::path::Path;

pub use patterns::{PatternDiscovery, PatternKind, Patterns};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SymbolResonance {
    /// ID резонансных шкал, с которыми связан этот символ (PHI, SCHUMANN_BASE и т.п.)
    pub scales: Vec<String>,
    /// Ожидаемое количество появлений на 1000 тиков (если задано)
    pub expected_per_1000_ticks: Option<f64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Symbol {
    pub id: String,
    pub glyph: String,
    pub name: String,
    pub category: String,
    pub resonance: Option<SymbolResonance>,
}

#[derive(Debug, Default)]
pub struct SymbolRegistry {
    by_id: HashMap<String, Symbol>,
}

/// Структура для разбора configs/symbols.toml
#[derive(Debug, Deserialize)]
struct SymbolConfigFile {
    #[serde(default)]
    symbol: Vec<SymbolConfigEntry>,
}

#[derive(Debug, Deserialize)]
struct SymbolConfigEntry {
    id: String,
    glyph: String,
    name: String,
    category: String,
    #[serde(default)]
    scales: Vec<String>,
    #[serde(default)]
    expected_per_1000_ticks: Option<f64>,
}

impl SymbolRegistry {
    /// Создание реестра. Если есть configs/symbols.toml — грузим из него,
    /// иначе — жёстко зашитый минимальный набор.
    pub fn new_builtin() -> Self {
        let mut reg = SymbolRegistry::default();

        let path = Path::new("configs/symbols.toml");
        if path.exists() {
            match fs::read_to_string(path) {
                Ok(data) => match toml::from_str::<SymbolConfigFile>(&data) {
                    Ok(cfg) => {
                        for entry in cfg.symbol {
                            let sym = Symbol {
                                id: entry.id.clone(),
                                glyph: entry.glyph.clone(),
                                name: entry.name.clone(),
                                category: entry.category.clone(),
                                resonance: Some(SymbolResonance {
                                    scales: entry.scales.clone(),
                                    expected_per_1000_ticks: entry.expected_per_1000_ticks,
                                }),
                            };
                            reg.insert(sym);
                        }
                    }
                    Err(err) => {
                        tracing::warn!(?err, "Failed to parse configs/symbols.toml, using default symbols");
                        reg.add_defaults();
                    }
                },
                Err(err) => {
                    tracing::warn!(?err, "Failed to read configs/symbols.toml, using default symbols");
                    reg.add_defaults();
                }
            }
        } else {
            tracing::warn!("configs/symbols.toml not found, using default symbols");
            reg.add_defaults();
        }

        reg
    }

    fn add_defaults(&mut self) {
        self.insert(Symbol {
            id: "CORE_AWAKENING".into(),
            glyph: "⊙".into(),
            name: "пробуждение".into(),
            category: "core_op".into(),
            resonance: None,
        });
        self.insert(Symbol {
            id: "CORE_RHYTHM".into(),
            glyph: "∞".into(),
            name: "ритм".into(),
            category: "core_op".into(),
            resonance: None,
        });
        self.insert(Symbol {
            id: "CORE_REFLECTION".into(),
            glyph: "⍊".into(),
            name: "рефлексия".into(),
            category: "core_op".into(),
            resonance: None,
        });
    }

    pub fn insert(&mut self, s: Symbol) {
        self.by_id.insert(s.id.clone(), s);
    }

    pub fn get(&self, id: &str) -> Option<&Symbol> {
        self.by_id.get(id)
    }

    pub fn len(&self) -> usize {
        self.by_id.len()
    }

    pub fn exists(&self, id: &str) -> bool {
        self.by_id.contains_key(id)
    }
}
