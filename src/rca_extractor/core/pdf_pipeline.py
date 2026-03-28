"""
pdf_pipeline.py — Orquesta el procesamiento de un PDF individual.

Flujo:
  1. Detecta si el PDF es escaneado (sin texto extraíble).
  2a. PDF con texto   → sube a Gemini Files API → generate()
  2b. PDF escaneado   → convierte páginas a imágenes → generate_from_images()
  3. Valida y normaliza el JSON de salida.
  4. Siempre limpia el archivo de Gemini (solo para PDFs con texto).
"""

import logging
from pathlib import Path

from rca_extractor.core.gemini_client import GeminiClient
from rca_extractor.utils.prompt_builder import build_prompt, expected_keys
from rca_extractor.utils.output_validator import parse_and_validate
from rca_extractor.utils.pdf_utils import detect_scanned
from rca_extractor import config

log = logging.getLogger("rca_extractor")


class RCAExtractor:
    def __init__(
        self,
        model: str | None = None,
        temperature: float | None = None,
        max_retries: int | None = None,
        retry_base_delay: float | None = None,
    ):
        self.client = GeminiClient(
            api_key=config.GEMINI_API_KEY,
            model=model or config.GEMINI_MODEL,
            temperature=temperature if temperature is not None else config.TEMPERATURE,
        )
        self.max_retries      = max_retries or config.MAX_RETRIES
        self.retry_base_delay = retry_base_delay or config.RETRY_BASE_DELAY

    def process_pdf(self, pdf_path: str | Path, variables: list[dict]) -> dict:
        """
        Procesa un PDF y devuelve un dict con las variables extraídas.
        Detecta automáticamente si el PDF es escaneado y usa el método adecuado.
        """
        pdf_path = Path(pdf_path)
        log.info("Procesando: %s", pdf_path.name)

        prompt = build_prompt(variables, prompt_file=config.PROMPT_FILE)
        keys   = expected_keys(variables)

        scanned = detect_scanned(pdf_path)

        if scanned:
            log.info("📷 %s detectado como escaneado → procesando por imágenes", pdf_path.name)
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

        data = parse_and_validate(raw, keys)
        data["archivo"]   = pdf_path.name
        data["escaneado"] = "sí" if scanned else "no"
        log.info(
            "✓ %s → %d variables extraídas%s",
            pdf_path.name, len(data) - 2,
            " [escaneado]" if scanned else "",
        )
        return data
