"""
output_validator.py — Valida y normaliza el JSON devuelto por Gemini.

Responsabilidades:
  1. Extraer el bloque JSON del texto crudo (resiste markdown, texto extra).
  2. Parsear el JSON de forma segura, con reparacion via json-repair.
  3. Rellenar con "N/A" las claves esperadas que falten.
  4. Advertir sobre claves inesperadas (posible alucinacion de clave).
"""

import json
import re
import logging

try:
    from json_repair import repair_json

    _HAS_JSON_REPAIR = True
except ImportError:
    _HAS_JSON_REPAIR = False

log = logging.getLogger("rca_extractor")


def extract_json_block(text: str) -> str:
    """
    Extrae el primer bloque JSON del texto.
    Soporta JSON envuelto en markdown.
    """
    md_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if md_match:
        return md_match.group(1)

    start = text.find("{")
    if start == -1:
        return "{}"

    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]

    return "{}"


def _try_parse(block: str) -> dict | None:
    """Intenta parsear JSON. Devuelve dict o None si falla."""
    try:
        data = json.loads(block)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def parse_and_validate(raw_text: str, keys: list[str]) -> dict:
    """
    Parsea el texto crudo de Gemini y devuelve un dict validado.
    """
    block = extract_json_block(raw_text)

    # Intento 1: JSON limpio
    data = _try_parse(block)

    # Intento 2: json-repair (si esta instalado)
    if data is None:
        if _HAS_JSON_REPAIR:
            log.warning("JSON invalido. Intentando reparar con json-repair...")
            try:
                repaired = repair_json(block, return_objects=True)
                data = repaired if isinstance(repaired, dict) else None
                if data is not None:
                    log.info("JSON reparado exitosamente.")
            except Exception as exc:
                log.warning("json-repair fallo: %s", exc)
                data = None
        else:
            log.warning(
                "JSON invalido y json-repair no instalado. Ejecuta: pip install json-repair"
            )

    if data is None:
        log.warning("No se pudo parsear el JSON. Se devolvera resultado vacio.")
        data = {}

    # Normalizar claves
    data = {k.lower().strip(): v for k, v in data.items()}
    normalized_keys = [k.lower().strip() for k in keys]

    result: dict = {}
    missing = []

    for key in normalized_keys:
        if key in data:
            result[key] = data[key]
        else:
            result[key] = "N/A"
            missing.append(key)

    if missing:
        log.debug("Claves faltantes rellenas con N/A: %s", missing)

    unexpected = set(data.keys()) - set(normalized_keys)
    if unexpected:
        log.warning("Claves inesperadas ignoradas: %s", unexpected)

    return result


# ── Claves por tecnología (prompts específicos) ──────────────────────────────

# Claves comunes (25) — presentes en ambos prompts
COMMON_KEYS = {
    "region_provincia_y_comuna", "coordenadas_utm_geograficas_poligono",
    "tipo_de_generacion", "potencia_nominal_bruta_mw", "vida_util_anos",
    "factor_de_planta", "superficie_total_intervenida_ha",
    "intensidad_de_uso_de_suelo_ha_mw_1", "perdida_de_cobertura_vegetal_ha",
    "uso_de_suelo_previo", "proximidad_y_superposicion_con_areas_protegidas",
    "emisiones_mp10_t_ano_1", "emisiones_mp2_5_t_ano_1",
    "emisiones_gases_nox_co_so2_kg_dia_1", "ruido_operacion_db_a",
    "consumo_de_agua_dulce_m3_mwh_1", "efluentes_liquidos_l_dia_1",
    "perdida_suelo_m3", "cambio_propiedades_suelo", "perdida_flora_individuos_o_ha",
    "perturbacion_fauna_terrestre", "impacto_visual_paisaje",
    "impacto_patrimonio_cultural", "restriccion_circulacion_horas",
    "emisiones_gei_embebidas_g_co2_eq_kwh_1",
}

# Claves exclusivas de Eólica (14)
EOLICA_KEYS = {
    "numero_aerogeneradores", "potencia_unitaria_aerogenerador_kw",
    "altura_buje_m", "diametro_rotor_m", "numero_aspas_por_aerogenerador",
    "velocidad_arranque_m_s", "velocidad_nominal_m_s", "velocidad_parada_m_s",
    "sombra_parpadeante_efecto_disco",
    "tasas_de_mortalidad_de_aves_murcielagos", "mortalidad_aves_murcielagos_total_ind",
    "demanda_energia_acumulada_mj_kwh_1",
    "potencial_de_acidificacion_g_so2_eq_kwh_1",
    "potencial_de_eutrofizacion_g_po4_eq_kwh_1",
}

# Claves exclusivas de Fotovoltaica (24)
FV_KEYS = {
    "subtipo_tecnologico", "potencia_pico_mwp", "numero_modulos_paneles",
    "numero_inversores", "configuracion_seguimiento", "altura_modulos_sobre_suelo_m",
    "irradiacion_ghi_kwh_m2_ano_1", "transformacion_superficie_km2_gw_1",
    "transformacion_superficie_km2_twh_1", "erosion_suelo_ha", "calidad_suelo_sqr",
    "consumo_agua_limpieza_m3_mwp_ano_1", "fuente_abastecimiento_hidrico",
    "fragmentacion_habitat_ha", "calidad_habitat_local",
    "mortalidad_aves_ind_mw_ano_1", "mortalidad_fauna_colision_quemadura_ind",
    "mortalidad_fauna_balsas_evaporacion_ind", "aceptacion_social",
    "emisiones_particulas_t_ano_1", "emisiones_mercurio_g_hg_gwh_1",
    "emisiones_cadmio_g_cd_gwh_1", "potencial_acidificacion_lluvia_acida_g_so2_gwh_1",
    "potencial_eutrofizacion_g_n_gwh_1",
}

# Claves de trazabilidad del pipeline
PIPELINE_KEYS = {"archivo", "escaneado", "tecnologia_detectada"}

ALL_VALID_KEYS = COMMON_KEYS | EOLICA_KEYS | FV_KEYS | PIPELINE_KEYS


def validate_output(data: dict) -> dict:
    """
    Valida y normaliza el dict extraído por Gemini con prompts específicos.

    - Elimina claves no reconocidas.
    - Rellena con "N/A" las claves esperadas según tecnología que falten.
    - Determina la tecnología del dict a partir de 'tipo_de_generacion'.
    """
    # Normalizar claves del dict
    data = {k.lower().strip(): v for k, v in data.items()}

    tech = data.get("tipo_de_generacion", "Desconocido")
    expected = set(COMMON_KEYS)
    if isinstance(tech, str) and "Eólica" in tech:
        expected |= EOLICA_KEYS
    if isinstance(tech, str) and ("Fotovoltaica" in tech or "CSP" in tech):
        expected |= FV_KEYS

    cleaned = {k: v for k, v in data.items() if k in ALL_VALID_KEYS}
    for key in expected:
        cleaned.setdefault(key, "N/A")
    return cleaned

