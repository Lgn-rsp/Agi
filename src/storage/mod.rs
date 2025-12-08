use crate::resonance::ResonanceState;
use crate::self_core::SelfState;
use crate::symbolic::Patterns;
use anyhow::{bail, Result};
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::Path;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Snapshot {
    pub tick: u64,
    pub self_state: SelfState,
    pub resonance: ResonanceState,
    pub patterns: Patterns,
}

const SNAPSHOT_PATH: &str = "data/snapshots/latest.json";

pub fn load_snapshot() -> Result<Snapshot> {
    let path = Path::new(SNAPSHOT_PATH);
    if !path.exists() {
        bail!("no snapshot");
    }
    let data = fs::read_to_string(path)?;
    let snap: Snapshot = serde_json::from_str(&data)?;
    Ok(snap)
}

pub fn save_snapshot(
    tick: u64,
    self_state: &SelfState,
    resonance: &ResonanceState,
    patterns: &Patterns,
) -> Result<()> {
    let snapshot = Snapshot {
        tick,
        self_state: self_state.clone(),
        resonance: resonance.clone(),
        patterns: patterns.clone(),
    };

    let path = Path::new(SNAPSHOT_PATH);
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }

    let data = serde_json::to_string_pretty(&snapshot)?;
    fs::write(path, data)?;
    Ok(())
}
