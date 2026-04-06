# 🔍☑️ RCA Variables Extractor v7

**Herramienta para extraer automáticamente variables técnicas y ambientales desde Resoluciones de Calificación Ambiental (RCA) del Sistema de Evaluación de Impacto Ambiental (SEIA) de Chile.**

Procesa PDFs nativamente con la API de Google Gemini —incluyendo documentos escaneados— y extrae datos estructurados en JSON. El pipeline cubre adquisición de documentos, extracción LLM, post-procesamiento, georreferenciación, análisis de ciclo de vida y visualización interactiva.

[![CI](https://github.com/RobertoOtarola/rca_variables_extractor/actions/workflows/ci.yml/badge.svg)](https://github.com/RobertoOtarola/rca_variables_extractor/actions)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License: GPL-3.0](https://img.shields.io/badge/License-GPL--3.0-green.svg)](LICENSE)

---

## Estado del Proyecto

| Fase | Estado | Descripción |
|------|--------|-------------|
| 🌐 **-1 · Adquisición** | ✅ `v0.6.0` | Scraper SEIA — descarga RCA e ICE por `id_expediente` |
| 📄 **0 · Validación PDFs** | ✅ `v0.1.0` | Detección de corruptos, cifrados y escaneados |
| 🤖 **1 · Extracción LLM** | ✅ `v0.1.0` | Gemini — 430/432 PDFs procesados (99.5%) · 20.77 GW |
| 🗄️ **2 · Post-procesamiento** | ✅ `v0.2.0` | Normalización, validación y persistencia en SQLite |
| 🌍 **3 · Geoespacial** | ✅ `v0.3.0` | Parser UTM multi-formato → WGS84 y GeoJSON |
| ⚗️ **4 · ACV + API + Dashboard** | ✅ `v0.4.0` | LCA, FastAPI y Streamlit con acceso nativo a SQLite |
| 📦 **5 · Arquitectura** | ✅ `v0.5.0` | Paquete `src/`, CI/CD, lockfile, Makefile |
| 🚀 **6 · Scraper refactorizado** | ✅ `v0.6.0` | BS4, inyección de sesión, checkpoint, logging, streaming |
| 🔐 **7 · Auditoría y Concurrencia** | ✅ `v0.7.0` | Thread-safety (`--workers > 1`), soporte nativo `uv` y Code Review |

---

## Instalación

**Prerrequisitos:** Python ≥ 3.11 (o la herramienta [uv](https://github.com/astral-sh/uv))

```bash
git clone https://github.com/RobertoOtarola/rca_variables_extractor.git
cd rca_variables_extractor

# Opción A: Instalación ultrarrápida con uv (Recomendado)
uv sync                 # lee el uv.lock y prepara el entorno .venv al instante
source .venv/bin/activate

# Opción B: Modo tradicional con pip
python3 -m venv .venv && source .venv/bin/activate
pip install -e "."        # instalación base
pip install -e ".[dev]"   # incluye pytest, ruff, mypy

# Configuración
cp .env.example .env      # añadir GEMINI_API_KEY
```

---

## Uso Rápido

```bash
# 1. Descargar RCAs desde el SEIA
rca_scraper --input data/expedientes.csv --delay 4.0

# 2. Extraer variables con Gemini
rca_extractor --pdf-folder data/raw/scraped --output data/processed/results.xlsx

# 3. Post-procesar y persistir en BD
python -m rca_extractor.post_processing.run --input data/processed/results.xlsx

# 4. Levantar servicios
uvicorn rca_extractor.api.main:app --reload          # API REST → http://localhost:8000/docs
streamlit run src/rca_extractor/dashboard/app.py    # Dashboard → http://localhost:8501
```

---

## Estructura del Proyecto

```
rca_variables_extractor/
├── pyproject.toml                  # Dependencias y configuración del paquete
├── requirements.txt                # Dependencias legacy (referencia; usar pyproject.toml)
├── seia-variables.xlsx             # Schema de variables a extraer
├── .env.example                    # Template de variables de entorno
├── .gitignore
├── LICENSE                         # GPL-3.0
│
├── prompts/
│   └── extraction_prompt.md        # Prompt con formatos estrictos por variable
│
├── tests/
│   ├── conftest.py                 # Fixture: GEMINI_API_KEY=dummy
│   ├── test_checkpoint.py
│   ├── test_output_validator.py
│   ├── test_prompt_builder.py
│   └── test_rca_scraper.py
│
└── src/rca_extractor/              # Package root (pip install -e .)
    ├── cli.py                      # Entrypoint del extractor LLM
    ├── config.py                   # Configuración centralizada (env vars)
    │
    ├── core/
    │   ├── gemini_client.py        # Cliente Gemini + backoff + retry inteligente
    │   └── pdf_pipeline.py         # Orquestación: PDF nativo o escaneado
    │
    ├── utils/
    │   ├── checkpoint.py           # Checkpoint/resume para procesos batch
    │   ├── logger.py               # Logging rotativo estructurado
    │   ├── output_validator.py     # Extracción y reparación de JSON
    │   ├── pdf_utils.py            # Detección de PDFs escaneados
    │   └── prompt_builder.py       # Construcción de prompts desde schema XLSX
    │
    ├── tools/
    │   ├── check_gitignore.py      # Verifica que archivos locales estén bien ignorados por Git
    │   ├── check_pdfs.py           # Auditoría del corpus: corruptos, cifrados, escaneados
    │   ├── list_models.py          # Lista los modelos Gemini disponibles para la API Key
    │   ├── rca_scraper.py          # Scraper SEIA: descarga RCA + ICE (PDF/XML)
    │   └── snippet_api_key.py      # Verifica que la API Key de Gemini funciona
    │
    ├── post_processing/
    │   ├── db_storage.py           # ORM SQLAlchemy → SQLite / PostgreSQL
    │   ├── normalizer.py           # Strings → valores tipados (formato numérico chileno)
    │   ├── run.py                  # CLI: python -m rca_extractor.post_processing.run
    │   └── validator.py            # Rangos científicos + detección de outliers
    │
    ├── geo/
    │   ├── coord_parser.py         # UTM multi-formato → WGS84
    │   └── spatial_analysis.py     # Intersección con áreas protegidas SNASPE
    │
    ├── lca/
    │   ├── benchmarks.py           # Clasificación LOW / NORMAL / HIGH
    │   ├── calculator.py           # Cálculo de GEI, agua y energía de vida útil
    │   └── factors.py              # Factores IPCC/NREL/IEA por tecnología
    │
    ├── api/
    │   └── main.py                 # FastAPI: /health /stats /projects /lca
    │
    └── dashboard/
        ├── app.py                  # Streamlit + pd.read_sql
        └── components/
            ├── charts.py           # Histogramas, scatter, box plots
            └── maps.py             # Mapas Plotly/Mapbox
```

---

## Scraper SEIA (`tools/rca_scraper.py`)

Descarga RCAs e ICEs desde `seia.sea.gob.cl` dado un `id_expediente`. Soporta lotes desde CSV, XLSX u ODS.

```bash
# Descarga individual (RCA)
rca_scraper --id 7021124

# Descarga individual (RCA + ICE)
rca_scraper --id 7021124 --ice

# Lote desde archivo (columna requerida: id_expediente)
rca_scraper --input data/expedientes.csv --delay 4.0 --ice
```

**Variables de entorno del scraper** (en `.env`):

| Variable | Default | Descripción |
|----------|---------|-------------|
| `SCRAPED_DIR` | `data/raw/scraped` | Directorio de salida |
| `SCRAPER_DELAY` | `3.0` | Segundos base entre requests |
| `SCRAPER_CHECKPOINT` | `checkpoints/scraper_checkpoint.json` | Archivo de checkpoint |

Los documentos se guardan en `data/raw/scraped/{id_expediente}/RCA.pdf` (o `.xml` para ICE).

---

## Extractor LLM (`cli.py`)

```bash
# Estrategia de 2 pasadas (recomendada para lotes grandes)
rca_extractor --pdf-folder data/raw/scraped --output data/processed/results.xlsx \
  --workers 1 --cooldown 15 --max-retries 2

# Segunda pasada — solo los fallidos (el checkpoint omite los exitosos)
rca_extractor --pdf-folder data/raw/scraped --output data/processed/results.xlsx \
  --workers 1 --cooldown 15 --max-retries 5
```

| Opción | Default | Descripción |
|--------|---------|-------------|
| `--pdf-folder` | `rcas/` | Carpeta con PDFs de entrada |
| `--output` | `rca_results.xlsx` | Archivo Excel de salida |
| `--workers` | `1` | Paralelismo — **> 1 es seguro** (escritura con bloqueo transaccional) |
| `--model` | `gemini-2.5-flash` | Modelo de Gemini |
| `--cooldown` | `15` | Segundos entre PDFs |
| `--max-retries` | `8` | Reintentos por PDF |
| `--reset` | `False` | Ignorar checkpoint existente |
| `--dry-run` | `False` | Listar PDFs pendientes sin procesar |

---

## Calidad y Tests

```bash
# Tests con cobertura
PYTHONPATH=src pytest tests/ --cov=rca_extractor --cov-report=term-missing

# Linting
ruff check src/

# Tipado
mypy src/rca_extractor/core/
```

**Estado actual:** 38 tests passing · 2 skipped (requieren credenciales reales) · `ruff` ✅ · `mypy` ✅

---

## Variables de Entorno

Copiar desde `.env.example` y completar:

```bash
# Requerida
GEMINI_API_KEY="tu_api_key_aqui"

# Modelo Gemini (default: gemini-2.5-flash)
# GEMINI_MODEL=models/gemini-2.5-flash

# Retries y delays
# MAX_RETRIES="8"
# RETRY_BASE_DELAY="65.0"
# INTER_PDF_COOLDOWN="15"

# Rutas
# PDF_FOLDER="data/raw"
# OUTPUT_FILE="data/processed/results.xlsx"
# CHECKPOINT_FILE="checkpoints/checkpoint.json"
# LOG_FILE="logs/extractor.log"

# Scraper SEIA
# SCRAPED_DIR="data/raw/scraped"
# SCRAPER_DELAY="3.0"
# SCRAPER_CHECKPOINT="checkpoints/scraper_checkpoint.json"
```

---

## Variables Extraídas

Definidas en `seia-variables.xlsx`. El prompt en `prompts/extraction_prompt.md` especifica el formato exacto de cada una.

| Variable | Cobertura | Formato |
|----------|-----------|---------|
| `potencia_nominal_bruta_mw` | 98.8% | Float (MW) |
| `superficie_total_intervenida_ha` | 98.8% | Float (ha) |
| `intensidad_de_uso_de_suelo_ha_mw_1` | 97.7% | Float (ha/MW) |
| `vida_util_anos` | 98.4% | Float (años) |
| `tipo_de_generacion_eolica_fv_csp` | 99.8% | `"Fotovoltaica"` / `"Eólica"` / `"CSP"` |
| `factor_de_planta` | 26.3% | Float 0–1 |
| `emisiones_mp10_t_ano_1` | 80.9% | Float (t/año) |
| `emisiones_mp2_5_t_ano_1` | 68.1% | Float (t/año) |
| `perdida_de_cobertura_vegetal_ha` | 65.8% | Float (ha) |
| `consumo_de_agua_dulce_m3_mwh_1` | 21.9% | Float (m³/MWh) |
| `region_provincia_y_comuna` | 100% | String |
| `coordenadas_utm_geograficas_punto_representativo` | 97.4% | String (UTM) |
| `proximidad_y_superposicion_con_areas_protegidas` | 99.8% | String ≤ 200 chars |
| `caracteristicas_del_generador` | 100% | Texto descriptivo |
| `tasas_de_mortalidad_de_aves_murcielagos` | 3.7% | String o `"N/A"` |
| `escaneado` | 100% | `"sí"` / `"no"` (metadato del pipeline) |

---

## Resultados del Corpus

| Indicador | Valor |
|-----------|-------|
| Total RCAs procesadas | 430 / 432 (99.5%) |
| Potencia total documentada | **20,770 MW (20.77 GW)** |
| Proyectos fotovoltaicos | 369 (85.8%) — 12,159 MW |
| Proyectos eólicos | 58 (13.5%) — 8,107 MW |
| PDFs escaneados (ruta imagen) | 125 (29.1%) |
| Proyectos georreferenciados | 419 (97.4%) |
| Región con mayor capacidad | Antofagasta — 8,329 MW |

---

## Licencia

[GPL-3.0](LICENSE) — Roberto Otárola · CEDEUS UC · 2026
