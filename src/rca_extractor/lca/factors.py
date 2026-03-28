"""
lca/factors.py — Factores de intensidad de ciclo de vida (ACV) por tecnología.

Fuentes:
  - GEI (g CO₂-eq/kWh): IPCC AR6 WG3 Ch.6 (2022), mediana de estudios LCA
  - Agua (m³/MWh):       NREL (2011), Meldrum et al. (2013)
  - Tierra (ha/MW):      McDonald et al. (2009), Ong et al. (2013)

Estos son valores de referencia internacional. Los valores calculados de las
RCAs chilenas se comparan contra estos benchmarks en benchmarks.py.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TechFactors:
    tech: str
    ghg_median: float  # g CO₂-eq/kWh — mediana IPCC
    ghg_p25: float  # percentil 25 (bajo)
    ghg_p75: float  # percentil 75 (alto)
    water_median: float  # m³/MWh — operación
    land_median: float  # ha/MW — área directa
    lifetime_yrs: float  # vida útil de referencia


FACTORS: dict[str, TechFactors] = {
    "FV": TechFactors(
        tech="Fotovoltaica",
        ghg_median=24,
        ghg_p25=13,
        ghg_p75=46,
        water_median=0.02,
        land_median=2.5,
        lifetime_yrs=30,
    ),
    "Eólica": TechFactors(
        tech="Eólica",
        ghg_median=11,
        ghg_p25=7,
        ghg_p75=15,
        water_median=0.004,
        land_median=72,  # directo solo; el resto es compartible
        lifetime_yrs=25,
    ),
    "CSP": TechFactors(
        tech="Concentración Solar Térmica",
        ghg_median=22,
        ghg_p25=14,
        ghg_p75=32,
        water_median=3.0,  # enfriamiento húmedo
        land_median=4.0,
        lifetime_yrs=30,
    ),
    "Eólica+FV": TechFactors(
        tech="Híbrido Eólica + Fotovoltaica",
        ghg_median=17,
        ghg_p25=10,
        ghg_p75=30,  # promedio ponderado
        water_median=0.01,
        land_median=37,
        lifetime_yrs=27,
    ),
    "FV+CSP": TechFactors(
        tech="Híbrido Fotovoltaica + CSP",
        ghg_median=23,
        ghg_p25=13,
        ghg_p75=39,
        water_median=1.5,
        land_median=3.0,
        lifetime_yrs=30,
    ),
}


def get_factors(tech_raw: str) -> TechFactors | None:
    """Devuelve los factores para una tecnología. Tolerante a variantes textuales."""
    if not tech_raw:
        return None
    t = str(tech_raw).strip()
    if t in FACTORS:
        return FACTORS[t]
    # Fallback por keyword
    tl = t.lower()
    if "eólica" in tl and "fotovoltaica" in tl:
        return FACTORS["Eólica+FV"]
    if "csp" in tl or "termosolar" in tl or "concentración" in tl:
        return FACTORS["CSP"]
    if "fotovoltaica" in tl or "fv" in tl:
        return FACTORS["FV"]
    if "eólica" in tl or "eolica" in tl:
        return FACTORS["Eólica"]
    return None
