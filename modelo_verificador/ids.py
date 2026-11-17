"""Códigos ID del Modelo de Datos ICANH V4 (reglas del Catálogo de objetos).

  Polígono general (REGIS_AUTO)   R0125A22                    8   R + 4 dígitos + A + año (2)
  Polígono específico             R0125A220005               12   + numeración (4)
  Zonificación                    R0125A220005ZO0001         18   + ZO + consecutivo (4)
  Actividad (Aprobación PMA)      R0125A220005DI00001        19   + DI + consecutivo (5) por polígono específico
  Actividad (Implementación PMA)  R0125A220005PI00001        19   + PI + consecutivo (5)
  Actividad (intervención 1/3/4)  R0125A22I0000000001        19   REGIS_AUTO + I + consecutivo (10) *
  Unidad mínima (Aprobación PMA)  R0125A220005ND0001         18   + ND + consecutivo (4)
  Unidad mínima (Implementación)  R0125A220005NP0001         18   + NP + consecutivo (4)
  Unidad mínima (intervención)    R0125A22N000000001         18   REGIS_AUTO + N + consecutivo (9) *
  Materiales                      <ID_ACT> + prefijo + consecutivo (4), reinicia por actividad

  * El catálogo solo dice «seguido de un consecutivo» y fija la longitud total; el ancho del
    consecutivo se deduce de esa longitud.
"""
import re
from collections import namedtuple

Material = namedtuple("Material", "capa campo prefijo longitud")

# capa -> campo ID, prefijo, longitud total (catálogo V4, hoja ESTRUCTURA OBJETOS)
MATERIALES = {m.capa: m for m in [
    Material("CERAMICAS", "ID_CERAMIC", "C", 24),
    Material("RESTOS BOTANICOS", "ID_RESTO_B", "B", 24),
    Material("METALES", "ID_METALES", "M", 24),
    Material("LITICOS", "ID_LITICOS", "L", 24),
    Material("MUESTRAS DE SUELOS", "ID_SUELOS", "S", 24),
    Material("ESTRUCTURAS", "ID_EST", "E", 24),
    Material("RASGOS", "ID_RAS", "R", 24),
    Material("TEXTILES", "ID_TEXTILE", "T", 24),
    Material("VIDRIOS", "ID_VIDRIOS", "V", 24),
    Material("OTROS OBJETOS O MATERIALES", "ID_O_OB_MA", "OB", 25),
    Material("OBJETOS COMPUESTOS", "ID_O_OB_CO", "OBC", 26),
    Material("OSEOS ANIMALES", "ID_OSEOS_A", "OA", 25),
    Material("OSEOS HUMANOS", "ID_OSEOS_H", "H", 24),
    Material("INDIVIDUOS", "COD_INDIVI", "IH", 25),
    Material("EMBARCACIONES", "COD_EMBAR", "EM", 25),
    Material("MADERAS", "ID_MADER", "MA", 25),
    Material("ANOMALIAS CON SENSORES REMOTOS", "ID_ANO_ARQ", "A", 24),
]}
CAMPO_A_CAPA = {m.campo: m.capa for m in MATERIALES.values()}

_REG = r"R\d{4}A\d{2}"
_POL = _REG + r"\d{4}"
RE = {
    "registro": re.compile(rf"^{_REG}$"),
    "poligono": re.compile(rf"^{_POL}$"),
    "zonificacion": re.compile(rf"^{_POL}ZO\d{{4}}$"),
    "actividad": re.compile(rf"^(?:{_POL}(?:DI|PI)\d{{5}}|{_REG}I\d{{10}})$"),
    "unidad": re.compile(rf"^(?:{_POL}(?:ND|NP)\d{{4}}|{_REG}N\d{{9}})$"),
}
_ACT = rf"(?:{_POL}(?:DI|PI)\d{{5}}|{_REG}I\d{{10}})"
# prefijos más largos primero (OBC antes que OB, OA antes que…)
_PREF = sorted(MATERIALES.values(), key=lambda m: -len(m.prefijo))
RE_MATERIAL = re.compile(rf"^({_ACT})({'|'.join(m.prefijo for m in _PREF)})(\d{{4}})$")

FASES = {"DI": "Aprobación del PMA (diagnóstico y prospección)", "PI": "Implementación del PMA", "I": "Intervención tipo 1/3/4"}


def analizar(codigo, capa=None):
    """Identifica qué es un código y lo descompone. Devuelve dict con 'tipo', 'valido', partes y 'errores'.

    `capa` (opcional) fuerza la interpretación como material de esa capa."""
    c = str(codigo or "").strip()
    out = dict(codigo=c, tipo=None, valido=False, errores=[])
    if not c:
        out["errores"].append("vacío")
        return out
    if capa:
        return _material(c, MATERIALES[capa], out)
    for tipo in ("registro", "poligono", "zonificacion", "actividad", "unidad"):
        if RE[tipo].match(c):
            out.update(tipo=tipo, valido=True)
            out["registro"] = c[:8]
            if tipo != "registro" and not c[8:9] in ("I", "N"):
                out["poligono"] = c[:12]
            if tipo == "actividad":
                out["fase"] = FASES["I"] if c[8] == "I" else FASES[c[12:14]]
                out["consecutivo"] = int(c[-10:] if c[8] == "I" else c[-5:])
            if tipo == "unidad":
                out["consecutivo"] = int(c[-9:] if c[8] == "N" else c[-4:])
            return out
    m = RE_MATERIAL.match(c)
    if m:
        mat = next(x for x in _PREF if x.prefijo == m.group(2))
        return _material(c, mat, out)
    out["errores"].append("no corresponde a ningún formato de ID del catálogo V4")
    return out


def _material(c, mat, out):
    out.update(tipo="material", capa=mat.capa, campo=mat.campo, prefijo=mat.prefijo)
    m = re.match(rf"^({_ACT}){re.escape(mat.prefijo)}(\d{{4}})$", c)
    if not m:
        out["errores"].append(f"{mat.campo} debe ser ID_ACT_ARQ (19) + «{mat.prefijo}» + consecutivo de 4 dígitos")
    else:
        out.update(actividad=m.group(1), consecutivo=int(m.group(2)))
    if len(c) != mat.longitud:
        out["errores"].append(f"longitud {len(c)} ≠ {mat.longitud}")
    out["valido"] = not out["errores"]
    return out


def es_valido(codigo, tipo):
    """tipo ∈ registro | poligono | zonificacion | actividad | unidad | <capa de material>."""
    if tipo in MATERIALES:
        return analizar(codigo, capa=tipo)["valido"]
    return bool(RE[tipo].match(str(codigo or "").strip()))


# ------------------------------------------------------------------ generación
def poligono(registro, n):
    return f"{registro}{n:04d}"


def actividad(poligono_esp, n, fase="PI"):
    """fase: 'PI' (Implementación) o 'DI' (Aprobación PMA). Para intervenciones 1/3/4 usar actividad_intervencion."""
    if fase not in ("PI", "DI"):
        raise ValueError("fase debe ser 'PI' o 'DI'")
    return f"{poligono_esp}{fase}{n:05d}"


def actividad_intervencion(registro, n):
    return f"{registro}I{n:010d}"


def unidad(poligono_esp, n, fase="PI"):
    """Unidad mínima: NP en Implementación, ND en Aprobación PMA."""
    return f"{poligono_esp}{'NP' if fase == 'PI' else 'ND'}{n:04d}"


def unidad_intervencion(registro, n):
    return f"{registro}N{n:09d}"


def zonificacion(poligono_esp, n):
    return f"{poligono_esp}ZO{n:04d}"


def material(id_act, capa, n):
    m = MATERIALES[capa]
    if n > 9999:
        raise ValueError(f"consecutivo {n} > 9999 en {id_act} ({capa})")
    return f"{id_act}{m.prefijo}{n:04d}"


def fase_de_actividad(id_act):
    return "DI" if str(id_act)[12:14] == "DI" else "PI"


def siguiente(existentes, prefijo, ancho):
    """Siguiente consecutivo libre tras el máximo de los códigos que empiezan por `prefijo`."""
    ns = [int(c[len(prefijo):]) for c in existentes
          if c and str(c).startswith(prefijo) and str(c)[len(prefijo):].isdigit() and len(str(c)) == len(prefijo) + ancho]
    return max(ns, default=0) + 1


class Contador:
    """Consecutivos por prefijo, continuando desde los códigos ya existentes (idempotencia al agregar)."""

    def __init__(self, existentes=(), ancho=4):
        self.ancho = ancho
        self._exist = [str(c) for c in existentes if c]
        self._n = {}

    def nuevo(self, prefijo):
        if prefijo not in self._n:
            self._n[prefijo] = siguiente(self._exist, prefijo, self.ancho) - 1
        self._n[prefijo] += 1
        return f"{prefijo}{self._n[prefijo]:0{self.ancho}d}"
