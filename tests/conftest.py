"""
conftest.py — Configuración compartida para todos los tests.

Inyecta GEMINI_API_KEY=dummy antes de que config.py la valide,
permitiendo ejecutar tests unitarios sin credenciales reales.
"""

import os
import pytest

# Se setea ANTES de cualquier import de config.py
os.environ.setdefault("GEMINI_API_KEY", "dummy-key-for-tests")
