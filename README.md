# 🔍☑️ RCA Variables Extractor

**Herramienta para extraer automáticamente variables técnicas y ambientales desde Resoluciones de Calificación Ambiental (RCA) del Sistema de Evaluación de Impacto Ambiental (SEIA) de Chile.**

Procesa PDFs nativamente con la API de Google Gemini —incluyendo documentos escaneados— y extrae datos estructurados en JSON. El pipeline cubre adquisición de documentos, detección automática de tecnología, extracción LLM con prompts específicos por tecnología (eólica / fotovoltaica / CSP), post-procesamiento, georreferenciación, análisis de ciclo de vida (ACV/LCA) y visualización interactiva.

[![CI](https://github.com/RobertoOtarola/rca_variables_extractor/actions/workflows/ci.yml/badge.svg)](https://github.com/RobertoOtarola/rca_variables_extractor/actions)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License: GPL-3.0](https://img.shields.io/badge/License-GPL--3.0-green.svg)](LICENSE)

---

## Estado del Proyecto

| Fase | Versión | Estado | Descripción |
|------|---------|--------|-------------|
| 🌐 **-1 · Adquisición** | `v0.6.0` | ✅ | Scraper SEIA — descarga RCA e ICE por `id_expediente` |
| 📄 **0 · Validación PDFs** | `v0.1.0` | ✅ | Detección de corruptos, cifrados y escaneados |
| 🤖 **1 · Extracción LLM** | `v0.1.0` | ✅ | Gemini 2.5 Flash — 430/432 PDFs procesados (99.5%) · 20.77 GW |
| 🗄️ **2 · Post-procesamiento** | `v0.2.0` | ✅ | Normalización, validación y persistencia en SQLite |
| 🌍 **3 · Geoespacial** | `v0.3.0` | ✅ | Parser UTM multi-formato → WGS84 y GeoJSON |
| ⚗️ **4 · ACV + API + Dashboard** | `v0.4.0` | ✅ | LCA, FastAPI y Streamlit con acceso nativo a SQLite |
| 📦 **5 · Arquitectura** | `v0.5.0` | ✅ | Paquete `src/`, CI/CD, lockfile, Makefile |
| 🚀 **6 · Scraper refactorizado** | `v0.6.0` | ✅ | BS4, inyección de sesión, checkpoint, logging, streaming |
| 🔧 **7 · Estabilidad** | `v0.7.0` | ✅ | Thread-safety en CLI, módulos LCA/Dashboard completos, geo opcional |
| 🎛️ **8 · Dashboard integrado** | `v0.8.0` | ✅ | `app.py` usa componentes `charts.py`/`maps.py`; backup en `--reset` |
| 🧠 **9 · Prompts específicos** | `v0.9.0` | ✅ | Detección automática de tecnología, prompts eólica/FV, single upload |
| 🏁 **10 · Estabilización v1.0** | `v1.0.0` | ✅ | Dashboard optimizado, migrate.py, mypy extendido, 103 tests |

> **Corpus procesado:** 430 RCAs · 20.77 GW · 369 proyectos FV · 58 eólicos · 125 PDFs escaneados · 419 georreferenciados.

---

## Prerrequisitos

- Python ≥ 3.11
- [uv](https://github.com/astral-sh/uv) (recomendado) o pip
- API Key de Google Gemini ([obtener aquí](https://aistudio.google.com/app/apikey))
- Para capa geoespacial: GDAL en el sistema (`brew install gdal` / `apt-get install gdal-bin libgdal-dev`)

---

## Instalación

### Con `uv` (recomendado)

```bash
git clone https://github.com/RobertoOtarola/rca_variables_extractor.git
cd rca_variables_extractor

curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync --dev                   # instalación base
uv sync --extra geo --dev       # + capa geoespacial (requiere GDAL)

cp .env.example .env            # añadir GEMINI_API_KEY
```

### Con `pip`

```bash
git clone https://github.com/RobertoOtarola/rca_variables_extractor.git
cd rca_variables_extractor
python3 -m venv .venv && source .venv/bin/activate

pip install -e "."              # instalación base
pip install -e ".[geo]"         # + capa geoespacial (requiere GDAL)
pip install -e ".[dev]"         # herramientas de desarrollo

cp .env.example .env            # añadir GEMINI_API_KEY
```

### Migración desde v0.x

Si tienes una base de datos `rca_data.db` creada con versiones anteriores (< v1.0.0), ejecuta el script de migración para añadir las nuevas columnas sin perder registros:

```bash
python -m rca_extractor.post_processing.migrate --db data/processed/rca_data.db
```

---

## Uso Rápido

```bash
# 1. Descargar RCAs desde el SEIA
rca-scraper --input data/expedientes.csv --delay 4.0

# 2. Extraer variables con Gemini 2.5 Flash (detección automática de tecnología)
rca-extractor --pdf-folder data/raw/scraped --output data/processed/results.xlsx \
  --workers 2 --cooldown 60 --max-retries 8

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
├── Makefile                        # make check | make start-api | make scrape
├── .env.example                    # Template de variables de entorno
├── .gitignore
├── LICENSE                         # GPL-3.0
├── .github/
│   └── workflows/
│       └── ci.yml                  # CI: ruff + mypy (core/ + post_processing/ + lca/) + pytest
│
├── prompts/
│   ├── extraction_prompt.md            # Fallback genérico (corpus histórico)
│   ├── extraction_prompt_eolica.md     # 39 variables · Bloques 1-12 (eólica)
│   ├── extraction_prompt_fv.md         # 49 variables · Bloques 1-12 (FV/CSP)
│   └── tech_detection_prompt.md        # Detección ultraligera (primeras 3 pág., 1-token response)
│
├── tests/
│   ├── conftest.py                 # Fixture: GEMINI_API_KEY=dummy
│   ├── test_benchmarks.py          # 25 tests — lca/benchmarks
│   ├── test_checkpoint.py          # 7 tests  — utils/checkpoint
│   ├── test_lca_calculator.py      # 16 tests — lca/calculator
│   ├── test_output_validator.py    # 18 tests — utils/output_validator
│   ├── test_prompt_builder.py      # 14 tests — utils/prompt_builder
│   ├── test_rca_scraper.py         # 6 tests  — tools/rca_scraper
│   ├── test_tech_detector.py       # 11 tests — utils/tech_detector
│   └── test_tools.py               # tests  — tools/snippet_api_key, list_models
│                                   # Total: 103 tests + 2 skipped (requieren credenciales)
│
└── src/rca_extractor/
    ├── cli.py                      # Entrypoint LLM — thread-safe · backup --reset · carga condicional
    ├── config.py                   # GEMINI_MODEL, TECH_DETECTION_ENABLED, rutas de prompts
    │
    ├── core/
    │   ├── gemini_client.py        # Cliente Gemini 2.5 Flash + backoff + timeout 300s
    │   └── pdf_pipeline.py         # Single upload → detect → prompt específico → generate → delete
    │
    ├── utils/
    │   ├── checkpoint.py           # Checkpoint/resume para procesos batch
    │   ├── logger.py               # Logging rotativo estructurado
    │   ├── output_validator.py     # Superset COMMON ∪ EOLICA ∪ FV + parse_json_response()
    │   ├── pdf_utils.py            # Detección de PDFs escaneados (< 50 chars/pág)
    │   ├── prompt_builder.py       # get_prompt_for_technology() + routing table
    │   └── tech_detector.py        # detect_technology(file_ref | images) — 1-token response
    │
    ├── tools/
    │   ├── check_gitignore.py      # Verifica archivos ignorados por Git
    │   ├── check_pdfs.py           # Auditoría del corpus: corruptos, cifrados, escaneados
    │   ├── list_models.py          # Lista los modelos Gemini disponibles
    │   ├── rca_scraper.py          # Scraper SEIA: RCA + ICE (PDF/XML)
    │   └── snippet_api_key.py      # Verifica conexión Gemini y modelo activo
    │
    ├── post_processing/
    │   ├── db_storage.py           # ORM SQLAlchemy — 64 columnas (63 + prompt_version)
    │   ├── migrate.py              # Migración v0.x → v1.0.0 (añade columnas nullable)
    │   ├── normalizer.py           # Strings → valores tipados + mapeo tipo_de_generacion
    │   ├── run.py                  # CLI: python -m rca_extractor.post_processing.run
    │   └── validator.py            # Rangos científicos + 14 RangeRule nuevas (eólica + FV)
    │
    ├── geo/                        # Extra opcional: pip install -e ".[geo]" + GDAL
    │   ├── coord_parser.py         # UTM multi-formato → WGS84
    │   └── spatial_analysis.py     # Intersección SNASPE (v2024, BCN Chile)
    │
    ├── lca/
    │   ├── benchmarks.py           # classify_ghg/water/land/project() (IPCC/NREL/Ong)
    │   ├── calculator.py           # compute_lca() → LCAResult(ghg, water, energy)
    │   └── factors.py              # Factores IPCC/NREL/IEA por tecnología
    │
    ├── api/
    │   └── main.py                 # FastAPI: /health /stats /projects /lca (paginación O(N) — ver deuda)
    │
    └── dashboard/
        ├── app.py                  # Streamlit — delega a charts.py y maps.py; single DB read
        └── components/
            ├── __init__.py
            ├── charts.py           # render_histogram / render_scatter / render_box_plot
            └── maps.py             # render_project_map (scatter_mapbox centrado en Chile)
```

> **Nota:** `data/config/seia-variables.xlsx` está **deprecado**. La definición de variables reside ahora en los prompts `.md` de `prompts/`. El XLSX se mantiene solo como referencia científica (papers + criterios SEA).

---

## Detección Automática de Tecnología (v1.0.0)

El extractor detecta la tecnología de cada RCA con un prompt ultraligero (primeras 3 páginas, respuesta de 1 token). Usa el mismo `file_ref` para detección y extracción — **una sola subida por PDF**.

```
PDF
 ↓ upload_pdf()  ──────────────────────────────────── (1 sola subida)
 ├── PDF escaneado → pdf_to_images() → primeras 3 → detect
 └── PDF nativo   → file_ref → detect
 ↓ detect_technology()  →  "Eólica" / "Fotovoltaica" / "CSP" / "Desconocido"
 ↓ get_prompt_for_technology()
 ├── Eólica          → extraction_prompt_eolica.md  (39 variables)
 ├── Fotovoltaica    → extraction_prompt_fv.md      (49 variables)
 ├── CSP             → extraction_prompt_fv.md      (49 variables)
 ├── Eólica + FV     → extraction_prompt_eolica.md  (39 variables)
 └── Desconocido     → extraction_prompt.md         (fallback genérico)
 ↓ generate(prompt, file_ref | all_images)
 ↓ delete_file()  ──────────────────────────────────── (1 sola eliminación)
JSON → parse_json_response() → validate_output() → results.xlsx
```

Para desactivar la detección y usar el prompt genérico:

```bash
TECH_DETECTION_ENABLED=false rca-extractor --pdf-folder data/raw/scraped ...
```

---

## Variables Extraídas (v1.0.0)

### Variables compartidas — presentes en todos los prompts

| Variable | Cobertura v1 | Formato |
|----------|-------------|---------|
| `potencia_nominal_bruta_mw` | 98.8% | Float (MW) |
| `superficie_total_intervenida_ha` | 98.8% | Float (ha) |
| `intensidad_de_uso_de_suelo_ha_mw_1` | 97.7% | Float (ha/MW) |
| `vida_util_anos` | 98.4% | Float (años) |
| `tipo_de_generacion_eolica_fv_csp` | 99.8% | `"Fotovoltaica"` / `"Eólica"` / `"CSP"` |
| `factor_de_planta` | 26.3% ⚠️ | Float 0–1 |
| `emisiones_mp10_t_ano_1` | 80.9% | Float (t/año) |
| `emisiones_mp2_5_t_ano_1` | 68.1% | Float (t/año) |
| `perdida_de_cobertura_vegetal_ha` | 65.8% | Float (ha) |
| `consumo_de_agua_dulce_m3_mwh_1` | 21.9% ⚠️ | Float (m³/MWh) |
| `region_provincia_y_comuna` | 100% | String |
| `coordenadas_utm_geograficas_poligono` | 97.4% | String (UTM) |
| `proximidad_y_superposicion_con_areas_protegidas` | 99.8% | String ≤ 200 chars |
| `uso_de_suelo_previo` | 100% | Texto descriptivo |
| `escaneado` | 100% | `"sí"` / `"no"` |
| `prompt_version` | 100% | `"v1_generic"` / `"v2_eolica"` / `"v2_fv"` |

### Variables exclusivas de Eólica (14)

`numero_aerogeneradores` · `potencia_unitaria_aerogenerador_kw` · `altura_buje_m` · `diametro_rotor_m` · `numero_aspas_por_aerogenerador` · `velocidad_arranque_m_s` · `velocidad_nominal_m_s` · `velocidad_parada_m_s` · `sombra_parpadeante_efecto_disco` · `tasas_de_mortalidad_de_aves_murcielagos` · `mortalidad_aves_murcielagos_total_ind` · `demanda_energia_acumulada_mj_kwh_1` · `potencial_de_acidificacion_g_so2_eq_kwh_1` · `potencial_de_eutrofizacion_g_po4_eq_kwh_1`

### Variables exclusivas de Fotovoltaica / CSP (24)

`subtipo_tecnologico` · `potencia_pico_mwp` · `numero_modulos_paneles` · `numero_inversores` · `configuracion_seguimiento` · `altura_modulos_sobre_suelo_m` · `irradiacion_ghi_kwh_m2_ano_1` · `transformacion_superficie_km2_gw_1` · `transformacion_superficie_km2_twh_1` · `erosion_suelo_ha` · `calidad_suelo_sqr` · `consumo_agua_limpieza_m3_mwp_ano_1` · `fuente_abastecimiento_hidrico` · `fragmentacion_habitat_ha` · `calidad_habitat_local` · `mortalidad_aves_ind_mw_ano_1` · `mortalidad_fauna_colision_quemadura_ind` · `mortalidad_fauna_balsas_evaporacion_ind` · `aceptacion_social` · `emisiones_particulas_t_ano_1` · `emisiones_mercurio_g_hg_gwh_1` · `emisiones_cadmio_g_cd_gwh_1` · `potencial_acidificacion_lluvia_acida_g_so2_gwh_1` · `potencial_eutrofizacion_g_n_gwh_1`

> **Limitación de unidades en ACV:** Las variables de acidificación y eutrofización no son directamente comparables entre tecnologías sin conversión previa.
> - **Eólica:** `g SO₂-eq/kWh` (acidificación) · `g PO₄-eq/kWh` (eutrofización)
> - **Fotovoltaica:** `g SO₂/GWh` (acidificación) · `g N/GWh` (eutrofización)
>
> Usar `prompt_version` para distinguir el origen de los datos y evitar cruces sesgados entre tecnologías.

---

## Scraper SEIA (`tools/rca_scraper.py`)

```bash
rca-scraper --id 7021124                                       # RCA individual
rca-scraper --id 7021124 --ice                                 # RCA + ICE
rca-scraper --input data/expedientes.csv --delay 4.0 --ice    # Lote (columna: id_expediente)
```

| Variable de entorno | Default | Descripción |
|---------------------|---------|-------------|
| `SCRAPED_DIR` | `data/raw/scraped` | Directorio de salida |
| `SCRAPER_DELAY` | `3.0` | Segundos base entre requests (+ jitter ±0.5–1.5s) |
| `SCRAPER_CHECKPOINT` | `checkpoints/scraper_checkpoint.json` | Archivo de checkpoint |

El scraper implementa tres niveles de fallback: descarga directa PDF → visor intermedio → XML. Usa User-Agent institucional (`CEDEUS UC`) y `delay ≥ 3s`.

---

## Extractor LLM (`cli.py`)

```bash
# Estrategia de 2 pasadas (recomendada para lotes grandes)
# Pasada 1: Rápida, falla pronto ante saturación
rca-extractor --pdf-folder data/raw/scraped --output data/processed/results.xlsx \
  --workers 1 --cooldown 30 --max-retries 2 --max-backoff 120 --reset

# Pasada 2: Exhaustiva, solo procesa fallidos
rca-extractor --pdf-folder data/raw/scraped --output data/processed/results.xlsx \
  --workers 1 --cooldown 90 --max-retries 8 --max-backoff 300
```

| Opción | Default | Descripción |
|--------|---------|-------------|
| `--pdf-folder` | `rcas/` | Carpeta con PDFs de entrada |
| `--output` | `rca_results.xlsx` | Archivo Excel de salida |
| `--workers` | `1` | Paralelismo — thread-safe desde v0.7.0 |
| `--model` | `gemini-2.5-flash` | Modelo Gemini (ID explícito, no aliases) |
| `--cooldown` | `15` | Segundos entre PDFs (≥ 60 recomendado con 503s frecuentes) |
| `--max-retries` | `8` | Reintentos por PDF |
| `--max-backoff` | `300` | Tiempo máximo de espera (s) entre reintentos |
| `--reset` | `False` | Ignora checkpoint — crea backup `.bak` automático |
| `--dry-run` | `False` | Lista PDFs pendientes sin procesar |

> El log correcto al iniciar debe mostrar: `[INFO] Modo prompt específico: variables embebidas en los MD`

---

## Módulos LCA

```python
from rca_extractor.lca.benchmarks import classify_project, classify_ghg, classify_water, classify_land
from rca_extractor.lca.calculator import compute_lca

result = classify_project(row)                # BenchmarkResult(ghg, water, land)
label  = classify_ghg("Fotovoltaica", 35.0)  # → "NORMAL"
lca    = compute_lca(project_row)             # LCAResult(ghg, water, energy)
```

---

## Módulos Dashboard

```python
from rca_extractor.dashboard.components.charts import render_histogram, render_scatter, render_box_plot
from rca_extractor.dashboard.components.maps import render_project_map

fig = render_histogram(df, column="potencia_nominal_bruta_mw")
fig = render_scatter(df, x="potencia_nominal_bruta_mw", y="intensidad_de_uso_de_suelo_ha_mw_1")
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
# Makefile (recomendado)
make check   # ruff + mypy + pytest

# Con uv
uv run pytest tests/
uv run ruff check src/
uv run mypy src/rca_extractor/core/ src/rca_extractor/post_processing/ src/rca_extractor/lca/

# Con pip
PYTHONPATH=src pytest tests/ --cov=rca_extractor --cov-report=term-missing
```

**Estado actual (v1.0.0):** 103 tests (101 passed · 2 skipped) · `ruff` ✅ · `mypy` ✅ (14 source files)

---

## Variables de Entorno

```bash
# Requerida
GEMINI_API_KEY="tu_api_key_aqui"

# Modelo — ID explícito (los aliases no son determinísticos)
# GEMINI_MODEL=gemini-2.5-flash

# Detección de tecnología (default: true)
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
| Total RCAs procesadas | 430 / 432 (99.5%) |
| Potencia total documentada | **20,770 MW (20.77 GW)** |
| Proyectos fotovoltaicos | 369 (85.8%) — 12,159 MW |
| Proyectos eólicos | 58 (13.5%) — 8,107 MW |
| PDFs escaneados | 125 (29.1%) |
| Proyectos georreferenciados | 419 (97.4%) |
| Región con mayor capacidad | Antofagasta — 8,329 MW |

| Variable | Eólica (mediana) | Fotovoltaica (mediana) |
|----------|-----------------|----------------------|
| Factor de planta | 0.328 | 0.266 |
| Intensidad uso suelo (ha/MW) | 0.45 | 2.14 |
| Vida útil | 30 años | 30 años |

---

## Limitaciones Conocidas

- `factor_de_planta` (26.3%) y `consumo_de_agua_dulce` (21.9%) tienen baja cobertura; se espera mejora con los prompts específicos por tecnología en el próximo reprocesamiento.
- Variables de ACV (acidificación, eutrofización) usan unidades distintas entre tecnologías — no comparar directamente. Usar `prompt_version` para distinguir el origen.
- La capa geoespacial (`geo/`) requiere GDAL en el sistema. Sin GDAL, todas las demás funcionalidades operan normalmente.
- El dashboard y la API REST no implementan autenticación — uso previsto en entornos de investigación locales.
- La paginación en `api/main.py` es O(N) — suficiente para el corpus actual (430 registros), pero requiere refactorización para escalar.

---

## Licencia

[GPL-3.0](LICENSE) — Roberto Otárola · CEDEUS UC · 2026
