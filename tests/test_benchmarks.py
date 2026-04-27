"""
test_benchmarks.py — Tests para lca/benchmarks.py.

Verifica la clasificación LOW / NORMAL / HIGH contra factores de referencia.
"""

from rca_extractor.lca.benchmarks import (
    classify_ghg,
    classify_water,
    classify_land,
    classify_project,
    BenchmarkResult,
)


# ── classify_ghg ──────────────────────────────────────────────────────────────


class TestClassifyGhg:
    """Tests de clasificación de GEI por tecnología."""

    def test_fv_low(self):
        """FV con GEI ≤ p25 (13) → LOW."""
        assert classify_ghg("Fotovoltaica", 10.0) == "LOW"

    def test_fv_normal(self):
        """FV con GEI entre p25 y p75 → NORMAL."""
        assert classify_ghg("Fotovoltaica", 24.0) == "NORMAL"

    def test_fv_high(self):
        """FV con GEI ≥ p75 (46) → HIGH."""
        assert classify_ghg("Fotovoltaica", 50.0) == "HIGH"

    def test_eolica_low(self):
        """Eólica con GEI ≤ p25 (7) → LOW."""
        assert classify_ghg("Eólica", 7.0) == "LOW"

    def test_eolica_high(self):
        """Eólica con GEI ≥ p75 (15) → HIGH."""
        assert classify_ghg("Eólica", 15.0) == "HIGH"

    def test_none_value(self):
        """Valor None → None."""
        assert classify_ghg("Fotovoltaica", None) is None

    def test_unknown_tech(self):
        """Tecnología desconocida → None."""
        assert classify_ghg("Nuclear", 20.0) is None

    def test_boundary_p25_fv(self):
        """FV con valor exactamente en p25 → LOW."""
        assert classify_ghg("Fotovoltaica", 13.0) == "LOW"

    def test_boundary_p75_fv(self):
        """FV con valor exactamente en p75 → HIGH."""
        assert classify_ghg("Fotovoltaica", 46.0) == "HIGH"


# ── classify_water ────────────────────────────────────────────────────────────


class TestClassifyWater:
    """Tests de clasificación de consumo de agua."""

    def test_fv_low(self):
        """FV mediana 0.02 → ≤ 0.01 es LOW."""
        assert classify_water("Fotovoltaica", 0.005) == "LOW"

    def test_fv_normal(self):
        """FV mediana 0.02 → 0.015 es NORMAL."""
        assert classify_water("Fotovoltaica", 0.015) == "NORMAL"

    def test_fv_high(self):
        """FV mediana 0.02 → ≥ 0.04 es HIGH."""
        assert classify_water("Fotovoltaica", 0.05) == "HIGH"

    def test_csp_high(self):
        """CSP mediana 3.0 → ≥ 6.0 es HIGH."""
        assert classify_water("CSP", 7.0) == "HIGH"

    def test_none_value(self):
        assert classify_water("Eólica", None) is None

    def test_unknown_tech(self):
        assert classify_water("Geotérmica", 1.0) is None


# ── classify_land ─────────────────────────────────────────────────────────────


class TestClassifyLand:
    """Tests de clasificación de intensidad de uso de suelo."""

    def test_fv_low(self):
        """FV mediana 2.5 → ≤ 1.25 es LOW."""
        assert classify_land("Fotovoltaica", 1.0) == "LOW"

    def test_fv_normal(self):
        """FV mediana 2.5 → 2.0 es NORMAL."""
        assert classify_land("Fotovoltaica", 2.0) == "NORMAL"

    def test_fv_high(self):
        """FV mediana 2.5 → ≥ 5.0 es HIGH."""
        assert classify_land("Fotovoltaica", 6.0) == "HIGH"

    def test_eolica_normal(self):
        """Eólica mediana 72 → 50 es NORMAL."""
        assert classify_land("Eólica", 50.0) == "NORMAL"

    def test_none_value(self):
        assert classify_land("Fotovoltaica", None) is None

    def test_unknown_tech(self):
        assert classify_land("Biomasa", 5.0) is None


# ── classify_project ──────────────────────────────────────────────────────────


class TestClassifyProject:
    """Tests de clasificación completa de un proyecto."""

    def test_complete_fv_project(self):
        """Proyecto FV con todos los datos."""
        row = {
            "tipo_de_generacion_eolica_fv_csp": "Fotovoltaica",
            "ghg_intensity_g_kwh": 24.0,
            "consumo_de_agua_dulce_m3_mwh_1": 0.015,
            "intensidad_de_uso_de_suelo_ha_mw_1": 2.0,
        }
        result = classify_project(row)
        assert isinstance(result, BenchmarkResult)
        assert result.ghg == "NORMAL"
        assert result.water == "NORMAL"
        assert result.land == "NORMAL"

    def test_empty_row(self):
        """Row vacío → todos None."""
        result = classify_project({})
        assert result.ghg is None
        assert result.water is None
        assert result.land is None

    def test_partial_data(self):
        """Solo algunos datos disponibles."""
        row = {
            "tipo_de_generacion_eolica_fv_csp": "Eólica",
            "intensidad_de_uso_de_suelo_ha_mw_1": 50.0,
        }
        result = classify_project(row)
        assert result.ghg is None   # sin dato
        assert result.water is None  # sin dato
        assert result.land == "NORMAL"

    def test_water_fallback_to_calculated(self):
        """Si no hay dato RCA de agua, usa water_intensity_m3_mwh de calculator."""
        row = {
            "tipo_de_generacion_eolica_fv_csp": "CSP",
            "water_intensity_m3_mwh": 7.0,
        }
        result = classify_project(row)
        assert result.water == "HIGH"

    def test_nan_values_treated_as_none(self):
        """Valores NaN se tratan como None."""
        row = {
            "tipo_de_generacion_eolica_fv_csp": "Fotovoltaica",
            "ghg_intensity_g_kwh": float("nan"),
        }
        result = classify_project(row)
        assert result.ghg is None
