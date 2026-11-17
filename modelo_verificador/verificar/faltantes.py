"""Auditoría de INFORMACIÓN FALTANTE: qué datos no existen (no es validación de formato).

Ortoplanos requeridos, campos obligatorios/condicionales vacíos en actividades, unidades sin
descripción o sin profundidad, campos de materiales mayormente vacíos y filas del Metadato sin diligenciar.
"""
import os
import re
import collections

import openpyxl

from .. import rutas
from ..modelo import Modelo
from .informe import Informe
from .coherencia import TIPOS_CON_ORTOPLANO

OBLIGATORIOS_ACT = ["ID_POL_ESP", "RNA_ARQ_L", "FECHA_INI", "FECHA_FIN", "TIPO_ACT", "ALTITUD",
                    "ANCHO_CM", "LARGO_CM", "PROFUN_MAX", "MAT_ARQUEO"]


def verificar(modelo, umbral_vacios=0.5):
    M = modelo if isinstance(modelo, Modelo) else Modelo(modelo)
    inf = Informe("faltantes")
    act = {a: v["rec"] for a, v in M.actividades().items()}
    capas = {rutas.norm(L): [r for r, _ in M.registros(L)] for L in M.capas_materiales()}

    # 1. ortoplanos requeridos: un GeoTIFF por par actividad–unidad con materiales en Corte / Cuadrícula / Trinchera
    pares = collections.defaultdict(set)
    for L, recs in capas.items():
        if L == "ESTRUCTURAS":
            continue
        for r in recs:
            if r.get("ID_UNI_EX") and act.get(r.get("ID_ACT_ARQ"), {}).get("TIPO_ACT") in TIPOS_CON_ORTOPLANO:
                pares[r["ID_ACT_ARQ"]].add(r["ID_UNI_EX"])
    req = {f"{a}_{u}" for a, us in pares.items() for u in us}
    rd = M.carpeta_raster()
    tiene = {os.path.splitext(f)[0] for f in (os.listdir(rd) if rd else []) if f.lower().endswith((".tif", ".tiff"))}
    for a, us in sorted(pares.items()):
        if not any(f"{a}_{u}" in tiene for u in us):
            inf.aviso("RASTER", "Ningún ortoplano nombrado con una unidad que tenga materiales",
                      f"{a} {act[a].get('TIPO_ACT')} ({len(us)} unidades con materiales)")
    inf.datos["ortoplanos"] = dict(pares_actividad_unidad=len(req), con_ortoplano=len(req & tiene),
                                   sin_correspondencia=sorted(tiene - req))

    # 2. actividades: obligatorios y condicionales vacíos
    C = "ACTIVIDADES ARQUEOLOGICAS"
    usadas = {r.get("ID_ACT_ARQ") for recs in capas.values() for r in recs}
    for k, a in act.items():
        for f in OBLIGATORIOS_ACT:
            if a.get(f) in (None, ""):
                inf.error(C, f"Obligatorio vacío: {f}", k)
        if a.get("TIPO_ACT") == "Cuadrícula" and not a.get("CORTE"):
            inf.error(C, "Cuadrícula sin CORTE", k)
        if a.get("MAT_ARQUEO") == "Positivo" and not a.get("NMERO_UNE"):
            inf.aviso(C, "Actividad positiva sin NMERO_UNE", k)
        if a.get("MAT_ARQUEO") == "Positivo" and k not in usadas:
            inf.aviso(C, "Actividad positiva sin materiales en el Modelo", k)

    # 3. unidades sin descripción real o sin profundidad
    U = "UNIDAD MINIMA"
    for _, uid, tipo, desc in M.unidades():
        d = str(desc or "")
        if re.search(r"sin descripci[oó]n", d, re.I):
            inf.aviso(U, "Unidad sin descripción real", uid)
        if tipo != "Superficie" and not re.search(r"(?i)profundidad\s*(\(cm\))?\s*:\s*-?\d", d):
            inf.info(U, "Descripción sin profundidad («Profundidad: a - b cm»)", uid)

    # 4. campos de materiales vacíos en la mayoría de registros
    for L, recs in capas.items():
        if not recs:
            continue
        for f in recs[0]:
            if f.startswith("ID_") or f.startswith("COD_") or f in ("PROFUN_INI", "PROFUN_FIN"):
                continue
            n = sum(1 for r in recs if r[f] in (None, "") or str(r[f]).strip() in ("Sin identificar", "Indeterminado"))
            if n / len(recs) >= umbral_vacios:
                inf.info(L, "Campo mayormente vacío / sin identificar", f"{f}: {n}/{len(recs)}")

    # 5. metadato: filas de OBLIGACIÓN sin diligenciar en hojas de capas entregadas
    MD = "METADATO"
    mp = M.ruta_metadato()
    if mp:
        mw = openpyxl.load_workbook(mp, data_only=True)
        marcadas_no = []
        for ws in mw.worksheets:
            vcol = None
            for row in ws.iter_rows(max_row=6):
                for c in row:
                    if rutas.norm(c.value or "") == "INFORMACION USUARIO":
                        vcol = c.column
            if not vcol:
                continue
            entrega, pend = None, []
            for row in ws.iter_rows(min_row=3):
                vals = [c.value for c in row]
                txt = " ".join(str(v) for v in vals if v is not None)
                val = ws.cell(row=row[0].row, column=vcol).value
                if re.search(r"(?i)entrega la capa", txt):
                    entrega = str(val).strip().upper() if val else None
                if "OBLIGACI" in txt.upper() and (val in (None, "") or str(val).startswith("Diligenciar")
                                                    or rutas.norm(val) == "OBLIGACION"):
                    num_ = next((str(v) for v in vals[:2] if v is not None), "")
                    nombre = next((str(v).strip() for v in vals[2:4] if v and not str(v).upper().startswith("OBLIG")), "?")
                    nombre = f"{num_} {nombre}".strip()
                    pend.append(f"fila {row[0].row}: {nombre[:60]}")
            if entrega == "NO":
                marcadas_no.append(ws.title.strip())
            else:
                for p in pend:
                    inf.error(MD, f"Sin diligenciar · hoja «{ws.title.strip()}»", p)
        inf.datos["metadato_hojas_no_entregadas"] = marcadas_no
    return inf
