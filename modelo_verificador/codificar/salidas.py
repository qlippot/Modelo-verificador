"""Salidas del codificador: «BD codificada» (.xlsx) y escritura en una copia del Modelo."""
import os
import shutil
import datetime
import collections

import openpyxl
import shapefile
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

from .. import rutas, ids as _ids
from ..modelo import Modelo

_HDR = Font(bold=True, color="FFFFFF")
_FILL = PatternFill("solid", fgColor="4F4F4F")
COLUMNAS = ["ID_ACT_ARQ (Modelo)", "ID_UNI_EX (Modelo)", "ID(s) Modelo", "Estado", "Notas"]
ESTADOS = {"ok": "Codificado", "sin_resolver": "Sin resolver"}


def escribir_bd(res, bd_original, destino):
    """Copia de la BD con columnas de códigos al final de cada hoja + hojas «Unidades nuevas» y «Resumen codificación».
    La BD original no se modifica."""
    if os.path.abspath(bd_original) == os.path.abspath(destino):
        raise ValueError("El destino no puede ser la BD original")
    wb = openpyxl.load_workbook(bd_original)
    por_hoja = collections.defaultdict(list)
    for a in res["asignaciones"]:
        por_hoja[a["hoja"]].append(a)
    for hoja, filas in por_hoja.items():
        ws = wb[hoja]
        c0 = ws.max_column + 2
        hdr = res["config"]["hojas"][hoja].get("fila_encabezado", res["config"]["fila_encabezado"])
        for j, h in enumerate(COLUMNAS):
            c = ws.cell(row=hdr, column=c0 + j, value=h)
            c.font, c.fill = _HDR, _FILL
            ws.column_dimensions[get_column_letter(c0 + j)].width = [22, 22, 30, 14, 60][j]
        for a in filas:
            vals = [a["ID_ACT_ARQ"], a["ID_UNI_EX"], "; ".join(a["ids_modelo"]), ESTADOS[a["estado"]], " · ".join(a["notas"])]
            for j, v in enumerate(vals):
                ws.cell(row=a["fila"], column=c0 + j, value=v or None)
    wu = wb.create_sheet("Unidades nuevas")
    wu.append(["ID UNIDAD MÍNIMA DE EXCAVACIÓN VERTICAL", "TIPO", "DESCRIPCIÓN", "ACTIVIDAD", "CAPAS"])
    for u in sorted(res["unidades_nuevas"].values(), key=lambda x: x["id"]):
        wu.append([u["id"], u["tipo"], u["descripcion"], u["actividad"], ", ".join(u["materiales"])])
    wr = wb.create_sheet("Resumen codificación")
    rep = res["reporte"]
    filas = [("Fecha", datetime.date.today().isoformat()), ("Modo", res["config"]["modo"]),
             ("Filas codificadas", rep["filas"].get("ok", 0)), ("Filas sin resolver", rep["filas"].get("sin_resolver", 0)),
             ("Registros por capa", "; ".join(f"{k}: {v}" for k, v in rep["capas"].items())),
             ("Unidades nuevas", rep["unidades_nuevas"]),
             ("Sin profundidad (valor por defecto)", "; ".join(f"{k}: {v}" for k, v in rep["sin_profundidad"].items()) or "—"),
             ("Textos truncados (bytes DBF)", "; ".join(f"{k}: {v}" for k, v in rep["truncados"].items()) or "—"),
             ("Actividades que pasarían a MAT_ARQUEO Positivo", ", ".join(rep["actividades_a_positivo"]) or "—"),
             ("Sin resolver (hoja | actividad)", "; ".join(f"{k} ({v})" for k, v in rep["sin_resolver"].items()) or "—"),
             ("Columnas configuradas que no existen en la BD", "; ".join(f"{k}: {v}" for k, v in rep["columnas_faltantes"].items()) or "—")]
    for r in [("CONCEPTO", "DETALLE")] + filas:
        wr.append(list(r))
    for c in wr[1]:
        c.font, c.fill = _HDR, _FILL
    for ws, anchos in ((wu, (24, 22, 100, 24, 30)), (wr, (48, 120))):
        for col, w in zip("ABCDE", anchos):
            ws.column_dimensions[col].width = w
        for row in ws.iter_rows(min_row=2):
            for c in row:
                c.alignment = Alignment(wrap_text=True, vertical="top")
    wb.save(destino)
    return destino


def escribir_modelo(res, destino):
    """Escribe en `destino` (una COPIA del Modelo): capas de materiales de la configuración y unidades nuevas.

    modo «reemplazar»: cada capa configurada se reescribe solo con los registros de la BD.
    modo «agregar»: los registros nuevos se añaden a los existentes (IDs continúan el consecutivo).
    No toca ACTIVIDADES (el cambio a MAT_ARQUEO Positivo queda en el reporte)."""
    if os.path.abspath(destino) == os.path.abspath(res["modelo"]):
        raise ValueError("escribir_modelo no escribe sobre el Modelo leído: usar una copia de staging")
    M = Modelo(destino)
    mat_dir = rutas.carpeta_materiales(destino)
    if not mat_dir:
        raise FileNotFoundError("La copia no tiene carpeta «Documentación Materiales Arqueológicos»")
    log = {}
    for capa, items in res["registros"].items():
        tpl = rutas.plantilla(capa)
        r_tpl = shapefile.Reader(tpl, encoding="utf-8")
        campos = r_tpl.fields[1:]
        st = r_tpl.shapeType
        r_tpl.close()
        nombres = [f[0] for f in campos]
        actual = M.ruta(capa) or os.path.join(mat_dir, capa)
        previos = []
        if res["config"]["modo"] == "agregar" and M.ruta(capa):
            previos = M.registros(capa)
        for ext in (".shp", ".shx", ".dbf", ".qix", ".sbn", ".sbx"):
            if os.path.exists(actual + ext):
                os.remove(actual + ext)
        w = shapefile.Writer(actual, shapeType=st, encoding="utf-8")
        for f in campos:
            w.field(*f)
        for rec, sh in previos:
            w.shape(sh)
            w.record(*[rec.get(n) for n in nombres])
        for it in items:
            x, y = it["xy"]
            if st in (11, shapefile.POINTZ):
                w.pointz(x, y, 0)
            else:
                w.point(x, y)
            w.record(*[it["campos"].get(n) for n in nombres])
        w.close()
        for ext in (".prj", ".cpg"):
            if os.path.exists(tpl + ext):
                shutil.copy(tpl + ext, actual + ext)
        log[capa] = dict(previos=len(previos), nuevos=len(items))
    if res["unidades_nuevas"]:
        up = M.ruta_unidades()
        if not up:
            raise FileNotFoundError("La copia no tiene tabla UNIDAD MÍNIMA DE EXCAVACIÓN VERTICAL")
        wb = openpyxl.load_workbook(up)
        ws = wb.active
        ya = {r[0] for r in ws.iter_rows(min_row=2, values_only=True) if r and r[0]}
        n = 0
        for u in sorted(res["unidades_nuevas"].values(), key=lambda x: x["id"]):
            if u["id"] not in ya:
                ws.append([u["id"], u["tipo"], u["descripcion"][:600]]); n += 1
        wb.save(up)
        log["UNIDAD MINIMA"] = dict(nuevas=n)
    rutas.limpiar_cache()
    return log
