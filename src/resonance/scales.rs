use serde::Deserialize;
use std::fs;
use std::path::Path;

#[derive(Debug, Clone, Deserialize)]
pub struct ResonanceScale {
    /// Уникальный ID шкалы (PHI, SCHUMANN_BASE, HARMONIC_2_3 и т.п.)
    pub id: String,
    pub name: String,
    /// Категория: "mathematical", "physical" и т.п.
    pub category: String,
    /// Значение шкалы:
    ///  - если unit = "ratio"  — безразмерное отношение (например, φ),
    ///  - если unit = "Hz"     — частота в герцах,
    ///  - если unit = "ticks"  — шаги тиков.
    pub value: f64,
    pub unit: String,
}

#[derive(Debug, Clone)]
pub struct ResonanceScales {
    pub scales: Vec<ResonanceScale>,
}

#[derive(Debug, Deserialize)]
struct ResonanceScalesFile {
    #[serde(default)]
    scale: Vec<ResonanceScale>,
}

impl Default for ResonanceScales {
    fn default() -> Self {
        Self { scales: Vec::new() }
    }
}

impl ResonanceScales {
    pub fn load() -> Self {
        let path = Path::new("configs/resonance_scales.toml");
        if path.exists() {
            match fs::read_to_string(path) {
                Ok(data) => match toml::from_str::<ResonanceScalesFile>(&data) {
                    Ok(file) => {
                        return ResonanceScales {
                            scales: file.scale,
                        }
                    }
                    Err(err) => {
                        tracing::warn!(?err, "Failed to parse resonance_scales.toml, using default scales");
                    }
                },
                Err(err) => {
                    tracing::warn!(?err, "Failed to read resonance_scales.toml, using default scales");
                }
            }
        } else {
            tracing::warn!("configs/resonance_scales.toml not found, using default scales");
        }
        ResonanceScales::with_defaults()
    }

    pub fn with_defaults() -> Self {
        let mut s = ResonanceScales::default();
        // Золотое сечение как базовая математическая шкала
        s.scales.push(ResonanceScale {
            id: "PHI".into(),
            name: "Золотое сечение".into(),
            category: "mathematical".into(),
            value: 1.618_033_988_75,
            unit: "ratio".into(),
        });
        s
    }

    pub fn find(&self, id: &str) -> Option<&ResonanceScale> {
        self.scales.iter().find(|s| s.id == id)
    }
}
