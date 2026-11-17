"""Localización de archivos de referencia y de capas dentro de un Modelo de Datos ICANH V4.

Los Modelos reales varían en tildes y mayúsculas («Documentación» / «Documentacion»,
«UNIDAD MÍNIMA» / «UNIDAD MNIMA»), así que todas las búsquedas comparan nombres normalizados.
"""
import os
import re
import unicodedata
from functools import lru_cache

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFERENCIA = os.environ.get("MODELO_VERIFICADOR_REF", os.path.join(_RAIZ, "referencia"))
CATALOGO = os.path.join(REFERENCIA, "Catalogo_de_objetos_modelo_de_datos_geografico_ICANH.xls")
PLANTILLAS = os.path.join(REFERENCIA, "plantillas_V4")


def norm(t):
    """MAYÚSCULAS sin tildes ni espacios repetidos (para comparar nombres)."""
    t = unicodedata.normalize("NFKD", str(t)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", t).upper().strip()


@lru_cache(maxsize=64)
def _indice(raiz):
    """{(nombre_normalizado, ext): ruta} de todos los archivos bajo raiz."""
    idx = {}
    for d, _, fs in os.walk(raiz):
        for f in fs:
            base, ext = os.path.splitext(f)
            idx.setdefault((norm(base), ext.lower()), os.path.join(d, f))
    return idx


def limpiar_cache():
    _indice.cache_clear()


def buscar_capa(raiz, nombre):
    """Ruta sin extensión del shapefile `nombre` bajo `raiz` (o None)."""
    p = _indice(os.path.abspath(raiz)).get((norm(nombre), ".shp"))
    return p[:-4] if p else None


def plantilla(nombre):
    return buscar_capa(PLANTILLAS, nombre) if os.path.isdir(PLANTILLAS) else None


def buscar_unidad_minima(raiz):
    """La tabla UNIDAD MÍNIMA DE EXCAVACIÓN VERTICAL (.xlsx)."""
    for (n, ext), p in _indice(os.path.abspath(raiz)).items():
        if ext == ".xlsx" and "EXCAVACION VERTICAL" in n:
            return p
    return None


def buscar_carpeta(raiz, nombre):
    for d, ds, _ in os.walk(raiz):
        for x in ds:
            if norm(x) == norm(nombre):
                return os.path.join(d, x)
    return None


def buscar_metadato(raiz):
    """Primer .xlsx dentro de la carpeta «Metadato»."""
    c = buscar_carpeta(raiz, "Metadato")
    if not c:
        return None
    xs = sorted(f for f in os.listdir(c) if f.lower().endswith(".xlsx") and not f.startswith("~$"))
    return os.path.join(c, xs[0]) if xs else None


def carpeta_materiales(raiz):
    return buscar_carpeta(raiz, "Documentacion Materiales Arqueologicos")


def carpeta_raster(raiz):
    return buscar_carpeta(raiz, "Raster")
