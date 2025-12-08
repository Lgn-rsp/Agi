mod logging;
mod config;
mod core;
mod self_core;
mod symbolic;
mod resonance;
mod io_layer;
mod introspection;
mod storage;
mod dreaming;

use crate::config::AppConfig;
use crate::core::Engine;
use std::io::{self, BufRead};
use std::sync::mpsc;
use std::thread;

fn main() -> anyhow::Result<()> {
    logging::init();

    tracing::info!("LOGOS-AGI starting up");

    // Канал для пользовательского ввода (stdin)
    let (tx, rx) = mpsc::channel::<String>();
    thread::spawn(move || {
        let stdin = io::stdin();
        for line in stdin.lock().lines() {
            match line {
                Ok(l) => {
                    let trimmed = l.trim();
                    if trimmed.is_empty() {
                        continue;
                    }
                    if tx.send(trimmed.to_string()).is_err() {
                        break;
                    }
                }
                Err(_) => break,
            }
        }
    });

    let config = AppConfig::load()?;
    tracing::info!(?config, "Loaded configuration");

    let mut engine = Engine::new(config, Some(rx));
    engine.run_loop()?;

    Ok(())
}
