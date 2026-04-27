"""
test_lca_calculator.py — Tests para lca/calculator.py.

Verifica el cálculo de ACV para proyectos con datos completos y parciales.
"""

from rca_extractor.lca.calculator import calculate, LCAResult, _f


# ── Helper _f ─────────────────────────────────────────────────────────────────


class TestSafeFloat:
    """Tests del helper _f (conversión segura a float)."""

    def test_valid_int(self):
        assert _f(42) == 42.0

    def test_valid_float(self):
        assert _f(3.14) == 3.14

    def test_valid_string(self):
        assert _f("100.5") == 100.5

    def test_none(self):
        assert _f(None) is None

    def test_nan(self):
        assert _f(float("nan")) is None

    def test_invalid_string(self):
        assert _f("N/A") is None

    def test_empty_string(self):
        assert _f("") is None


# ── calculate() ───────────────────────────────────────────────────────────────


class TestCalculate:
    """Tests para la función principal calculate()."""

    def test_complete_fv_project(self):
        """Proyecto FV con todos los datos produce resultados completos."""
        row = {
            "archivo": "test_fv.pdf",
            "tipo_de_generacion_eolica_fv_csp": "Fotovoltaica",
            "potencia_nominal_bruta_mw": 100.0,
            "factor_de_planta": 0.26,
            "vida_util_anos": 30.0,
            "consumo_de_agua_dulce_m3_mwh_1": 0.015,
            "intensidad_de_uso_de_suelo_ha_mw_1": 2.5,
        }
        result = calculate(row)
        assert isinstance(result, LCAResult)
        assert result.archivo == "test_fv.pdf"
        assert result.tech == "Fotovoltaica"

        # Energía: 100 MW × 8760 h × 0.26 × 30 años ≈ 6,832,800 MWh
        assert result.lifetime_energy_mwh is not None
        assert result.lifetime_energy_mwh > 0

        # GEI
        assert result.ghg_intensity_g_kwh == 24  # mediana IPCC para FV
        assert result.ghg_total_kt is not None
        assert result.ghg_total_kt > 0
        assert result.ghg_benchmark in ("LOW", "NORMAL", "HIGH")

        # Agua — de RCA
        assert result.water_source == "rca"
        assert result.water_intensity_m3_mwh == 0.015
        assert result.water_total_hm3 is not None

        # Tierra
        assert result.land_ha_mw == 2.5
        assert result.land_benchmark == "NORMAL"

    def test_missing_capacity(self):
        """Sin potencia → energía y derivados son None."""
        row = {
            "archivo": "no_cap.pdf",
            "tipo_de_generacion_eolica_fv_csp": "Fotovoltaica",
            "vida_util_anos": 30.0,
        }
        result = calculate(row)
        assert result.lifetime_energy_mwh is None
        assert result.ghg_total_kt is None

    def test_missing_life(self):
        """Sin vida útil → energía es None."""
        row = {
            "archivo": "no_life.pdf",
            "tipo_de_generacion_eolica_fv_csp": "Eólica",
            "potencia_nominal_bruta_mw": 50.0,
        }
        result = calculate(row)
        assert result.lifetime_energy_mwh is None

    def test_water_from_benchmark(self):
        """Sin consumo de agua en RCA → usa benchmark."""
        row = {
            "archivo": "no_water.pdf",
            "tipo_de_generacion_eolica_fv_csp": "Eólica",
            "potencia_nominal_bruta_mw": 100.0,
            "vida_util_anos": 25.0,
        }
        result = calculate(row)
        assert result.water_source == "benchmark"
        assert result.water_intensity_m3_mwh == 0.004  # Eólica benchmark

    def test_unknown_tech(self):
        """Tecnología desconocida → factors=None → benchmarks None."""
        row = {
            "archivo": "unknown_tech.pdf",
            "tipo_de_generacion_eolica_fv_csp": "Geotérmica",
            "potencia_nominal_bruta_mw": 50.0,
            "vida_util_anos": 30.0,
        }
        result = calculate(row)
        assert result.ghg_intensity_g_kwh is None
        assert result.ghg_benchmark is None
        assert result.land_benchmark is None

    def test_empty_row(self):
        """Row vacío → todos los campos calculados son None/default."""
        result = calculate({})
        assert result.archivo == ""
        assert result.tech == ""
        assert result.lifetime_energy_mwh is None
        assert result.ghg_intensity_g_kwh is None

    def test_land_benchmark_high(self):
        """Uso de suelo ≥ 2× mediana → HIGH."""
        row = {
            "archivo": "high_land.pdf",
            "tipo_de_generacion_eolica_fv_csp": "Fotovoltaica",
            "intensidad_de_uso_de_suelo_ha_mw_1": 6.0,  # 2× mediana FV (2.5) = 5.0
        }
        result = calculate(row)
        assert result.land_benchmark == "HIGH"

    def test_land_benchmark_low(self):
        """Uso de suelo ≤ 0.5× mediana → LOW."""
        row = {
            "archivo": "low_land.pdf",
            "tipo_de_generacion_eolica_fv_csp": "Fotovoltaica",
            "intensidad_de_uso_de_suelo_ha_mw_1": 1.0,  # 0.5× mediana FV (2.5) = 1.25
        }
        result = calculate(row)
        assert result.land_benchmark == "LOW"
