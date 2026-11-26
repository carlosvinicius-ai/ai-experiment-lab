"""Coleta telemetria de hardware e mede cold start vs warm start no Ollama."""

import platform
import shutil
import sqlite3
import subprocess
import time
from pathlib import Path

import httpx
import psutil

from settings import ROOT_DIR, settings

DB_PATH = settings.lab_db_path
OLLAMA_URL = settings.ollama_url


def get_system_snapshot() -> dict:
    mem = psutil.virtual_memory()
    disk = shutil.disk_usage(ROOT_DIR)
    return {
        "os": f"{platform.system()} {platform.release()}",
        "cpu_cores_phys": psutil.cpu_count(logical=False),
        "cpu_cores_log": psutil.cpu_count(logical=True),
        "cpu_pct": psutil.cpu_percent(interval=0.5),
        "ram_total_mb": round(mem.total / (1024 ** 2), 1),
        "ram_used_mb": round(mem.used / (1024 ** 2), 1),
        "ram_free_mb": round(mem.available / (1024 ** 2), 1),
        "disk_total_gb": round(disk.total / (1024 ** 3), 1),
        "disk_free_gb": round(disk.free / (1024 ** 3), 1),
    }


def get_ollama_ps() -> str:
    try:
        res = subprocess.run(
            ["ollama", "ps"], capture_output=True, text=True, timeout=10, check=False
        )
        return res.stdout.strip()
    except Exception as exc:
        return f"erro_ollama_ps: {exc}"


def list_first_ollama_model() -> str | None:
    try:
        resp = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=5.0)
        resp.raise_for_status()
        models = resp.json().get("models", [])
        return models[0]["name"] if models else None
    except Exception:
        return None


def record_run(run_label: str, model_name: str | None, state: str, snap: dict, latency_ms: float, notes: str = "") -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO hardware_runs
                (run_label, model_name, state, cpu_pct, ram_used_mb, ram_free_mb, vram_used_mb, latency_ms, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_label,
                model_name,
                state,
                snap["cpu_pct"],
                snap["ram_used_mb"],
                snap["ram_free_mb"],
                None,
                round(latency_ms, 2),
                notes,
            ),
        )
        conn.commit()


def run_ollama_probe(model: str) -> None:
    subprocess.run(["ollama", "stop", model], capture_output=True, check=False)
    time.sleep(1.0)

    prompts = [
        ("cold_start", "Responda apenas com OK."),
        ("warm_start", "Responda apenas com OK."),
        ("warm_start", "Responda apenas com OK."),
    ]

    for idx, (state, prompt) in enumerate(prompts, start=1):
        t0 = time.perf_counter()
        resp = httpx.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.0, "seed": 42, "num_predict": 16},
            },
            timeout=120.0,
        )
        resp.raise_for_status()
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        snap = get_system_snapshot()
        ps_out = get_ollama_ps()
        record_run(f"diag_run_{idx}", model, state, snap, elapsed_ms, ps_out)
        print(f"Run {idx} ({state}) | Latencia: {elapsed_ms:.1f} ms | RAM livre: {snap['ram_free_mb']} MB")


def main() -> None:
    snap = get_system_snapshot()
    print("=== Diagnostico Basal do Sistema ===")
    for k, v in snap.items():
        print(f"  {k}: {v}")

    if DB_PATH.exists():
        record_run("basal_idle", None, "idle", snap, 0.0, "Sistema ocioso antes da chamada Ollama")

    model = list_first_ollama_model()
    if not model:
        print("\n[AVISO] Nenhum modelo encontrado ou servidor Ollama offline.")
        print("Baixe um modelo leve para testar (ex: ollama pull qwen2.5:3b) e rode novamente.")
        return

    print(f"\n=== Testando Cold Start vs Warm Start com modelo: {model} ===")
    run_ollama_probe(model)
    print("\n=== Saida atual de `ollama ps` ===")
    print(get_ollama_ps())


if __name__ == "__main__":
    main()
