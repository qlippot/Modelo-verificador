"""Lectura del Catálogo de objetos del Modelo de Datos Geográfico ICANH (.xls): atributos, obligatoriedad y dominios."""
import re
import collections
from dataclasses import dataclass, field
from functools import lru_cache

import xlrd

from . import rutas


@dataclass
class Atributo:
    codigo: int
    capa: str          # nombre de capa normalizado (MAYÚSCULAS sin tildes)
    nombre: str        # nombre del campo (p. ej. ID_CERAMIC)
    etiqueta: str
    tipo: str
    longitud: float | None
    obligacion: str
    con_dominio: bool

    @property
    def obligatorio(self):
        o = self.obligacion.lower()
        return o.startswith("obligación") and "posterior" not in o


@dataclass
class Catalogo:
    atributos: dict = field(default_factory=dict)                         # código -> Atributo
    dominios: dict = field(default_factory=lambda: collections.defaultdict(set))  # código -> {valores}

    def capa(self, nombre):
        """{campo: Atributo} de una capa."""
        n = rutas.norm(nombre)
        return {a.nombre: a for a in self.atributos.values() if a.capa == n}

    def capas(self):
        return sorted({a.capa for a in self.atributos.values()})

    def dominio(self, capa, campo):
        a = self.capa(capa).get(campo)
        return sorted(self.dominios.get(a.codigo, ())) if a else []


@lru_cache(maxsize=4)
def cargar(ruta=None):
    b = xlrd.open_workbook(ruta or rutas.CATALOGO)
    cat = Catalogo()
    eo = b.sheet_by_name("ESTRUCTURA OBJETOS")
    capa = None
    for r in range(eo.nrows):
        v = [str(x).strip() for x in eo.row_values(r)]
        m = re.match(r"NOMBRE DE(?:L| LA) (?:CAPA|TABLA|R[AÁ]STER)\s*:\s*(.*)", v[0])
        if m:
            capa = rutas.norm(m.group(1))
            continue
        if capa and v[2] and re.match(r"^\d+(\.0)?$", v[2]):
            cod = int(float(v[2]))
            lon = float(v[4]) if re.match(r"^\d+(\.\d+)?$", v[4]) else None
            cat.atributos[cod] = Atributo(cod, capa, v[1] or v[0], v[0], v[3], lon, v[7], v[6] == "DOMINIO")
    dm = b.sheet_by_name("DOMINIOS")
    cur = None
    for r in range(dm.nrows):
        v = [str(x).strip() for x in dm.row_values(r)]
        if v[0] == "ATRIBUTO":
            cur = int(float(v[1]))
            continue
        if v[0] in ("OBJETO", "CÓDIGO"):
            continue
        if cur and v[2]:
            cat.dominios[cur].add(v[2])
    return cat
