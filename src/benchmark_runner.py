"""Benchmark Runner para comparar SLMs locais (TTFT, TPS, p50/p95 e CPU/GPU offloading)."""

import argparse
import math
import sqlite3
import subprocess
from pathlib import Path

import httpx
import psutil

from settings import settings

DB_PATH = settings.lab_db_path
OLLAMA_URL = settings.ollama_url

DEFAULT_MODELS = [
    "qwen2.5:1.5b",
    "qwen2.5:3b",
    "qwen2.5:3b-instruct-q8_0",
    "qwen2.5:7b",
]

PROMPTS = [
    # 5 sinteses tecnicas curtas
    "Explique em 3 frases o que e quantizacao Q4_K_M em modelos de linguagem.",
    "Resuma a diferenca entre RAM e VRAM durante a inferencia local de um LLM.",
    "Explique em poucas palavras por que o formato colunar Parquet acelera consultas analiticas.",
    "Qual e a funcao do banco SQLite em um laboratorio de experimentos de IA?",
    "Descreva em 3 topicos o papel do Human-in-the-loop em sistemas com IA.",
    # 5 raciocinios curtos ligados aos problemas do catalogo (Obsidian, Planner/Scrum, Vagas)
    "Quebre a demanda 'Criar dashboard de vendas' em 3 subtarefas curtas no estilo Scrum.",
    "Classifique a urgencia (baixa, media, alta) de: 'Servidor de producao fora do ar'. Justifique em 1 frase.",
    "Liste 3 criterios objetivos para priorizar uma tarefa em uma sprint de 2 semanas.",
    "Sugira 3 tags para uma nota sobre 'Benchmark de quantizacao no Ollama com Python'.",
    "Se um modelo consome 3.4 GB e a GPU tem 2.3 GB livres, o que o Ollama faz com o restante?",
]


def ensure_benchmarks_table(db_path: Path) -> None:
    """Garante a criacao da tabela benchmarks no banco SQLite."""
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
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
            )
            """
        )
        conn.commit()


def get_installed_models() -> set[str]:
    """Consulta os modelos ja baixados no servidor Ollama local."""
    resp = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=10.0)
    resp.raise_for_status()
    return {m["name"] for m in resp.json().get("models", [])}


def parse_ollama_ps(model_name: str) -> tuple[str, str]:
    """Extrai SIZE e PROCESSOR da saida de `ollama ps` para o modelo ativo."""
    try:
        res = subprocess.run(
            ["ollama", "ps"], capture_output=True, text=True, timeout=10, check=False
        )
        for line in res.stdout.splitlines()[1:]:
            if model_name in line:
                parts = [p.strip() for p in line.split("  ") if p.strip()]
                size = parts[2] if len(parts) > 2 else "desconhecido"
                processor = parts[3] if len(parts) > 3 else "desconhecido"
                return size, processor
    except Exception:
        pass
    return "desconhecido", "desconhecido"


def percentile(values: list[float], pct: float) -> float:
    """Calcula percentil linear (ex.: p50, p95) sobre lista ordenada."""
    ordered = sorted(values)
    if not ordered:
        return 0.0
    idx = (len(ordered) - 1) * (pct / 100.0)
    low = math.floor(idx)
    high = math.ceil(idx)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (idx - low)


def call_ollama(model: str, prompt: str, num_ctx: int, num_predict: int) -> dict:
    """Executa uma chamada sincrona deterministica ao endpoint /api/generate."""
    resp = httpx.post(
        f"{OLLAMA_URL}/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.0,
                "seed": 42,
                "num_ctx": num_ctx,
                "num_predict": num_predict,
            },
        },
        timeout=180.0,
    )
    resp.raise_for_status()
    return resp.json()


def benchmark_model(model: str, num_ctx: int, num_predict: int) -> dict:
    """Roda 1 warmup descartado + 10 prompts medidos e retorna as metricas consolidadas."""
    print(f"\n>>> Benchmarking: {model} (num_ctx={num_ctx}, num_predict={num_predict})")

    # 1. Warmup obrigatorio (descartado da media para isolar Cold Start)
    print("  [warmup] Carregando modelo na memoria...")
    call_ollama(model, "Responda apenas: pronto.", num_ctx, 8)
    size_str, proc_str = parse_ollama_ps(model)
    print(f"  [ollama ps] Tamanho: {size_str} | Processador: {proc_str}")

    ttfts: list[float] = []
    tps_list: list[float] = []
    latencies: list[float] = []

    for idx, prompt in enumerate(PROMPTS, start=1):
        data = call_ollama(model, prompt, num_ctx, num_predict)
        prompt_eval_ns = data.get("prompt_eval_duration", 0)
        eval_count = data.get("eval_count", 0)
        eval_ns = data.get("eval_duration", 1)
        total_ns = data.get("total_duration", 0)

        ttft_ms = prompt_eval_ns / 1e6
        tps = eval_count / (eval_ns / 1e9) if eval_ns > 0 else 0.0
        total_ms = total_ns / 1e6

        ttfts.append(ttft_ms)
        tps_list.append(tps)
        latencies.append(total_ms)
        print(f"  Prompt {idx:02d}/10 | TTFT: {ttft_ms:6.1f} ms | TPS: {tps:5.1f} tok/s | Total: {total_ms:7.1f} ms")

    ram_free_mb = round(psutil.virtual_memory().available / (1024 ** 2), 1)
    result = {
        "model_name": model,
        "num_ctx": num_ctx,
        "prompt_count": len(PROMPTS),
        "ttft_ms_avg": round(sum(ttfts) / len(ttfts), 2),
        "tps_avg": round(sum(tps_list) / len(tps_list), 2),
        "latency_p50_ms": round(percentile(latencies, 50), 2),
        "latency_p95_ms": round(percentile(latencies, 95), 2),
        "ram_free_mb": ram_free_mb,
        "ollama_processor": proc_str,
        "ollama_size": size_str,
    }

    # Descarrega o modelo ao final para o proximo modelo pegar RAM/VRAM limpa
    subprocess.run(["ollama", "stop", model], capture_output=True, check=False)
    return result


def save_benchmark(db_path: Path, row: dict) -> None:
    """Persiste o resumo do benchmark no SQLite."""
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO benchmarks
                (model_name, num_ctx, prompt_count, ttft_ms_avg, tps_avg,
                 latency_p50_ms, latency_p95_ms, ram_free_mb, ollama_processor, ollama_size)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["model_name"],
                row["num_ctx"],
                row["prompt_count"],
                row["ttft_ms_avg"],
                row["tps_avg"],
                row["latency_p50_ms"],
                row["latency_p95_ms"],
                row["ram_free_mb"],
                row["ollama_processor"],
                row["ollama_size"],
            ),
        )
        conn.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark Runner de SLMs locais no Ollama.")
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS, help="Lista de modelos para testar.")
    parser.add_argument("--num-ctx", type=int, default=2048, help="Janela de contexto (padrao: 2048).")
    parser.add_argument("--num-predict", type=int, default=128, help="Maximo de tokens gerados (padrao: 128).")
    args = parser.parse_args()

    ensure_benchmarks_table(DB_PATH)
    installed = get_installed_models()
    targets = [m for m in args.models if m in installed]
    missing = [m for m in args.models if m not in installed]

    if missing:
        print(f"[AVISO] Modelos nao encontrados localmente (pulados): {', '.join(missing)}")
    if not targets:
        print("[ERRO] Nenhum dos modelos alvo esta instalado. Baixe com `ollama pull <modelo>`.")
        return

    summary: list[dict] = []
    for model in targets:
        res = benchmark_model(model, args.num_ctx, args.num_predict)
        save_benchmark(DB_PATH, res)
        summary.append(res)

    print("\n=== Resumo Comparativo (Salvo no SQLite) ===")
    print("| Modelo | Tamanho | Processador | TTFT Médio (ms) | TPS (tok/s) | p50 (ms) | p95 (ms) |")
    print("| :--- | :--- | :--- | :---: | :---: | :---: | :---: |")
    for r in summary:
        print(
            f"| {r['model_name']} | {r['ollama_size']} | {r['ollama_processor']} | "
            f"{r['ttft_ms_avg']} | {r['tps_avg']} | {r['latency_p50_ms']} | {r['latency_p95_ms']} |"
        )


if __name__ == "__main__":
    main()
