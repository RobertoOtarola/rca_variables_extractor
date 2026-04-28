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
from rca_extractor.utils.prompt_builder import get_prompt_for_technology
from rca_extractor.utils.output_validator import parse_json_response
from rca_extractor.utils.pdf_utils import detect_scanned, pdf_to_images
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
        max_backoff: float | None = None,
        detect_retries: int = 3,
    ) -> None:
        self.client = GeminiClient(
            api_key=config.GEMINI_API_KEY,
            model=model or config.GEMINI_MODEL,
            temperature=temperature if temperature is not None else config.TEMPERATURE,
            max_backoff=max_backoff or config.MAX_BACKOFF,
        )
        self.max_retries = max_retries or config.MAX_RETRIES
        self.retry_base_delay = retry_base_delay or config.RETRY_BASE_DELAY
        self.detect_retries = detect_retries

    def process_pdf(self, pdf_path: str | Path, variables: list[dict]) -> dict:
        """
        Procesa un PDF y devuelve un dict con las variables extraídas.
        Sigue el flujo de detección de tecnología y uso de prompts específicos.
        """
        pdf_path = Path(pdf_path)
        is_scanned = detect_scanned(pdf_path)

        # Subir el PDF UNA sola vez (solo si no es escaneado)
        file_ref = None
        if not is_scanned:
            file_ref = self.client.upload_pdf(str(pdf_path))
        
        try:
            # Fase 1: detectar tecnología
            tech = self._detect_tech(file_ref, pdf_path, is_scanned)
            log.info("[%s] Tecnología detectada: %s", pdf_path.name, tech)

            # Fase 2: prompt específico — NO inyectar variables externas
            prompt = get_prompt_for_technology(tech)
            # ↑ el prompt ya contiene el JSON de salida y todas las reglas

            if is_scanned:
                response = self._extract_from_images(pdf_path, prompt)
            else:
                assert file_ref is not None
                response = self.client.generate(
                    prompt=prompt,
                    file_ref=file_ref,
                    retries=self.max_retries,
                    base_delay=self.retry_base_delay,
                )
        finally:
            if file_ref:
                self.client.delete_file(file_ref)

        data = parse_json_response(response)
        data["archivo"] = pdf_path.name
        data["escaneado"] = "sí" if is_scanned else "no"
        data["tecnologia_detectada"] = tech
        
        # Metadata de versionado
        tech_key = tech.lower().replace(" ", "_").replace("+", "y")
        data["prompt_version"] = f"v2_{tech_key}" if tech != "Desconocido" else "v1_generic"
        
        return data

    def _detect_tech(self, file_ref, pdf_path: Path, is_scanned: bool) -> str:
        """Helper para detección de tecnología."""
        if not config.TECH_DETECTION_ENABLED:
            return "Desconocido"
            
        images = None
        if is_scanned:
            images = pdf_to_images(pdf_path)[:3]  # solo primeras 3 paginas para detección
            
        return detect_technology(
            self.client,
            pdf_path.name,
            file_ref=file_ref,
            images=images,
            retries=self.detect_retries,
            base_delay=self.retry_base_delay
        )

    def _extract_from_images(self, pdf_path: Path, prompt: str) -> str:
        """Helper para extracción desde imágenes (PDFs escaneados)."""
        images = pdf_to_images(pdf_path)
        return self.client.generate_from_images(
            prompt=prompt,
            images=images,
            retries=self.max_retries,
            base_delay=self.retry_base_delay,
        )
