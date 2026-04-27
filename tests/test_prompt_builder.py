"""
test_prompt_builder.py — Tests unitarios para prompt_builder.py y output_validator.py.

Uso:
    python -m pytest tests/ -v
"""

import pytest
from pathlib import Path

from rca_extractor.utils.prompt_builder import (
    load_variables, build_prompt, expected_keys, _to_snake_key, get_prompt_for_technology,
)
from rca_extractor.utils.output_validator import parse_and_validate


# ── _to_snake_key ─────────────────────────────────────────────────────────────

class TestToSnakeKey:
    @pytest.mark.parametrize("label, expected", [
        ("Potencia nominal bruta (MW)", "potencia_nominal_bruta_mw"),
        ("Coordenadas UTM/Geográficas (polígono)", "coordenadas_utm_geograficas_poligono"),
        ("Región, provincia y comuna", "region_provincia_y_comuna"),
        ("Emisiones GEI embebidas (kg CO2-eq kWh-1)", "emisiones_gei_embebidas_kg_co2_eq_kwh_1"),
        ("  Espacios  múltiples  ", "espacios_multiples"),
        ("MAYÚSCULAS Y TILDES", "mayusculas_y_tildes"),
    ])
    def test_conversion(self, label, expected):
        assert _to_snake_key(label) == expected


# ── load_variables ────────────────────────────────────────────────────────────

class TestLoadVariables:
    def test_loads_from_excel(self):
        """Carga variables desde el Excel real si existe."""
        excel_path = Path(__file__).parent.parent / "seia-variables.xlsx"
        if not excel_path.exists():
            pytest.skip("seia-variables.xlsx no encontrado")

        variables = load_variables(excel_path)
        assert len(variables) > 0
        assert all("label" in v and "key" in v for v in variables)

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_variables("archivo_inexistente.xlsx")

    def test_column_not_found(self):
        excel_path = Path(__file__).parent.parent / "seia-variables.xlsx"
        if not excel_path.exists():
            pytest.skip("seia-variables.xlsx no encontrado")

        with pytest.raises(ValueError, match="Columna"):
            load_variables(excel_path, column="Columna Inexistente")


# ── build_prompt ──────────────────────────────────────────────────────────────

class TestBuildPrompt:
    SAMPLE_VARS = [
        {"label": "Potencia nominal bruta (MW)", "key": "potencia_nominal_bruta_mw"},
        {"label": "Vida útil (años)", "key": "vida_util_anos"},
        {"label": "Región, provincia y comuna", "key": "region_provincia_y_comuna"},
    ]

    def test_contains_all_keys(self):
        prompt = build_prompt(self.SAMPLE_VARS)
        for key in expected_keys(self.SAMPLE_VARS):
            assert key in prompt

    def test_prompt_length(self):
        prompt = build_prompt(self.SAMPLE_VARS)
        assert len(prompt) > 100


# ── parse_and_validate ────────────────────────────────────────────────────────

class TestParseAndValidate:
    KEYS = ["potencia_nominal_bruta_mw", "vida_util_anos", "region_provincia_y_comuna"]

    def test_clean_json(self):
        raw = '{"potencia_nominal_bruta_mw": "489 MWp", "vida_util_anos": "33.5", "region_provincia_y_comuna": "Antofagasta"}'
        result = parse_and_validate(raw, self.KEYS)
        assert result["potencia_nominal_bruta_mw"] == "489 MWp"
        assert result["vida_util_anos"] == "33.5"

    def test_json_in_markdown(self):
        raw = '```json\n{"potencia_nominal_bruta_mw": "100 MW"}\n```'
        result = parse_and_validate(raw, self.KEYS)
        assert result["potencia_nominal_bruta_mw"] == "100 MW"
        assert result["vida_util_anos"] == "N/A"
        assert result["region_provincia_y_comuna"] == "N/A"

    def test_invalid_response(self):
        raw = "Lo siento, no pude extraer la información."
        result = parse_and_validate(raw, self.KEYS)
        assert all(v == "N/A" for v in result.values())

    def test_unexpected_keys_ignored(self):
        raw = '{"potencia_nominal_bruta_mw": "50 MW", "clave_inventada": "valor"}'
        result = parse_and_validate(raw, self.KEYS)
        assert "clave_inventada" not in result
        assert result["potencia_nominal_bruta_mw"] == "50 MW"


# ── get_prompt_for_technology ─────────────────────────────────────────────────

class TestGetPromptForTechnology:
    def test_get_prompt_eolica_contains_aerogenerador(self):
        prompt = get_prompt_for_technology("Eólica")
        assert "aerogenerador" in prompt.lower()

    def test_get_prompt_fv_contains_modulos(self):
        prompt = get_prompt_for_technology("Fotovoltaica")
        assert "módulos" in prompt.lower() or "modulos" in prompt.lower()

    def test_get_prompt_desconocido_returns_fallback(self):
        prompt = get_prompt_for_technology("Desconocido")
        assert len(prompt) > 0   # fallback siempre retorna algo

    def test_get_prompt_csp_uses_fv_prompt(self):
        prompt_csp = get_prompt_for_technology("CSP")
        prompt_fv = get_prompt_for_technology("Fotovoltaica")
        assert prompt_csp == prompt_fv

