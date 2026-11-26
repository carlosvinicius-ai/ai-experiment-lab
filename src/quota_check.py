"""Verifica o uso de disco atual do laboratorio frente ao orcamento de 1 TB."""

from pathlib import Path


QUOTAS_GB = {
    "data": 180.0,
    "models": 80.0,
    "db": 50.0,
    "src": 40.0,
    "notebooks": 10.0,
    "reports": 10.0,
}


def folder_size_gb(path: Path) -> float:
    if not path.exists():
        return 0.0
    total_bytes = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    return total_bytes / (1024 ** 3)


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    print(f"=== Uso de Armazenamento em {root} ===")
    for folder, limit_gb in QUOTAS_GB.items():
        used = folder_size_gb(root / folder)
        pct = (used / limit_gb) * 100.0 if limit_gb > 0 else 0.0
        print(f"  {folder:<12} | Usado: {used:6.3f} GB / {limit_gb:5.1f} GB ({pct:5.2f}%)")


if __name__ == "__main__":
    main()
