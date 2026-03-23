"""
config.py — Configuración centralizada del extractor de RCA.
Todas las rutas, parámetros del modelo y flags de ejecución viven aquí.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── API ──────────────────────────────────────────────────────────────────────
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

if not GEMINI_API_KEY:
    raise ValueError(
        "⚠️  GEMINI_API_KEY no encontrada. "
        "Defínela en tu archivo .env o en las variables de entorno del sistema."
    )

# ── Modelo ───────────────────────────────────────────────────────────────────
DEFAULT_MODEL: str = "gemini-2.0-flash"
GEMINI_MODEL: str  = os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0"))
MAX_RETRIES: int   = int(os.getenv("MAX_RETRIES", "4"))
RETRY_BASE_DELAY: float = float(os.getenv("RETRY_BASE_DELAY", "2.0"))   # segundos

# ── Rutas ────────────────────────────────────────────────────────────────────
BASE_DIR:        Path = Path(__file__).parent
PDF_FOLDER:      Path = BASE_DIR / os.getenv("PDF_FOLDER", "rcas")
OUTPUT_FILE:     Path = BASE_DIR / os.getenv("OUTPUT_FILE", "rca_results.xlsx")
VARIABLES_FILE:  Path = BASE_DIR / os.getenv("VARIABLES_FILE", "seia-variables.xlsx")
CHECKPOINT_FILE: Path = BASE_DIR / os.getenv("CHECKPOINT_FILE", "checkpoints/checkpoint.json")
LOG_FILE:        Path = BASE_DIR / os.getenv("LOG_FILE", "logs/extractor.log")
PROMPT_FILE:     Path = BASE_DIR / "prompts" / "extraction_prompt.md"

# ── Procesamiento ─────────────────────────────────────────────────────────────
MAX_WORKERS: int = int(os.getenv("MAX_WORKERS", "1"))   # >1 habilita concurrencia

# ── Columna del Excel de variables ───────────────────────────────────────────
VARIABLES_COLUMN: str = os.getenv("VARIABLES_COLUMN", "Variable Clave")
