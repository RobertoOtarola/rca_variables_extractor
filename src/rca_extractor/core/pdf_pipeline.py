"""
pdf_pipeline.py — Orquesta el procesamiento de un PDF individual.

Flujo:
  1. Detecta tecnología (prompt ultraligero, 2–5 segundos).
  2. Selecciona el prompt específico según tecnología detectada.
  3a. PDF con texto   → sube a Gemini Files API → generate()
  3b. PDF escaneado   → convierte páginas a imágenes → generate_from_images()
  4. Valida y normaliza el JSON de salida.
  5. Siempre limpia el archivo de Gemini (solo para PDFs con texto).
"""

import logging
from pathlib import Path

from rca_extractor.core.gemini_client import GeminiClient
from rca_extractor.utils.prompt_builder import (
    build_prompt,
    expected_keys,
    get_prompt_for_technology,
)
from rca_extractor.utils.output_validator import parse_and_validate, validate_output
from rca_extractor.utils.pdf_utils import detect_scanned
from rca_extractor.utils.tech_detector import detect_technology
from rca_extractor import config

log = logging.getLogger("rca_extractor")


class RCAExtractor:
    def __init__(
        self,
        model: str | None = None,
        temperature: float | None = None,
        max_retries: int | None = None,
        retry_base_delay: float | None = None,
    ) -> None:
        self.client = GeminiClient(
            api_key=config.GEMINI_API_KEY,
            model=model or config.GEMINI_MODEL,
            temperature=temperature if temperature is not None else config.TEMPERATURE,
        )
        self.max_retries = max_retries or config.MAX_RETRIES
        self.retry_base_delay = retry_base_delay or config.RETRY_BASE_DELAY

    def process_pdf(self, pdf_path: str | Path, variables: list[dict]) -> dict:
        """
        Procesa un PDF y devuelve un dict con las variables extraídas.

        Flujo en dos fases:
          1. Detecta tecnología (si TECH_DETECTION_ENABLED).
          2. Extrae variables con el prompt específico o el genérico como fallback.
        """
        pdf_path = Path(pdf_path)
        log.info("Procesando: %s", pdf_path.name)

        # ── Fase 1: detección de tecnología ──────────────────────────────────
        tech = "Desconocido"
        if config.TECH_DETECTION_ENABLED:
            tech = detect_technology(pdf_path, self.client)
            log.info("[%s] Tecnología detectada: %s", pdf_path.name, tech)

        # ── Fase 2: seleccionar prompt y extraer ─────────────────────────────
        use_specific_prompt = tech != "Desconocido"
        scanned = detect_scanned(pdf_path)

        if use_specific_prompt:
            # Prompt específico: ya contiene variables y formato de salida
            prompt = get_prompt_for_technology(tech)
        else:
            # Fallback: prompt genérico construido dinámicamente
            prompt = build_prompt(variables, prompt_file=config.PROMPT_FILE)

        if scanned:
            log.info(
                "📷 %s detectado como escaneado → procesando por imágenes",
                pdf_path.name,
            )
            raw = self.client.generate_from_images(
                prompt=prompt,
                pdf_path=str(pdf_path),
                retries=self.max_retries,
                base_delay=self.retry_base_delay,
            )
        else:
            file_ref = self.client.upload_pdf(str(pdf_path))
            try:
                raw = self.client.generate(
                    prompt=prompt,
                    file_ref=file_ref,
                    retries=self.max_retries,
                    base_delay=self.retry_base_delay,
                )
            finally:
                self.client.delete_file(file_ref)

        # ── Validación ───────────────────────────────────────────────────────
        if use_specific_prompt:
            # Prompt específico: parsear JSON y validar con superset de claves
            from rca_extractor.utils.output_validator import extract_json_block, _try_parse

            block = extract_json_block(raw)
            data = _try_parse(block)
            if data is None:
                try:
                    from json_repair import repair_json

                    repaired = repair_json(block, return_objects=True)
                    data = repaired if isinstance(repaired, dict) else {}
                except Exception:
                    data = {}
            data = validate_output(data)
        else:
            # Fallback genérico: usar parse_and_validate con claves del Excel
            keys = expected_keys(variables)
            data = parse_and_validate(raw, keys)

        data["archivo"] = pdf_path.name
        data["escaneado"] = "sí" if scanned else "no"
        data["tecnologia_detectada"] = tech

        n_vars = len(data) - 3  # excluir archivo, escaneado, tecnologia_detectada
        log.info(
            "✓ %s → %d variables extraídas [%s]%s",
            pdf_path.name,
            n_vars,
            tech,
            " [escaneado]" if scanned else "",
        )
        return data
