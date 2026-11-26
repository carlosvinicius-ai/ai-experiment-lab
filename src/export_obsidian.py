"""Exporta tabelas do SQLite (problems, experiments, benchmarks, hardware_runs) para Markdown no Obsidian."""

import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from settings import settings

DB_PATH = settings.lab_db_path
DEFAULT_REPORT_PATH = settings.default_report_path
OBSIDIAN_PANEL_PATH = settings.obsidian_panel_path


def _clean_cell(value: object) -> str:
    if value is None:
        return "—"
    text = str(value).replace("\n", " ").replace("|", "\\|").strip()
    return text if text else "—"


def _format_metrics(metrics_json: str | None) -> str:
    if not metrics_json:
        return "—"
    try:
        data = json.loads(metrics_json)
        if isinstance(data, dict):
            return ", ".join(f"`{k}={v}`" for k, v in data.items())
        return _clean_cell(data)
    except json.JSONDecodeError:
        return _clean_cell(metrics_json)


def _md_table(headers: list[str], rows: list[list[object]]) -> str:
    if not rows:
        return "_Nenhum registro encontrado nesta tabela ainda._\n"
    sep = ["---"] * len(headers)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(sep) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_clean_cell(cell) for cell in row) + " |")
    return "\n".join(lines) + "\n"


def fetch_markdown_report(db_path: Path) -> str:
    if not db_path.exists():
        raise FileNotFoundError(f"Banco SQLite nao encontrado em: {db_path}")

    with sqlite3.connect(db_path) as conn:
        problems = conn.execute(
            """
            SELECT code, title, front, score_total, status
            FROM problems
            ORDER BY id ASC
            """
        ).fetchall()

        experiments = conn.execute(
            """
            SELECT e.id, COALESCE(p.code, '—'), e.hypothesis, e.baseline,
                   e.approach, e.metrics_json, e.decision, e.evidence_level, e.created_at
            FROM experiments e
            LEFT JOIN problems p ON e.problem_id = p.id
            ORDER BY e.id DESC
            """
        ).fetchall()

        runs = conn.execute(
            """
            SELECT id, run_label, model_name, state, cpu_pct, ram_free_mb, latency_ms, created_at
            FROM hardware_runs
            ORDER BY id DESC
            LIMIT 20
            """
        ).fetchall()

        has_benchmarks = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='benchmarks'"
        ).fetchone()
        benchmarks = (
            conn.execute(
                """
                SELECT id, model_name, ollama_size, ollama_processor,
                       ttft_ms_avg, tps_avg, latency_p50_ms, latency_p95_ms, created_at
                FROM benchmarks
                ORDER BY id DESC
                LIMIT 20
                """
            ).fetchall()
            if has_benchmarks
            else []
        )

    benchmark_rows = [
        [
            r[0],
            f"`{r[1]}`",
            r[2],
            r[3],
            f"{r[4]:.1f}",
            f"{r[5]:.2f}",
            f"{r[6]:.1f}",
            f"{r[7]:.1f}",
            r[8],
        ]
        for r in benchmarks
    ]

    exp_rows = [
        [
            r[0],
            r[1],
            r[2],
            r[3],
            r[4],
            _format_metrics(r[5]),
            f"`{r[6]}`",
            r[7],
            r[8],
        ]
        for r in experiments
    ]

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    sections = [
        "---",
        "tipo: projeto",
        "type: dashboard",
        "status: ativo",
        "tags:",
        "  - roadmap-ia",
        "  - sqlite",
        "  - experimentos",
        "---",
        "",
        "# 📊 Painel de Experimentos (Exportado do SQLite)",
        "",
        f"> **Última sincronização:** `{now_str}` | **Fonte:** `SQLite local (lab_experiments.db)`",
        "",
        "---",
        "",
        "## 🎯 Problemas Cadastrados (`problems`)",
        _md_table(["Código", "Título", "Frente", "Score", "Status"], problems),
        "## 🧪 Experimentos Registrados (`experiments`)",
        _md_table(
            ["ID", "Problema", "Hipótese", "Baseline", "Abordagem", "Métricas", "Decisão", "Evidência", "Data"],
            exp_rows,
        ),
        "## 🚀 Benchmarks de Modelos Locais (`benchmarks` — últimos 20)",
        _md_table(
            ["ID", "Modelo", "Tamanho", "Processador", "TTFT (ms)", "TPS (tok/s)", "p50 (ms)", "p95 (ms)", "Data"],
            benchmark_rows,
        ),
        "## 💻 Telemetria Recente de Hardware (`hardware_runs` — últimos 20)",
        _md_table(
            ["ID", "Execução", "Modelo", "Estado", "CPU (%)", "RAM Livre (MB)", "Latência (ms)", "Data"],
            runs,
        ),
        "---",
        "## Conexões",
        "- **Roadmap**: [[00_Roadmap_Plataforma_IA]]",
        "- **Problemas**: [[Catalogo de Problemas Reais]]",
        "- **Hardware**: [[Inventario de Hardware e Quotas 1TB]]",
        "- **Arquitetura**: [[Arquitetura e Codigo do Laboratorio (ai-experiment-lab)]]",
        "- **Benchmark**: [[Benchmark de Modelos Locais (TTFT, TPS, p50 e p95)]]",
        "",
    ]
    return "\n".join(sections)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Exporta tabelas do lab_experiments.db para Markdown formatado para o Obsidian."
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help="Caminho do arquivo Markdown local de saida.",
    )
    parser.add_argument(
        "--obsidian",
        action="store_true",
        help="Tambem grava diretamente na pasta do projeto no cofre Obsidian.",
    )
    args = parser.parse_args()

    markdown = fetch_markdown_report(DB_PATH)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(markdown, encoding="utf-8")
    print(f"[OK] Relatorio Markdown salvo em: {args.out}")

    if args.obsidian:
        OBSIDIAN_PANEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        OBSIDIAN_PANEL_PATH.write_text(markdown, encoding="utf-8")
        print(f"[OK] Painel atualizado no Obsidian em: {OBSIDIAN_PANEL_PATH}")

    print("\n" + markdown)


if __name__ == "__main__":
    main()
