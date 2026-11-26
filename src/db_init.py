"""Inicializa o banco SQLite mestre de experimentos do laboratório."""

import sqlite3
from pathlib import Path

from settings import ROOT_DIR, settings

DB_PATH = settings.lab_db_path


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS problems (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    front TEXT NOT NULL,
    score_total INTEGER,
    baseline_desc TEXT NOT NULL,
    human_control TEXT NOT NULL,
    status TEXT DEFAULT 'ativo',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS datasets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    source_url TEXT,
    license TEXT,
    nature TEXT NOT NULL, -- real | sintetico | simulado | anonimizado
    rows_count INTEGER,
    cols_count INTEGER,
    leakage_risk TEXT,
    sha256_hash TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS experiments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    problem_id INTEGER REFERENCES problems(id),
    dataset_id INTEGER REFERENCES datasets(id),
    hypothesis TEXT NOT NULL,
    baseline TEXT NOT NULL,
    approach TEXT NOT NULL,
    metrics_json TEXT NOT NULL,
    decision TEXT NOT NULL,
    evidence_level TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS hardware_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_id INTEGER REFERENCES experiments(id),
    run_label TEXT NOT NULL,
    model_name TEXT,
    state TEXT, -- idle | cold_start | warm_start
    cpu_pct REAL,
    ram_used_mb REAL,
    ram_free_mb REAL,
    vram_used_mb REAL,
    latency_ms REAL,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS benchmarks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_name TEXT NOT NULL,
    num_ctx INTEGER NOT NULL,
    prompt_count INTEGER NOT NULL,
    ttft_ms_avg REAL NOT NULL,
    tps_avg REAL NOT NULL,
    latency_p50_ms REAL NOT NULL,
    latency_p95_ms REAL NOT NULL,
    ram_free_mb REAL NOT NULL,
    ollama_processor TEXT,
    ollama_size TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

INITIAL_PROBLEMS = [
    (
        "PROB-01",
        "Triagem e Conexao de Notas Rapidas (Jornal)",
        "Frente A - Vida Pessoal",
        39,
        "Classificador lexico por palavras-chave e regex em Python (< 5 ms).",
        "Modo somente sugestao (Human-in-the-loop): usuario aprova antes de editar o cofre.",
        "ativo",
    ),
    (
        "PROB-02",
        "Estruturacao, Classificacao de Demandas e Gestao Scrum no Microsoft Planner",
        "Frente B - Trabalho Corporativo",
        42,
        "Template Scrum padrao de cards + regras deterministicas de triagem e validacao de campos (< 5 ms).",
        "Modo copiloto (Human-in-the-loop): sugere classificacao, subtarefas e alertas; usuario aprova no Planner.",
        "ativo",
    ),
]


def ensure_directories(root: Path) -> None:
    """Garante a criacao da arvore de pastas do laboratorio."""
    for rel in [
        "db",
        "data/raw",
        "data/processed",
        "data/golden",
        "models",
        "notebooks",
        "reports",
        "src",
    ]:
        (root / rel).mkdir(parents=True, exist_ok=True)


def init_db() -> None:
    ensure_directories(ROOT_DIR)

    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.executemany(
            """
            INSERT OR IGNORE INTO problems
                (code, title, front, score_total, baseline_desc, human_control, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            INITIAL_PROBLEMS,
        )
        conn.commit()
    print(f"[OK] Banco SQLite inicializado em: {DB_PATH}")


if __name__ == "__main__":
    init_db()
