# 🔍☑️ RCA Variables Extractor

**Herramienta para extraer automáticamente variables técnicas y ambientales desde Resoluciones de Calificación Ambiental (RCA) del Sistema de Evaluación de Impacto Ambiental (SEIA) de Chile.**

Procesa PDFs nativamente con la API de Google Gemini —incluyendo documentos escaneados— y extrae datos estructurados en JSON. El pipeline cubre adquisición de documentos, detección automática de tecnología, extracción LLM con prompts específicos por tecnología, post-procesamiento, georreferenciación, análisis de ciclo de vida y visualización interactiva.

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
| 🎛️ **8 · Dashboard integrado** | ✅ `v0.8.0` | `app.py` usa componentes `charts.py`/`maps.py`; backup en `--reset` |
| 🏁 **10 · Arquitectura y Estabilización** | ✅ `v1.0.0` | Refactor de concurrencia, single upload, testing integración E2E |

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

# 2. Extraer variables con Gemini 2.5 Flash (detección automática de tecnología)
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
├── pyproject.toml                  # Dependencias y configuración (v1.0.0)
├── uv.lock                         # Lockfile determinístico
├── .env.example                    # Template de variables de entorno
├── .gitignore
├── LICENSE                         # GPL-3.0
├── .github/
│   └── workflows/
│       └── ci.yml                  # CI: ruff + ruff format + mypy + pytest (con GDAL)
│
├── prompts/
│   ├── extraction_prompt.md            # Fallback genérico (mantener como respaldo)
│   ├── extraction_prompt_eolica.md     # 39 variables · Bloques 1-12 (eólica)
│   ├── extraction_prompt_fv.md         # 49 variables · Bloques 1-12 (FV/CSP)
│   └── tech_detection_prompt.md        # Detección ultraligera (1-token response)
│
├── tests/
│   ├── conftest.py                 # Fixture: GEMINI_API_KEY=dummy
│   ├── test_benchmarks.py          # 25 tests — lca/benchmarks
│   ├── test_checkpoint.py          # 7 tests  — utils/checkpoint
│   ├── test_lca_calculator.py      # 16 tests — lca/calculator
│   ├── test_output_validator.py    # 18 tests — utils/output_validator
│   ├── test_prompt_builder.py      # 14 tests — utils/prompt_builder
│   ├── test_rca_scraper.py         # 6 tests  — tools/rca_scraper
│   └── test_tech_detector.py       # 8 tests  — utils/tech_detector
│                                   # Total: 94 tests + 2 skipped (credenciales)
└── src/rca_extractor/
    ├── cli.py                      # Entrypoint LLM — thread-safe · backup --reset
    ├── config.py                   # GEMINI_MODEL, TECH_DETECTION_ENABLED, rutas prompts
    │
    ├── core/
    │   ├── gemini_client.py        # Cliente Gemini 2.5 Flash + backoff + retry
    │   └── pdf_pipeline.py         # Detect tech → seleccionar prompt → extraer
    │
    ├── utils/
    │   ├── checkpoint.py           # Checkpoint/resume para procesos batch
    │   ├── logger.py               # Logging rotativo estructurado
    │   ├── output_validator.py     # Superset de claves: COMMON ∪ EOLICA ∪ FV
    │   ├── pdf_utils.py            # Detección de PDFs escaneados
    │   ├── prompt_builder.py       # get_prompt_for_technology() + routing table
    │   └── tech_detector.py        # detect_technology() — detección ultraligera
    │
    ├── tools/
    │   ├── check_gitignore.py      # Verifica que archivos locales estén bien ignorados
    │   ├── check_pdfs.py           # Auditoría del corpus: corruptos, cifrados, escaneados
    │   ├── list_models.py          # Lista los modelos Gemini disponibles para la API Key
    │   ├── rca_scraper.py          # Scraper SEIA: RCA + ICE (PDF/XML)
    │   └── snippet_api_key.py      # Verifica conexión con Gemini y modelo activo
    │
    ├── post_processing/
    │   ├── db_storage.py           # ORM SQLAlchemy — 63 columnas (25 comunes + 14 eólica + 24 FV)
    │   ├── normalizer.py           # Strings → valores tipados (formato numérico chileno)
    │   ├── run.py                  # CLI: python -m rca_extractor.post_processing.run
    │   └── validator.py            # Rangos científicos + detección de outliers
    │
    ├── geo/                        # Requiere pip install -e ".[geo]" + GDAL del sistema
    │   ├── coord_parser.py         # UTM multi-formato → WGS84
    │   └── spatial_analysis.py     # Intersección con áreas protegidas SNASPE
    │
    ├── lca/
    │   ├── benchmarks.py           # classify_ghg/water/land/project() (IPCC/NREL/Ong)
    │   ├── calculator.py           # compute_lca() → LCAResult(ghg, water, energy)
    │   └── factors.py              # Factores de referencia por tecnología
    │
    ├── api/
    │   └── main.py                 # FastAPI: /health /stats /projects /lca
    │
    └── dashboard/
        ├── app.py                  # Streamlit — usa componentes charts.py y maps.py
        └── components/
            ├── __init__.py
            ├── charts.py           # render_histogram / render_scatter / render_box_plot
            └── maps.py             # render_project_map (scatter_mapbox centrado en Chile)
```

---

## Detección Automática de Tecnología (v1.0.0)

Desde v1.0.0, el extractor detecta automáticamente la tecnología de cada RCA antes de la extracción completa, usando un prompt ultraligero de una sola respuesta, y enruta al prompt específico correspondiente.

```
PDF
 ↓ upload_pdf()  ──────────────────────────────── (1 sola subida)
 ↓ detect_tech()  →  "Eólica" / "Fotovoltaica" / "CSP" / "Desconocido"
 ↓ get_prompt_for_technology()
 ├── Eólica          → extraction_prompt_eolica.md  (39 variables)
 ├── Fotovoltaica    → extraction_prompt_fv.md      (49 variables)
 ├── CSP             → extraction_prompt_fv.md      (49 variables)
 ├── Eólica+FV       → extraction_prompt_eolica.md  (39 variables)
 └── Desconocido     → extraction_prompt.md         (fallback genérico)
 ↓ generate(prompt, file_ref)
 ↓ delete_file()  ──────────────────────────────── (1 sola eliminación)
JSON estructurado → output_validator → results.xlsx
```

Para desactivar la detección automática y usar el prompt genérico para todos los documentos:

```bash
TECH_DETECTION_ENABLED=false rca-extractor --pdf-folder data/raw/scraped ...
```

---

## Variables Extraídas (v1.0.0)

### Variables compartidas (25) — presentes en todos los prompts

| Variable | Cobertura v1 | Formato |
|----------|-------------|---------|
| `potencia_nominal_bruta_mw` | 98.8% | Float (MW) |
| `superficie_total_intervenida_ha` | 98.8% | Float (ha) |
| `intensidad_de_uso_de_suelo_ha_mw_1` | 97.7% | Float (ha/MW) |
| `vida_util_anos` | 98.4% | Float (años) |
| `tipo_de_generacion` | 99.8% | `"Fotovoltaica"` / `"Eólica"` / `"CSP"` |
| `factor_de_planta` | 26.3% | Float 0–1 |
| `emisiones_mp10_t_ano_1` | 80.9% | Float (t/año) |
| `emisiones_mp2_5_t_ano_1` | 68.1% | Float (t/año) |
| `perdida_de_cobertura_vegetal_ha` | 65.8% | Float (ha) |
| `consumo_de_agua_dulce_m3_mwh_1` | 21.9% | Float (m³/MWh) |
| `region_provincia_y_comuna` | 100% | String |
| `coordenadas_utm_geograficas_poligono` | 97.4% | String (UTM) |
| `proximidad_y_superposicion_con_areas_protegidas` | 99.8% | String ≤ 200 chars |
| `uso_de_suelo_previo` | 100% | Texto descriptivo |
| `escaneado` | 100% | `"sí"` / `"no"` |
| *(+10 variables de impacto ambiental y paisaje)* | | |

### Variables exclusivas de Eólica (14)

`numero_aerogeneradores` · `potencia_unitaria_aerogenerador_kw` · `altura_buje_m` · `diametro_rotor_m` · `numero_aspas_por_aerogenerador` · `velocidad_arranque_m_s` · `velocidad_nominal_m_s` · `velocidad_parada_m_s` · `sombra_parpadeante_efecto_disco` · `tasas_de_mortalidad_de_aves_murcielagos` · `mortalidad_aves_murcielagos_total_ind` · `demanda_energia_acumulada_mj_kwh_1` · `potencial_de_acidificacion_g_so2_eq_kwh_1` · `potencial_de_eutrofizacion_g_po4_eq_kwh_1`

### Variables exclusivas de Fotovoltaica / CSP (24)

`subtipo_tecnologico` · `potencia_pico_mwp` · `numero_modulos_paneles` · `numero_inversores` · `configuracion_seguimiento` · `altura_modulos_sobre_suelo_m` · `irradiacion_ghi_kwh_m2_ano_1` · `transformacion_superficie_km2_gw_1` · `transformacion_superficie_km2_twh_1` · `erosion_suelo_ha` · `calidad_suelo_sqr` · `consumo_agua_limpieza_m3_mwp_ano_1` · `fuente_abastecimiento_hidrico` · `fragmentacion_habitat_ha` · `calidad_habitat_local` · `mortalidad_aves_ind_mw_ano_1` · `mortalidad_fauna_colision_quemadura_ind` · `mortalidad_fauna_balsas_evaporacion_ind` · `aceptacion_social` · `emisiones_particulas_t_ano_1` · `emisiones_mercurio_g_hg_gwh_1` · `emisiones_cadmio_g_cd_gwh_1` · `potencial_acidificacion_lluvia_acida_g_so2_gwh_1` · `potencial_eutrofizacion_g_n_gwh_1`

> [!WARNING]
> **Limitación de Unidades en ACV (LCA):** Las variables de acidificación y eutrofización no son directamente comparables entre tecnologías sin conversión previa.
> - **Eólica:** Usa `g SO₂-eq/kWh` (acidificación) y `g PO₄-eq/kWh` (eutrofización).
> - **Fotovoltaica:** Usa `g SO₂/GWh` (acidificación) y `g N/GWh` (eutrofización).
> 
> La base de datos incluye la columna `prompt_version` (ej. `v1_generic`, `v2_eolica`, `v2_fv`) para distinguir el origen de los datos y prevenir cruces sesgados.

---

## Scraper SEIA (`tools/rca_scraper.py`)

```bash
rca-scraper --id 7021124                                       # RCA individual
rca-scraper --id 7021124 --ice                                 # RCA + ICE
rca-scraper --input data/expedientes.csv --delay 4.0 --ice    # Lote (columna: id_expediente)
```

| Variable | Default | Descripción |
|----------|---------|-------------|
| `SCRAPED_DIR` | `data/raw/scraped` | Directorio de salida |
| `SCRAPER_DELAY` | `3.0` | Segundos base entre requests |
| `SCRAPER_CHECKPOINT` | `checkpoints/scraper_checkpoint.json` | Archivo de checkpoint |

---

## Extractor LLM (`cli.py`)

```bash
# 2 pasadas (recomendado para lotes grandes)
rca-extractor --pdf-folder data/raw/scraped --output data/processed/results.xlsx \
  --workers 2 --cooldown 15 --max-retries 2

rca-extractor --pdf-folder data/raw/scraped --output data/processed/results.xlsx \
  --workers 2 --cooldown 15 --max-retries 5
```

| Opción | Default | Descripción |
|--------|---------|-------------|
| `--pdf-folder` | `rcas/` | Carpeta con PDFs de entrada |
| `--output` | `rca_results.xlsx` | Archivo Excel de salida |
| `--workers` | `1` | Paralelismo — thread-safe desde v0.7.0 |
| `--model` | `gemini-2.5-flash` | Modelo Gemini (ID explícito, no aliases) |
| `--cooldown` | `15` | Segundos entre PDFs |
| `--max-retries` | `8` | Reintentos por PDF |
| `--reset` | `False` | Ignora checkpoint — crea backup `.bak` automático |
| `--dry-run` | `False` | Listar PDFs pendientes sin procesar |

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
```

**Estado actual (v1.0.0 estable):** 76–94 tests · `ruff` ✅ · `mypy` ✅

---

## Variables de Entorno

```bash
# Requerida
GEMINI_API_KEY="tu_api_key_aqui"

# Modelo Gemini — ID explícito (no aliases; los aliases no son determinísticos)
# GEMINI_MODEL=gemini-2.5-flash

# Detección de tecnología (default: true). Desactivar para usar prompt genérico.
# TECH_DETECTION_ENABLED=true

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

## Resultados del Corpus

| Indicador | Valor |
|-----------|-------|
| Total RCAs procesadas (prompt genérico v1) | 430 / 432 (99.5%) |
| Potencia total documentada | **20,770 MW (20.77 GW)** |
| Proyectos fotovoltaicos | 369 (85.8%) — 12,159 MW |
| Proyectos eólicos | 58 (13.5%) — 8,107 MW |
| PDFs escaneados (ruta imagen) | 125 (29.1%) |
| Proyectos georreferenciados | 419 (97.4%) |
| Región con mayor capacidad | Antofagasta — 8,329 MW |

---

## Licencia

[GPL-3.0](LICENSE) — Roberto Otárola Estrada · CEDEUS UC · 2026
