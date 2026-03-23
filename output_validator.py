"""
output_validator.py — Valida y normaliza el JSON devuelto por Gemini.

Responsabilidades:
  1. Extraer el bloque JSON del texto crudo (resiste markdown, texto extra).
  2. Parsear el JSON de forma segura.
  3. Rellenar con "N/A" las claves esperadas que falten.
  4. Advertir sobre claves inesperadas (posible alucinación de clave).
"""

import json
import re
import logging

log = logging.getLogger("rca_extractor")


def extract_json_block(text: str) -> str:
    """
    Extrae el primer bloque JSON del texto.
    Soporta JSON envuelto en markdown (```json ... ```).
    """
    # Primero intenta bloques markdown
    md_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if md_match:
        return md_match.group(1)

    # Luego busca el primer { ... } balanceado
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


def parse_and_validate(raw_text: str, keys: list[str]) -> dict:
    """
    Parsea el texto crudo de Gemini y devuelve un dict validado:
      - Claves esperadas presentes → se conservan.
      - Claves esperadas ausentes  → se rellenan con "N/A".
      - Claves inesperadas         → se registran como advertencia.
    """
    block = extract_json_block(raw_text)

    try:
        data = json.loads(block)
    except json.JSONDecodeError as exc:
        log.warning("JSON inválido (%s). Se devolverá resultado vacío.", exc)
        data = {}

    if not isinstance(data, dict):
        log.warning("La respuesta no es un objeto JSON. Tipo: %s", type(data))
        data = {}

    # Normalizar: todas las claves a minúsculas y sin espacios extremos
    data = {k.lower().strip(): v for k, v in data.items()}

    # Normalizar también las claves esperadas (defensivo ante espacios en el Excel)
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
