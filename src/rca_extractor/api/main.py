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
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware

from rca_extractor.lca.calculator import calculate
from rca_extractor.post_processing.db_storage import get_engine, Project, sessionmaker
from rca_extractor.config import DB_URL

# ── Configuración de BD ───────────────────────────────────────────────────────
engine = get_engine(DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI(
    title="RCA Extractor API",
    description="API REST sobre 430 RCAs de energías renovables del SEIA de Chile",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])


# ── Helpers ────────────────────────────────────────────────────────────────────

def _project_to_dict(proj: Project) -> dict:
    """Convierte un objeto SQLAlchemy Project a un dict serializable."""
    data = {c.name: getattr(proj, c.name) for c in proj.__table__.columns}
    # Asegurar que nulos no rompan el JSON o sean consistentes con N/A si se prefiere
    return data


# ── Endpoints ──────────────────────────────────────────────────────────────────


@app.get("/health", tags=["sistema"])
def health(db: Session = Depends(get_db)):
    """Liveness check — devuelve estado y cantidad de proyectos en BD."""
    try:
        n = db.query(Project).count()
        return {"status": "ok", "db_connected": True, "projects_in_db": n}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database error: {str(e)}")


@app.get("/stats", tags=["resumen"])
def stats(db: Session = Depends(get_db)):
    """KPIs globales consultados directamente desde la base de datos."""
    total = db.query(Project).count()
    if total == 0:
        return {"total_projects": 0}

    # Agregaciones básicas
    metrics = db.query(
        func.sum(Project.potencia_nominal_bruta_mw),
        func.avg(Project.potencia_nominal_bruta_mw),
        func.max(Project.potencia_nominal_bruta_mw),
        func.sum(Project.superficie_total_intervenida_ha),
        func.avg(Project.vida_util_anos),
    ).first()

    # Conteos por tecnología (usando los valores normalizados en BD: FV, Eólica)
    n_fv = db.query(Project).filter(Project.tipo_de_generacion_eolica_fv_csp.ilike("%FV%")).count()
    n_eo = db.query(Project).filter(Project.tipo_de_generacion_eolica_fv_csp.ilike("%Eólica%")).count()
    n_scanned = db.query(Project).filter(Project.escaneado.is_(True)).count()

    return {
        "total_projects":      total,
        "total_gw":            round((metrics[0] or 0) / 1000, 3),
        "median_mw":           round(metrics[1] or 0, 2), # AVG como proxy de mediana en SQL simple
        "max_mw":              round(metrics[2] or 0, 2),
        "pct_fotovoltaica":    round((n_fv / total) * 100, 1),
        "pct_eolica":          round((n_eo / total) * 100, 1),
        "total_ha":            round(metrics[3] or 0, 1),
        "avg_vida_util_yrs":   round(metrics[4] or 0, 1),
        "scanned_pct":         round((n_scanned / total) * 100, 1),
    }


@app.get("/regions", tags=["resumen"])
def regions(db: Session = Depends(get_db)):
    """Métricas agregadas por región (calculadas dinámicamente)."""
    # Nota: Aquí podríamos usar una vista o una tabla 'region_summary' si fuera muy lento
    results = db.query(
        Project.region_provincia_y_comuna,
        func.count(Project.archivo).label("n"),
        func.sum(Project.potencia_nominal_bruta_mw).label("mw")
    ).group_by(Project.region_provincia_y_comuna).all()

    return [
        {"region_raw": r[0], "count": r[1], "potencia_mw": round(r[2] or 0, 1)}
        for r in results
    ]


@app.get("/projects", tags=["proyectos"])
def list_projects(
    page:      int   = Query(1, ge=1),
    size:      int   = Query(20, ge=1, le=200),
    region:    Optional[str] = None,
    tech:      Optional[str] = None,
    min_mw:    Optional[float] = None,
    max_mw:    Optional[float] = None,
    escaneado: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """Lista paginada de proyectos con filtros directos de base de datos."""
    query = db.query(Project)

    if region:
        query = query.filter(Project.region_provincia_y_comuna.ilike(f"%{region}%"))
    if tech:
        query = query.filter(Project.tipo_de_generacion_eolica_fv_csp.ilike(f"%{tech}%"))
    if min_mw is not None:
        query = query.filter(Project.potencia_nominal_bruta_mw >= min_mw)
    if max_mw is not None:
        query = query.filter(Project.potencia_nominal_bruta_mw <= max_mw)
    if escaneado is not None:
        query = query.filter(Project.escaneado == escaneado)

    total = query.count()
    items = query.offset((page - 1) * size).limit(size).all()

    return {
        "total": total,
        "page":  page,
        "size":  size,
        "pages": math.ceil(total / size) if total else 0,
        "items": [_project_to_dict(i) for i in items],
    }


@app.get("/projects/{archivo}", tags=["proyectos"])
def get_project(archivo: str, db: Session = Depends(get_db)):
    """Detalle completo de un proyecto por nombre de archivo."""
    proj = db.query(Project).filter(Project.archivo == archivo).first()
    if not proj:
        raise HTTPException(status_code=404, detail=f"Proyecto '{archivo}' no encontrado")
    return _project_to_dict(proj)


@app.get("/lca/{archivo}", tags=["acv"])
def get_lca(archivo: str, db: Session = Depends(get_db)):
    """Métricas de ACV calculadas para un proyecto de la BD."""
    proj = db.query(Project).filter(Project.archivo == archivo).first()
    if not proj:
        raise HTTPException(status_code=404, detail=f"Proyecto '{archivo}' no encontrado")
    
    # El calculator espera un dict que coincida con las columnas del Excel
    # El modelo Project tiene nombres de campos alineados.
    data = _project_to_dict(proj)
    result = calculate(data)
    return vars(result)
