"""
api/main.py — FastAPI REST para el RCA Extractor.

Endpoints:
  GET /health                 — liveness check
  GET /stats                  — KPIs globales
  GET /regions                — métricas por región
  GET /projects               — lista paginada con filtros opcionales
  GET /projects/{archivo}     — detalle de un proyecto
  GET /lca/{archivo}          — métricas ACV de un proyecto

Arrancar:
    uvicorn api.main:app --reload --port 8000
"""

import math
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

_BASE = Path(__file__).parent.parent
sys.path.insert(0, str(_BASE))

from lca.calculator import calculate  # noqa: E402

app = FastAPI(
    title="RCA Extractor API",
    description="API REST sobre 430 RCAs de energías renovables del SEIA de Chile",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"]
)

_DATA_DIR = _BASE / "data" / "processed"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _load_df() -> pd.DataFrame:
    """Carga el Excel más completo disponible (prioriza normalizado)."""
    for fname in ("results_lca.xlsx", "results_normalized.xlsx", "results.xlsx"):
        p = _DATA_DIR / fname
        if p.exists():
            return pd.read_excel(p)
    raise FileNotFoundError(f"No se encontró results*.xlsx en {_DATA_DIR}")


def _cast(v):
    """Convierte tipos numpy a Python nativos para serialización JSON."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    return v


def _row_to_dict(row: pd.Series) -> dict:
    return {k: _cast(v) for k, v in row.items()}


# ── Cache simple en memoria ────────────────────────────────────────────────────
_cache: dict = {}


def _df() -> pd.DataFrame:
    if "df" not in _cache:
        _cache["df"] = _load_df()
    return _cache["df"]


def _region_df() -> pd.DataFrame:
    if "regions" not in _cache:
        p = _DATA_DIR / "region_summary.xlsx"
        _cache["regions"] = pd.read_excel(p) if p.exists() else pd.DataFrame()
    return _cache["regions"]


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health", tags=["sistema"])
def health():
    """Liveness check — devuelve estado y cantidad de proyectos cargados."""
    try:
        n = len(_df())
        return {"status": "ok", "projects_loaded": n}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/stats", tags=["resumen"])
def stats():
    """KPIs globales del dataset completo."""
    df = _df()
    pot = df["potencia_nominal_bruta_mw"].dropna()
    fv_mask  = df["tipo_de_generacion_eolica_fv_csp"].str.contains(
        r"FV|[Ff]otovoltaica", na=False)
    eo_mask  = df["tipo_de_generacion_eolica_fv_csp"].str.contains(
        r"Eólica|Eolica", na=False)

    region_col = df["region_provincia_y_comuna"].str.extract(
        r"Región\s+(?:de(?:l)?\s+)?([^,]+)"
    )[0]

    return {
        "total_projects":      int(len(df)),
        "total_gw":            round(float(pot.sum()) / 1000, 3),
        "median_mw":           round(float(pot.median()), 2),
        "max_mw":              round(float(pot.max()), 2),
        "pct_fotovoltaica":    round(float(fv_mask.mean()) * 100, 1),
        "pct_eolica":          round(float(eo_mask.mean()) * 100, 1),
        "total_ha":            round(float(df["superficie_total_intervenida_ha"].sum()), 1),
        "avg_vida_util_yrs":   round(float(df["vida_util_anos"].mean()), 1),
        "n_regions":           int(region_col.nunique()),
        "scanned_pct":         round(float((df.get("escaneado", pd.Series()) == "sí").mean()) * 100, 1),
        # ACV (si disponibles)
        "total_twh_lifetime":  round(float(df["lifetime_energy_mwh"].sum()) / 1e6, 2)
                               if "lifetime_energy_mwh" in df.columns else None,
        "total_ghg_kt":        round(float(df["ghg_total_kt"].sum()), 0)
                               if "ghg_total_kt" in df.columns else None,
    }


@app.get("/regions", tags=["resumen"])
def regions():
    """Métricas agregadas por región (from region_summary.xlsx)."""
    reg = _region_df()
    if reg.empty:
        raise HTTPException(status_code=404, detail="region_summary.xlsx no encontrado")
    return [_row_to_dict(r) for _, r in reg.iterrows()]


@app.get("/projects", tags=["proyectos"])
def list_projects(
    page:    int   = Query(1, ge=1, description="Página (1-indexed)"),
    size:    int   = Query(20, ge=1, le=200, description="Proyectos por página"),
    region:  Optional[str] = Query(None, description="Filtro región (substring, insensible a tildes)"),
    tech:    Optional[str] = Query(None, description="FV | Eólica | CSP"),
    min_mw:  Optional[float] = Query(None, ge=0, description="Potencia mínima (MW)"),
    max_mw:  Optional[float] = Query(None, ge=0, description="Potencia máxima (MW)"),
    escaneado: Optional[bool] = Query(None, description="True = solo escaneados"),
):
    """Lista paginada de proyectos con filtros opcionales."""
    df = _df()

    if region:
        df = df[df["region_provincia_y_comuna"].str.contains(region, case=False, na=False)]
    if tech:
        tech_str = str(tech) if tech else None
        df = df[df["tipo_de_generacion_eolica_fv_csp"].str.contains(tech_str, case=False, na=False, regex=False)]
    if min_mw is not None:
        df = df[df["potencia_nominal_bruta_mw"] >= min_mw]
    if max_mw is not None:
        df = df[df["potencia_nominal_bruta_mw"] <= max_mw]
    if escaneado is not None and "escaneado" in df.columns:
        val = "sí" if escaneado else "no"
        df = df[df["escaneado"] == val]

    total = len(df)
    start = (page - 1) * size
    page_df = df.iloc[start: start + size]

    return {
        "total": total,
        "page":  page,
        "size":  size,
        "pages": math.ceil(total / size) if total else 0,
        "items": [_row_to_dict(r) for _, r in page_df.iterrows()],
    }


@app.get("/projects/{archivo}", tags=["proyectos"])
def get_project(archivo: str):
    """Detalle completo de un proyecto por nombre de archivo (ej: 163.pdf)."""
    df  = _df()
    matches = df[df["archivo"] == archivo]
    if matches.empty:
        raise HTTPException(status_code=404, detail=f"Proyecto '{archivo}' no encontrado")
    return _row_to_dict(matches.iloc[0])


@app.get("/lca/{archivo}", tags=["acv"])
def get_lca(archivo: str):
    """Métricas de Análisis de Ciclo de Vida calculadas para un proyecto."""
    df = _df()
    matches = df[df["archivo"] == archivo]
    if matches.empty:
        raise HTTPException(status_code=404, detail=f"Proyecto '{archivo}' no encontrado")
    result = calculate(matches.iloc[0].to_dict())
    return {k: _cast(v) for k, v in vars(result).items()}
