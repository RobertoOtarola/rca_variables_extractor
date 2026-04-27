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
DEFAULT_MODEL: str = "gemini-2.5-flash"
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0"))
MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "8"))
RETRY_BASE_DELAY: float = float(
    os.getenv("RETRY_BASE_DELAY", "65.0")
)  # segundos — piso para 429 free tier
INTER_PDF_COOLDOWN: int = int(os.getenv("INTER_PDF_COOLDOWN", "15"))  # segundos entre PDFs

# ── Rutas ────────────────────────────────────────────────────────────────────
PROJECT_ROOT: Path = Path(__file__).parent.parent.parent
PDF_FOLDER: Path = PROJECT_ROOT / os.getenv("PDF_FOLDER", "data/raw")
DATA_DIR: Path = PROJECT_ROOT / "data" / "processed"
DB_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR}/rca_data.db")

OUTPUT_FILE: Path = DATA_DIR / os.getenv("OUTPUT_FILE", "results.xlsx")
VARIABLES_FILE: Path = PROJECT_ROOT / os.getenv("VARIABLES_FILE", "data/config/seia-variables.xlsx")
CHECKPOINT_FILE: Path = PROJECT_ROOT / os.getenv("CHECKPOINT_FILE", "checkpoints/checkpoint.json")
LOG_FILE: Path = PROJECT_ROOT / os.getenv("LOG_FILE", "logs/extractor.log")
PROMPT_FILE: Path = PROJECT_ROOT / "prompts" / "extraction_prompt.md"

# ── Prompts específicos por tecnología ────────────────────────────────────────
PROMPTS_DIR: Path = PROJECT_ROOT / "prompts"
TECH_DETECTION_PROMPT: Path = PROMPTS_DIR / "tech_detection_prompt.md"
PROMPT_EOLICA: Path = PROMPTS_DIR / "extraction_prompt_eolica.md"
PROMPT_FV: Path = PROMPTS_DIR / "extraction_prompt_fv.md"
PROMPT_FALLBACK: Path = PROMPTS_DIR / "extraction_prompt.md"
TECH_DETECTION_ENABLED: bool = os.getenv("TECH_DETECTION_ENABLED", "true").lower() != "false"

# ── Scraper SEIA ─────────────────────────────────────────────────────────────
SCRAPED_DIR: Path = PROJECT_ROOT / os.getenv("SCRAPED_DIR", "data/scraped")
SCRAPER_DELAY: float = float(os.getenv("SCRAPER_DELAY", "3.0"))
SCRAPER_CHECKPOINT: Path = PROJECT_ROOT / os.getenv("SCRAPER_CHECKPOINT", "checkpoints/scraper_checkpoint.json")
SCRAPER_LOG_FILE: Path = PROJECT_ROOT / os.getenv("SCRAPER_LOG_FILE", "logs/scraper.log")

# ── Procesamiento ─────────────────────────────────────────────────────────────
MAX_WORKERS: int = int(os.getenv("MAX_WORKERS", "1"))  # >1 habilita concurrencia

# ── Columna del Excel de variables ───────────────────────────────────────────
VARIABLES_COLUMN: str = os.getenv("VARIABLES_COLUMN", "Variable Clave")
