"""
gemini_client.py — Cliente Gemini con backoff exponencial y limpieza garantizada.
Actualizado para usar SDK google-genai.
"""

import time
import logging
from google import genai
from google.genai import types

log = logging.getLogger("rca_extractor")


class GeminiClient:
    def __init__(self, api_key: str, model: str, temperature: float = 0):
        self.client = genai.Client(api_key=api_key)
        self.model_name = model
        self.temperature = temperature
        log.debug("GeminiClient inicializado con modelo: %s", model)

    # ── File management ───────────────────────────────────────────────────────

    def upload_pdf(self, path: str) -> types.File:
        """
        Sube el PDF a la Files API de Gemini y espera a que esté ACTIVE.
        El polling evita enviar la request de generación antes de que el
        archivo esté listo (error 'File is not ready').
        """
        log.debug("Subiendo archivo: %s", path)
        file_ref = self.client.files.upload(file=path, config={"mime_type": "application/pdf"})

        # Polling hasta que el archivo esté activo (máx. 60 s)
        for _ in range(20):
            file_ref = self.client.files.get(name=file_ref.name)
            if file_ref.state.name == "ACTIVE":
                break
            if file_ref.state.name == "FAILED":
                raise RuntimeError(f"El archivo {path} falló al procesarse en Gemini Files API.")
            time.sleep(3)
        else:
            raise TimeoutError(f"Timeout esperando ACTIVE en {path}")

        log.debug("Archivo activo: %s", file_ref.name)
        return file_ref

    def delete_file(self, file_ref) -> None:
        """Elimina el archivo de la Files API. Falla silenciosamente."""
        try:
            self.client.files.delete(name=file_ref.name)
            log.debug("Archivo eliminado: %s", file_ref.name)
        except Exception as exc:
            log.warning("No se pudo eliminar %s: %s", file_ref.name, exc)

    # ── Generación ────────────────────────────────────────────────────────────

    def generate(self, prompt: str, file_ref, retries: int = 4, base_delay: float = 2.0) -> str:
        """
        Envía el prompt + archivo a Gemini con backoff exponencial.
        Devuelve el texto de la respuesta o '{}' ante bloqueo de seguridad.
        """
        gen_config = types.GenerateContentConfig(
            temperature=self.temperature,
            response_mime_type="text/plain",
        )

        for attempt in range(retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=[file_ref, prompt],
                    config=gen_config,
                )
                try:
                    text = response.text
                    log.debug("Respuesta recibida (%d chars)", len(text))
                    return text
                except ValueError:
                    log.warning("Respuesta bloqueada por políticas de seguridad de Gemini.")
                    return "{}"

            except Exception as exc:
                wait = base_delay * (2 ** attempt)
                log.warning("Intento %d/%d fallido: %s. Reintentando en %.1fs…",
                             attempt + 1, retries, exc, wait)
                if attempt < retries - 1:
                    time.sleep(wait)

        raise RuntimeError(f"Gemini no respondió después de {retries} intentos.")
