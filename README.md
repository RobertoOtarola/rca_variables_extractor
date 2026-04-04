# 🔍☑️ RCA Variables Extractor

**Extractor automático de variables técnicas y ambientales desde Resoluciones de Calificación Ambiental (RCA) del Sistema de Evaluación de Impacto Ambiental (SEIA) de Chile.**

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
| 📦 **5 · Arquitectura** | ✅ `v0.5.0` | Paquete `src/`, CI/CD, `uv.lock`, Makefile |
| 🚀 **6 · Scraper refactorizado** | ✅ `v0.6.0` | BS4, inyección de sesión, checkpoint, logging, streaming |

---

## Instalación

**Prerrequisitos:** Python ≥ 3.11 · [uv](https://github.com/astral-sh/uv) (recomendado) o pip

```bash
git clone https://github.com/RobertoOtarola/rca_variables_extractor.git
cd rca_variables_extractor

# Con uv (reproducible con lockfile)
uv sync --all-extras --dev

# Con pip (modo editable)
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Configuración
cp .env.example .env   # Añadir GEMINI_API_KEY
```

---

## Uso Rápido

```bash
# 1. Descargar RCAs desde el SEIA
rca-scraper --input data/expedientes.csv --delay 4.0

# 2. Extraer variables con Gemini
rca-extractor --pdf-folder data/raw/scraped --output data/processed/results.xlsx

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
├── Makefile                        # make check | make start-api | make scrape ID=...
├── uv.lock                         # Lockfile determinístico
├── .env.example                    # Template de variables de entorno
├── .github/
│   └── workflows/
│       └── ci.yml                  # CI: ruff + mypy + pytest
│
└── src/rca_extractor/              # Package root
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
    │   ├── check_pdfs.py           # Auditoría del corpus PDF
    │   └── rca_scraper.py          # Scraper SEIA: RCA + ICE (PDF/XML)
    │
    ├── post_processing/
    │   ├── normalizer.py           # Strings → valores tipados (formato chileno)
    │   ├── validator.py            # Rangos científicos + detección de outliers
    │   └── db_storage.py           # ORM SQLAlchemy → SQLite / PostgreSQL
    │
    ├── geo/
    │   ├── coord_parser.py         # UTM multi-formato → WGS84
    │   └── spatial_analysis.py     # Intersección con áreas protegidas SNASPE
    │
    ├── lca/
    │   ├── factors.py              # Factores IPCC/NREL/IEA por tecnología
    │   ├── calculator.py           # Cálculo de GEI, agua y energía de vida útil
    │   └── benchmarks.py           # Clasificación LOW / NORMAL / HIGH
    │
    ├── api/
    │   └── main.py                 # FastAPI: /health /stats /projects /lca
    │
    └── dashboard/
        ├── app.py                  # Streamlit + pd.read_sql
        └── components/
            ├── maps.py             # Mapas Plotly/Mapbox
            └── charts.py           # Histogramas, scatter, box plots
```

---

## Scraper SEIA (`tools/rca_scraper.py`)

Descarga RCAs e ICEs desde `seia.sea.gob.cl` dado un `id_expediente`. Soporta lotes desde CSV, XLSX u ODS.

```bash
# Descarga individual (RCA)
rca-scraper --id 7021124

# Descarga individual (RCA + ICE)
rca-scraper --id 7021124 --ice

# Lote desde archivo (columna requerida: id_expediente)
rca-scraper --input data/expedientes.csv --delay 4.0 --ice

# Shortcut via Makefile
make scrape ID=7021124
```

**Variables de entorno del scraper** (en `.env`):

| Variable | Default | Descripción |
|----------|---------|-------------|
| `SCRAPED_DIR` | `data/raw/scraped` | Directorio de salida |
| `SCRAPER_DELAY` | `3.0` | Segundos base entre requests |
| `SCRAPER_CHECKPOINT` | `checkpoints/scraper_checkpoint.json` | Archivo de checkpoint |

Los documentos descargados se guardan en `data/raw/scraped/{id_expediente}/RCA.pdf` (o `.xml` para ICE).

---

## Extractor LLM (`cli.py`)

```bash
# Extracción completa — estrategia de 2 pasadas (recomendada)
rca-extractor --pdf-folder data/raw/scraped --output data/processed/results.xlsx \
  --workers 1 --cooldown 15 --max-retries 2

# Segunda pasada — solo los fallidos
rca-extractor --pdf-folder data/raw/scraped --output data/processed/results.xlsx \
  --workers 1 --cooldown 15 --max-retries 5
```

| Opción | Default | Descripción |
|--------|---------|-------------|
| `--pdf-folder` | `rcas/` | Carpeta con PDFs de entrada |
| `--output` | `rca_results.xlsx` | Archivo Excel de salida |
| `--workers` | `1` | Paralelismo — **no usar > 1** (no thread-safe) |
| `--model` | `gemini-2.5-flash` | Modelo de Gemini |
| `--cooldown` | `15` | Segundos entre PDFs |
| `--max-retries` | `8` | Reintentos por PDF |
| `--reset` | `False` | Ignorar checkpoint existente |
| `--dry-run` | `False` | Listar PDFs pendientes sin procesar |

---

## Calidad y Tests

```bash
# Suite completa (ruff + mypy + pytest)
make check

# Solo tests con cobertura
uv run pytest tests/ --cov=rca_extractor --cov-report=term-missing

# Solo linting
uv run ruff check src/

# Solo tipos
uv run mypy src/rca_extractor/core/
```

**Estado actual:** 38 tests passing · 2 skipped (requieren credenciales) · `ruff` ✅ · `mypy` ✅

---

## Variables de Entorno

Todas las variables se configuran en `.env` (copiar desde `.env.example`):

```bash
# Requerida
GEMINI_API_KEY="tu_api_key_aqui"

# Modelo Gemini (default: gemini-2.5-flash)
# GEMINI_MODEL=models/gemini-2.5-flash

# Retries y delays
# MAX_RETRIES="8"
# RETRY_BASE_DELAY="65.0"
# INTER_PDF_COOLDOWN="15"

# Rutas de salida
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

Definidas en `data/config/seia-variables.xlsx`. El prompt en `prompts/extraction_prompt.md` especifica el formato exacto.

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
| `escaneado` | 100% | `"sí"` / `"no"` (metadato) |

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

[GPL-3.0](LICENSE) — Roberto Otárola Estrada · CEDEUS UC · 2026
