# 🔍☑️ RCA Variables Extractor

> **Herramienta para extraer automáticamente variables técnicas y ambientales desde Resoluciones de Calificación Ambiental (RCA) del Sistema de Evaluación de Impacto Ambiental (SEIA) de Chile.**

Procesa PDFs nativamente con la API de Google Gemini —incluyendo documentos escaneados— y extrae datos estructurados en JSON. El pipeline cubre adquisición de documentos, extracción LLM, post-procesamiento, georreferenciación, análisis de ciclo de vida y visualización interactiva.

**Versión Actual:** `v0.9.0`  
**Última Actualización:** 26 de abril de 2026

[![CI](https://github.com/RobertoOtarola/rca_variables_extractor/actions/workflows/ci.yml/badge.svg)](https://github.com/RobertoOtarola/rca_variables_extractor/actions)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License: GPL-3.0](https://img.shields.io/badge/License-GPL--3.0-green.svg)](LICENSE)
[![Version: v0.9.0](https://img.shields.io/badge/version-v0.9.0-orange.svg)](pyproject.toml)

---

## 📑 Tabla de Contenidos

- [Características Principales](#-características-principales)
- [Estado del Proyecto](#-estado-del-proyecto)
- [Instalación](#-instalación)
- [Uso Rápido](#-uso-rápido)
- [Estructura del Proyecto](#-estructura-del-proyecto)
- [Módulos Principales](#-módulos-principales)
  - [Scraper SEIA](#scraper-seia)
  - [Extractor LLM](#extractor-llm)
  - [Módulos LCA](#módulos-lca)
  - [Dashboard Interactivo](#dashboard-interactivo)
- [Herramientas de Diagnóstico y Calidad](#-herramientas-de-diagnóstico-y-calidad)
- [Configuración (Variables de Entorno)](#-configuración-variables-de-entorno)
- [Resultados Extras y Corpus](#-resultados-extras-y-corpus)
- [Contribución](#-contribución)
- [Licencia](#-licencia)

---

## ✨ Características Principales

- **Web Scraper Integrado:** Descarga automática de RCAs e ICEs desde `seia.sea.gob.cl`.
- **Extracción NLP Avanzada:** Uso de **Gemini 2.5 Flash** con prompts específicos por tecnología (Eólica: 39 variables, Fotovoltaica: 49 variables) y detección automática de tecnología.
- **Detección Automática:** Validación rigurosa de documentos (PDFs nativos, escaneados, cifrados, corruptos).
- **Procesamiento Geoespacial:** Parseo de coordenadas UTM a WGS84, e intersección con áreas protegidas.
- **Análisis de Ciclo de Vida (LCA):** Clasificación según estándares IPCC/NREL y estimación de impactos ambientales.
- **Dashboard y API:** Visualización interactiva con **Streamlit** y acceso REST con **FastAPI**.
- **Robusto y Resiliente:** Sistema robusto de checkpoints para reanudación ante interrupciones, logging rotativo estructurado y backups.

---

## 📈 Estado del Proyecto

| Fase | Estado | Descripción |
|------|--------|-------------|
| 🌐 **-1 · Adquisición** | ✅ | Scraper SEIA — descarga RCA e ICE por `id_expediente` |
| 📄 **0 · Validación PDFs** | ✅ | Detección de corruptos, cifrados y escaneados |
| 🤖 **1 · Extracción LLM** | ✅ | Gemini 2.5 Flash — 430/432 PDFs procesados (99.5%) · 20.77 GW |
| 🗄️ **2 · Post-proc** | ✅ | Normalización, validación y persistencia en SQLite |
| 🌍 **3 · Geoespacial** | ✅ | Parser UTM multi-formato → WGS84 y GeoJSON |
| ⚗️ **4 · ACV + API + UI**| ✅ | LCA, FastAPI y Streamlit con acceso nativo a SQLite |
| 📦 **5 · Arquitectura** | ✅ | Paquete `src/`, CI/CD, lockfile, Makefile |
| 🚀 **6 · Scraper refactor**| ✅ | BS4, sesión, checkpoint, logging, streaming |
| 🔧 **7 · Estabilidad** | ✅ | Thread-safety, módulos completos, geo opcional |
| 🎛️ **8 · Integración** | ✅ | Gráficos reactivos, mapas, backup en `--reset` |
| 🚀 **9 · Prompts específicos** | ✅ | Detección automática de tecnología + prompts Eólica/FV |

---

## 🚀 Instalación

**Prerrequisitos:** Python ≥ 3.11

### Con `uv` (Recomendado)

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

## 💡 Uso Rápido

```bash
# 1. Descargar RCAs desde el SEIA
rca-scraper --input data/expedientes.csv --delay 4.0

# 2. Extraer variables con Gemini 2.5 Flash
rca-extractor --pdf-folder data/scraped --output data/processed/results.xlsx

# 3. Post-procesar y persistir en BD
python -m rca_extractor.post_processing.run --input data/processed/results.xlsx

# 4. Levantar servicios
uvicorn rca_extractor.api.main:app --reload          # API REST → http://localhost:8000/docs
streamlit run src/rca_extractor/dashboard/app.py     # Dashboard → http://localhost:8501
```

---

## 📂 Estructura del Proyecto

```text
rca_variables_extractor/
├── pyproject.toml                  # Dependencias y configuración (v0.9.0)
├── uv.lock                         # Lockfile determinístico
├── .env.example                    # Template de variables de entorno
├── LICENSE                         # GPL-3.0
├── .github/workflows/ci.yml        # CI test workflow con ruff, mypy, pytest
├── prompts/                        # Prompts específicos por tecnología + detección
├── tests/                          # 101 tests automatizados 
└── src/rca_extractor/
    ├── api/                        # FastAPI REST API Router
    ├── core/                       # Integración principal Gemini y Pipeline
    ├── dashboard/                  # Interfaz Streamlit modular
    ├── geo/                        # Análisis e intersección geoespacial (opcional)
    ├── lca/                        # Cálculo de variables ACV e impacto
    ├── post_processing/            # Validación fina, persistencia lógica DB
    ├── tools/                      # Utilitarios y scraper SEIA 
    └── utils/                      # Checkpoints, logging unificado, validación JSON
```

---

## ⚙️ Módulos Principales

### Scraper SEIA (`tools/rca_scraper.py`)
Descarga RCAs e ICEs desde `seia.sea.gob.cl`. Soporta lotes desde CSV.
```bash
rca-scraper --id 7021124                                      # RCA individual
rca-scraper --id 7021124 --ice                                # RCA + ICE
rca-scraper --input data/expedientes.csv --delay 4.0 --ice    # Procesamiento por lotes
```

### Extractor LLM (`cli.py`)
Pipeline de extracción en dos fases con detección automática de tecnología:
1. **Fase 1 — Detección:** Prompt ultraligero clasifica la RCA (Eólica, Fotovoltaica, CSP, híbrida).
2. **Fase 2 — Extracción:** Prompt específico extrae 39 variables (Eólica) o 49 variables (Fotovoltaica).

Si la detección falla, se usa el prompt genérico como fallback.
```bash
rca-extractor --pdf-folder data/scraped --output data/processed/results.xlsx \
  --workers 2 --cooldown 15 --max-retries 5
```
> **Tip:** El flag `--reset` ignora el checkpoint actual pero crea una copia de seguridad automática (`.bak`) primero, previniendo perdida de avances considerables.

### Módulos LCA
```python
from rca_extractor.lca.benchmarks import classify_project, classify_ghg
from rca_extractor.lca.calculator import compute_lca

result = classify_project(row)               # BenchmarkResult(ghg, water, land)
lca    = compute_lca(project_row)            # LCAResult(ghg, water, energy)
```

### Dashboard Interactivo
Accede a componentes predefinidos para construcción rápida de dashboards.
```python
from rca_extractor.dashboard.components.charts import render_histogram, render_scatter
from rca_extractor.dashboard.components.maps import render_project_map

fig = render_project_map(df)                 # Renderiza mapa interactivo de Chile centrado
```

---

## 🛠 Herramientas de Diagnóstico y Calidad

Para evaluar la configuración o un corpus de documentos PDFs de manera rápida:
```bash
python src/rca_extractor/tools/snippet_api_key.py      # Verificar conexión y credenciales AI
python -m rca_extractor.tools.check_pdfs data/scraped/ --detect-scanned
```

**Testing y Calidad de Código:**
```bash
uv run pytest tests/
uv run ruff check src/
uv run mypy src/rca_extractor/core/
```
*(Estado Actual: 101 tests passing · 2 skipped · `ruff` ✅ · `mypy` ✅)*

---

## 🔧 Configuración (Variables de Entorno)

Copia o renombra tu `.env` a partir del `.env.example`:

```bash
# Obligatorio
GEMINI_API_KEY="tu_api_key_aqui"

# Model Target y Configuración Operativa
GEMINI_MODEL="gemini-2.5-flash"
MAX_RETRIES="8"
RETRY_BASE_DELAY="65.0"
INTER_PDF_COOLDOWN="15"

# Detección de Tecnología (desactivar para usar prompt genérico)
# TECH_DETECTION_ENABLED=false
```

---

## 📊 Resultados Extras y Corpus

**Variables Extraídas:** Procesamiento exhaustivo con prompts específicos por tecnología — **39 variables** para proyectos eólicos y **49 variables** para fotovoltaicos (25 compartidas). Las tasas promedias de éxito en lecturas superan el **97%**.

| Indicador | Valor |
|-----------|-------|
| Total RCAs procesadas | 430 / 432 (99.5%) |
| Potencia total documentada | **20,770 MW (20.77 GW)** |
| Proyectos fotovoltaicos | 369 (85.8%) — 12,159 MW |
| Proyectos eólicos | 58 (13.5%) — 8,107 MW |
| PDFs escaneados procesados | 125 (29.1%) |
| Proyectos georreferenciados | 419 (97.4%) |
| Región con mayor capacidad   | Antofagasta — 8,329 MW |

---

## 🤝 Contribución

¡Las contribuciones son plenamente bienvenidas! Sigue nuestras directrices:
1. Hacer un `Fork` del repositorio.
2. Crear una rama de características o parche respectivo (`git checkout -b feature/AmazingFeature`).
3. Asegurar que todos los tests pasen (`pytest tests/`) y el tipado sea riguroso (`mypy`).
4. Aplicar linter y estilo (`ruff format y ruff check`).
5. Abrir un Pull Request con el detalle de las implementaciones.

---

## 📄 Licencia

Este proyecto se distribuye bajo licencia [GPL-3.0](LICENSE).  
Desarrollado y mantenido por **Roberto Otárola** · **CEDEUS UC** · 2026
