"""Verificación de FORMATO contra el catálogo y las plantillas oficiales V4.

Estructura de campos y geometría vs. plantilla, sistema de referencia (.prj), obligatorios vacíos,
valores fuera de dominio, longitudes en bytes, formato/longitud/unicidad de IDs, vínculos
ID_ACT_ARQ / ID_UNI_EX, profundidades. Solo lee archivos.
"""
import os
import re
import collections

import shapefile

from .. import catalogo as _cat, ids as _ids, rutas, geom
from ..modelo import Modelo, CAPAS_VECTORIALES
from ..texto import bytes_utf8
from .informe import Informe


def _prj(t):
    """Compara parámetros de proyección, no el nombre del PROJCS."""
    return re.sub(r'^PROJCS\["[^"]*"', "PROJCS", t.strip())


def verificar(modelo, catalogo=None):
    M = modelo if isinstance(modelo, Modelo) else Modelo(modelo)
    cat = _cat.cargar(catalogo) if catalogo else _cat.cargar()
    inf = Informe("formato")
    resumen = {}

    # ---------- unidades mínimas
    UM = {}
    if not M.ruta_unidades():
        inf.error("UNIDAD MINIMA", "No existe la tabla UNIDAD MÍNIMA DE EXCAVACIÓN VERTICAL")
    for fila, uid, tipo, desc in M.unidades():
        if uid in UM:
            inf.error("UNIDAD MINIMA", "ID duplicado", uid)
        UM[uid] = (tipo, desc)
        if not _ids.es_valido(uid, "unidad") or len(str(uid)) != 18:
            inf.error("UNIDAD MINIMA", "ID: formato / longitud 18", f"fila {fila}: {uid}")
        if not tipo:
            inf.error("UNIDAD MINIMA", "TIPO obligatorio vacío", uid)
        elif len(str(tipo)) > 50:
            inf.error("UNIDAD MINIMA", "TIPO > 50 caracteres", uid)
        if not desc:
            inf.error("UNIDAD MINIMA", "DESCRIPCIÓN obligatoria vacía", uid)
        elif len(str(desc)) > 600:
            inf.error("UNIDAD MINIMA", "DESCRIPCIÓN > 600 caracteres", uid)
    resumen["UNIDAD MINIMA"] = len(UM)

    # ---------- actividades (para vínculos)
    ACT = {a: v["anillos"] for a, v in M.actividades().items()}
    tpl_cer = rutas.plantilla("CERAMICAS")
    ref_prj = _prj(open(tpl_cer + ".prj").read()) if tpl_cer and os.path.exists(tpl_cer + ".prj") else None
    if not rutas.plantilla("ACTIVIDADES ARQUEOLOGICAS"):
        inf.aviso("-", "Plantillas V4 no encontradas: se omite la comparación de estructura y CRS", rutas.PLANTILLAS)

    ref_uni = collections.Counter()
    for nombre in CAPAS_VECTORIALES:
        p = M.ruta(nombre)
        if not p:
            continue
        r = shapefile.Reader(p, encoding="utf-8")
        tpl = rutas.plantilla(nombre)
        if tpl:
            t = shapefile.Reader(tpl, encoding="utf-8")
            tf = [tuple(f[:3]) for f in t.fields[1:]]
            mf = [tuple(f[:3]) for f in r.fields[1:]]
            if tf != mf:
                sobran = [x for x in mf if x not in tf]
                faltan = [x for x in tf if x not in mf]
                det = f"sobran {sobran} · faltan {faltan}" if (sobran or faltan) else "mismos campos en otro orden"
                inf.error(nombre, "Estructura de campos distinta a la plantilla V4", det)
            if (t.shapeType % 10) != (r.shapeType % 10):
                inf.error(nombre, "Tipo de geometría distinto a la plantilla", f"{r.shapeTypeName} vs {t.shapeTypeName}")
            t.close()
        if not os.path.exists(p + ".prj"):
            inf.error(nombre, "Falta .prj")
        elif ref_prj and _prj(open(p + ".prj").read()) != ref_prj:
            inf.error(nombre, "Sistema de referencia distinto a CTM12 (plantilla)")

        largos = {f[0]: int(f[2]) for f in r.fields[1:] if f[1] == "C"}
        cf = cat.capa(nombre)
        mat = _ids.MATERIALES.get(nombre)
        ids_vistos = collections.Counter()
        recs, shapes = r.records(), r.shapes()
        for i, (rec, sh) in enumerate(zip(recs, shapes), start=1):
            d = rec.as_dict()
            for fld, a in cf.items():
                if fld not in d:
                    continue
                v = d[fld]
                vs = "" if v is None else str(v).strip()
                if a.obligatorio and vs == "":
                    inf.error(nombre, f"Obligatorio vacío: {fld}", f"fila {i}")
                elif vs == "" and "posterior" in a.obligacion.lower():
                    # exigido desde el Diagnóstico; la verificación por fase lo omite en el Registro
                    inf.error(nombre, f"Obligatorio después del Registro: {fld}", f"fila {i}")
                if a.con_dominio and vs and a.codigo in cat.dominios and vs not in cat.dominios[a.codigo]:
                    inf.error(nombre, f"Fuera de dominio: {fld}", vs)
            for fld, n in largos.items():
                if d.get(fld) and bytes_utf8(d[fld]) > n:
                    inf.error(nombre, f"Texto excede {n} bytes: {fld}", f"fila {i}")
            if not sh.points:
                inf.error(nombre, "Registro sin geometría", f"fila {i}")
            if mat:
                v = d.get(mat.campo, "")
                ids_vistos[v] += 1
                aa = d.get("ID_ACT_ARQ", "")
                an = _ids.analizar(v, capa=nombre)
                for e in an["errores"]:
                    inf.error(nombre, f"{mat.campo}: {e}", v)
                if an.get("actividad") and an["actividad"] != aa:
                    inf.error(nombre, f"{mat.campo} no empieza por su ID_ACT_ARQ", f"{v} ↔ {aa}")
                if aa not in ACT:
                    inf.error(nombre, "ID_ACT_ARQ inexistente en ACTIVIDADES", aa)
                elif sh.points and r.shapeType in (1, 11, 21) and not geom.punto_en_poligono(sh.points[0], ACT[aa]):
                    inf.aviso(nombre, "Punto fuera del polígono de su actividad", v)
                if "ID_UNI_EX" in d:
                    u = d["ID_UNI_EX"]
                    ref_uni[u] += 1
                    if u not in UM:
                        inf.error(nombre, "ID_UNI_EX inexistente en la tabla UNIDAD MÍNIMA", u)
                pi, pf = d.get("PROFUN_INI"), d.get("PROFUN_FIN")
                if pi is not None and pf is not None:
                    if pi < 0 or pf < 0:
                        inf.error(nombre, "Profundidad negativa", v)
                    if pi > pf:
                        inf.error(nombre, "PROFUN_INI > PROFUN_FIN", v)
                    if pi == 0 and pf == 0 and not str(UM.get(d.get("ID_UNI_EX"), ("",))[0]).startswith("Superficie"):
                        inf.aviso(nombre, "Profundidad 0-0 en unidad que no es Superficie", v)
            if nombre == "ACTIVIDADES ARQUEOLOGICAS":
                ida = d.get("ID_ACT_ARQ")
                ids_vistos[ida] += 1
                if not _ids.es_valido(ida, "actividad"):
                    inf.error(nombre, "ID_ACT_ARQ: formato / longitud 19", ida)
                elif d.get("ID_POL_ESP") and ida[8] != "I" and not ida.startswith(str(d["ID_POL_ESP"])):
                    inf.error(nombre, "ID_ACT_ARQ no empieza por su ID_POL_ESP", f"{ida} ↔ {d['ID_POL_ESP']}")
                fi = d.get("FECHA_INI")
                if fi and hasattr(fi, "year") and fi.year < 2000:
                    inf.aviso(nombre, "FECHA_INI anterior a 2000 (¿error de siglo?)", f"{ida} {fi}")
            if nombre == "POLIGONOS ESPECIFICOS":
                if d.get("ID_POL_ESP"):
                    ids_vistos[d["ID_POL_ESP"]] += 1
                if d.get("ID_POL_ESP") and not _ids.es_valido(d.get("ID_POL_ESP"), "poligono"):
                    inf.error(nombre, "ID_POL_ESP: formato / longitud 12", d.get("ID_POL_ESP"))
            if nombre == "ZONIFICACION ARQUEOLOGICA":
                ids_vistos[d.get("ID_ZON_ARQ")] += 1
                if not _ids.es_valido(d.get("ID_ZON_ARQ"), "zonificacion"):
                    inf.error(nombre, "ID_ZON_ARQ: formato / longitud 18", d.get("ID_ZON_ARQ"))
        for k, n in ids_vistos.items():
            if n > 1:
                inf.error(nombre, "ID duplicado", f"{k} ×{n}")
        resumen[nombre] = len(recs)
        r.close()

    inf.datos = dict(registros=resumen, unidades_sin_materiales=sum(1 for u in UM if u not in ref_uni))
    return inf
