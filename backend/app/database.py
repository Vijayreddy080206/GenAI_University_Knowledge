"""
SDD Section 4.1 & 4.2: Relational Database Schema & Data Dictionary
Enforces surrogate primary keys and foreign-key constraints across all 8 tables:
1. Users
2. Sessions
3. Queries
4. Responses
5. ResponseCitations
6. Feedback
7. Documents
8. DocumentChunks
"""
import sqlite3
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

POSTGRESQL_DDL = """
-- SDD Section 4.2 PostgreSQL Production DDL
CREATE TABLE IF NOT EXISTS Users (
    user_id BIGSERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(150) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('STUDENT', 'FACULTY', 'ADMIN')),
    auth_source VARCHAR(20) NOT NULL CHECK (auth_source IN ('SSO', 'LOCAL')),
    password_hash VARCHAR(255),
    department VARCHAR(100) DEFAULT 'CSE',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS Sessions (
    session_id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES Users(user_id) ON DELETE CASCADE,
    title VARCHAR(255) DEFAULT 'New Conversation',
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_activity_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('ACTIVE', 'EXPIRED', 'ENDED'))
);

CREATE TABLE IF NOT EXISTS Queries (
    query_id BIGSERIAL PRIMARY KEY,
    session_id BIGINT NOT NULL REFERENCES Sessions(session_id) ON DELETE CASCADE,
    query_text TEXT NOT NULL,
    category VARCHAR(80) NOT NULL DEFAULT 'General',
    submitted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    anonymized_at TIMESTAMP NULL
);

CREATE TABLE IF NOT EXISTS Responses (
    response_id BIGSERIAL PRIMARY KEY,
    query_id BIGINT UNIQUE NOT NULL REFERENCES Queries(query_id) ON DELETE CASCADE,
    answer_text TEXT NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('ANSWERED', 'FALLBACK', 'ERROR')),
    model_name VARCHAR(100) NOT NULL,
    latency_ms INTEGER NOT NULL,
    generated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS Documents (
    document_id BIGSERIAL PRIMARY KEY,
    uploaded_by BIGINT NOT NULL REFERENCES Users(user_id),
    title VARCHAR(255) NOT NULL,
    department VARCHAR(100) NOT NULL,
    category VARCHAR(100) NOT NULL,
    file_type VARCHAR(10) NOT NULL CHECK (file_type IN ('PDF', 'DOCX', 'TXT')),
    file_size_bytes BIGINT NOT NULL,
    storage_uri VARCHAR(500) NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('PROCESSING', 'INDEXED', 'FAILED')),
    version INTEGER NOT NULL DEFAULT 1,
    uploaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS DocumentChunks (
    chunk_id BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES Documents(document_id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    token_count INTEGER NOT NULL,
    vector_id VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS ResponseCitations (
    citation_id BIGSERIAL PRIMARY KEY,
    response_id BIGINT NOT NULL REFERENCES Responses(response_id) ON DELETE CASCADE,
    chunk_id BIGINT NULL REFERENCES DocumentChunks(chunk_id) ON DELETE SET NULL,
    similarity_score FLOAT NOT NULL,
    rank SMALLINT NOT NULL
);

CREATE TABLE IF NOT EXISTS Feedback (
    feedback_id BIGSERIAL PRIMARY KEY,
    response_id BIGINT NOT NULL REFERENCES Responses(response_id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES Users(user_id) ON DELETE CASCADE,
    rating VARCHAR(10) NOT NULL CHECK (rating IN ('UP', 'DOWN')),
    comment TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(response_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_queries_submitted_at ON Queries(submitted_at);
CREATE INDEX IF NOT EXISTS idx_queries_category ON Queries(category);
CREATE INDEX IF NOT EXISTS idx_documents_status ON Documents(status);
"""

SQLITE_DDL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS Users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(150) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('STUDENT', 'FACULTY', 'ADMIN')),
    auth_source VARCHAR(20) NOT NULL CHECK (auth_source IN ('SSO', 'LOCAL')),
    password_hash VARCHAR(255),
    department VARCHAR(100) DEFAULT 'CSE',
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS Sessions (
    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES Users(user_id) ON DELETE CASCADE,
    title VARCHAR(255) DEFAULT 'New Conversation',
    started_at TIMESTAMP NOT NULL,
    last_activity_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('ACTIVE', 'EXPIRED', 'ENDED'))
);

CREATE TABLE IF NOT EXISTS Queries (
    query_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES Sessions(session_id) ON DELETE CASCADE,
    query_text TEXT NOT NULL,
    category VARCHAR(80) NOT NULL DEFAULT 'General',
    submitted_at TIMESTAMP NOT NULL,
    anonymized_at TIMESTAMP NULL
);

CREATE TABLE IF NOT EXISTS Responses (
    response_id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_id INTEGER UNIQUE NOT NULL REFERENCES Queries(query_id) ON DELETE CASCADE,
    answer_text TEXT NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('ANSWERED', 'FALLBACK', 'ERROR')),
    model_name VARCHAR(100) NOT NULL,
    latency_ms INTEGER NOT NULL,
    generated_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS Documents (
    document_id INTEGER PRIMARY KEY AUTOINCREMENT,
    uploaded_by INTEGER NOT NULL REFERENCES Users(user_id),
    title VARCHAR(255) NOT NULL,
    department VARCHAR(100) NOT NULL,
    category VARCHAR(100) NOT NULL,
    file_type VARCHAR(10) NOT NULL CHECK (file_type IN ('PDF', 'DOCX', 'TXT')),
    file_size_bytes INTEGER NOT NULL,
    storage_uri VARCHAR(500) NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('PROCESSING', 'INDEXED', 'FAILED')),
    version INTEGER NOT NULL DEFAULT 1,
    uploaded_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS DocumentChunks (
    chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES Documents(document_id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    token_count INTEGER NOT NULL,
    vector_id VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS ResponseCitations (
    citation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    response_id INTEGER NOT NULL REFERENCES Responses(response_id) ON DELETE CASCADE,
    chunk_id INTEGER NULL REFERENCES DocumentChunks(chunk_id) ON DELETE SET NULL,
    similarity_score FLOAT NOT NULL,
    rank SMALLINT NOT NULL
);

CREATE TABLE IF NOT EXISTS Feedback (
    feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
    response_id INTEGER NOT NULL REFERENCES Responses(response_id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES Users(user_id) ON DELETE CASCADE,
    rating VARCHAR(10) NOT NULL CHECK (rating IN ('UP', 'DOWN')),
    comment TEXT,
    created_at TIMESTAMP NOT NULL,
    UNIQUE(response_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_queries_submitted_at ON Queries(submitted_at);
CREATE INDEX IF NOT EXISTS idx_queries_category ON Queries(category);
CREATE INDEX IF NOT EXISTS idx_documents_status ON Documents(status);
"""

DB_PATH = Path(__file__).resolve().parent.parent / "storage" / "nu_knowledge_assistant.db"

def get_db_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    target = db_path or DB_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db(db_path: Optional[Path] = None) -> None:
    conn = get_db_connection(db_path)
    conn.executescript(SQLITE_DDL)
    conn.commit()
    conn.close()
