"""Configuracoes tipadas via variaveis de ambiente (.env) com Pydantic Settings."""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent


class LabSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    lab_db_path: Path = ROOT_DIR / "db" / "experiments.db"
    ollama_url: str = "http://localhost:11434"
    obsidian_project_dir: Path = ROOT_DIR / "reports" / "obsidian"

    @property
    def catalog_path(self) -> Path:
        return self.obsidian_project_dir / "Catalogo de Problemas Reais.md"

    @property
    def obsidian_panel_path(self) -> Path:
        return self.obsidian_project_dir / "Painel de Experimentos (SQLite).md"

    @property
    def default_report_path(self) -> Path:
        return ROOT_DIR / "reports" / "painel_experimentos.md"


settings = LabSettings()
