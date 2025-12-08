mod scales;

pub use scales::{ResonanceScale, ResonanceScales};

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResonanceMetrics {
    pub novelty_score: f64,
    pub stability_score: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResonanceState {
    pub metrics: ResonanceMetrics,
    #[serde(skip)]
    pub scales: ResonanceScales,
}

impl ResonanceState {
    pub fn new() -> Self {
        Self {
            metrics: ResonanceMetrics {
                novelty_score: 0.0,
                stability_score: 1.0,
            },
            scales: ResonanceScales::load(),
        }
    }

    /// Обновление резонансных метрик на каждом тике.
    /// Пока простая модель: псевдо-резонанс по φ (PHI).
    pub fn update_for_tick(&mut self, tick: u64) {
        let phi = if let Some(phi_scale) = self.scales.find("PHI") {
            phi_scale.value
        } else {
            1.618_033_988_75
        };

        let phase = (tick as f64 / 1000.0) * phi;
        let s = (phase.sin() + 1.0) / 2.0;

        self.metrics.novelty_score = s;
        self.metrics.stability_score = 1.0 - (s - 0.5).abs();
    }
}
