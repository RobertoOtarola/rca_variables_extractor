"""
post_processing/db_storage.py — Persistencia en SQLite vía SQLAlchemy.

Esquema alineado con las 16 variables extraídas + metadatos de pipeline.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import (
    create_engine, Column, Float, String, Boolean,
    DateTime, Integer, Text, inspect,
)
from sqlalchemy.orm import declarative_base, sessionmaker

log = logging.getLogger("rca_extractor")
Base = declarative_base()


class Project(Base):
    __tablename__ = "projects"

    # ── Identidad ────────────────────────────────────────────────────────────
    archivo          = Column(String, primary_key=True)
    escaneado        = Column(Boolean, nullable=True)

    # ── Localización ─────────────────────────────────────────────────────────
    region_provincia_y_comuna                          = Column(String)
    coordenadas_utm_geograficas_punto_representativo   = Column(Text)

    # ── Técnicas principales ─────────────────────────────────────────────────
    tipo_de_generacion_eolica_fv_csp   = Column(String)
    potencia_nominal_bruta_mw          = Column(Float)
    superficie_total_intervenida_ha    = Column(Float)
    intensidad_de_uso_de_suelo_ha_mw_1 = Column(Float)
    vida_util_anos                     = Column(Float)
    factor_de_planta                   = Column(Float)
    caracteristicas_del_generador      = Column(Text)

    # ── Ambientales ──────────────────────────────────────────────────────────
    perdida_de_cobertura_vegetal_ha                    = Column(Float)
    tasas_de_mortalidad_de_aves_murcielagos            = Column(Text)
    proximidad_y_superposicion_con_areas_protegidas    = Column(Text)
    consumo_de_agua_dulce_m3_mwh_1                     = Column(Float)
    emisiones_mp10_t_ano_1                             = Column(Float)
    emisiones_mp2_5_t_ano_1                            = Column(Float)
    emisiones_gei_embebidas_kg_co2_eq_kwh_1            = Column(Float)

    # ── Metadatos de pipeline ─────────────────────────────────────────────────
    validation_status   = Column(String, default="ok")
    outlier_flags       = Column(Integer, default=0)   # nº de flags de outlier
    range_flags         = Column(Integer, default=0)   # nº de flags fuera de rango
    created_at          = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at          = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                                  onupdate=lambda: datetime.now(timezone.utc))


def get_engine(db_url: str = "sqlite:///data/processed/rca_data.db"):
    Path(db_url.replace("sqlite:///", "")).parent.mkdir(parents=True, exist_ok=True)
    return create_engine(db_url, echo=False)


def init_db(engine) -> None:
    Base.metadata.create_all(engine)
    log.info("BD inicializada: %s", engine.url)


def upsert_projects(engine, df: pd.DataFrame,
                    outlier_df: pd.DataFrame, range_df: pd.DataFrame) -> int:
    """
    Inserta o actualiza proyectos. Devuelve el número de filas upsertadas.
    Usa session.merge() para manejar duplicados por primary key (archivo).
    """
    Session = sessionmaker(bind=engine)
    session = Session()

    # Contar flags por archivo
    outlier_counts = outlier_df.groupby("archivo").size().to_dict() if len(outlier_df) else {}
    range_counts   = range_df.groupby("archivo").size().to_dict()   if len(range_df)   else {}

    # Columnas del modelo
    model_cols = {c.key for c in Project.__table__.columns}

    count = 0
    for _, row in df.iterrows():
        data = {
            k: (None if pd.isna(v) else
                bool(v == "sí") if k == "escaneado" else v)
            for k, v in row.items()
            if k in model_cols
        }
        arch = data.get("archivo", "")
        data["outlier_flags"] = outlier_counts.get(arch, 0)
        data["range_flags"]   = range_counts.get(arch, 0)
        data["validation_status"] = (
            "has_issues" if (data["outlier_flags"] + data["range_flags"]) > 0 else "ok"
        )
        session.merge(Project(**data))
        count += 1

    session.commit()
    session.close()
    log.info("Upserted %d proyectos en BD.", count)
    return count
