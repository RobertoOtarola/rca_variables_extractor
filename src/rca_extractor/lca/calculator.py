"""
lca/calculator.py — Calcula métricas de ACV por proyecto a partir de datos RCA.

Para cada proyecto calcula:
  - Energía generada a lo largo de vida útil (MWh)
  - GEI embebidos estimados (t CO₂-eq) usando factores IPCC
  - Intensidad de agua (m³/MWh) — de RCA si disponible, si no benchmark
  - Benchmark de uso de suelo vs referencia internacional
"""

from dataclasses import dataclass
from typing import Optional
import math

from lca.factors import get_factors, TechFactors


@dataclass
class LCAResult:
    archivo:                    str
    tech:                       str
    # Energía
    lifetime_energy_mwh:        Optional[float]   # MWh en vida útil
    # GEI
    ghg_intensity_g_kwh:        Optional[float]   # g CO₂-eq/kWh (benchmark)
    ghg_total_kt:               Optional[float]   # kt CO₂-eq en vida útil
    ghg_benchmark:              Optional[str]     # LOW / NORMAL / HIGH
    # Agua
    water_intensity_m3_mwh:     Optional[float]   # de RCA o benchmark
    water_source:               str               # "rca" | "benchmark"
    water_total_hm3:            Optional[float]   # hm³ en vida útil
    # Tierra
    land_ha_mw:                 Optional[float]   # de RCA
    land_benchmark:             Optional[str]     # LOW / NORMAL / HIGH


def calculate(row: dict) -> LCAResult:
    """
    Calcula el ACV de un proyecto a partir de su fila del DataFrame normalizado.
    """
    arch  = str(row.get("archivo", ""))
    tech  = str(row.get("tipo_de_generacion_eolica_fv_csp", "") or "")
    factors: Optional[TechFactors] = get_factors(tech)

    cap   = _f(row.get("potencia_nominal_bruta_mw"))
    cf    = _f(row.get("factor_de_planta"))
    life  = _f(row.get("vida_util_anos"))
    water_rca = _f(row.get("consumo_de_agua_dulce_m3_mwh_1"))
    land  = _f(row.get("intensidad_de_uso_de_suelo_ha_mw_1"))

    # ── Energía ───────────────────────────────────────────────────────────────
    lifetime_energy: Optional[float] = None
    if cap and life:
        cf_used = cf if cf else (factors.water_median if factors else 0.25)
        # Si no hay CF, estimar según tecnología
        if not cf and factors:
            cf_used = {"FV": 0.26, "Eólica": 0.35, "CSP": 0.40}.get(
                tech, 0.28
            )
        lifetime_energy = round(cap * 8760 * cf_used * life, 0)

    # ── GEI ───────────────────────────────────────────────────────────────────
    ghg_g_kwh: Optional[float] = factors.ghg_median if factors else None
    ghg_total: Optional[float] = None
    ghg_bench: Optional[str]   = None

    if ghg_g_kwh and lifetime_energy:
        ghg_total = round(ghg_g_kwh * lifetime_energy * 1e3 / 1e9, 3)  # kt CO₂-eq

    if factors and ghg_g_kwh:
        if ghg_g_kwh <= factors.ghg_p25:
            ghg_bench = "LOW"
        elif ghg_g_kwh >= factors.ghg_p75:
            ghg_bench = "HIGH"
        else:
            ghg_bench = "NORMAL"

    # ── Agua ──────────────────────────────────────────────────────────────────
    if water_rca:
        water_src = "rca"
        water_int = water_rca
    elif factors:
        water_src = "benchmark"
        water_int = factors.water_median
    else:
        water_src = "benchmark"
        water_int = None

    water_total: Optional[float] = None
    if water_int and lifetime_energy:
        water_total = round(water_int * lifetime_energy / 1e6, 4)  # hm³

    # ── Tierra ────────────────────────────────────────────────────────────────
    land_bench: Optional[str] = None
    if land and factors:
        if land <= factors.land_median * 0.5:
            land_bench = "LOW"
        elif land >= factors.land_median * 2:
            land_bench = "HIGH"
        else:
            land_bench = "NORMAL"

    return LCAResult(
        archivo=arch,
        tech=tech,
        lifetime_energy_mwh=lifetime_energy,
        ghg_intensity_g_kwh=ghg_g_kwh,
        ghg_total_kt=ghg_total,
        ghg_benchmark=ghg_bench,
        water_intensity_m3_mwh=water_int,
        water_source=water_src,
        water_total_hm3=water_total,
        land_ha_mw=land,
        land_benchmark=land_bench,
    )


def _f(v) -> Optional[float]:
    """Convierte a float, devuelve None si NaN/None."""
    try:
        f = float(v)
        return None if (f != f) else f   # NaN check
    except (TypeError, ValueError):
        return None
