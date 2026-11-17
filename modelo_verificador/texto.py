"""Utilidades de texto y números para campos DBF y celdas de bases de datos."""
import re

SIN_INFO = re.compile(r"(?i)^(sin\s*inf\w*|na|n/a|no aplica|-|\.|\"+|)$")


def s(v):
    """Celda → texto limpio (enteros sin «.0», espacios colapsados)."""
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return re.sub(r"\s+", " ", str(v)).strip()


def num(v):
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


def tiene(v):
    """True si la celda trae un dato real (no vacío / «sin información» / «NA» / «-»)."""
    return not SIN_INFO.match(s(v))


def ajustar(t, nbytes):
    """Trunca por BYTES UTF-8: el límite de un campo DBF es en bytes (las tildes ocupan 2)."""
    t = s(t)
    if len(t.encode("utf-8")) <= nbytes:
        return t
    while t and len((t + "…").encode("utf-8")) > nbytes:
        t = t[:-1]
    return t.rstrip() + "…"


def bytes_utf8(t):
    return len(s(t).encode("utf-8"))


def rango_profundidad(*vals):
    """Primer valor interpretable como «a - b» o «a» → (min, max) en cm positivos; None si no hay."""
    for v in vals:
        t = s(v)
        m = re.match(r"^-?(\d+(?:[.,]\d+)?)\s*-\s*-?(\d+(?:[.,]\d+)?)$", t)
        if m:
            return tuple(sorted((num(m.group(1)), num(m.group(2)))))
        if re.match(r"^-?\d+(?:[.,]\d+)?$", t):
            x = abs(num(t))
            return (x, x)
    return None


def par_profundidad(ini, fin):
    a = abs(num(s(ini))) if tiene(ini) and num(s(ini)) is not None else None
    b = abs(num(s(fin))) if tiene(fin) and num(s(fin)) is not None else None
    if a is None and b is None:
        return None
    a = a if a is not None else b
    b = b if b is not None else a
    return tuple(sorted((a, b)))


def profundidad_en_descripcion(d):
    """«Profundidad: a - b cm» dentro de la descripción de una unidad → (a, b)."""
    m = re.search(r"(?i)profundidad\s*(?:\(cm\))?\s*:\s*(-?\d+(?:[.,]\d+)?)\s*-\s*(-?\d+(?:[.,]\d+)?)", d or "")
    return tuple(sorted((abs(num(m.group(1))), abs(num(m.group(2)))))) if m else None
