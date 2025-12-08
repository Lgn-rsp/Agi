use anyhow::Result;
use serde::Deserialize;
use std::fs;
use std::path::Path;

#[derive(Debug, Clone, Deserialize)]
pub struct CoreConfig {
    pub tick_interval_ms: u64,
}

#[derive(Debug, Clone, Deserialize)]
pub struct AppConfig {
    pub core: CoreConfig,
}

impl Default for CoreConfig {
    fn default() -> Self {
        Self {
            tick_interval_ms: 500,
        }
    }
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            core: CoreConfig::default(),
        }
    }
}

impl AppConfig {
    pub fn load() -> Result<Self> {
        let path = Path::new("configs/core.toml");
        if path.exists() {
            let data = fs::read_to_string(path)?;
            let core_cfg: CoreConfig = toml::from_str(&data)?;
            Ok(Self { core: core_cfg })
        } else {
            tracing::warn!("configs/core.toml not found, using defaults");
            Ok(Self::default())
        }
    }
}
