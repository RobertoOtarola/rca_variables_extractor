"""
post_processing/db_storage.py — Persistencia en SQLite vía SQLAlchemy.

Esquema alineado con las 16 variables extraídas + metadatos de pipeline.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import (
    create_engine,
    Column,
    Float,
    String,
    Boolean,
    DateTime,
    Integer,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker

log = logging.getLogger("rca_extractor")


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"

    # ── Identidad ────────────────────────────────────────────────────────────
    archivo = Column(String, primary_key=True)
    escaneado = Column(Boolean, nullable=True)

    # ── Localización ─────────────────────────────────────────────────────────
    region_provincia_y_comuna = Column(String)
    coordenadas_utm_geograficas_punto_representativo = Column(Text)

    # ── Técnicas principales ─────────────────────────────────────────────────
    tipo_de_generacion_eolica_fv_csp = Column(String)
    potencia_nominal_bruta_mw = Column(Float)
    superficie_total_intervenida_ha = Column(Float)
    intensidad_de_uso_de_suelo_ha_mw_1 = Column(Float)
    vida_util_anos = Column(Float)
    factor_de_planta = Column(Float)
    caracteristicas_del_generador = Column(Text)

    # ── Ambientales ──────────────────────────────────────────────────────────
    perdida_de_cobertura_vegetal_ha = Column(Float)
    tasas_de_mortalidad_de_aves_murcielagos = Column(Text)
    proximidad_y_superposicion_con_areas_protegidas = Column(Text)
    consumo_de_agua_dulce_m3_mwh_1 = Column(Float)
    emisiones_mp10_t_ano_1 = Column(Float)
    emisiones_mp2_5_t_ano_1 = Column(Float)
    emisiones_gei_embebidas_kg_co2_eq_kwh_1 = Column(Float)

    # ── Variables compartidas (prompts específicos) ───────────────────────────
    coordenadas_utm_geograficas_poligono = Column(Text)
    tipo_de_generacion = Column(String)
    uso_de_suelo_previo = Column(String)
    emisiones_gases_nox_co_so2_kg_dia_1 = Column(String)
    ruido_operacion_db_a = Column(Float)
    efluentes_liquidos_l_dia_1 = Column(Float)
    perdida_suelo_m3 = Column(Float)
    cambio_propiedades_suelo = Column(String)
    perdida_flora_individuos_o_ha = Column(String)
    perturbacion_fauna_terrestre = Column(String)
    impacto_visual_paisaje = Column(String)
    impacto_patrimonio_cultural = Column(String)
    restriccion_circulacion_horas = Column(String)

    # ── Columnas exclusivas Eólica ─────────────────────────────────────────────
    numero_aerogeneradores = Column(Integer)
    potencia_unitaria_aerogenerador_kw = Column(Float)
    altura_buje_m = Column(Float)
    diametro_rotor_m = Column(Float)
    numero_aspas_por_aerogenerador = Column(Integer)
    velocidad_arranque_m_s = Column(Float)
    velocidad_nominal_m_s = Column(Float)
    velocidad_parada_m_s = Column(Float)
    sombra_parpadeante_efecto_disco = Column(String)
    mortalidad_aves_murcielagos_total_ind = Column(Integer)
    demanda_energia_acumulada_mj_kwh_1 = Column(Float)
    potencial_de_acidificacion_g_so2_eq_kwh_1 = Column(Float)
    potencial_de_eutrofizacion_g_po4_eq_kwh_1 = Column(Float)

    # ── Columnas exclusivas Fotovoltaica ───────────────────────────────────────
    subtipo_tecnologico = Column(String)
    potencia_pico_mwp = Column(Float)
    numero_modulos_paneles = Column(Integer)
    numero_inversores = Column(Integer)
    configuracion_seguimiento = Column(String)
    altura_modulos_sobre_suelo_m = Column(Float)
    irradiacion_ghi_kwh_m2_ano_1 = Column(Float)
    transformacion_superficie_km2_gw_1 = Column(Float)
    transformacion_superficie_km2_twh_1 = Column(Float)
    erosion_suelo_ha = Column(Float)
    calidad_suelo_sqr = Column(Float)
    consumo_agua_limpieza_m3_mwp_ano_1 = Column(Float)
    fuente_abastecimiento_hidrico = Column(String)
    fragmentacion_habitat_ha = Column(Float)
    calidad_habitat_local = Column(String)
    mortalidad_aves_ind_mw_ano_1 = Column(Float)
    mortalidad_fauna_colision_quemadura_ind = Column(Integer)
    mortalidad_fauna_balsas_evaporacion_ind = Column(Integer)
    aceptacion_social = Column(String)
    emisiones_particulas_t_ano_1 = Column(Float)
    emisiones_mercurio_g_hg_gwh_1 = Column(Float)
    emisiones_cadmio_g_cd_gwh_1 = Column(Float)
    potencial_acidificacion_lluvia_acida_g_so2_gwh_1 = Column(Float)
    potencial_eutrofizacion_g_n_gwh_1 = Column(Float)

    # ── Trazabilidad de detección ─────────────────────────────────────────────
    tecnologia_detectada = Column(String)

    # ── Metadatos de pipeline ─────────────────────────────────────────────────
    validation_status = Column(String, default="ok")
    outlier_flags = Column(Integer, default=0)  # nº de flags de outlier
    range_flags = Column(Integer, default=0)  # nº de flags fuera de rango
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


def get_engine(db_url: str = "sqlite:///data/processed/rca_data.db"):
    Path(db_url.replace("sqlite:///", "")).parent.mkdir(parents=True, exist_ok=True)
    return create_engine(db_url, echo=False)


def init_db(engine) -> None:
    Base.metadata.create_all(engine)
    log.info("BD inicializada: %s", engine.url)


def upsert_projects(
    engine, df: pd.DataFrame, outlier_df: pd.DataFrame, range_df: pd.DataFrame
) -> int:
    """
    Inserta o actualiza proyectos. Devuelve el número de filas upsertadas.
    Usa session.merge() para manejar duplicados por primary key (archivo).
    """
    Session = sessionmaker(bind=engine)
    session = Session()

    # Contar flags por archivo
    outlier_counts = outlier_df.groupby("archivo").size().to_dict() if len(outlier_df) else {}
    range_counts = range_df.groupby("archivo").size().to_dict() if len(range_df) else {}

    # Columnas del modelo
    model_cols = {c.key for c in Project.__table__.columns}

    count = 0
    for _, row in df.iterrows():
        data = {
            k: (None if pd.isna(v) else bool(v == "sí") if k == "escaneado" else v)
            for k, v in row.items()
            if k in model_cols
        }
        arch = data.get("archivo", "")
        outlier_f = int(outlier_counts.get(arch, 0))
        range_f = int(range_counts.get(arch, 0))
        data["outlier_flags"] = outlier_f
        data["range_flags"] = range_f
        data["validation_status"] = (
            "has_issues" if (outlier_f + range_f) > 0 else "ok"
        )
        session.merge(Project(**data))
        count += 1

    session.commit()
    session.close()
    log.info("Upserted %d proyectos en BD.", count)
    return count
