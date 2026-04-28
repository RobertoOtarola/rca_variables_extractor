"""
gemini_client.py — Cliente Gemini con backoff inteligente y limpieza garantizada.
Actualizado para usar SDK google-genai.
"""

import re
import time
import random
import logging
from google import genai
from google.genai import types

log = logging.getLogger("rca_extractor")

# ── Clasificación de errores ──────────────────────────────────────────────────
_QUOTA_CODES = {"429", "RESOURCE_EXHAUSTED"}
_TRANSIENT_CODES = {"500", "502", "503", "INTERNAL", "UNAVAILABLE"}
_FATAL_CODES = {
    "400",
    "401",
    "403",
    "404",
    "INVALID_ARGUMENT",
    "PERMISSION_DENIED",
    "UNAUTHENTICATED",
    "NOT_FOUND",
}

# Tiempos de espera
_QUOTA_MIN_WAIT = 65.0  # piso para 429
_QUOTA_MAX_WAIT = 600.0  # techo: 10 minutos
_TRANSIENT_MIN_WAIT = 60.0  # piso para 5xx (subido de 30s para dar más aire)
_TRANSIENT_MAX_WAIT = 300.0  # techo: 5 minutos


def _classify_error(exc_str: str) -> str:
    """
    Clasifica el error en:
      'quota'     → 429 / RESOURCE_EXHAUSTED  (backoff largo)
      'transient' → 5xx / UNAVAILABLE         (backoff corto)
      'fatal'     → 400 / 404 / etc.          (falla inmediata)
    """
    for code in _QUOTA_CODES:
        if code in exc_str:
            return "quota"
    for code in _FATAL_CODES:
        if code in exc_str:
            return "fatal"
    for code in _TRANSIENT_CODES:
        if code in exc_str:
            return "transient"
    return "transient"  # default conservador


def _compute_wait(
    kind: str, attempt: int, exc_str: str, base_delay: float = 65.0, max_backoff: float = 300.0
) -> float:
    """Calcula el tiempo de espera con backoff + jitter según el tipo de error."""
    if kind == "quota":
        # Usamos el base_delay (ej. 65s) como piso para 429
        wait = min(base_delay * (2**attempt), max_backoff)
    else:
        # Para 5xx usamos un backoff más corto (piso 30s o 60s según la versión)
        wait = min(_TRANSIENT_MIN_WAIT * (2**attempt), max_backoff)

    # Si la API indica un tiempo concreto, respetarlo (+ 2 s margen)
    match = re.search(r"Please retry in (\d+(?:\.\d+)?)s", exc_str)
    if match:
        wait = max(wait, float(match.group(1)) + 2.0)

    # Jitter ±10 %
    wait *= random.uniform(0.90, 1.10)
    return max(1.0, wait)


def _short_err(exc_str: str) -> str:
    """Limpia el mensaje de error eliminando el bloque JSON gigante."""
    if " {'error':" in exc_str:
        return exc_str.split(" {'error':")[0]
    return exc_str.split("\n")[0]


class GeminiClient:
    def __init__(self, api_key: str, model: str, temperature: float = 0, max_backoff: float = 300.0):
        self.client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=300)  # 300s (5 minutos)
        )
        self.model_name = model
        self.temperature = temperature
        self.max_backoff = max_backoff
        log.debug("GeminiClient inicializado con modelo: %s (max_backoff: %.1fs)", model, max_backoff)

    # ── File management ───────────────────────────────────────────────────────

    def upload_pdf(self, path: str) -> types.File:
        """Sube el PDF a la Files API de Gemini y espera a que esté ACTIVE."""
        log.debug("Subiendo archivo: %s", path)
        file_ref = self.client.files.upload(file=path, config={"mime_type": "application/pdf"})  # type: ignore

        if not file_ref.name:
            raise RuntimeError("Gemini no devolvió un nombre de archivo.")

        for _ in range(20):
            file_ref = self.client.files.get(name=file_ref.name)
            if file_ref.state and file_ref.state.name == "ACTIVE":
                break
            if file_ref.state and file_ref.state.name == "FAILED":
                raise RuntimeError(f"El archivo {path} falló al procesarse en Gemini Files API.")
            time.sleep(3)
        else:
            raise TimeoutError(f"Timeout esperando ACTIVE en {path}")

        log.debug("Archivo activo: %s", file_ref.name)
        return file_ref

    def delete_file(self, file_ref: types.File) -> None:
        """Elimina el archivo de la Files API. Falla silenciosamente."""
        if not file_ref.name:
            return
        try:
            self.client.files.delete(name=file_ref.name)
            log.debug("Archivo eliminado: %s", file_ref.name)
        except Exception as exc:
            log.warning("No se pudo eliminar %s: %s", file_ref.name, exc)

    # ── Generación (PDFs con texto) ───────────────────────────────────────────

    def generate(self, prompt: str, file_ref: types.File, retries: int = 8, base_delay: float = 65.0) -> str:
        """
        Envía el prompt + archivo a Gemini con backoff inteligente por tipo de error.

          - fatal (400/401/403/404): falla inmediata, sin reintentos.
          - quota (429):             backoff largo [65s, 300s].
          - transient (5xx):         backoff corto [2s, 60s].
        """
        gen_config = types.GenerateContentConfig(
            temperature=self.temperature,  # type: ignore
            response_mime_type="text/plain",  # type: ignore
        )

        if not file_ref.uri:
            raise RuntimeError("Gemini no devolvió un URI válido.")

        pdf_part = types.Part.from_uri(
            file_uri=file_ref.uri,  # type: ignore
            mime_type="application/pdf",  # type: ignore
        )
        
        contents_list: list[types.Part | str] = [pdf_part, prompt]

        for attempt in range(retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=contents_list,  # type: ignore
                    config=gen_config,
                )
                try:
                    text = response.text or ""
                    log.debug("Respuesta recibida (%d chars)", len(text))
                    return text
                except ValueError:
                    log.warning("Respuesta bloqueada por políticas de seguridad de Gemini.")
                    return "{}"

            except Exception as exc:
                exc_str = str(exc)
                kind = _classify_error(exc_str)
                err = _short_err(exc_str)

                if kind == "fatal":
                    log.error("Error fatal (sin reintentos): %s", err)
                    raise RuntimeError(f"Error fatal de Gemini: {err}")

                wait = _compute_wait(
                    kind, attempt, exc_str, base_delay=base_delay, max_backoff=self.max_backoff
                )
                log.warning(
                    "Intento %d/%d fallido [%s]: %s. Reintentando en %.1fs…",
                    attempt + 1,
                    retries,
                    kind,
                    err,
                    wait,
                )
                if attempt < retries - 1:
                    time.sleep(wait)

        raise RuntimeError(f"Gemini no respondió después de {retries} intentos.")

    # ── Generación (PDFs escaneados → imágenes) ───────────────────────────────

    def generate_from_images(
        self, prompt: str, images: list[bytes], retries: int = 8, base_delay: float = 65.0
    ) -> str:
        """
        Envía las imágenes (ya extraídas del PDF) a Gemini.
        Usado para PDFs escaneados sin capa de texto o para detección.
        """
        image_parts = [
            types.Part.from_bytes(data=img, mime_type="image/png") for img in images
        ]
        log.debug("Enviando %d imágenes a Gemini", len(image_parts))

        gen_config = types.GenerateContentConfig(
            temperature=self.temperature,  # type: ignore
            response_mime_type="text/plain",  # type: ignore
        )

        contents_list: list[types.Part | str] = [*image_parts, prompt]

        for attempt in range(retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=contents_list,  # type: ignore
                    config=gen_config,
                )
                try:
                    text = response.text or ""
                    log.debug("Respuesta recibida (%d chars)", len(text))
                    return text
                except ValueError:
                    log.warning("Respuesta bloqueada por políticas de seguridad de Gemini.")
                    return "{}"

            except Exception as exc:
                exc_str = str(exc)
                kind = _classify_error(exc_str)
                err = _short_err(exc_str)

                if kind == "fatal":
                    log.error("Error fatal (sin reintentos): %s", err)
                    raise RuntimeError(f"Error fatal de Gemini: {err}")

                wait = _compute_wait(
                    kind, attempt, exc_str, base_delay=base_delay, max_backoff=self.max_backoff
                )
                log.warning(
                    "Intento %d/%d fallido [%s]: %s. Reintentando en %.1fs…",
                    attempt + 1,
                    retries,
                    kind,
                    err,
                    wait,
                )
                if attempt < retries - 1:
                    time.sleep(wait)

        raise RuntimeError(f"Gemini no respondió después de {retries} intentos.")
