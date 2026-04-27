"""
tech_detector.py — Detección automática de tecnología de generación eléctrica.

Usa un prompt ultraligero (~50 tokens) para clasificar la RCA antes
de la extracción completa. Esto permite seleccionar el prompt específico
(eólica vs fotovoltaica) sin procesamiento doble.
"""

from __future__ import annotations

import logging

from rca_extractor.core.gemini_client import GeminiClient
from rca_extractor import config

log = logging.getLogger("rca_extractor")

TECH_VALUES = frozenset({
    "Fotovoltaica",
    "Eólica",
    "CSP",
    "Eólica + Fotovoltaica",
    "Fotovoltaica + CSP",
})


def detect_technology(
    client: GeminiClient, 
    pdf_name: str, 
    file_ref=None, 
    images: list[bytes] | None = None
) -> str:
    """
    Detecta el tipo de tecnología de una RCA antes de la extracción completa.

    Realiza una pasada ultraligera con el prompt de detección. El costo es
    despreciable (~$0.001 USD por cada 1000 PDFs con Gemini 2.5 Flash).

    Args:
        client: Instancia de GeminiClient ya configurada.
        pdf_name: Nombre del PDF (para logging).
        file_ref: Referencia del archivo en Gemini (para PDFs con texto).
        images: Lista de imágenes de las primeras páginas (para PDFs escaneados).

    Returns:
        Uno de los valores en TECH_VALUES, o "Desconocido" si no se puede
        determinar.
    """
    try:
        prompt = config.TECH_DETECTION_PROMPT.read_text(encoding="utf-8")
        
        if images is not None:
            response = client.generate_from_images(prompt, images, retries=2, base_delay=2.0)
        elif file_ref is not None:
            response = client.generate(prompt, file_ref, retries=2, base_delay=2.0)
        else:
            raise ValueError("Se debe proveer file_ref o images")

        tech = response.strip()
        if tech in TECH_VALUES:
            log.debug("Tecnología detectada para %s: %s", pdf_name, tech)
            return tech

        log.warning(
            "Respuesta de detección no reconocida para %s: %r",
            pdf_name,
            tech,
        )
        return "Desconocido"

    except Exception as exc:
        log.warning("Detección de tecnología falló para %s: %s", pdf_name, exc)
        return "Desconocido"
