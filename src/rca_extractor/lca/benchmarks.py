"""
lca/benchmarks.py — Clasificación de impactos LCA por proyecto.

Clasifica cada indicador ambiental como LOW / NORMAL / HIGH comparando
los valores del proyecto contra los factores de referencia internacionales
definidos en factors.py (IPCC AR6, NREL, Ong et al.).

Ejemplo de uso:
    from rca_extractor.lca.benchmarks import classify_project
    result = classify_project(row_dict)
    # result == {"ghg": "LOW", "water": "NORMAL", "land": "HIGH"}
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from rca_extractor.lca.factors import get_factors


# ── Constantes ────────────────────────────────────────────────────────────────

# Multiplicadores para clasificación de uso de suelo
LAND_LOW_THRESHOLD = 0.5   # ≤ 50% de la mediana → LOW
LAND_HIGH_THRESHOLD = 2.0  # ≥ 200% de la mediana → HIGH

# Multiplicadores para clasificación de consumo de agua
WATER_LOW_THRESHOLD = 0.5
WATER_HIGH_THRESHOLD = 2.0


@dataclass
class BenchmarkResult:
    """Resultado de la clasificación de un proyecto contra benchmarks."""

    ghg: Optional[str] = None      # LOW / NORMAL / HIGH
    water: Optional[str] = None    # LOW / NORMAL / HIGH
    land: Optional[str] = None     # LOW / NORMAL / HIGH


def classify_ghg(tech: str, value: Optional[float]) -> Optional[str]:
    """
    Clasifica la intensidad de GEI (g CO₂-eq/kWh) contra percentiles IPCC.

    - LOW:    ≤ percentil 25
    - HIGH:   ≥ percentil 75
    - NORMAL: entre ambos
    """
    if value is None:
        return None
    factors = get_factors(tech)
    if factors is None:
        return None

    if value <= factors.ghg_p25:
        return "LOW"
    if value >= factors.ghg_p75:
        return "HIGH"
    return "NORMAL"


def classify_water(tech: str, value: Optional[float]) -> Optional[str]:
    """
    Clasifica el consumo de agua (m³/MWh) contra benchmarks NREL.

    - LOW:    ≤ 50% de la mediana
    - HIGH:   ≥ 200% de la mediana
    - NORMAL: entre ambos
    """
    if value is None:
        return None
    factors = get_factors(tech)
    if factors is None:
        return None

    median = factors.water_median
    if median == 0:
        return "NORMAL"

    if value <= median * WATER_LOW_THRESHOLD:
        return "LOW"
    if value >= median * WATER_HIGH_THRESHOLD:
        return "HIGH"
    return "NORMAL"


def classify_land(tech: str, value: Optional[float]) -> Optional[str]:
    """
    Clasifica la intensidad de uso de suelo (ha/MW) contra referencia
    internacional (Ong et al., 2013).

    - LOW:    ≤ 50% de la mediana
    - HIGH:   ≥ 200% de la mediana
    - NORMAL: entre ambos
    """
    if value is None:
        return None
    factors = get_factors(tech)
    if factors is None:
        return None

    median = factors.land_median
    if median == 0:
        return "NORMAL"

    if value <= median * LAND_LOW_THRESHOLD:
        return "LOW"
    if value >= median * LAND_HIGH_THRESHOLD:
        return "HIGH"
    return "NORMAL"


def classify_project(row: dict) -> BenchmarkResult:
    """
    Clasifica un proyecto completo contra benchmarks internacionales.

    Espera un dict con al menos:
      - tipo_de_generacion_eolica_fv_csp: str
      - ghg_intensity_g_kwh: float (o None)
      - water_intensity_m3_mwh / consumo_de_agua_dulce_m3_mwh_1: float (o None)
      - intensidad_de_uso_de_suelo_ha_mw_1 / land_ha_mw: float (o None)
    """
    tech = str(row.get("tipo_de_generacion_eolica_fv_csp", "") or "")

    # GEI — usa intensidad calculada por calculator.py
    ghg_val = _safe_float(row.get("ghg_intensity_g_kwh"))

    # Agua — prioriza dato RCA, luego dato calculado
    water_val = _safe_float(
        row.get("consumo_de_agua_dulce_m3_mwh_1")
        or row.get("water_intensity_m3_mwh")
    )

    # Tierra — prioriza dato RCA, luego dato calculado
    land_val = _safe_float(
        row.get("intensidad_de_uso_de_suelo_ha_mw_1") or row.get("land_ha_mw")
    )

    return BenchmarkResult(
        ghg=classify_ghg(tech, ghg_val),
        water=classify_water(tech, water_val),
        land=classify_land(tech, land_val),
    )


def _safe_float(v: object) -> Optional[float]:
    """Convierte a float, devuelve None si NaN/None/inválido."""
    try:
        f = float(v)  # type: ignore[arg-type]
        return None if (f != f) else f  # NaN check
    except (TypeError, ValueError):
        return None
