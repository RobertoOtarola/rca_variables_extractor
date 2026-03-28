# 🔍☑️ RCA Variables Extractor

**Extractor automático de variables técnicas y ambientales desde Resoluciones de Calificación Ambiental (RCA) del Sistema de Evaluación de Impacto Ambiental (SEIA) de Chile.**

Utiliza la API de Google Gemini para procesar nativamente PDFs completos (texto y escaneados) y extraer datos estructurados en JSON. Incluye un pipeline completo de post-procesamiento, georreferenciación, ACV y visualización.

---

## Estado del Proyecto

| Fase | Estado | Descripción |
|------|--------|-------------|
| 🤖 **1 · Extracción LLM** | ✅ | Gemini 2.0 Flash — 430/432 PDFs procesados (99.5%) |
| 🗄️ **2 · Post-procesamiento** | ✅ | Normalización, validación y persistencia en **SQLite** |
| 🌍 **3 · Geoespacial** | ✅ | Parser UTM multi-formato → WGS84 y GeoJSON |
| ⚗️ **4 · ACV + API + Dashboard** | ✅ | Análisis de Ciclo de Vida, FastAPI y Streamlit (Nativos SQL) |
| 📦 **5 · Arquitectura** | ✅ | Estructura de paquete profesional en `src/rca_extractor/` |

---

## Instalación

```bash
git clone https://github.com/RobertoOtarola/rca_variables_extractor.git
cd rca_variables_extractor
python3 -m venv .venv && source .venv/bin/activate

# Instalación en modo editable
pip install -e "."

# Para desarrollo (tests, linting)
pip install -e ".[dev]"

# Configuración
cp .env.example .env   # Añadir tu GEMINI_API_KEY
```

---

## Uso

### Ejecución del Extractor
```bash
python -m rca_extractor.cli --pdf-folder data/raw --output data/processed/results.xlsx
```

### Post-procesamiento y Base de Datos
```bash
python -m rca_extractor.post_processing.run --input data/processed/results.xlsx
# Genera data/processed/rca_data.db (fuente de verdad para API y Dashboard)
```

### Visualización y Servicios
```bash
# API REST (FastAPI)
uvicorn rca_extractor.api.main:app --reload

# Dashboard (Streamlit)
streamlit run src/rca_extractor/dashboard/app.py
```

### Calidad de Código
```bash
# Ejecución de tests unitarios
PYTHONPATH=src pytest tests/

# Formateo (Ruff)
ruff format src/rca_extractor
```

---

## Estructura del Proyecto

```
rca_variables_extractor/
├── pyproject.toml              # Definición de paquete y dependencias
├── src/rca_extractor/          # Código fuente (Package Root)
│   ├── cli.py                  # Entrypoint principal
│   ├── config.py               # Configuración centralizada
│   ├── core/                   # Motor de extracción y Gemini
│   ├── api/                    # API FastAPI (con SQLite nativo)
│   ├── dashboard/              # Dashboard Streamlit (con SQLite nativo)
│   ├── geo/                    # Georreferenciación y análisis espacial
│   ├── lca/                    # Herramientas de ACV
│   ├── post_processing/        # Validación y persistencia BD
│   └── utils/                  # Checkpoints, Logger y Utils
├── tests/                      # Suite de pruebas con pytest
└── data/                       # Almacenamiento local (ignorada en git)
```

---

## Licencia

GPL-3.0
