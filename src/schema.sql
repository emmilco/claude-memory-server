-- Claude Memory + RAG Server Database Schema

-- Unified memories and documentation table
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    category TEXT NOT NULL CHECK(category IN ('preference', 'fact', 'event', 'workflow', 'context', 'documentation')),
    memory_type TEXT NOT NULL CHECK(memory_type IN ('memory', 'documentation')),
    scope TEXT NOT NULL CHECK(scope IN ('global', 'project')),
    project_name TEXT,
    source_file TEXT,
    heading TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    importance REAL DEFAULT 0.5 CHECK(importance >= 0.0 AND importance <= 1.0),
    tags TEXT,
    embedding BLOB NOT NULL
);

-- Indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_category ON memories(category);
CREATE INDEX IF NOT EXISTS idx_memory_type ON memories(memory_type);
CREATE INDEX IF NOT EXISTS idx_scope ON memories(scope);
CREATE INDEX IF NOT EXISTS idx_project ON memories(project_name);
CREATE INDEX IF NOT EXISTS idx_timestamp ON memories(timestamp);

-- Track ingested documentation files
CREATE TABLE IF NOT EXISTS ingested_docs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    ingested_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    chunk_count INTEGER DEFAULT 0,
    UNIQUE(project_name, file_path)
);

CREATE INDEX IF NOT EXISTS idx_ingested_project ON ingested_docs(project_name);
CREATE INDEX IF NOT EXISTS idx_ingested_path ON ingested_docs(file_path);
