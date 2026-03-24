"""
gemini_client.py — Cliente Gemini con backoff exponencial y limpieza garantizada.
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

# Errores de cuota/rate-limit: merecen backoff largo y muchos reintentos
_QUOTA_CODES    = {"429", "RESOURCE_EXHAUSTED"}
# Errores de servidor: merecen backoff corto y pocos reintentos
_TRANSIENT_CODES = {"500", "502", "503", "INTERNAL", "UNAVAILABLE"}
# Errores del request: falla inmediata, nunca se recuperan con tiempo
_FATAL_CODES    = {"400", "401", "403", "404",
                   "INVALID_ARGUMENT", "PERMISSION_DENIED",
                   "UNAUTHENTICATED", "NOT_FOUND"}

# Tiempos de espera
_QUOTA_MIN_WAIT     = 65.0   # segundos — piso para 429 (billing: ~60 RPM)
_QUOTA_MAX_WAIT     = 300.0  # techo: 5 minutos
_TRANSIENT_MIN_WAIT =  2.0   # segundos — piso para 5xx
_TRANSIENT_MAX_WAIT = 60.0   # techo: 1 minuto


def _classify_error(exc_str: str) -> str:
    """
    Clasifica el error en una de tres categorías:
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
    return "transient"   # default conservador: reintenta con backoff corto


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
        """
        log.debug("Subiendo archivo: %s", path)
        file_ref = self.client.files.upload(
            file=path, config={"mime_type": "application/pdf"}
        )

        # Polling hasta ACTIVE (máx. 60 s)
        for _ in range(20):
            file_ref = self.client.files.get(name=file_ref.name)
            if file_ref.state.name == "ACTIVE":
                break
            if file_ref.state.name == "FAILED":
                raise RuntimeError(
                    f"El archivo {path} falló al procesarse en Gemini Files API."
                )
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

    def generate(self, prompt: str, file_ref, retries: int = 8, base_delay: float = 65.0) -> str:
        """
        Envía el prompt + archivo a Gemini con backoff inteligente por tipo de error:

          - fatal (400/401/403/404): falla inmediata, sin reintentos.
          - quota (429):             backoff largo [65s, 300s] con jitter.
          - transient (5xx):         backoff corto [2s, 60s] con jitter.

        Devuelve el texto o '{}' si la respuesta está bloqueada por seguridad.
        """
        gen_config = types.GenerateContentConfig(
            temperature=self.temperature,
            response_mime_type="text/plain",
        )

        pdf_part = types.Part.from_uri(
            file_uri=file_ref.uri,
            mime_type="application/pdf",
        )

        for attempt in range(retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=[pdf_part, prompt],
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
                exc_str = str(exc)
                kind    = _classify_error(exc_str)
                short_err = (
                    exc_str.split(" {'error':")[0]
                    if " {'error':" in exc_str
                    else exc_str.split("\n")[0]
                )

                # ── Errores fatales: falla inmediata ───────────────────────
                if kind == "fatal":
                    log.error(
                        "Error fatal (sin reintentos): %s", short_err
                    )
                    raise RuntimeError(f"Error fatal de Gemini: {short_err}")

                # ── Calcular tiempo de espera ──────────────────────────────
                if kind == "quota":
                    wait = min(_QUOTA_MIN_WAIT * (2 ** attempt), _QUOTA_MAX_WAIT)
                else:  # transient
                    wait = min(_TRANSIENT_MIN_WAIT * (2 ** attempt), _TRANSIENT_MAX_WAIT)

                # Si la API indica un tiempo concreto, respetarlo (+ 2 s margen)
                match = re.search(r"Please retry in (\d+(?:\.\d+)?)s", exc_str)
                if match:
                    wait = max(wait, float(match.group(1)) + 2.0)

                # Jitter ±10 % para evitar thundering herd
                wait *= random.uniform(0.90, 1.10)
                wait  = max(1.0, wait)

                log.warning(
                    "Intento %d/%d fallido [%s]: %s. Reintentando en %.1fs…",
                    attempt + 1, retries, kind, short_err, wait,
                )
                if attempt < retries - 1:
                    time.sleep(wait)

        raise RuntimeError(f"Gemini no respondió después de {retries} intentos.")
