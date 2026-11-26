"""CLI interativa para cadastrar um novo problema no SQLite e atualizar o Obsidian."""

import sqlite3
from pathlib import Path

from export_obsidian import fetch_markdown_report
from settings import settings

DB_PATH = settings.lab_db_path
CATALOG_PATH = settings.catalog_path
OBSIDIAN_PANEL_PATH = settings.obsidian_panel_path

FRONTS = {
    "1": "Frente A - Vida Pessoal",
    "2": "Frente B - Trabalho Corporativo",
    "3": "Frente C - Problemas da Sociedade",
    "4": "Frente D - Fronteiras Cientificas e Tecnologicas",
}

CANVAS_QUESTIONS = [
    "Quem possui o problema?",
    "Qual é a decisão ou tarefa afetada?",
    "Qual é o impacto atual?",
    "Como o problema é resolvido hoje?",
    "Quais dados estão disponíveis?",
    "A IA é realmente necessária?",
    "Qual é o baseline sem IA?",
    "Qual métrica indicará melhoria?",
    "Qual é o risco de uma resposta incorreta?",
    "Como uma pessoa continuará no controle?",
]

PRIORITY_CRITERIA = [
    "Relevância pessoal/profissional",
    "Impacto potencial",
    "Disponibilidade de dados",
    "Qualidade dos dados",
    "Experimentação local",
    "Clareza das métricas",
    "Originalidade",
    "Possibilidade de reutilização",
    "Risco ético (1=baixo, 5=alto)",
    "Esforço de implementação (1=baixo, 5=alto)",
]


def ask_text(prompt: str, default: str = "") -> str:
    """Solicita texto ao usuario, aceitando valor padrao opcional."""
    suffix = f" [{default}]" if default else ""
    while True:
        value = input(f"{prompt}{suffix}: ").strip()
        if value:
            return value
        if default:
            return default
        print("  Campo obrigatorio. Digite um valor.")


def ask_score(label: str) -> int:
    """Solicita uma nota inteira valida entre 1 e 5."""
    while True:
        raw = input(f"  Nota 1-5 ({label}): ").strip()
        if raw.isdigit() and 1 <= int(raw) <= 5:
            return int(raw)
        print("  Valor invalido. Digite um numero inteiro entre 1 e 5.")


def generate_next_code(db_path: Path) -> str:
    """Gera automaticamente o proximo codigo sequencial"""
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT COALESCE(MAX(id), 0) FROM problems").fetchone()
    next_num = (row[0] if row else 0) + 1
    return f"PROB-{next_num:02d}"


def insert_problem(
    db_path: Path,
    code: str,
    title: str,
    front: str,
    score_total: int,
    baseline_desc: str,
    human_control: str,
) -> None:
    """Grava o problema na tabela problems usando query parametrizada."""
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO problems
                (code, title, front, score_total, baseline_desc, human_control, status)
            VALUES (?, ?, ?, ?, ?, ?, 'ativo')
            """,
            (code, title, front, score_total, baseline_desc, human_control),
        )
        conn.commit()


def add_to_catalog(
    catalog_path: Path,
    code: str,
    title: str,
    front: str,
    canvas: list[tuple[str, str]],
    scores: list[tuple[str, int]],
) -> None:
    """Formata o Canvas em Markdown e insere antes de ## Conexões no Obsidian."""
    if not catalog_path.exists():
        print(f"[AVISO] Catalogo nao encontrado em {catalog_path}.")
        return

    content = catalog_path.read_text(encoding="utf-8")
    if f"## 🎯 {code} " in content:
        print(f"[AVISO] {code} ja existe no catalogo Markdown. Pulando insercao duplicada.")
        return

    lines = [
        f"## 🎯 {code} — {title}",
        "",
        f"* **Frente**: {front}",
        "* **Status**: `ativo`",
        "",
        "### Canvas de Problema (10 Perguntas)",
    ]
    for idx, (question, answer) in enumerate(canvas, start=1):
        lines.append(f"{idx}. **{question}** {answer}")

    lines.extend([
        "",
        "### Matriz de Priorização (1 a 5)",
        "| Critério | Nota (1–5) |",
        "| :--- | :---: |",
    ])
    for criterion, score in scores:
        lines.append(f"| {criterion} | {score} |")
    lines.append("")

    block = "\n".join(lines)
    marker = "## Conexões"
    if marker in content:
        idx = content.index(marker)
        new_content = content[:idx].rstrip() + "\n\n---\n\n" + block + "\n---\n" + content[idx:]
    else:
        new_content = content.rstrip() + "\n\n---\n\n" + block

    catalog_path.write_text(new_content, encoding="utf-8")
    print(f"[OK] Canvas adicionado ao Obsidian ({catalog_path}).")


def main() -> None:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Banco SQLite nao encontrado em {DB_PATH}. Rode src/db_init.py antes.")

    code = generate_next_code(DB_PATH)
    print(f"=== Cadastro Automatico: {code} (Problema Antes da Tecnologia) ===")
    title = ask_text("Titulo curto do problema")

    print("Frentes: 1=Pessoal | 2=Corporativo | 3=Sociedade | 4=Fronteiras")
    front_key = ask_text("Escolha a Frente (1-4)", "1")
    front = FRONTS.get(front_key, FRONTS["1"])

    print("\n--- Canvas de Problema (10 Perguntas) ---")
    canvas = [(q, ask_text(q)) for q in CANVAS_QUESTIONS]

    print("\n--- Matriz de Priorizacao (1 a 5) ---")
    scores = [(c, ask_score(c)) for c in PRIORITY_CRITERIA]
    score_total = sum(score for _, score in scores)

    insert_problem(
        db_path=DB_PATH,
        code=code,
        title=title,
        front=front,
        score_total=score_total,
        baseline_desc=canvas[6][1],
        human_control=canvas[9][1],
    )
    print(f"\n[OK] {code} gravado no SQLite ({DB_PATH}).")

    add_to_catalog(CATALOG_PATH, code, title, front, canvas, scores)

    markdown_panel = fetch_markdown_report(DB_PATH)
    OBSIDIAN_PANEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    OBSIDIAN_PANEL_PATH.write_text(markdown_panel, encoding="utf-8")
    print(f"[OK] Painel atualizado no Obsidian ({OBSIDIAN_PANEL_PATH}).")


if __name__ == "__main__":
    main()
