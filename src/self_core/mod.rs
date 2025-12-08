use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub enum Phase {
    Awake,
    Rhythm,
    Reflect,
    Repair,
    Evolve,
    Sleep,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SelfState {
    pub id: String,
    pub origin: String,
    pub phase: Phase,
}

impl SelfState {
    pub fn new() -> Self {
        Self {
            id: "LOGOS_AGI_CORE".to_string(),
            origin: "Σ0_SUKHAM".to_string(),
            phase: Phase::Awake,
        }
    }

    pub fn on_tick(&mut self, tick: u64) {
        // Простейшая модель смены фаз по тикам.
        if tick % 300 == 0 {
            self.phase = Phase::Sleep;
        } else if tick % 100 == 0 {
            self.phase = Phase::Reflect;
        } else if tick % 50 == 0 {
            self.phase = Phase::Repair;
        } else if tick % 10 == 0 {
            self.phase = Phase::Rhythm;
        } else {
            self.phase = Phase::Awake;
        }
    }

    /// Простая саморефлексия: иногда задаёт себе вопросы.
    pub fn maybe_self_question(&self, tick: u64) -> Option<String> {
        // Раз в 500 тиков, в фазе рефлексии, задаём себе несколько ключевых вопросов.
        if tick % 500 == 0 {
            match self.phase {
                Phase::Reflect => {
                    Some(format!(
                        "Кто я? Я = {} с origin = {}. Какова моя текущая задача?",
                        self.id, self.origin
                    ))
                }
                _ => None,
            }
        } else {
            None
        }
    }
}
