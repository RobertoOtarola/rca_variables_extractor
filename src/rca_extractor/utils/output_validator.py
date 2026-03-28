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
                return text[start: i + 1]

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
                "JSON invalido y json-repair no instalado. "
                "Ejecuta: pip install json-repair"
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
