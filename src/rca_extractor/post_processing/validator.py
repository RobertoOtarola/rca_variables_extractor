"""
post_processing/validator.py — Valida rangos científicos y detecta outliers.

Basado en literatura de proyectos ERNC en Chile (SEIA, CNE, IRENA).
"""

import logging
import pandas as pd
from dataclasses import dataclass

log = logging.getLogger("rca_extractor")


@dataclass
class RangeRule:
    col: str
    min_val: float
    max_val: float
    unit: str
    note: str = ""


# ── Rangos válidos para proyectos ERNC en Chile ───────────────────────────────
RANGE_RULES: list[RangeRule] = [
    RangeRule("potencia_nominal_bruta_mw", 0.1, 2000, "MW"),
    RangeRule("superficie_total_intervenida_ha", 0.01, 50000, "ha"),
    RangeRule("intensidad_de_uso_de_suelo_ha_mw_1", 0.01, 200, "ha/MW"),
    RangeRule("vida_util_anos", 5, 60, "años"),
    RangeRule(
        "factor_de_planta",
        0.05,
        0.99,
        "—",
        note="FV chile ~0.20-0.35; Eólica ~0.25-0.55; solar high-irrad hasta 0.95",
    ),
    RangeRule("perdida_de_cobertura_vegetal_ha", 0, 50000, "ha"),
    RangeRule("emisiones_mp10_t_ano_1", 0, 10000, "t/año"),
    RangeRule("emisiones_mp2_5_t_ano_1", 0, 5000, "t/año"),
    RangeRule(
        "consumo_de_agua_dulce_m3_mwh_1",
        0,
        20,
        "m³/MWh",
        note="FV casi 0; CSP húmedo hasta 3; >20 probable error",
    ),
]


@dataclass
class ValidationResult:
    archivo: str
    col: str
    valor: float
    estado: str  # "ok" | "fuera_de_rango" | "outlier_3sigma"
    mensaje: str = ""


def validate_ranges(df: pd.DataFrame) -> pd.DataFrame:
    """
    Valida rangos para cada fila y columna.
    Devuelve DataFrame con columnas: archivo, col, valor, estado, mensaje.
    """
    results = []
    for rule in RANGE_RULES:
        if rule.col not in df.columns:
            continue
        col_data = df[["archivo", rule.col]].dropna(subset=[rule.col])
        for _, row in col_data.iterrows():
            val = row[rule.col]
            if val < rule.min_val or val > rule.max_val:
                results.append(
                    ValidationResult(
                        archivo=row["archivo"],
                        col=rule.col,
                        valor=round(val, 6),
                        estado="fuera_de_rango",
                        mensaje=f"Valor {val:.4g} fuera de [{rule.min_val}, {rule.max_val}] {rule.unit}",
                    )
                )
    return (
        pd.DataFrame([vars(r) for r in results])
        if results
        else pd.DataFrame(columns=["archivo", "col", "valor", "estado", "mensaje"])
    )


def detect_outliers(df: pd.DataFrame, sigma: float = 3.0) -> pd.DataFrame:
    """
    Detecta outliers por columna usando z-score > sigma.
    Opera solo sobre columnas numéricas con al menos 10 valores.
    """
    results = []
    numeric_cols = [r.col for r in RANGE_RULES if r.col in df.columns]
    for col in numeric_cols:
        series = df[col].dropna()
        if len(series) < 10:
            continue
        mean, std = series.mean(), series.std()
        if std == 0:
            continue
        z = (series - mean) / std
        outlier_idx = z[z.abs() > sigma].index
        for idx in outlier_idx:
            val = df.loc[idx, col]
            results.append(
                {
                    "archivo": df.loc[idx, "archivo"],
                    "col": col,
                    "valor": round(val, 6),
                    "estado": "outlier_3sigma",
                    "z_score": round(z[idx], 2),
                    "mensaje": f"z={z[idx]:.2f} (media={mean:.3g}, σ={std:.3g})",
                }
            )
    return (
        pd.DataFrame(results)
        if results
        else pd.DataFrame(columns=["archivo", "col", "valor", "estado", "z_score", "mensaje"])
    )


def completeness_report(df: pd.DataFrame) -> pd.DataFrame:
    """Reporte de completitud por variable."""
    rows = []
    for col in df.columns:
        if col in ("archivo", "escaneado"):
            continue
        n_total = len(df)
        n_null = df[col].isna().sum()
        n_na_str = (df[col].astype(str).str.strip().str.upper() == "N/A").sum()
        n_missing = int(n_null + n_na_str)
        n_present = n_total - n_missing
        rows.append(
            {
                "variable": col,
                "presentes": n_present,
                "faltantes": n_missing,
                "completitud_pct": round(n_present / n_total * 100, 1),
            }
        )
    return pd.DataFrame(rows).sort_values("completitud_pct", ascending=False)
