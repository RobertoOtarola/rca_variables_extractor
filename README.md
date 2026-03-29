# 🔍☑️ RCA Variables Extractor

**Extractor automático de variables técnicas y ambientales desde Resoluciones de Calificación Ambiental (RCA) del Sistema de Evaluación de Impacto Ambiental (SEIA) de Chile.**

Utiliza la API de Google Gemini para procesar nativamente PDFs completos (texto y escaneados) y extraer datos estructurados en JSON. Incluye un pipeline completo de post-procesamiento, georreferenciación, Análisis de Ciclo de Vida (ACV) y visualización.

---

## Estado del Proyecto

| Fase | Estado | Descripción |
|------|--------|-------------|
| 🤖 **1 · Extracción LLM** | ✅ | Gemini Flash (Latest) — 430/432 PDFs procesados (99.5%) |
| 🛰️ **2 · Scraping SEIA** | ✅ | Descarga RCA/ICE (Refactorización pendiente → EPIC 11) |
| 🗄️ **3 · Post-procesamiento** | ✅ | Normalización, validación y persistencia en **SQLite** |
| 🌍 **4 · Geoespacial** | ✅ | Parser UTM multi-formato → WGS84 y GeoJSON |
| ⚗️ **5 · ACV + API + Dashboard** | ✅ | Análisis de Ciclo de Vida, FastAPI y Streamlit (Nativos SQL) |
| 📦 **6 · Arquitectura** | ✅ | Estructura de paquete profesional en `src/rca_extractor/` |

---

## Instalación y Setup

Se recomienda el uso de [uv](https://github.com/astral-sh/uv) para una gestión de dependencias ultra-rápida.

```bash
git clone https://github.com/RobertoOtarola/rca_variables_extractor.git
cd rca_variables_extractor

# Crear venv e instalar dependencias (incluyendo dev)
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# Configuración de variables de entorno
cp .env.example .env   # Añade tu GEMINI_API_KEY en el archivo .env
```

---

## Uso

### 1. Ejecución del Extractor (CLI)
Puedes usar el comando instalado o llamar al módulo directamente:
```bash
# Opción A: Comando directo (recomendado)
rca-extractor --pdf-folder data/raw --output data/processed/results.xlsx

# Opción B: Módulo Python
python -m rca_extractor.cli --pdf-folder data/raw --output data/processed/results.xlsx
```

### 2. Post-procesamiento (Persistence)
```bash
python -m rca_extractor.post_processing.run --input data/processed/results.xlsx
# Esto genera 'data/processed/rca_data.db' para la API y el Dashboard
```

### 3. Servicios y Visualización
```bash
# API REST (FastAPI)
uvicorn rca_extractor.api.main:app --reload

# Dashboard (Streamlit)
streamlit run src/rca_extractor/dashboard/app.py
```

---

## Desarrollo Rápido (Makefile)

El proyecto incluye un `Makefile` para automatizar tareas comunes:

| Comando | Descripción |
|---------|-------------|
| `make test` | Ejecuta la suite de pruebas con pytest |
| `make lint` | Verifica estilo con Ruff y tipos con Mypy |
| `make format` | Formatea el código automáticamente con Ruff |
| `make start-api` | Inicia la API de desarrollo |
| `make start-dashboard` | Inicia el Dashboard de Streamlit |

---

## Estructura del Proyecto

```
rca_variables_extractor/
├── src/rca_extractor/          # Package Root
│   ├── cli.py                  # Entrypoint principal (CLI)
│   ├── config.py               # Configuración centralizada
│   ├── core/                   # Pipeline de extracción y Gemini
│   ├── api/                    # API FastAPI
│   ├── dashboard/              # Dashboard Streamlit
│   ├── geo/                    # Análisis espacial y georreferenciación
│   ├── post_processing/        # SQLite, validadores y normalización
│   └── utils/                  # Herramientas transversales
├── tests/                      # Suite de pruebas
├── pyproject.toml              # Metadatos del paquete
└── Makefile                    # Atajos de comandos
```

---

## Licencia

GPL-3.0
