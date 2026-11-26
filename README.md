# AI Experiment Lab

Laboratório local e modular para experimentação em **Inteligência Artificial**, **Ciência de Dados** e **Computação Quântica**, com persistência de telemetria em SQLite e sincronização opcional com um cofre Obsidian.

- **Motor de Inferência Local**: Ollama (SLMs/LLMs quantizados em GGUF).
- **Persistência de Experimentos**: SQLite (`db/lab_experiments.db`).
- **Configuração Segura**: Variáveis de ambiente em `.env` carregadas e validadas via `pydantic-settings` (`src/settings.py`).

---

## ⚙️ Configuração Inicial (Windows PowerShell)

1. **Criar e ativar o ambiente virtual (`venv`)**:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

2. **Configurar variáveis locais sem expor caminhos no Git**:
   ```powershell
   Copy-Item .env.example .env
   ```
   Edite o arquivo `.env` (ignorado pelo `.gitignore`) com os caminhos da sua máquina (`LAB_DB_PATH`, `OLLAMA_URL`, `OBSIDIAN_PROJECT_DIR`).

3. **Inicializar o banco SQLite e rodar o diagnóstico de hardware**:
   ```powershell
   python src/db_init.py
   python src/lab_diag.py
   ```

---

## 🧩 Scripts Disponíveis (`src/`)

| Script | Responsabilidade | Exemplo de Uso |
| :--- | :--- | :--- |
| `src/settings.py` | Carrega e valida variáveis do `.env` via `pydantic-settings` (caminhos do banco, drive, Ollama e Obsidian). | Importado automaticamente pelos demais módulos. |
| `src/db_init.py` | Cria as pastas do laboratório e inicializa as tabelas SQLite (`problems`, `datasets`, `experiments`, `hardware_runs`, `benchmarks`). | `python src/db_init.py` |
| `src/lab_diag.py` | Coleta telemetria real de CPU, RAM, disco e testa o Ollama (Cold Start vs. Warm Start), salvando em `hardware_runs`. | `python src/lab_diag.py` |
| `src/quota_check.py` | Audita o consumo de disco por módulo em relação às quotas planejadas do drive local. | `python src/quota_check.py` |
| `src/add_problem.py` | CLI interativa para cadastrar novos problemas reais (`PROB-XX`) via Canvas de 10 perguntas e Matriz de Priorização no SQLite e sincronizar o Obsidian. | `python src/add_problem.py` |
| `src/benchmark_runner.py` | Executa benchmark determinístico (`temperature=0.0`, `seed=42`, 1 warmup descartado + 10 prompts) medindo `TTFT`, `TPS`, `p50`, `p95` e uso CPU/GPU (`ollama ps`). | `python src/benchmark_runner.py --models qwen2.5:1.5b qwen2.5:3b` |
| `src/export_obsidian.py` | Exporta as tabelas `problems`, `experiments`, `benchmarks` e `hardware_runs` do SQLite para Markdown (`reports/` e cofre Obsidian). | `python src/export_obsidian.py --obsidian` |

---

## 📊 Notebooks de Análise (`notebooks/`)

- **`notebooks/semana_02_analise_benchmark.ipynb`**: Análise exploratória e visual (Pandas + Matplotlib + Seaborn) dos benchmarks da tabela `benchmarks`, comparando eficiência por GB, `TTFT`/`p50`/`p95`, impacto controlado da quantização (`Q4_K_M` vs. `Q8_0`) e projeção de processamento em lote.

---

## 🔐 Segurança e Boas Práticas de Versionamento

Este repositório segue uma política estrita de higiene no Git:
- **Nunca versionar**: `.env`, chaves (`.key`, `.pem`), bancos de dados (`.db`, `.sqlite`), datasets brutos/processados (`data/raw/`, `data/processed/`), pesos de modelos (`.gguf`, `.safetensors`, `models/`) e relatórios locais gerados (`reports/`).
- **Sempre versionar**: `.env.example` (somente placeholders neutros), código-fonte (`src/`), `requirements.txt` e notebooks sem dados sensíveis.
