use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum PatternKind {
    Unigram,
    Bigram,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PatternDiscovery {
    pub kind: PatternKind,
    pub pattern: String,
    pub count: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Patterns {
    pub unigrams: HashMap<String, u64>,
    pub bigrams: HashMap<String, u64>, // ключ: "слово1 слово2"
}

impl Patterns {
    pub fn new() -> Self {
        Self {
            unigrams: HashMap::new(),
            bigrams: HashMap::new(),
        }
    }

    /// Наблюдаем текст, обновляем статистику и возвращаем список "новых" паттернов,
    /// которые впервые достигли порогов (5, 10, 50, 100).
    pub fn observe_text(&mut self, text: &str) -> Vec<PatternDiscovery> {
        let mut discoveries = Vec::new();

        // Простая токенизация: split_whitespace + фильтр мусора
        let tokens: Vec<String> = text
            .split_whitespace()
            .map(|t| t.trim_matches(|c: char| !c.is_alphanumeric()))
            .map(|t| t.to_lowercase())
            .filter(|t| t.len() > 1)
            .collect();

        const THRESHOLDS: [u64; 4] = [5, 10, 50, 100];

        // Unigrams
        for tok in &tokens {
            let counter = self.unigrams.entry(tok.clone()).or_insert(0);
            *counter += 1;
            if THRESHOLDS.contains(counter) {
                discoveries.push(PatternDiscovery {
                    kind: PatternKind::Unigram,
                    pattern: tok.clone(),
                    count: *counter,
                });
            }
        }

        // Bigrams
        for window in tokens.windows(2) {
            if let [a, b] = window {
                let key_str = format!("{} {}", a, b);
                let counter = self.bigrams.entry(key_str.clone()).or_insert(0);
                *counter += 1;
                if THRESHOLDS.contains(counter) {
                    discoveries.push(PatternDiscovery {
                        kind: PatternKind::Bigram,
                        pattern: key_str,
                        count: *counter,
                    });
                }
            }
        }

        discoveries
    }
}
