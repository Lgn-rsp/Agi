use serde::{Deserialize, Serialize};
use std::fs;
use std::fs::File;
use std::io::{BufRead, BufReader};
use std::path::{Path, PathBuf};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum EventSource {
    TextCorpus,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IncomingEvent {
    pub source: EventSource,
    pub payload: String,
}

/// Источник событий из текстового корпуса в data/corpus
pub struct FileCorpusSource {
    files: Vec<PathBuf>,
    current_file_index: usize,
    current_reader: Option<BufReader<File>>,
}

impl FileCorpusSource {
    /// Создаёт источник из каталога. Если там ничего нет — вернёт None.
    pub fn new<P: AsRef<Path>>(root: P) -> Option<Self> {
        let root = root.as_ref();
        if !root.exists() {
            tracing::warn!(path = ?root, "Corpus directory does not exist");
            return None;
        }

        let mut files = Vec::new();
        if let Ok(entries) = fs::read_dir(root) {
            for entry in entries.flatten() {
                let path = entry.path();
                if path.is_file() {
                    files.push(path);
                }
            }
        }

        if files.is_empty() {
            tracing::warn!(path = ?root, "Corpus directory has no files");
            return None;
        }

        Some(Self {
            files,
            current_file_index: 0,
            current_reader: None,
        })
    }

    /// Возвращает следующее событие (строку) из корпуса, или None, если всё прочитано.
    pub fn next_event(&mut self) -> Option<IncomingEvent> {
        loop {
            if self.current_reader.is_none() {
                if self.current_file_index >= self.files.len() {
                    return None;
                }
                let path = &self.files[self.current_file_index];
                match File::open(path) {
                    Ok(file) => {
                        self.current_reader = Some(BufReader::new(file));
                        tracing::info!(file = ?path, "Starting to read corpus file");
                    }
                    Err(err) => {
                        tracing::warn!(?err, file = ?path, "Failed to open corpus file");
                        self.current_file_index += 1;
                        continue;
                    }
                }
            }

            if let Some(reader) = &mut self.current_reader {
                let mut line = String::new();
                match reader.read_line(&mut line) {
                    Ok(0) => {
                        // конец файла
                        self.current_reader = None;
                        self.current_file_index += 1;
                        continue;
                    }
                    Ok(_) => {
                        let trimmed = line.trim();
                        if trimmed.is_empty() {
                            continue;
                        }
                        return Some(IncomingEvent {
                            source: EventSource::TextCorpus,
                            payload: trimmed.to_string(),
                        });
                    }
                    Err(err) => {
                        tracing::warn!(?err, "Error reading corpus file");
                        self.current_reader = None;
                        self.current_file_index += 1;
                        continue;
                    }
                }
            }
        }
    }
}
