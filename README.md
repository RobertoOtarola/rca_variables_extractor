# 🔍☑️ RCA Extractor

**Extractor automático de variables técnicas y ambientales desde Resoluciones de Calificación Ambiental (RCA) del Sistema de Evaluación de Impacto Ambiental (SEIA) de Chile.**

Utiliza la API de Google Gemini para procesar nativamente PDFs completos y extraer datos estructurados en JSON.

---

## Características (implementadas)

| Característica | Descripción |
|----------------|-------------|
| 🤖 **Extracción LLM-first** | Gemini 2.0 Flash procesa PDFs completos sin OCR ni regex |
| 📋 **Variables dinámicas** | Definidas en un Excel editable (`seia-variables.xlsx`) |
| 🔄 **Checkpoint & Resume** | Reanuda ejecuciones interrumpidas automáticamente |
| ⚡ **Concurrencia** | Procesa múltiples PDFs en paralelo (`ThreadPoolExecutor`) |
| 🛡️ **Validación de PDFs** | Detecta corruptos, cifrados y formatos incorrectos |

### Planificado (aún no implementado)

| Característica | Descripción |
|----------------|-------------|
| 📊 **Post-procesamiento** | Normalización de unidades, validación de rangos, detección de outliers |
| 🗄️ **Persistencia** | SQLite (local) o PostgreSQL + PostGIS (producción) |
| 🌍 **Geoespacial** | Coordenadas UTM → geometrías, intersección con áreas protegidas |
| 📈 **Dashboard** | Streamlit + Plotly con mapas, KPIs y gráficos |
| 🌱 **ACV** | Análisis de Ciclo de Vida con factores IPCC/NREL |

---

## Requisitos Previos

- **Python** 3.11+
- **API Key de Gemini** → [Google AI Studio](https://aistudio.google.com/)

---

## Instalación

```bash
# 1. Clonar el repositorio
git clone https://github.com/<usuario>/rca-extractor.git
cd rca-extractor

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

### 1. Validar PDFs

```bash
# Escaneo rápido
python tools/check_pdfs.py data/raw/ -o data/reporte_pdfs.csv

# Escaneo profundo
python tools/check_pdfs.py data/raw/ --deep --hash --strict
```

### 2. Extraer variables

```bash
# Prueba con 5 PDFs (free tier: cooldown generoso)
python main.py --pdf-folder data/raw --output data/processed/rca_results.xlsx \
  --workers 1 --cooldown 60

# Lote completo (con billing activado)
python main.py --pdf-folder data/raw --output data/processed/rca_results.xlsx \
  --workers 1 --cooldown 5

# Reanudar ejecución interrumpida
python main.py --pdf-folder data/raw --output data/processed/rca_results.xlsx

# Reprocesar todo (ignorar checkpoint)
python main.py --pdf-folder data/raw --output data/processed/rca_results.xlsx --reset
```

### 3. Ejecutar tests

```bash
pip install pytest
python -m pytest tests/ -v
```

---

## Opciones del CLI

```
python main.py [opciones]

Opciones:
  --pdf-folder   Carpeta con PDFs de RCA          (default: rcas/)
  --variables    Excel con variables a extraer     (default: seia-variables.xlsx)
  --output       Archivo Excel de salida           (default: rca_results.xlsx)
  --workers      Nº de PDFs en paralelo            (default: 1)
  --model        Modelo Gemini                     (default: gemini-2.0-flash)
  --cooldown     Segundos de pausa entre PDFs      (default: 15 — usar 60+ en free tier)
  --reset        Ignorar checkpoint, reprocesar todo
  --dry-run      Listar PDFs pendientes sin procesar
```

---

## Estructura del Proyecto

```
rca_variables_extractor/
├── main.py                  # CLI principal
├── config.py                # Configuración centralizada (.env)
├── gemini_client.py         # Cliente Gemini API con backoff
├── pdf_pipeline.py          # Pipeline de extracción por PDF
├── prompt_builder.py        # Construcción de prompts dinámicos
├── output_validator.py      # Validación y normalización de JSON
├── checkpoint.py            # Checkpoint/resume entre ejecuciones
├── logger.py                # Logging rotativo (consola + archivo)
│
├── prompts/
│   └── extraction_prompt.md # Prompt editable (rol + reglas + formato)
│
├── tools/
│   ├── check_pdfs.py        # Validación masiva de PDFs
│   ├── check_gitignore.py   # Verificar archivos trackeados vs .gitignore
│   ├── list_models.py       # Listar modelos Gemini disponibles
│   └── snippet_api_key.py   # Test rápido de conexión API
│
├── tests/
│   ├── conftest.py          # Configuración pytest
│   ├── test_prompt_builder.py
│   ├── test_output_validator.py
│   └── test_checkpoint.py
│
├── post_processing/         # 🚧 Planificado
├── geo/                     # 🚧 Planificado
├── lca/                     # 🚧 Planificado
├── api/                     # 🚧 Planificado
├── dashboard/               # 🚧 Planificado
│
├── data/
│   └── raw/                 # PDFs originales (no versionados)
│
├── seia-variables.xlsx      # Schema de variables a extraer
├── requirements.txt
└── .env.example
```

---

## Stack Tecnológico

| Capa | Tecnología |
|------|-----------|
| Extracción | Gemini 2.0 Flash + File API |
| Validación PDFs | pypdf |
| Datos | Pandas + openpyxl |
| Configuración | python-dotenv |

---

## Variables Extraídas

El sistema extrae ~15 variables por RCA, configurables en `seia-variables.xlsx`:

| Variable | Tipo | Ejemplo |
|----------|------|---------|
| Potencia nominal | float | `489 MW` |
| Superficie total | float | `689 ha` |
| Tipo de tecnología | string | `FV`, `Eólica`, `CSP` |
| Vida útil | float | `30 años` |
| Coordenadas UTM | string | `E 543.023, N 7.346.950` |
| Emisiones MP10 | float | `72.6 t/año` |
| Consumo de agua | float | `0.02 m³/MWh` |

---

## Prompt de Extracción

El prompt es editable sin modificar código — vive en `prompts/extraction_prompt.md`.

**Reglas clave:**
- Valor explícito → texto exacto + unidad
- Valor calculable → `[derivado: <cálculo>]`
- No aplica → `N/A — <razón>`
- No encontrado → `No encontrado`
- Nunca inventa valores

---

## Costos Estimados

| Modelo | Costo por PDF | 400 PDFs |
|--------|--------------|----------|
| Gemini 2.0 Flash | ~$0.01–0.03 | ~$4–12 USD |
| Gemini 1.5 Pro | ~$0.03–0.10 | ~$12–40 USD |

---

## Contribuir

1. Fork del repositorio
2. Crear branch: `git checkout -b feat/mi-feature`
3. Commits: `git commit -m "feat(modulo): descripción"`
4. Push: `git push origin feat/mi-feature`
5. Crear Pull Request

Ver [GITHUB_PROJECTS.md](GITHUB_PROJECTS.md) para el detalle de EPICs, Tasks y convenciones.

---

## Licencia

GPL-3.0

---

## Documentación

- [NOTES.md](NOTES.md) — Arquitectura unificada y comandos paso a paso
- [GITHUB_PROJECTS.md](GITHUB_PROJECTS.md) — EPICs, Tasks y Git workflow
