"""
test_output_validator.py — Tests unitarios para output_validator.py.

Cubre extract_json_block con edge cases y escenarios reales de respuestas
de Gemini.
"""

from rca_extractor.utils.output_validator import (
    extract_json_block, parse_and_validate, validate_output,
    COMMON_KEYS,
)


class TestExtractJsonBlock:
    def test_plain_json(self):
        text = '{"key": "value"}'
        assert extract_json_block(text) == '{"key": "value"}'

    def test_json_in_markdown(self):
        text = '```json\n{"key": "value"}\n```'
        assert extract_json_block(text) == '{"key": "value"}'

    def test_json_in_markdown_no_lang(self):
        text = '```\n{"key": "value"}\n```'
        assert extract_json_block(text) == '{"key": "value"}'

    def test_json_with_surrounding_text(self):
        text = 'Aquí va el resultado:\n{"a": 1}\nEso es todo.'
        result = extract_json_block(text)
        assert '"a": 1' in result

    def test_nested_json(self):
        text = '{"outer": {"inner": "value"}}'
        result = extract_json_block(text)
        assert '"inner"' in result
        assert '"outer"' in result

    def test_no_json(self):
        text = "No hay JSON aquí."
        assert extract_json_block(text) == "{}"

    def test_empty_string(self):
        assert extract_json_block("") == "{}"

    def test_unbalanced_braces(self):
        text = '{"key": "value"'
        # Should return {} since braces never balance
        assert extract_json_block(text) == "{}"


class TestParseAndValidateEdgeCases:
    KEYS = ["a", "b"]

    def test_empty_json_fills_na(self):
        result = parse_and_validate("{}", self.KEYS)
        assert result == {"a": "N/A", "b": "N/A"}

    def test_case_insensitive_keys(self):
        raw = '{"A": "val_a", "B": "val_b"}'
        result = parse_and_validate(raw, self.KEYS)
        assert result["a"] == "val_a"
        assert result["b"] == "val_b"

    def test_whitespace_in_keys(self):
        raw = '{" a ": "val_a"}'
        result = parse_and_validate(raw, self.KEYS)
        assert result["a"] == "val_a"

    def test_non_dict_response(self):
        raw = '["array", "response"]'
        result = parse_and_validate(raw, self.KEYS)
        assert result == {"a": "N/A", "b": "N/A"}


# ── validate_output (prompts específicos) ─────────────────────────────────────

class TestValidateOutput:
    def test_eolica_includes_eolica_keys(self):
        data = {"tipo_de_generacion": "Eólica", "altura_buje_m": 120}
        result = validate_output(data)
        assert "altura_buje_m" in result
        assert "numero_aerogeneradores" in result  # rellenado con N/A

    def test_fv_includes_fv_keys(self):
        data = {"tipo_de_generacion": "Fotovoltaica", "potencia_pico_mwp": 300}
        result = validate_output(data)
        assert "potencia_pico_mwp" in result
        assert "numero_modulos_paneles" in result  # rellenado con N/A

    def test_unknown_keys_removed(self):
        data = {"tipo_de_generacion": "Eólica", "clave_inventada": "valor"}
        result = validate_output(data)
        assert "clave_inventada" not in result

    def test_common_keys_always_filled(self):
        data = {"tipo_de_generacion": "Desconocido"}
        result = validate_output(data)
        for key in COMMON_KEYS:
            assert key in result

    def test_eolica_does_not_include_fv_exclusive(self):
        data = {"tipo_de_generacion": "Eólica"}
        result = validate_output(data)
        # FV-exclusive keys should not be forced (not in expected)
        assert result.get("potencia_pico_mwp", "N/A") == "N/A"

    def test_case_insensitive_keys_in_validate(self):
        data = {"Tipo_De_Generacion": "Fotovoltaica", "POTENCIA_PICO_MWP": 150}
        result = validate_output(data)
        assert result["potencia_pico_mwp"] == 150

