# 🔍☑️ RCA Extractor

**Extractor automático de variables técnicas y ambientales desde Resoluciones de Calificación Ambiental (RCA) del Sistema de Evaluación de Impacto Ambiental (SEIA) de Chile.**

Utiliza la API de Google Gemini para procesar nativamente PDFs completos (con texto y escaneados) y extraer datos estructurados en JSON.

---

## Características

| Característica | Estado | Descripción |
|----------------|--------|-------------|
| 🤖 **Extracción LLM-first** | ✅ | Gemini 2.5 Flash procesa PDFs completos sin OCR ni regex |
| 📷 **PDFs escaneados** | ✅ | Detección automática + conversión a imágenes vía pymupdf |
| 📋 **Variables dinámicas** | ✅ | Definidas en Excel editable (`seia-variables.xlsx`) |
| 🔄 **Checkpoint & Resume** | ✅ | Reanuda ejecuciones interrumpidas automáticamente |
| 🛡️ **Validación de PDFs** | ✅ | Detecta corruptos, cifrados, escaneados |
| 🔁 **Retry inteligente** | ✅ | Clasifica errores (fatal/quota/transient) con backoff diferenciado |
| 🔧 **JSON repair** | ✅ | Repara JSON malformado antes de descartar resultados |
| 📊 **Barra de progreso** | ✅ | tqdm con N/Total, ETA y conteo ok/error en tiempo real |
| 🗄️ **Post-procesamiento** | ✅ | Normalización de tipos, validación de rangos, SQLite |
| 🌍 **Geoespacial** | ✅ | Parser UTM multi-formato → WGS84, GeoJSON, resumen regional |
| 📈 **Dashboard** | 🚧 | Streamlit + Plotly con mapas, KPIs y gráficos |
| 🌱 **ACV** | 🚧 | Análisis de Ciclo de Vida con factores IPCC/NREL |

---

## Resultados — Lote de 432 RCAs

| Métrica | Valor |
|---------|-------|
| PDFs procesados exitosamente | **430 / 432 (99.5%)** |
| PDFs escaneados (procesados vía imágenes) | **125 (29.1%)** |
| Irrecuperables (400 INVALID_ARGUMENT) | 2 (349.pdf, 616.pdf) |
| Variables extraídas por RCA | 16 |
| Proyectos georreferenciados | **262 / 430 (60.9%)** |
| Tiempo total (pasada 1 + pasada 2) | ~19.5 horas |
| Costo API Gemini | **8.878 CLP (~$8.9 USD aprox.)** |

---

## Requisitos Previos

- **Python** 3.11+
- **API Key de Gemini** → [Google AI Studio](https://aistudio.google.com/) con billing activado
- Modelo requerido: `gemini-2.5-flash` (`gemini-2.0-flash` deprecado para cuentas nuevas)

---

## Instalación

```bash
# 1. Clonar el repositorio
git clone https://github.com/RobertoOtarola/rca_variables_extractor.git
cd rca_variables_extractor

# 2. Crear entorno virtual
python3 -m venv .venv
source .venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar API key
cp .env.example .env
# Editar .env → GEMINI_API_KEY=tu_clave_aqui
```

---

## Uso Rápido

### 1. Validar PDFs (recomendado antes de extraer)

```bash
# Escaneo rápido + detección de escaneados
python tools/check_pdfs.py data/raw/ --detect-scanned -o data/reporte_pdfs.csv -w 8
```

### 2. Extraer variables — estrategia de 2 pasadas

```bash
# Pasada 1 — rápida, sin atascarse en PDFs problemáticos
python main.py \
  --pdf-folder data/raw \
  --output data/processed/results.xlsx \
  --workers 1 --cooldown 10 --max-retries 2 \
  2>&1 | tee logs/run_pasada1_$(date +%Y%m%d_%H%M).log

# Pasada 2 — solo los fallidos, con más paciencia
python main.py \
  --pdf-folder data/raw \
  --output data/processed/results.xlsx \
  --workers 1 --cooldown 10 --max-retries 5 \
  2>&1 | tee logs/run_pasada2_$(date +%Y%m%d_%H%M).log
```

### 3. Post-procesamiento (Fase 2)

```bash
# Normaliza tipos, valida rangos, persiste en SQLite
python -m post_processing.run --input data/processed/results.xlsx

# Outputs: results_normalized.xlsx, validation_report.xlsx, rca_data.db
```

### 4. Georreferenciación (Fase 3)

```bash
# Solo parseo de coordenadas → WGS84
python -m geo.run --input data/processed/results_normalized.xlsx

# Con análisis de áreas protegidas SNASPE (requiere shapefile)
python -m geo.run \
  --input data/processed/results_normalized.xlsx \
  --protected data/geo/snaspe.shp \
  --protected-name-col NOMBRE \
  --buffer-km 5

# Outputs: results_geo.xlsx, region_summary.xlsx, projects.geojson
```

### 5. Ejecutar tests

```bash
python -m pytest tests/ -v
```

---

## Opciones del CLI

### `main.py`

```
  --pdf-folder   Carpeta con PDFs de RCA           (default: rcas/)
  --variables    Excel con variables a extraer      (default: seia-variables.xlsx)
  --output       Archivo Excel de salida            (default: rca_results.xlsx)
  --workers      Nº de PDFs en paralelo             (default: 1)
  --model        Modelo Gemini                      (default: gemini-2.5-flash)
  --cooldown     Segundos de pausa entre PDFs       (default: 15)
  --max-retries  Reintentos ante errores de API     (default: 8)
  --reset        Ignorar checkpoint, reprocesar todo
  --dry-run      Listar PDFs pendientes sin procesar
```

### `post_processing/run.py`

```
  --input        Excel de extracción               (default: data/processed/results.xlsx)
  --output-dir   Carpeta de salida                 (default: data/processed)
  --db           URL SQLAlchemy                    (default: sqlite:///data/processed/rca_data.db)
  --no-db        Omite persistencia en BD
  --sigma        Umbral z-score para outliers       (default: 3.0)
```

### `geo/run.py`

```
  --input              Excel normalizado             (default: data/processed/results_normalized.xlsx)
  --output-dir         Carpeta de salida             (default: data/processed)
  --protected          Shapefile áreas protegidas    (opcional — SNASPE/sitios prioritarios)
  --protected-name-col Columna de nombre en shapefile
  --buffer-km          Radio de buffer en km         (default: 5.0)
```

---

## Estructura del Proyecto

```
rca_variables_extractor/
├── main.py                    # CLI principal con barra de progreso (tqdm)
├── config.py                  # Configuración centralizada (.env)
├── gemini_client.py           # Cliente Gemini: retry inteligente por tipo de error
├── pdf_pipeline.py            # Orquesta extracción (texto o imágenes según tipo PDF)
├── pdf_utils.py               # Detección de PDFs escaneados (compartido)
├── prompt_builder.py          # Construcción de prompts dinámicos
├── output_validator.py        # Validación + reparación de JSON (json-repair)
├── checkpoint.py              # Checkpoint/resume entre ejecuciones
├── logger.py                  # Logging rotativo (consola + archivo)
│
├── prompts/
│   └── extraction_prompt.md  # Prompt con formatos estrictos por variable
│
├── post_processing/           # Fase 2 — normalización + validación + BD
│   ├── __init__.py
│   ├── normalizer.py          # String → float64, vocabulario controlado, derivación
│   ├── validator.py           # Rangos científicos, outliers 3σ, completitud
│   ├── db_storage.py          # SQLAlchemy → SQLite (upsert con flags de validación)
│   └── run.py                 # CLI: genera results_normalized.xlsx + rca_data.db
│
├── geo/                       # Fase 3 — georreferenciación
│   ├── __init__.py
│   ├── coord_parser.py        # Parser UTM multi-formato → WGS84 (10+ patrones regex)
│   ├── spatial_analysis.py    # GeoDataFrame, intersección SNASPE, resumen regional
│   └── run.py                 # CLI: genera results_geo.xlsx + projects.geojson
│
├── tools/
│   ├── check_pdfs.py          # Auditoría masiva de PDFs (corruptos, cifrados, escaneados)
│   ├── check_gitignore.py
│   ├── list_models.py
│   └── snippet_api_key.py
│
├── tests/
│   ├── conftest.py
│   ├── test_prompt_builder.py
│   ├── test_output_validator.py
│   └── test_checkpoint.py
│
├── lca/                       # 🚧 Fase 4 — ACV
├── api/                       # 🚧 Fase 4 — FastAPI
├── dashboard/                 # 🚧 Fase 4 — Streamlit
│
├── data/
│   ├── raw/                   # PDFs originales (no versionados)
│   ├── geo/                   # Shapefiles SNASPE (no versionados)
│   └── processed/             # Outputs de pipeline (no versionados)
│       ├── results.xlsx               # Extracción cruda
│       ├── results_normalized.xlsx    # Tipos normalizados (Fase 2)
│       ├── validation_report.xlsx     # Flags de rango y outliers
│       ├── rca_data.db                # SQLite (Fase 2)
│       ├── results_geo.xlsx           # Con lon/lat WGS84 (Fase 3)
│       ├── region_summary.xlsx        # Métricas por región
│       └── projects.geojson           # GeoJSON para QGIS/Mapbox
│
├── seia-variables.xlsx        # Schema de variables a extraer
├── requirements.txt
└── .env.example
```

---

## Stack Tecnológico

| Capa | Tecnología |
|------|-----------|
| Extracción (texto) | Gemini 2.5 Flash + Files API |
| Extracción (escaneados) | pymupdf → PNG + Gemini multimodal |
| Validación PDFs | pypdf |
| Reparación JSON | json-repair |
| Progreso | tqdm |
| Datos | Pandas + openpyxl |
| Post-procesamiento | SQLAlchemy + SQLite |
| Geoespacial | GeoPandas, Shapely, pyproj |
| Configuración | python-dotenv |

---

## Variables Extraídas

16 variables por RCA, configurables en `seia-variables.xlsx`. El prompt en `prompts/extraction_prompt.md` define el formato exacto de salida de cada una.

| Variable (clave JSON) | Completitud | Formato |
|----------------------|-------------|---------|
| `region_provincia_y_comuna` | 100% | `"Región de X, Provincia de Y, Comuna de Z"` |
| `tipo_de_generacion_eolica_fv_csp` | 99.8% | `"Fotovoltaica"` / `"Eólica"` / `"CSP"` |
| `potencia_nominal_bruta_mw` | 98.8% | Número en MW (punto decimal) |
| `vida_util_anos` | 98.6% | Número en años decimales |
| `superficie_total_intervenida_ha` | 97.4% | Número en ha |
| `intensidad_de_uso_de_suelo_ha_mw_1` | 96.3% | Número en ha/MW |
| `coordenadas_utm_geograficas_punto_representativo` | 95.8% | String con datum y huso |
| `proximidad_y_superposicion_con_areas_protegidas` | 98.1% | String ≤200 chars |
| `emisiones_mp10_t_ano_1` | 79.3% | Número en t/año |
| `perdida_de_cobertura_vegetal_ha` | 67.4% | Número en ha o `"N/A"` |
| `emisiones_mp2_5_t_ano_1` | 67.4% | Número en t/año |
| `factor_de_planta` | 27.2% | Decimal 0-1 |
| `consumo_de_agua_dulce_m3_mwh_1` | 24.2% | Número en m³/MWh |
| `tasas_de_mortalidad_de_aves_murcielagos` | 3.3% | String corto o `"N/A"` |
| `emisiones_gei_embebidas_kg_co2_eq_kwh_1` | 0% | No reportado en RCAs (dato ACV) |
| `caracteristicas_del_generador` | 97.2% | Texto descriptivo conciso |

> Variables con baja completitud (factor de planta, consumo de agua, GEI) no están en las RCAs — se calcularán en la Fase 4 (ACV).

---

## Outputs del Pipeline

| Archivo | Fase | Descripción |
|---------|------|-------------|
| `results.xlsx` | 1 | Extracción cruda — 430 filas × 18 columnas |
| `results_normalized.xlsx` | 2 | Tipos float64, vocabulario controlado |
| `validation_report.xlsx` | 2 | Hojas: completitud, fuera_de_rango, outliers |
| `rca_data.db` | 2 | SQLite — 430 proyectos con flags de validación |
| `results_geo.xlsx` | 3 | Con lon/lat WGS84, huso, método de parseo |
| `region_summary.xlsx` | 3 | Métricas agregadas por región |
| `projects.geojson` | 3 | 262 proyectos georreferenciados para QGIS/Mapbox |

---

## Costos

| Concepto | Valor |
|----------|-------|
| gemini-2.5-flash pasada 1 (420 PDFs) | 8.654 CLP |
| gemini-2.5-flash pasada 2 (12 PDFs) | 224 CLP |
| **Total** | **8.878 CLP (~$8.9 USD)** |
| Costo por PDF | ~20.6 CLP / ~$0.022 USD |

---

## Contribuir

1. Fork del repositorio
2. Crear branch: `git checkout -b feat/mi-feature`
3. Commits: `git commit -m "feat(modulo): descripción"`
4. Push: `git push origin feat/mi-feature`
5. Crear Pull Request

Ver [NOTES.md](NOTES.md) para arquitectura completa y guía de implementación.

---

## Licencia

GPL-3.0
