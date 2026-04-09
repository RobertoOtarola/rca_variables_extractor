# 🔍☑️ RCA Variables Extractor

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
| 🤖 **1 · Extracción LLM** | ✅ `v0.1.0` | Gemini 2.5 Flash — 430/432 PDFs procesados (99.5%) · 20.77 GW |
| 🗄️ **2 · Post-procesamiento** | ✅ `v0.2.0` | Normalización, validación y persistencia en SQLite |
| 🌍 **3 · Geoespacial** | ✅ `v0.3.0` | Parser UTM multi-formato → WGS84 y GeoJSON |
| ⚗️ **4 · ACV + API + Dashboard** | ✅ `v0.4.0` | LCA, FastAPI y Streamlit con acceso nativo a SQLite |
| 📦 **5 · Arquitectura** | ✅ `v0.5.0` | Paquete `src/`, CI/CD, lockfile, Makefile |
| 🚀 **6 · Scraper refactorizado** | ✅ `v0.6.0` | BS4, inyección de sesión, checkpoint, logging, streaming |
| 🔧 **7 · Estabilidad** | ✅ `v0.7.0` | Thread-safety en CLI, módulos LCA/Dashboard completos, geo opcional |

---

## Instalación

**Prerrequisitos:** Python ≥ 3.11

### Con `uv` (recomendado)

```bash
git clone https://github.com/RobertoOtarola/rca_variables_extractor.git
cd rca_variables_extractor

# Instalar uv si no está disponible
curl -LsSf https://astral.sh/uv/install.sh | sh

# Instalar entorno completo (reproducible con uv.lock)
uv sync --dev

# Con capa geoespacial (requiere GDAL en el sistema)
# macOS:  brew install gdal
# Ubuntu: sudo apt-get install gdal-bin libgdal-dev
uv sync --extra geo --dev

cp .env.example .env   # añadir GEMINI_API_KEY
```

### Con `pip`

```bash
git clone https://github.com/RobertoOtarola/rca_variables_extractor.git
cd rca_variables_extractor
python3 -m venv .venv && source .venv/bin/activate

pip install -e "."          # instalación base (sin capa geoespacial)
pip install -e ".[geo]"     # con capa geoespacial (requiere GDAL)
pip install -e ".[dev]"     # herramientas de desarrollo

cp .env.example .env   # añadir GEMINI_API_KEY
```

---

## Uso Rápido

```bash
# 1. Descargar RCAs desde el SEIA
rca-scraper --input data/expedientes.csv --delay 4.0

# 2. Extraer variables con Gemini 2.5 Flash
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
├── pyproject.toml                  # Dependencias y configuración (v0.7.0)
├── uv.lock                         # Lockfile determinístico
├── .env.example                    # Template de variables de entorno
├── .gitignore
├── LICENSE                         # GPL-3.0
├── .github/
│   └── workflows/
│       └── ci.yml                  # CI: ruff + ruff format + mypy + pytest (con GDAL)
│
├── prompts/
│   └── extraction_prompt.md        # Prompt con formatos estrictos por variable
│
├── tests/
│   ├── conftest.py                 # Fixture: GEMINI_API_KEY=dummy
│   ├── test_benchmarks.py          # 25 tests — lca/benchmarks
│   ├── test_checkpoint.py          # 7 tests  — utils/checkpoint
│   ├── test_lca_calculator.py      # 16 tests — lca/calculator
│   ├── test_output_validator.py    # 12 tests — utils/output_validator
│   ├── test_prompt_builder.py      # 10 tests — utils/prompt_builder
│   └── test_rca_scraper.py         # 6 tests  — tools/rca_scraper
│                                   # Total: 76 tests + 2 skipped (requieren credenciales)
└── src/rca_extractor/
    ├── cli.py                      # Entrypoint extractor LLM (thread-safe con Lock desde v0.7.0)
    ├── config.py                   # GEMINI_MODEL = "gemini-2.5-flash" (ID explícito)
    │
    ├── core/
    │   ├── gemini_client.py        # Cliente Gemini 2.5 Flash + backoff + retry
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
    │   ├── check_gitignore.py      # Verifica que archivos locales estén bien ignorados
    │   ├── check_pdfs.py           # Auditoría del corpus: corruptos, cifrados, escaneados
    │   ├── list_models.py          # Lista los modelos Gemini disponibles para la API Key
    │   ├── rca_scraper.py          # Scraper SEIA: RCA + ICE (PDF/XML)
    │   └── snippet_api_key.py      # Verifica conexión con Gemini y modelo activo
    │
    ├── post_processing/
    │   ├── db_storage.py           # ORM SQLAlchemy → SQLite / PostgreSQL
    │   ├── normalizer.py           # Strings → valores tipados (formato numérico chileno)
    │   ├── run.py                  # CLI: python -m rca_extractor.post_processing.run
    │   └── validator.py            # Rangos científicos + detección de outliers
    │
    ├── geo/                        # Requiere pip install -e ".[geo]" + GDAL del sistema
    │   ├── coord_parser.py         # UTM multi-formato → WGS84
    │   └── spatial_analysis.py     # Intersección con áreas protegidas SNASPE
    │
    ├── lca/
    │   ├── benchmarks.py           # Clasificación LOW/NORMAL/HIGH (IPCC/NREL/Ong)
    │   ├── calculator.py           # compute_lca() → LCAResult(ghg, water, energy)
    │   └── factors.py              # Factores de referencia por tecnología
    │
    ├── api/
    │   └── main.py                 # FastAPI: /health /stats /projects /lca
    │
    └── dashboard/
        ├── app.py                  # Streamlit + pd.read_sql
        └── components/
            ├── __init__.py
            ├── charts.py           # render_histogram / render_scatter / render_box_plot
            └── maps.py             # render_project_map (scatter_mapbox centrado en Chile)
```

---

## Scraper SEIA (`tools/rca_scraper.py`)

Descarga RCAs e ICEs desde `seia.sea.gob.cl` dado un `id_expediente`. Soporta lotes desde CSV, XLSX u ODS.

```bash
rca-scraper --id 7021124                                       # RCA individual
rca-scraper --id 7021124 --ice                                 # RCA + ICE
rca-scraper --input data/expedientes.csv --delay 4.0 --ice    # Lote (columna: id_expediente)
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
rca-extractor --pdf-folder data/raw/scraped --output data/processed/results.xlsx \
  --workers 1 --cooldown 15 --max-retries 2

rca-extractor --pdf-folder data/raw/scraped --output data/processed/results.xlsx \
  --workers 1 --cooldown 15 --max-retries 5
```

| Opción | Default | Descripción |
|--------|---------|-------------|
| `--pdf-folder` | `rcas/` | Carpeta con PDFs de entrada |
| `--output` | `rca_results.xlsx` | Archivo Excel de salida |
| `--workers` | `1` | Paralelismo — thread-safe desde v0.7.0 |
| `--model` | `gemini-2.5-flash` | Modelo Gemini (ID explícito, no aliases) |
| `--cooldown` | `15` | Segundos entre PDFs |
| `--max-retries` | `8` | Reintentos por PDF |
| `--reset` | `False` | Ignorar checkpoint existente |
| `--dry-run` | `False` | Listar PDFs pendientes sin procesar |

> **Concurrencia:** El CLI es thread-safe desde `v0.7.0`. Para lotes grandes, usa `--workers 2` o `--workers 4` ajustando `--cooldown` para no exceder la cuota de Gemini (HTTP 429).

---

## Módulos LCA

```python
from rca_extractor.lca.benchmarks import classify_project, classify_ghg, classify_water, classify_land
from rca_extractor.lca.calculator import compute_lca

# Clasificación de un proyecto
result = classify_project(row)          # BenchmarkResult con ghg/water/land
label  = classify_ghg("Fotovoltaica", 35.0)   # → "NORMAL"

# Cálculo LCA
lca = compute_lca(project_row)          # LCAResult(ghg, water, energy)
```

---

## Módulos Dashboard

```python
from rca_extractor.dashboard.components.charts import render_histogram, render_scatter, render_box_plot
from rca_extractor.dashboard.components.maps import render_project_map

fig = render_histogram(df, column="potencia_nominal_bruta_mw")
fig = render_scatter(df, x="potencia_nominal_bruta_mw", y="superficie_total_intervenida_ha")
fig = render_box_plot(df, x="tipo_de_generacion_eolica_fv_csp", y="factor_de_planta")
fig = render_project_map(df)   # scatter_mapbox centrado en Chile
```

---

## Herramientas de Diagnóstico (`tools/`)

```bash
python src/rca_extractor/tools/snippet_api_key.py   # Verificar Gemini + modelo activo
python src/rca_extractor/tools/list_models.py        # Listar modelos disponibles
python -m rca_extractor.tools.check_pdfs data/raw/scraped/ --detect-scanned
python src/rca_extractor/tools/check_gitignore.py    # Verificar .gitignore
```

---

## Calidad y Tests

```bash
# Con uv
uv run pytest tests/
uv run ruff check src/
uv run mypy src/rca_extractor/core/

# Con pip
PYTHONPATH=src pytest tests/ --cov=rca_extractor --cov-report=term-missing
ruff check src/
mypy src/rca_extractor/core/
```

**Estado actual (v0.7.0):** 76 tests passing · 2 skipped · `ruff` ✅ · `mypy` ✅

---

## Variables de Entorno

```bash
# Requerida
GEMINI_API_KEY="tu_api_key_aqui"

# Modelo — usar ID explícito (los aliases no son determinísticos)
# GEMINI_MODEL=gemini-2.5-flash

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
| `escaneado` | 100% | `"sí"` / `"no"` |

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
