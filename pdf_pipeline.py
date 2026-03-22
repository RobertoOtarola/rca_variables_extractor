"""
pdf_pipeline.py — Orquesta el procesamiento de un PDF individual.

Flujo:
  1. Sube el PDF a Gemini Files API.
  2. Construye el prompt con las variables.
  3. Genera la respuesta.
  4. Valida y normaliza el JSON de salida.
  5. Siempre limpia el archivo de Gemini (try/finally).
"""

import logging
from pathlib import Path

from gemini_client import GeminiClient
from prompt_builder import build_prompt, expected_keys
from output_validator import parse_and_validate
import config

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
            model=model or config.MODEL_NAME,
            temperature=temperature if temperature is not None else config.TEMPERATURE,
        )
        self.max_retries = max_retries or config.MAX_RETRIES
        self.retry_base_delay = retry_base_delay or config.RETRY_BASE_DELAY

    def process_pdf(self, pdf_path: str | Path, variables: list[dict]) -> dict:
        """
        Procesa un PDF y devuelve un dict con las variables extraídas.
        Agrega la clave 'archivo' con el nombre del PDF.
        Garantiza la eliminación del archivo en Gemini.
        """
        pdf_path = Path(pdf_path)
        log.info("Procesando: %s", pdf_path.name)

        prompt = build_prompt(variables, prompt_file=config.PROMPT_FILE)
        keys   = expected_keys(variables)

        file_ref = self.client.upload_pdf(str(pdf_path))

        try:
            raw = self.client.generate(
                prompt=prompt,
                file_ref=file_ref,
                retries=self.max_retries,
                base_delay=self.retry_base_delay,
            )
            data = parse_and_validate(raw, keys)
            data["archivo"] = pdf_path.name
            log.info("✓ %s → %d variables extraídas", pdf_path.name, len(data) - 1)
            return data

        finally:
            self.client.delete_file(file_ref)
