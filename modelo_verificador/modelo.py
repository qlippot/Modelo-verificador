"""Lectura de un Modelo de Datos ICANH V4 (solo lectura)."""
import os
import glob
import collections

import shapefile
import openpyxl

from . import rutas, geom

CAPAS_VECTORIALES = [
    "POLIGONO GENERAL", "POLIGONOS ESPECIFICOS", "ZONIFICACION ARQUEOLOGICA", "ACTIVIDADES ARQUEOLOGICAS",
    "CERAMICAS", "RESTOS BOTANICOS", "METALES", "LITICOS", "MUESTRAS DE SUELOS", "ESTRUCTURAS", "RASGOS",
    "TEXTILES", "VIDRIOS", "OTROS OBJETOS O MATERIALES", "OBJETOS COMPUESTOS", "OSEOS ANIMALES", "OSEOS HUMANOS",
    "INDIVIDUOS", "EMBARCACIONES", "MADERAS", "ANOMALIAS CON SENSORES REMOTOS",
]


class Modelo:
    """Acceso perezoso a las capas, la tabla de unidades mínimas y el metadato de un Modelo."""

    def __init__(self, raiz):
        if not os.path.isdir(raiz):
            raise FileNotFoundError(f"No existe la carpeta del Modelo: {raiz}")
        self.raiz = os.path.abspath(raiz)
        rutas.limpiar_cache()
        self._cache = {}

    def ruta(self, capa):
        return rutas.buscar_capa(self.raiz, capa)

    def capa(self, nombre):
        """Reader de pyshp, o None si la capa no existe."""
        p = self.ruta(nombre)
        return shapefile.Reader(p, encoding="utf-8") if p else None

    def registros(self, nombre):
        """[(dict_registro, shape)] de una capa (vacío si no existe)."""
        if nombre not in self._cache:
            r = self.capa(nombre)
            self._cache[nombre] = [] if r is None else [(x.record.as_dict(), x.shape) for x in r.iterShapeRecords()]
            if r is not None:
                r.close()
        return self._cache[nombre]

    def capas_presentes(self):
        return [c for c in CAPAS_VECTORIALES if self.ruta(c)]

    def capas_materiales(self):
        """Shapefiles de la carpeta de materiales (incluye ESTRUCTURAS)."""
        d = rutas.carpeta_materiales(self.raiz)
        return sorted(os.path.basename(f)[:-4] for f in glob.glob(os.path.join(d, "*.shp"))) if d else []

    def actividades(self):
        """{ID_ACT_ARQ: {"rec": dict, "anillos": [...], "centroide": (x, y)}}"""
        if "_act" not in self._cache:
            out = {}
            for rec, sh in self.registros("ACTIVIDADES ARQUEOLOGICAS"):
                an = geom.anillos(sh) if sh.points else []
                out[rec["ID_ACT_ARQ"]] = dict(rec=rec, anillos=an, centroide=geom.centroide(an) if an else None)
            self._cache["_act"] = out
        return self._cache["_act"]

    def ruta_unidades(self):
        return rutas.buscar_unidad_minima(self.raiz)

    def unidades(self):
        """[(fila_excel, id, tipo, descripcion)] de la tabla UNIDAD MÍNIMA DE EXCAVACIÓN VERTICAL."""
        if "_um" not in self._cache:
            p = self.ruta_unidades()
            out = []
            if p:
                ws = openpyxl.load_workbook(p, read_only=True, data_only=True).active
                for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                    row = tuple(row) + (None,) * 3
                    if not any(row[:3]):
                        continue
                    out.append((i, row[0], row[1], row[2]))
            self._cache["_um"] = out
        return self._cache["_um"]

    def ruta_metadato(self):
        return rutas.buscar_metadato(self.raiz)

    def carpeta_raster(self):
        return rutas.carpeta_raster(self.raiz)

    def ids_materiales(self):
        """Counter de todos los IDs de materiales/estructuras existentes."""
        from .ids import MATERIALES
        c = collections.Counter()
        for capa in self.capas_materiales():
            m = MATERIALES.get(rutas.norm(capa))
            if not m:
                continue
            for rec, _ in self.registros(capa):
                c[rec.get(m.campo)] += 1
        return c
