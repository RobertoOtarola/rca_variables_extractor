"""
geo/coord_parser.py — Parsea coordenadas UTM desde texto libre de RCAs chilenas.

Versión 2 — fixes aplicados:
  - Sufijo " m" / " m," / "mE" / "mS" después de números (#fix-m-suffix)
  - Separador "y" en español entre Este y Norte (#fix-separador-y)
  - Formato E_339.945/N_6.343.851 con underscore (#fix-underscore)
  - Advertencia cuando el datum no es WGS84 (#fix-datum-warning)
"""

import re
import logging
from dataclasses import dataclass
from typing import Optional

import pyproj

log = logging.getLogger("rca_extractor")

ESTE_MIN, ESTE_MAX = 200_000, 920_000
NORTE_MIN, NORTE_MAX = 5_400_000, 8_300_000

ZONE_HINTS = {"18": 18, "18s": 18, "18h": 18, "19": 19, "19s": 19, "19h": 19}

# Datums no-WGS84 presentes en RCAs antiguas chilenas
# PSAD56 (EPSG:24879) es el más común — diferencia máx ~200m con WGS84 en Chile
_NON_WGS84_RE = re.compile(r"PSAD|Provisorio\s+Sudamericano|SAD\s*56|SAD\s*69|Chile\s*\d{4}", re.I)


@dataclass
class UTMPoint:
    easting: float
    northing: float
    zone: int
    lon: float
    lat: float
    method: str
    datum_warning: str = ""  # vacío si WGS84, mensaje si otro datum


def _clean_num(s: str) -> float:
    """
    Convierte string numérico de PDFs chilenos a float.
    Punto = separador de miles, coma = decimal.
    '6.535.968' → 6535968.0  |  '6.245,56' → 6245.56  |  '303574.3' → 303574.3
    """
    s = s.strip()
    if "," in s:
        return float(s.replace(".", "").replace(",", "."))
    dot_count = s.count(".")
    if dot_count == 0:
        return float(s)
    if dot_count >= 2:
        parts = s.split(".")
        if len(parts[-1]) == 2:
            return float("".join(parts[:-1]) + "." + parts[-1])
        return float(s.replace(".", ""))
    # Un solo punto
    parts = s.split(".")
    if len(parts[1]) == 3:  # "406.871" → 406871
        return float(s.replace(".", ""))
    return float(s)  # "303574.3" → 303574.3


def _detect_zone(text: str) -> int:
    m = re.search(r"[Hh]uso\s*(\d{2})|UTM\s*(\d{2})|(\d{2})[Ss]\b", text)
    if m:
        z = next(g for g in m.groups() if g)
        return ZONE_HINTS.get(z.lower(), 19)
    if re.search(r"\b18[SsHh]?\b", text):
        return 18
    return 19


def _to_wgs84(e: float, n: float, zone: int) -> tuple[float, float]:
    t = pyproj.Transformer.from_crs(f"EPSG:{32700 + zone}", "EPSG:4326", always_xy=True)
    return t.transform(e, n)


def _valid(e: float, n: float) -> bool:
    return (ESTE_MIN <= e <= ESTE_MAX) and (NORTE_MIN <= n <= NORTE_MAX)


def _try(a: float, b: float, a_is_este: bool) -> Optional[tuple[float, float]]:
    e, n = (a, b) if a_is_este else (b, a)
    if _valid(e, n):
        return e, n
    if _valid(b, a):
        return b, a
    return None


# ── Grupos de regex ───────────────────────────────────────────────────────────
_N = r"([\d]+(?:[.,]\d+)*)"  # número UTM
_MS = r"(?:\s*m[EeSsNn]?\b)?"  # sufijo opcional: "m", "mE", "mS", "m N"
_SEP = r"[\s,;/y]+"  # separadores incluyendo "y" español
_NR = r"(?:[Nn]orte|[Ss]ur|[Nn])"  # Norte / Sur / N

PATTERNS = [
    # ── Con etiqueta prefijo ──────────────────────────────────────────────────
    # "Este 327000 m, Norte 6284733 m" / "Este: 289.460 y Norte: 6.235.578"
    (
        "este_norte",
        True,
        re.compile(r"[Ee]ste[\s:_(mM)]+?" + _N + _MS + _SEP + _NR + r"[\s:_(mM)]+?" + _N, re.I),
    ),
    (
        "norte_este",
        False,
        re.compile(_NR + r"[\s:_(mM)]+?" + _N + _MS + _SEP + r"[Ee]ste[\s:_(mM)]+?" + _N, re.I),
    ),
    # "328.998 m Este y 6.263.697 m Norte" (número → etiqueta)
    (
        "numEste",
        True,
        re.compile(_N + _MS + r"\s+[Ee]ste" + _SEP + _N + _MS + r"\s+(?:[Nn]orte|[Ss]ur)\b", re.I),
    ),
    (
        "numNorte",
        False,
        re.compile(_N + _MS + r"\s+(?:[Nn]orte|[Ss]ur)" + _SEP + _N + _MS + r"\s+[Ee]ste\b", re.I),
    ),
    # ── Sufijo letra E/N ──────────────────────────────────────────────────────
    # "427.670 E, 7.699.345 N" / "730723 mE, 5850944 mS"
    ("numE_numN", True, re.compile(_N + r"\s*m?[Ee]\b" + _SEP + _N + r"\s*m?[Nn]\b")),
    ("numN_numE", False, re.compile(_N + r"\s*m?[Nn]\b" + _SEP + _N + r"\s*m?[Ee]\b")),
    # ── Con etiqueta prefijo corta ────────────────────────────────────────────
    # "E: 275.669 y N: 6.245.944" / "E_339.945/N_6.343.851"
    ("E_colon_N", True, re.compile(r"\bE[:\s_]+" + _N + _MS + _SEP + _NR + r"[:\s_]+" + _N, re.I)),
    ("N_colon_E", False, re.compile(_NR + r"[:\s_]+" + _N + _MS + _SEP + r"E[:\s_]+" + _N, re.I)),
    # ── Paréntesis (X)/(Y) ────────────────────────────────────────────────────
    (
        "este_xy",
        True,
        re.compile(r"[Ee]ste\s*\([XxYy]\)\s*" + _N + _SEP + r"[Nn]orte\s*\([XxYy]\)\s*" + _N, re.I),
    ),
    (
        "norte_xy",
        False,
        re.compile(r"[Nn]orte\s*\([XxYy]\)\s*" + _N + _SEP + r"[Ee]ste\s*\([XxYy]\)\s*" + _N, re.I),
    ),
    # ── Bare pair sin etiqueta ────────────────────────────────────────────────
    ("bare_EN", True, re.compile(r"\b([2-9]\d{5}(?:[.,]\d+)?)\s+([5-8]\d{6}(?:[.,]\d+)?)\b")),
    ("bare_NE", False, re.compile(r"\b([5-8]\d{6}(?:[.,]\d+)?)\s+([2-9]\d{5}(?:[.,]\d+)?)\b")),
]

_VER_RE = re.compile(r"^(ver\s|en\s+el\s+numeral|en\s+anexo|se\s+presentan)", re.I)


def parse_utm(text: str) -> Optional[UTMPoint]:
    if not text:
        return None
    s = str(text).strip()
    if s.lower() in {"nan", "n/a"} or _VER_RE.match(s):
        return None

    zone = _detect_zone(s)

    # Detectar datum no-WGS84
    datum_warning = ""
    if _NON_WGS84_RE.search(s):
        datum_warning = (
            f"Datum no-WGS84 detectado en '{s[:60]}…'. "
            "Coordenadas pueden diferir hasta ~200m del valor WGS84."
        )
        log.debug("Datum no-WGS84: %s", s[:80])

    for name, a_is_este, pat in PATTERNS:
        m = pat.search(s)
        if not m:
            continue
        try:
            a, b = _clean_num(m.group(1)), _clean_num(m.group(2))
        except (ValueError, IndexError):
            continue

        result = _try(a, b, a_is_este)
        if not result:
            continue
        e, n = result

        try:
            lon, lat = _to_wgs84(e, n, zone)
            if not (-82 <= lon <= -65 and -57 <= lat <= -17):
                continue
        except Exception:
            continue

        return UTMPoint(
            easting=round(e, 2),
            northing=round(n, 2),
            zone=zone,
            lon=round(lon, 6),
            lat=round(lat, 6),
            method=name,
            datum_warning=datum_warning,
        )
    return None
