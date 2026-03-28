"""
prompt_builder.py — Construye el prompt final que se envía a Gemini.

Estrategia:
  1. Carga el system prompt base desde prompts/extraction_prompt.md.
  2. Normaliza cada variable a una clave snake_case para asegurar
     que el JSON de salida sea predecible y fácil de procesar.
  3. Inyecta las variables + su clave esperada en el prompt.
"""

import re
import os
import logging
import pandas as pd
from pathlib import Path

log = logging.getLogger("rca_extractor")

# ── Normalización de claves ───────────────────────────────────────────────────

def _to_snake_key(text: str) -> str:
    """
    Convierte un nombre de variable legible en una clave JSON snake_case.
    Ej: 'Potencia nominal bruta (MW)' → 'potencia_nominal_bruta_mw'
    """
    text = text.lower()
    text = re.sub(r"[áàäâã]", "a", text)
    text = re.sub(r"[éèëê]",   "e", text)
    text = re.sub(r"[íìïî]",   "i", text)
    text = re.sub(r"[óòöôõ]",  "o", text)
    text = re.sub(r"[úùüû]",   "u", text)
    text = re.sub(r"[ñ]",      "n", text)
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text


# ── Carga del archivo de variables ───────────────────────────────────────────

def load_variables(path: Path | str, column: str = "Variable Clave") -> list[dict]:
    """
    Carga el Excel de variables y devuelve una lista de dicts:
      [{"label": "Nombre legible", "key": "snake_key"}, ...]
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Archivo de variables no encontrado: {path}")

    df = pd.read_excel(path)

    if column not in df.columns:
        raise ValueError(f"Columna '{column}' no existe en {path}. Disponibles: {df.columns.tolist()}")

    variables = []
    for label in df[column].dropna():
        label = str(label).strip()
        if label:
            variables.append({"label": label, "key": _to_snake_key(label)})

    log.info("Variables cargadas: %d", len(variables))
    return variables


# ── Carga del system prompt base ─────────────────────────────────────────────

def _load_system_prompt(prompt_file: Path) -> str:
    if prompt_file.exists():
        return prompt_file.read_text(encoding="utf-8").strip()
    log.warning("Archivo de prompt no encontrado: %s. Usando prompt mínimo.", prompt_file)
    return (
        "Eres un analista ambiental experto en Resoluciones de Calificación Ambiental (RCA) "
        "del Sistema de Evaluación Ambiental de Chile. "
        "Extrae variables estructuradas del documento. "
        "Devuelve SOLO un JSON válido, sin texto adicional."
    )


# ── Constructor de prompt ─────────────────────────────────────────────────────

def build_prompt(variables: list[dict], prompt_file: Path | None = None) -> str:
    """
    Construye el prompt completo:
      - System prompt con rol y reglas.
      - Lista de variables con su clave JSON esperada.
      - Ejemplo de formato de salida.
    """
    base = _load_system_prompt(prompt_file) if prompt_file else (
        "Eres un analista ambiental experto en RCA de Chile. "
        "Extrae las variables indicadas. Devuelve SOLO JSON válido."
    )

    lines = []
    for v in variables:
        lines.append(f'  "{v["key"]}": "<valor de: {v["label"]}>"')

    variables_block = "\n".join(lines)

    return f"""{base}

---

# VARIABLES A EXTRAER

Para cada variable, usa EXACTAMENTE la clave indicada en el JSON de salida.
Si el valor no existe en el documento → usa "N/A".
Si hay múltiples valores → usa el principal del proyecto.

{chr(10).join(f'- Clave: "{v["key"]}" → Buscar: "{v["label"]}"' for v in variables)}

---

# FORMATO DE SALIDA OBLIGATORIO

Devuelve ÚNICAMENTE el siguiente JSON (sin markdown, sin comentarios, sin texto extra):

{{
{variables_block}
}}
"""


# ── Utilidad: diccionario de claves esperadas ─────────────────────────────────

def expected_keys(variables: list[dict]) -> list[str]:
    """Devuelve la lista de claves snake_case esperadas en el JSON de salida."""
    return [v["key"] for v in variables]
