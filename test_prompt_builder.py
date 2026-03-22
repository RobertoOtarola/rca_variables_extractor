"""
test_prompt_builder.py — Verifica el pipeline de prompt y validación
sin necesitar la API key de Gemini.

Uso:
    python test_prompt_builder.py
"""

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))

import os
os.environ.setdefault("GEMINI_API_KEY", "dummy")   # evita el ValueError de config

from prompt_builder import load_variables, build_prompt, expected_keys, _to_snake_key
from output_validator import parse_and_validate

# ── Test 1: normalización de claves ──────────────────────────────────────────
print("── Test 1: snake_key ─────────────────────────────────────────────")
casos = [
    ("Potencia nominal bruta (MW)",          "potencia_nominal_bruta_mw"),
    ("Coordenadas UTM/Geográficas (polígono)", "coordenadas_utm_geograficas_poligono"),
    ("Región, provincia y comuna",            "region_provincia_y_comuna"),
    ("Emisiones GEI embebidas (kg CO2-eq kWh-1)", "emisiones_gei_embebidas_kg_co2_eq_kwh_1"),
]
all_ok = True
for label, expected in casos:
    got = _to_snake_key(label)
    status = "✓" if got == expected else f"✗ esperado '{expected}'"
    print(f"  {status}  '{label}' → '{got}'")
    if got != expected:
        all_ok = False

# ── Test 2: carga de variables desde Excel real ───────────────────────────────
print("\n── Test 2: carga de variables ────────────────────────────────────")
try:
    vars_ = load_variables("seia-variables.xlsx")
    print(f"  ✓ {len(vars_)} variables cargadas")
    for v in vars_[:3]:
        print(f"     label='{v['label']}'  key='{v['key']}'")
    print("     ...")
except FileNotFoundError:
    print("  ⚠ seia-variables.xlsx no encontrado — colócalo en la raíz del proyecto")
    vars_ = [
        {"label": "Potencia nominal bruta (MW)", "key": "potencia_nominal_bruta_mw"},
        {"label": "Vida útil (años)",             "key": "vida_util_anos"},
        {"label": "Región, provincia y comuna",   "key": "region_provincia_y_comuna"},
    ]
    print(f"  Usando {len(vars_)} variables de ejemplo para continuar tests.")

# ── Test 3: construcción de prompt ────────────────────────────────────────────
print("\n── Test 3: build_prompt ──────────────────────────────────────────")
prompt = build_prompt(vars_[:3])
print(f"  Longitud del prompt: {len(prompt)} chars")
for key in expected_keys(vars_[:3]):
    assert key in prompt, f"Clave '{key}' no encontrada en el prompt"
print("  ✓ Todas las claves están en el prompt")

# ── Test 4: parse_and_validate ────────────────────────────────────────────────
print("\n── Test 4: output_validator ──────────────────────────────────────")

keys = expected_keys(vars_[:3])

# Caso A: JSON limpio
raw_a = '{"potencia_nominal_bruta_mw": "489 MWp", "vida_util_anos": "33.5", "region_provincia_y_comuna": "Antofagasta"}'
res_a = parse_and_validate(raw_a, keys)
assert res_a["potencia_nominal_bruta_mw"] == "489 MWp"
print("  ✓ JSON limpio parseado correctamente")

# Caso B: JSON envuelto en markdown
raw_b = '```json\n{"potencia_nominal_bruta_mw": "100 MW"}\n```'
res_b = parse_and_validate(raw_b, keys)
assert res_b["potencia_nominal_bruta_mw"] == "100 MW"
# Las demás claves del subset deben rellenarse con N/A
missing_keys = [k for k in keys if k != "potencia_nominal_bruta_mw"]
assert all(res_b[k] == "N/A" for k in missing_keys)
print("  ✓ JSON en markdown extraído + claves faltantes → N/A")

# Caso C: JSON completamente inválido
raw_c = "Lo siento, no pude extraer la información."
res_c = parse_and_validate(raw_c, keys)
assert all(v == "N/A" for v in res_c.values())
print("  ✓ Respuesta inválida → todas las claves devuelven N/A")

# Caso D: Claves inesperadas (ignoradas)
raw_d = '{"potencia_nominal_bruta_mw": "50 MW", "clave_inventada": "valor"}'
res_d = parse_and_validate(raw_d, keys)
assert "clave_inventada" not in res_d
print("  ✓ Claves inesperadas ignoradas correctamente")

print("\n✅ Todos los tests pasaron.")
