# 🔍☑️ RCA Extractor

**Extractor automático de variables técnicas y ambientales desde Resoluciones de Calificación Ambiental (RCA) del Sistema de Evaluación de Impacto Ambiental (SEIA) de Chile.**

Utiliza la API de Google Gemini para procesar nativamente PDFs completos (texto y escaneados) y extraer datos estructurados en JSON. Incluye pipeline completo de post-procesamiento, georreferenciación, ACV y visualización.

---

## Estado del Pipeline

| Fase | Estado | Descripción |
|------|--------|-------------|
| 🤖 **1 · Extracción LLM** | ✅ | Gemini 2.5 Flash — 430/432 PDFs (99.5%), incluyendo 125 escaneados |
| 🗄️ **2 · Post-procesamiento** | ✅ | Normalización de tipos, validación de rangos, SQLite |
| 🌍 **3 · Geoespacial** | ✅ | Parser UTM multi-formato → WGS84, GeoJSON, resumen regional |
| ⚗️ **4 · ACV + API + Dashboard** | ✅ | Análisis de Ciclo de Vida, FastAPI REST, Streamlit |

---

## Resultados — Lote de 432 RCAs

| Métrica | Valor |
|---------|-------|
| PDFs procesados exitosamente | **430 / 432 (99.5%)** |
| PDFs escaneados (vía imágenes) | **125 (29.1%)** |
| Irrecuperables (400 INVALID_ARGUMENT) | 2 — 349.pdf, 616.pdf |
| Variables extraídas por RCA | 16 |
| Proyectos georreferenciados | **284 / 430 (66.0%)** |
| Potencia instalada total | **20.34 GW** |
| Energía estimada (vida útil) | **1.498 TWh** |
| GEI embebido estimado | **27.997 kt CO₂-eq** |
| Costo API Gemini total | **8.878 CLP (~$8.9 USD)** |

---

## Instalación

```bash
git clone https://github.com/RobertoOtarola/rca_variables_extractor.git
cd rca_variables_extractor
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # añadir GEMINI_API_KEY=tu_clave
```

---

## Uso — Pipeline completo

### Fase 1 · Extracción

```bash
# Pasada 1 — procesa todo el lote
python main.py \
  --pdf-folder data/raw \
  --output data/processed/results.xlsx \
  --workers 1 --cooldown 10 --max-retries 2 \
  2>&1 | tee logs/run_pasada1_$(date +%Y%m%d_%H%M).log

# Pasada 2 — solo los fallidos (el checkpoint salta los exitosos)
python main.py \
  --pdf-folder data/raw \
  --output data/processed/results.xlsx \
  --workers 1 --cooldown 10 --max-retries 5 \
  2>&1 | tee logs/run_pasada2_$(date +%Y%m%d_%H%M).log
```

### Fase 2 · Post-procesamiento

```bash
python -m post_processing.run --input data/processed/results.xlsx
# → results_normalized.xlsx, validation_report.xlsx, rca_data.db
```

### Fase 3 · Georreferenciación

```bash
# Solo coordenadas
python -m geo.run --input data/processed/results_normalized.xlsx

# Con áreas protegidas SNASPE
python -m geo.run \
  --input data/processed/results_normalized.xlsx \
  --protected data/geo/snaspe.shp \
  --protected-name-col NOMBRE \
  --buffer-km 5
# → results_geo.xlsx, region_summary.xlsx, projects.geojson
```

### Fase 4 · ACV + API + Dashboard

```bash
# 4a — Calcular métricas ACV
python -m lca.run --input data/processed/results_normalized.xlsx
# → results_lca.xlsx

# 4b — Levantar API REST
uvicorn api.main:app --reload --port 8000
# Docs: http://localhost:8000/docs

# 4c — Levantar Dashboard
streamlit run dashboard/app.py
# → http://localhost:8501
```

---

## API REST — Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/health` | Liveness check |
| GET | `/stats` | KPIs globales — potencia, energía, GEI, regiones |
| GET | `/regions` | Métricas agregadas por región |
| GET | `/projects` | Lista paginada con filtros opcionales |
| GET | `/projects/{archivo}` | Detalle de un proyecto (ej: `163.pdf`) |
| GET | `/lca/{archivo}` | Métricas ACV de un proyecto |

**Filtros disponibles en `/projects`:**

| Parámetro | Tipo | Ejemplo |
|-----------|------|---------|
| `page` / `size` | int | `?page=2&size=50` |
| `region` | string | `?region=Atacama` |
| `tech` | string | `?tech=Eólica` |
| `min_mw` / `max_mw` | float | `?min_mw=100&max_mw=500` |
| `escaneado` | bool | `?escaneado=true` |

Documentación interactiva en `http://localhost:8000/docs` (Swagger UI).

---

## ACV — Metodología

El módulo `lca/` calcula las siguientes métricas por proyecto usando factores de referencia internacional:

| Métrica | Fuente | Descripción |
|---------|--------|-------------|
| **Energía vida útil** | RCA (potencia + CF + vida útil) | MWh generados a lo largo de la vida del proyecto |
| **GEI embebidos** | IPCC AR6 WG3 Ch.6 (2022) | g CO₂-eq/kWh × energía → kt CO₂-eq total |
| **Consumo agua** | RCA si disponible; NREL si no | m³/MWh; total hm³ en vida útil |
| **Benchmark tierra** | Ong et al. (2013) | Compara ha/MW del proyecto vs referencia internacional |

Benchmarks de GEI por tecnología (IPCC AR6, medianas):

| Tecnología | GEI g CO₂-eq/kWh | Agua m³/MWh | Tierra ha/MW (ref.) |
|-----------|-----------------|-------------|---------------------|
| Fotovoltaica | 24 (13–46) | 0.02 | 2.5 |
| Eólica | 11 (7–15) | 0.004 | 72 (mayoría compartible) |
| CSP | 22 (14–32) | 3.0 | 4.0 |

---

## Opciones del CLI

### `main.py`
```
  --pdf-folder    PDFs a procesar          (default: rcas/)
  --output        Excel de salida          (default: rca_results.xlsx)
  --workers       PDFs en paralelo         (default: 1)
  --model         Modelo Gemini            (default: gemini-2.5-flash)
  --cooldown      Pausa entre PDFs (s)     (default: 15)
  --max-retries   Reintentos API           (default: 8)
  --reset         Ignorar checkpoint
  --dry-run       Listar pendientes
```

### `post_processing/run.py`
```
  --input         Excel crudo              (default: data/processed/results.xlsx)
  --db            URL SQLAlchemy           (default: sqlite:///data/processed/rca_data.db)
  --no-db         Omitir BD
  --sigma         Umbral outliers          (default: 3.0)
```

### `geo/run.py`
```
  --input               Excel normalizado
  --protected           Shapefile SNASPE   (opcional)
  --protected-name-col  Columna nombre en shapefile
  --buffer-km           Radio buffer (km)  (default: 5.0)
```

### `lca/run.py`
```
  --input         Excel normalizado        (default: data/processed/results_normalized.xlsx)
  --output-dir    Carpeta de salida        (default: data/processed)
```

---

## Estructura del Proyecto

```
rca_variables_extractor/
├── main.py                    # CLI extracción — tqdm, checkpoint, retry
├── config.py                  # Configuración (.env)
├── gemini_client.py           # Cliente Gemini con retry inteligente
├── pdf_pipeline.py            # Orquesta extracción texto/imágenes
├── pdf_utils.py               # Detección PDFs escaneados
├── prompt_builder.py          # Prompts dinámicos
├── output_validator.py        # Validación + json-repair
├── checkpoint.py              # Resume entre ejecuciones
├── logger.py                  # Logging rotativo
│
├── prompts/
│   └── extraction_prompt.md  # Prompt con formatos estrictos por variable
│
├── post_processing/           # Fase 2
│   ├── normalizer.py          # str → float64, vocabulario controlado, derivación
│   ├── validator.py           # Rangos científicos, outliers 3σ, completitud
│   ├── db_storage.py          # SQLAlchemy → SQLite
│   └── run.py                 # CLI
│
├── geo/                       # Fase 3
│   ├── coord_parser.py        # 12 patrones regex UTM → WGS84
│   ├── spatial_analysis.py    # GeoDataFrame, SNASPE, resumen regional
│   └── run.py                 # CLI
│
├── lca/                       # Fase 4a — ACV
│   ├── factors.py             # Factores IPCC AR6 / NREL / Ong (2013)
│   ├── calculator.py          # Energía, GEI, agua, benchmarks tierra
│   └── run.py                 # CLI → results_lca.xlsx
│
├── api/                       # Fase 4b — FastAPI
│   └── main.py                # 5 endpoints REST + paginación + filtros
│
├── dashboard/                 # Fase 4c — Streamlit
│   └── app.py                 # KPIs, mix tech, regiones, ACV, mapa, tabla
│
├── tools/
│   ├── check_pdfs.py          # Auditoría masiva PDFs
│   └── ...
│
├── tests/
│   └── ...
│
├── data/
│   ├── raw/                   # PDFs (no versionados)
│   ├── geo/                   # Shapefiles SNASPE (no versionados)
│   └── processed/             # Outputs del pipeline (no versionados)
│       ├── results.xlsx               # Extracción cruda
│       ├── results_normalized.xlsx    # Fase 2 — tipos normalizados
│       ├── validation_report.xlsx     # Fase 2 — rangos y outliers
│       ├── rca_data.db                # Fase 2 — SQLite 430 proyectos
│       ├── results_geo.xlsx           # Fase 3 — lon/lat WGS84
│       ├── region_summary.xlsx        # Fase 3 — métricas por región
│       ├── projects.geojson           # Fase 3 — 284 proyectos para QGIS
│       └── results_lca.xlsx           # Fase 4 — ACV completo
│
├── seia-variables.xlsx
├── requirements.txt
└── .env.example
```

---

## Stack Tecnológico

| Capa | Tecnología |
|------|-----------|
| Extracción texto | Gemini 2.5 Flash + Files API |
| Extracción escaneados | pymupdf → PNG + Gemini multimodal |
| Validación PDFs | pypdf |
| Reparación JSON | json-repair |
| Post-procesamiento | Pandas, SQLAlchemy + SQLite |
| Geoespacial | GeoPandas, Shapely, pyproj |
| ACV | Factores IPCC AR6, NREL, Ong (2013) |
| API REST | FastAPI + uvicorn |
| Dashboard | Streamlit + Plotly |
| Configuración | python-dotenv |

---

## Variables Extraídas

| Variable | Completitud | Formato |
|----------|-------------|---------|
| `region_provincia_y_comuna` | 100% | `"Región de X, Provincia de Y, Comuna de Z"` |
| `tipo_de_generacion_eolica_fv_csp` | 99.8% | `"Fotovoltaica"` / `"Eólica"` / `"CSP"` |
| `potencia_nominal_bruta_mw` | 98.8% | float MW |
| `vida_util_anos` | 98.6% | float años |
| `proximidad_y_superposicion_con_areas_protegidas` | 98.1% | string |
| `superficie_total_intervenida_ha` | 97.4% | float ha |
| `caracteristicas_del_generador` | 97.2% | texto descriptivo |
| `intensidad_de_uso_de_suelo_ha_mw_1` | 96.3% | float ha/MW |
| `coordenadas_utm_geograficas_punto_representativo` | 95.8% | string UTM |
| `emisiones_mp10_t_ano_1` | 79.3% | float t/año |
| `perdida_de_cobertura_vegetal_ha` | 67.4% | float ha |
| `emisiones_mp2_5_t_ano_1` | 67.4% | float t/año |
| `factor_de_planta` | 27.2% | float 0–1 |
| `consumo_de_agua_dulce_m3_mwh_1` | 24.2% | float m³/MWh |
| `tasas_de_mortalidad_de_aves_murcielagos` | 3.3% | string |
| `emisiones_gei_embebidas_kg_co2_eq_kwh_1` | 0% | no reportado en RCAs |

---

## Outputs del Pipeline

| Archivo | Fase | Descripción |
|---------|------|-------------|
| `results.xlsx` | 1 | Extracción cruda — 430 × 18 columnas |
| `results_normalized.xlsx` | 2 | Columnas numéricas como float64 |
| `validation_report.xlsx` | 2 | Completitud, fuera_de_rango, outliers |
| `rca_data.db` | 2 | SQLite con flags de validación |
| `results_geo.xlsx` | 3 | + lon, lat, utm_zone, datum_warning |
| `region_summary.xlsx` | 3 | Métricas por región |
| `projects.geojson` | 3 | 284 proyectos para QGIS / Mapbox |
| `results_lca.xlsx` | 4 | + 9 columnas ACV por proyecto |

---

## Costos

| Concepto | Valor |
|----------|-------|
| Pasada 1 — 420 PDFs | 8.654 CLP |
| Pasada 2 — 12 PDFs | 224 CLP |
| **Total** | **8.878 CLP (~$8.9 USD)** |
| Por PDF exitoso | ~20.6 CLP / ~$0.022 USD |

---

## Contribuir

```bash
git checkout -b feat/mi-feature
git commit -m "feat(modulo): descripción"
git push origin feat/mi-feature
```

Ver [NOTES.md](NOTES.md) para arquitectura detallada.

---

## Licencia

GPL-3.0
