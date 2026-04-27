"""
post_processing/normalizer.py — Convierte columnas string → tipos Python correctos.

El prompt ya forzó formato numérico estricto (punto decimal, sin unidades),
así que la normalización es mayormente un pd.to_numeric + mapeo de categorías.
"""

import logging
import pandas as pd
import numpy as np

log = logging.getLogger("rca_extractor")

# ── Columnas numéricas ────────────────────────────────────────────────────────
NUMERIC_COLS: dict[str, str] = {
    "potencia_nominal_bruta_mw": "float64",
    "superficie_total_intervenida_ha": "float64",
    "intensidad_de_uso_de_suelo_ha_mw_1": "float64",
    "vida_util_anos": "float64",
    "factor_de_planta": "float64",
    "perdida_de_cobertura_vegetal_ha": "float64",
    "emisiones_mp10_t_ano_1": "float64",
    "emisiones_mp2_5_t_ano_1": "float64",
    "consumo_de_agua_dulce_m3_mwh_1": "float64",
    "emisiones_gei_embebidas_kg_co2_eq_kwh_1": "float64",
}

# ── Columnas numéricas exclusivas por tecnología ─────────────────────────────
NUMERIC_COLUMNS_EOLICA: list[str] = [
    "numero_aerogeneradores",
    "potencia_unitaria_aerogenerador_kw",
    "altura_buje_m",
    "diametro_rotor_m",
    "numero_aspas_por_aerogenerador",
    "velocidad_arranque_m_s",
    "velocidad_nominal_m_s",
    "velocidad_parada_m_s",
    "mortalidad_aves_murcielagos_total_ind",
    "demanda_energia_acumulada_mj_kwh_1",
    "potencial_de_acidificacion_g_so2_eq_kwh_1",
    "potencial_de_eutrofizacion_g_po4_eq_kwh_1",
]

NUMERIC_COLUMNS_FV: list[str] = [
    "potencia_pico_mwp",
    "numero_modulos_paneles",
    "numero_inversores",
    "altura_modulos_sobre_suelo_m",
    "irradiacion_ghi_kwh_m2_ano_1",
    "transformacion_superficie_km2_gw_1",
    "transformacion_superficie_km2_twh_1",
    "erosion_suelo_ha",
    "calidad_suelo_sqr",
    "consumo_agua_limpieza_m3_mwp_ano_1",
    "fragmentacion_habitat_ha",
    "mortalidad_aves_ind_mw_ano_1",
    "mortalidad_fauna_colision_quemadura_ind",
    "mortalidad_fauna_balsas_evaporacion_ind",
    "emisiones_particulas_t_ano_1",
    "emisiones_mercurio_g_hg_gwh_1",
    "emisiones_cadmio_g_cd_gwh_1",
    "potencial_acidificacion_lluvia_acida_g_so2_gwh_1",
    "potencial_eutrofizacion_g_n_gwh_1",
]


# ── Mapeo vocabulario controlado para tipo de generación ─────────────────────
TECH_MAP: dict[str, str] = {
    "fotovoltaica": "FV",
    "fv": "FV",
    "fotovoltaico": "FV",
    "eólica": "Eólica",
    "eolica": "Eólica",
    "eólico": "Eólica",
    "eolico": "Eólica",
    "csp": "CSP",
    "concentración solar": "CSP",
    "termosolar": "CSP",
    "eólica + fotovoltaica": "Eólica+FV",
    "fotovoltaica + csp": "FV+CSP",
}


def _to_numeric(series: pd.Series) -> pd.Series:
    """
    Convierte una serie de strings a float.
    Trata 'N/A', 'n/a', 'nan', '' como NaN.
    """
    return pd.to_numeric(
        series.astype(str)
        .str.strip()
        .replace({"N/A": np.nan, "n/a": np.nan, "nan": np.nan, "": np.nan}),
        errors="coerce",
    )


def _normalize_tech(series: pd.Series) -> pd.Series:
    """Estandariza tipo de generación a FV / Eólica / CSP / híbridos."""

    def _map(val):
        if pd.isna(val) or str(val).strip().lower() in ("n/a", "nan", ""):
            return np.nan
        key = str(val).strip().lower()
        return TECH_MAP.get(key, str(val).strip())

    return series.map(_map)


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    """
    Recibe el DataFrame crudo del Excel de extracción y devuelve uno con:
      - Columnas numéricas convertidas a float64 (NaN donde no aplica)
      - tipo_de_generacion estandarizado
      - columna 'intensidad_calculada' cuando falta pero se puede derivar
    """
    df = df.copy()

    # 1. Convertir numéricas (comunes)
    for col, dtype in NUMERIC_COLS.items():
        if col in df.columns:
            df[col] = _to_numeric(df[col])

    # 1b. Convertir numéricas (específicas por tecnología)
    for col in NUMERIC_COLUMNS_EOLICA + NUMERIC_COLUMNS_FV:
        if col in df.columns:
            df[col] = _to_numeric(df[col])

    # 2. Estandarizar tipo de generación
    if "tipo_de_generacion_eolica_fv_csp" in df.columns:
        df["tipo_de_generacion_eolica_fv_csp"] = _normalize_tech(
            df["tipo_de_generacion_eolica_fv_csp"]
        )

    # 3. Derivar intensidad uso suelo cuando falta pero hay potencia y superficie
    if all(
        c in df.columns
        for c in [
            "intensidad_de_uso_de_suelo_ha_mw_1",
            "superficie_total_intervenida_ha",
            "potencia_nominal_bruta_mw",
        ]
    ):
        mask = (
            df["intensidad_de_uso_de_suelo_ha_mw_1"].isna()
            & df["superficie_total_intervenida_ha"].notna()
            & df["potencia_nominal_bruta_mw"].notna()
            & (df["potencia_nominal_bruta_mw"] > 0)
        )
        df.loc[mask, "intensidad_de_uso_de_suelo_ha_mw_1"] = (
            df.loc[mask, "superficie_total_intervenida_ha"]
            / df.loc[mask, "potencia_nominal_bruta_mw"]
        ).round(4)
        n_derived = mask.sum()
        if n_derived:
            log.info("Intensidad uso suelo derivada en %d registros.", n_derived)

    return df
