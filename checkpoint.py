"""
checkpoint.py — Persiste el estado de procesamiento entre ejecuciones.

Permite reanudar un batch sin reprocesar PDFs ya completados.
El archivo de checkpoint es un JSON con la forma:
  { "rca_001.pdf": {"status": "ok", "ts": "2024-01-01T10:00:00"},
    "rca_002.pdf": {"status": "error", "msg": "...", "ts": "..."},
    ... }
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("rca_extractor")


class Checkpoint:
    STATUS_OK    = "ok"
    STATUS_ERROR = "error"

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict = self._load()

    # ── I/O ──────────────────────────────────────────────────────────────────
    def _load(self) -> dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                log.warning("Checkpoint corrupto, se reinicia: %s", exc)
        return {}

    def _save(self) -> None:
        self.path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ── API pública ───────────────────────────────────────────────────────────
    def is_done(self, filename: str) -> bool:
        """Devuelve True si el PDF ya fue procesado con éxito."""
        entry = self._data.get(filename, {})
        return entry.get("status") == self.STATUS_OK

    def mark_ok(self, filename: str) -> None:
        self._data[filename] = {
            "status": self.STATUS_OK,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        self._save()

    def mark_error(self, filename: str, msg: str) -> None:
        self._data[filename] = {
            "status": self.STATUS_ERROR,
            "msg": str(msg),
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        self._save()

    def pending(self, all_files: list[Path]) -> list[Path]:
        """Filtra la lista devolviendo sólo los PDFs pendientes."""
        return [f for f in all_files if not self.is_done(f.name)]

    def summary(self) -> dict:
        ok    = sum(1 for v in self._data.values() if v["status"] == self.STATUS_OK)
        error = sum(1 for v in self._data.values() if v["status"] == self.STATUS_ERROR)
        return {"total": len(self._data), "ok": ok, "error": error}
