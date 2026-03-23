# Walkthrough — Revisión y Mejora del Repositorio

## Resumen

Se revisaron los **21 archivos** del repo y se aplicaron **13 cambios** organizados en 6 áreas.

## Cambios Realizados

### 🔴 Seguridad
- **[.env](file:///Users/roberto/Documents/1%20Projects/CEDEUS%20UC/Code/DB/rca_variables_extractor/.env)**: Limpiado, agregada advertencia para rotar API key expuesta

### 🟡 Corrección de Bugs

- **[gemini_client.py](file:///Users/roberto/Documents/1%20Projects/CEDEUS%20UC/Code/DB/rca_variables_extractor/gemini_client.py)**: Backoff para errores non-429 cambiado de 65s base a 2s base (máx 60s)

```diff:gemini_client.py
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

# Tiempo mínimo de espera cuando la API responde con 429 / RESOURCE_EXHAUSTED.
# gemini-2.0-flash free tier tiene límite de ~15 RPM → ventana de 60 s.
_QUOTA_MIN_WAIT = 65.0   # segundos
_QUOTA_MAX_WAIT = 600.0  # techo: 10 minutos


def _is_quota_error(exc_str: str) -> bool:
    """Devuelve True si el error es un 429 o RESOURCE_EXHAUSTED."""
    return "429" in exc_str or "RESOURCE_EXHAUSTED" in exc_str


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

    def generate(self, prompt: str, file_ref, retries: int = 8, base_delay: float = 65.0) -> str:
        """
        Envía el prompt + archivo a Gemini con backoff exponencial consciente de cuotas.

        Para errores 429 / RESOURCE_EXHAUSTED la espera mínima es _QUOTA_MIN_WAIT (65 s)
        porque el free tier de gemini-2.0-flash tiene un límite de ~15 RPM.
        Si la API incluye "Please retry in Xs" se respeta ese valor cuando supera
        el mínimo calculado.

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
                exc_str = str(exc)

                # ── Calcular tiempo de espera ──────────────────────────────
                if _is_quota_error(exc_str):
                    # Backoff exponencial con piso de _QUOTA_MIN_WAIT
                    wait = min(_QUOTA_MIN_WAIT * (2 ** attempt), _QUOTA_MAX_WAIT)
                else:
                    # Otros errores: backoff suave (2, 4, 8, 16 … s)
                    wait = base_delay * (2 ** attempt)

                # Si la API indica un tiempo concreto, respetarlo (+ 2 s de margen)
                match = re.search(r"Please retry in (\d+(?:\.\d+)?)s", exc_str)
                if match:
                    api_wait = float(match.group(1)) + 2.0
                    wait = max(wait, api_wait)

                # Jitter ±10 % para evitar thundering herd con múltiples workers
                wait += random.uniform(-wait * 0.10, wait * 0.10)
                wait = max(1.0, wait)  # nunca menos de 1 s

                # ── Log limpio (sin el bloque JSON gigante del error) ──────
                short_err = exc_str.split(" {'error':")[0] if " {'error':" in exc_str else exc_str.split("\n")[0]

                log.warning(
                    "Intento %d/%d fallido: %s. Reintentando en %.1fs…",
                    attempt + 1, retries, short_err, wait,
                )
                if attempt < retries - 1:
                    time.sleep(wait)

        raise RuntimeError(f"Gemini no respondió después de {retries} intentos.")
===
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

# Tiempo mínimo de espera cuando la API responde con 429 / RESOURCE_EXHAUSTED.
# gemini-2.0-flash free tier tiene límite de ~15 RPM → ventana de 60 s.
_QUOTA_MIN_WAIT = 65.0   # segundos
_QUOTA_MAX_WAIT = 600.0  # techo: 10 minutos


def _is_quota_error(exc_str: str) -> bool:
    """Devuelve True si el error es un 429 o RESOURCE_EXHAUSTED."""
    return "429" in exc_str or "RESOURCE_EXHAUSTED" in exc_str


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

    def generate(self, prompt: str, file_ref, retries: int = 8, base_delay: float = 65.0) -> str:
        """
        Envía el prompt + archivo a Gemini con backoff exponencial consciente de cuotas.

        Para errores 429 / RESOURCE_EXHAUSTED la espera mínima es _QUOTA_MIN_WAIT (65 s)
        porque el free tier de gemini-2.0-flash tiene un límite de ~15 RPM.
        Si la API incluye "Please retry in Xs" se respeta ese valor cuando supera
        el mínimo calculado.

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
                exc_str = str(exc)

                # ── Calcular tiempo de espera ──────────────────────────────
                if _is_quota_error(exc_str):
                    # Backoff exponencial con piso de _QUOTA_MIN_WAIT
                    wait = min(_QUOTA_MIN_WAIT * (2 ** attempt), _QUOTA_MAX_WAIT)
                else:
                    # Otros errores: backoff suave (2, 4, 8, 16 … s) — máx 60 s
                    wait = min(2.0 * (2 ** attempt), 60.0)

                # Si la API indica un tiempo concreto, respetarlo (+ 2 s de margen)
                match = re.search(r"Please retry in (\d+(?:\.\d+)?)s", exc_str)
                if match:
                    api_wait = float(match.group(1)) + 2.0
                    wait = max(wait, api_wait)

                # Jitter ±10 % para evitar thundering herd con múltiples workers
                wait += random.uniform(-wait * 0.10, wait * 0.10)
                wait = max(1.0, wait)  # nunca menos de 1 s

                # ── Log limpio (sin el bloque JSON gigante del error) ──────
                short_err = exc_str.split(" {'error':")[0] if " {'error':" in exc_str else exc_str.split("\n")[0]

                log.warning(
                    "Intento %d/%d fallido: %s. Reintentando en %.1fs…",
                    attempt + 1, retries, short_err, wait,
                )
                if attempt < retries - 1:
                    time.sleep(wait)

        raise RuntimeError(f"Gemini no respondió después de {retries} intentos.")
```

- **[prompt_builder.py](file:///Users/roberto/Documents/1%20Projects/CEDEUS%20UC/Code/DB/rca_variables_extractor/prompt_builder.py)**: Docstring corregido `zero_shot_prompt.md` → [extraction_prompt.md](file:///Users/roberto/Documents/1%20Projects/CEDEUS%20UC/Code/DB/rca_variables_extractor/prompts/extraction_prompt.md)

### ⚙️ Configuración
- **[.env.example](file:///Users/roberto/Documents/1%20Projects/CEDEUS%20UC/Code/DB/rca_variables_extractor/.env.example)**: Sincronizado con valores reales de [config.py](file:///Users/roberto/Documents/1%20Projects/CEDEUS%20UC/Code/DB/rca_variables_extractor/config.py) (`MAX_RETRIES=8`, `RETRY_BASE_DELAY=65.0`, `INTER_PDF_COOLDOWN=15`)

### 📦 Dependencias
- **[requirements.txt](file:///Users/roberto/Documents/1%20Projects/CEDEUS%20UC/Code/DB/rca_variables_extractor/requirements.txt)**: Eliminada `tenacity` (no se usa en el proyecto)

### 🧪 Tests
| Archivo | Descripción |
|---------|-------------|
| [tests/conftest.py](file:///Users/roberto/Documents/1%20Projects/CEDEUS%20UC/Code/DB/rca_variables_extractor/tests/conftest.py) | Inyecta `GEMINI_API_KEY=dummy` |
| [tests/test_prompt_builder.py](file:///Users/roberto/Documents/1%20Projects/CEDEUS%20UC/Code/DB/rca_variables_extractor/tests/test_prompt_builder.py) | 10 tests (snake_key, load_variables, build_prompt, parse_and_validate) |
| [tests/test_output_validator.py](file:///Users/roberto/Documents/1%20Projects/CEDEUS%20UC/Code/DB/rca_variables_extractor/tests/test_output_validator.py) | 12 tests (extract_json_block edge cases, normalization) |
| [tests/test_checkpoint.py](file:///Users/roberto/Documents/1%20Projects/CEDEUS%20UC/Code/DB/rca_variables_extractor/tests/test_checkpoint.py) | 7 tests (mark_ok/error, pending, persistence, corruption) |
| ~~[test_prompt_builder.py](file:///Users/roberto/Documents/1%20Projects/CEDEUS%20UC/Code/DB/rca_variables_extractor/test_prompt_builder.py)~~ | Eliminado de la raíz |

**Resultado: 34/34 tests pasaron ✅**

### 📝 Documentación
- **[README.md](file:///Users/roberto/Documents/1%20Projects/CEDEUS%20UC/Code/DB/rca_variables_extractor/README.md)**: Separado implementado vs planificado, corregido stack tecnológico, arregladas referencias a archivos

### 🧹 Limpieza
- Creado [tools/__init__.py](file:///Users/roberto/Documents/1%20Projects/CEDEUS%20UC/Code/DB/rca_variables_extractor/tools/__init__.py)
- Eliminado `__pycache__/` y [dashboard/.DS_Store](file:///Users/roberto/Documents/1%20Projects/CEDEUS%20UC/Code/DB/rca_variables_extractor/dashboard/.DS_Store)

## Acción Manual Pendiente

> [!CAUTION]
> **Rotar la API key** de Gemini en [Google AI Studio](https://aistudio.google.com/) si fue commiteada en Git en algún momento. Verificar con `git log -p -- .env`.
