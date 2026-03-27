"""
geo/coord_parser.py — Parsea coordenadas UTM desde texto libre de RCAs chilenas.

Cubre formatos heterogéneos observados en 430 RCAs del SEIA:
  "Este 406.871 Norte 7.089.424"      → 406871, 7089424
  "427.670 E, 7.699.345 N"            → 427670, 7699345
  "7.579.785 N / 442.074 E"           → 7579785, 442074
  "Norte (m) 6.206.785,56 Este 263.150,56" → 6206785.56, 263150.56
  "Este 303574.3, Norte 6133940.3"    → 303574.3, 6133940.3
  "740.990 Este, 5.787.978 Norte"     → 740990, 5787978
  "Este 715949, Sur 5848534"          → 715949, 5848534
"""

import re
import logging
from dataclasses import dataclass
from typing import Optional

import pyproj

log = logging.getLogger("rca_extractor")

ESTE_MIN,  ESTE_MAX  = 200_000,   920_000
NORTE_MIN, NORTE_MAX = 5_400_000, 8_300_000

ZONE_HINTS = {"18": 18, "18s": 18, "18h": 18, "19": 19, "19s": 19, "19h": 19}


@dataclass
class UTMPoint:
    easting: float; northing: float; zone: int
    lon: float; lat: float; method: str


def _clean_num(s: str) -> float:
    """
    Convierte string numérico de PDFs chilenos a float.
    Reglas aplicadas en orden:
      1. Coma presente → coma es decimal, puntos son miles
      2. Múltiples puntos → todos son separadores de miles
      3. Un punto seguido de exactamente 3 dígitos al final → separador de miles
      4. Un punto con 1-2 dígitos al final → decimal normal
    """
    s = s.strip()
    if ',' in s:
        return float(s.replace('.', '').replace(',', '.'))
    dot_count = s.count('.')
    if dot_count == 0:
        return float(s)
    if dot_count >= 2:
        # "6.535.968" → 6535968, "6.382.310" → 6382310
        # Pero "6.245.944,56" ya fue manejado arriba
        # Si el último segmento tiene exactamente 2 dígitos → decimal
        parts = s.split('.')
        if len(parts[-1]) == 2:
            return float(''.join(parts[:-1]) + '.' + parts[-1])
        return float(s.replace('.', ''))
    # Un solo punto
    parts = s.split('.')
    after = parts[1]
    if len(after) == 3:          # "406.871" → 406871
        return float(s.replace('.', ''))
    return float(s)              # "303574.3" → 303574.3


def _detect_zone(text: str) -> int:
    m = re.search(r'[Hh]uso\s*(\d{2})|UTM\s*(\d{2})|(\d{2})[Ss]\b', text)
    if m:
        z = next(g for g in m.groups() if g)
        return ZONE_HINTS.get(z.lower(), 19)
    if re.search(r'\b18[SsHh]?\b', text): return 18
    return 19


def _to_wgs84(e: float, n: float, zone: int) -> tuple[float, float]:
    t = pyproj.Transformer.from_crs(f"EPSG:{32700 + zone}", "EPSG:4326", always_xy=True)
    return t.transform(e, n)


def _valid(e: float, n: float) -> bool:
    return (ESTE_MIN <= e <= ESTE_MAX) and (NORTE_MIN <= n <= NORTE_MAX)


def _try(a: float, b: float, a_is_este: bool) -> Optional[tuple[float, float]]:
    e, n = (a, b) if a_is_este else (b, a)
    if _valid(e, n): return e, n
    if _valid(b, a): return b, a
    return None


_N = r"([\d]+(?:[.,]\d+)*)"
# Norte y sus alias en zona austral
_NR = r"(?:[Nn]orte|[Ss]ur|[Nn])"

PATTERNS = [
    # Prefijo: "Este X, Norte Y" y variantes
    ("este_norte", True,  re.compile(r"[Ee]ste[\s:_(mM)]+?"   + _N + r"[\s,;/]+" + _NR + r"[\s:_(mM)]+?" + _N, re.I)),
    ("norte_este", False, re.compile(_NR + r"[\s:_(mM)]+?"     + _N + r"[\s,;/]+[Ee]ste[\s:_(mM)]+?"    + _N, re.I)),
    # Sufijo: "427.670 E, 7.699.345 N" y variantes con Sur
    ("numE_numN",  True,  re.compile(_N + r"\s*[Ee]\b[\s,;/]+" + _N + r"\s*[Nn]\b")),
    ("numN_numE",  False, re.compile(_N + r"\s*[Nn]\b[\s,;/]+" + _N + r"\s*[Ee]\b")),
    # Sufijo con palabra: "740.990 Este, 5.787.978 Norte"
    ("numEste",    True,  re.compile(_N + r"\s+[Ee]ste[\s,;/]+"   + _N + r"\s+(?:[Nn]orte|[Ss]ur)\b", re.I)),
    ("numNorte",   False, re.compile(_N + r"\s+(?:[Nn]orte|[Ss]ur)[\s,;/]+" + _N + r"\s+[Ee]ste\b", re.I)),
    # "E: X y N: Y"  / "N: Y / E: X"
    ("E_colon_N",  True,  re.compile(r"\bE[:\s]+" + _N + r"[\s,;/y]+" + _NR + r"[:\s]+" + _N, re.I)),
    ("N_colon_E",  False, re.compile(_NR + r"[:\s]+" + _N + r"[\s,;/y]+E[:\s]+"         + _N, re.I)),
    # "Este (X) / Norte (Y)"
    ("este_xy",    True,  re.compile(r"[Ee]ste\s*\([XxYy]\)\s*"   + _N + r"[\s,;/]+[Nn]orte\s*\([XxYy]\)\s*" + _N, re.I)),
    ("norte_xy",   False, re.compile(r"[Nn]orte\s*\([XxYy]\)\s*"  + _N + r"[\s,;/]+[Ee]ste\s*\([XxYy]\)\s*"  + _N, re.I)),
    # Bare pair: Este ~200k-920k + Norte ~5.4M-8.3M
    ("bare_EN",    True,  re.compile(r"\b([2-9]\d{5}(?:[.,]\d+)?)\s+([5-8]\d{6}(?:[.,]\d+)?)\b")),
    ("bare_NE",    False, re.compile(r"\b([5-8]\d{6}(?:[.,]\d+)?)\s+([2-9]\d{5}(?:[.,]\d+)?)\b")),
]

_VER_RE = re.compile(r"^(ver\s|en\s+el\s+numeral|en\s+anexo|se\s+presentan)", re.I)


def parse_utm(text: str) -> Optional[UTMPoint]:
    if not text: return None
    s = str(text).strip()
    if s.lower() in {"nan", "n/a"} or _VER_RE.match(s): return None

    zone = _detect_zone(s)

    for name, a_is_este, pat in PATTERNS:
        m = pat.search(s)
        if not m: continue
        try:
            a, b = _clean_num(m.group(1)), _clean_num(m.group(2))
        except (ValueError, IndexError): continue

        result = _try(a, b, a_is_este)
        if not result: continue
        e, n = result

        try:
            lon, lat = _to_wgs84(e, n, zone)
            if not (-82 <= lon <= -65 and -57 <= lat <= -17): continue
        except Exception: continue

        return UTMPoint(
            easting=round(e, 2), northing=round(n, 2), zone=zone,
            lon=round(lon, 6), lat=round(lat, 6), method=name
        )
    return None
