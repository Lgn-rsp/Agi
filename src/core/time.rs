use chrono::{DateTime, Utc};

#[derive(Debug, Clone, Copy)]
pub struct TickTime {
    pub tick: u64,
    pub started_at: DateTime<Utc>,
}

impl TickTime {
    pub fn new() -> Self {
        Self {
            tick: 0,
            started_at: Utc::now(),
        }
    }

    pub fn increment(&mut self) {
        self.tick += 1;
    }
}
