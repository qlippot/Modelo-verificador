"""Verificación de COHERENCIA interna del Modelo: geometría, contención, solapes, vínculos,
fechas, medidas vs. geometría, rásteres, consistencia actividad ↔ contenido y conteos del metadato.
Complementa formato.py. No modifica nada.
"""
import os
import re
import datetime
import collections

import openpyxl
from shapely.geometry import shape, Point, box
from shapely.ops import unary_union
from shapely.strtree import STRtree

from .. import geom, rutas
from ..ids import MATERIALES
from ..modelo import Modelo
from .informe import Informe

TIPOS_CON_ORTOPLANO = ("Corte", "Cuadrícula", "Trinchera")
TOL = 0.05   # m² de tolerancia para contenciones / solapes


def _g(sh):
    g = shape(sh.__geo_interface__)
    return g if g.is_valid else g.buffer(0)


def verificar(modelo, hoy=None):
    M = modelo if isinstance(modelo, Modelo) else Modelo(modelo)
    inf = Informe("coherencia")
    hoy = hoy or datetime.date.today()

    # ------------------------------------------------ zona de estudio
    pg = [s for _, s in M.registros("POLIGONO GENERAL") if s.points]
    PG = unary_union([_g(s) for s in pg]) if pg else None
    if PG is None:
        inf.error("POLIGONO GENERAL", "Capa vacía o inexistente")
    PE = {r["ID_POL_ESP"]: _g(s) for r, s in M.registros("POLIGONOS ESPECIFICOS") if s.points}
    for pid, g in PE.items():
        if PG is not None and g.difference(PG.buffer(TOL)).area > TOL:
            inf.error("POLIGONOS ESPECIFICOS", "Polígono específico fuera del polígono general", f"{pid} {g.difference(PG).area:.2f} m²")
    for r, s in M.registros("ZONIFICACION ARQUEOLOGICA"):
        pe = PE.get(r.get("ID_POL_ESP"))
        if pe is None:
            inf.error("ZONIFICACION ARQUEOLOGICA", "ID_POL_ESP inexistente", f"{r.get('ID_ZON_ARQ')} → {r.get('ID_POL_ESP')}")
        elif s.points and _g(s).difference(pe.buffer(TOL)).area > TOL:
            inf.aviso("ZONIFICACION ARQUEOLOGICA", "Zona fuera de su polígono específico", r.get("ID_ZON_ARQ"))

    # ------------------------------------------------ actividades
    C = "ACTIVIDADES ARQUEOLOGICAS"
    ACT, ACTG, vistos = {}, {}, collections.Counter()
    for r, s in M.registros(C):
        a = r["ID_ACT_ARQ"]
        vistos[a] += 1
        ACT[a] = r
        if not s.points:
            inf.error(C, "Actividad sin geometría", a)
            continue
        g0 = shape(s.__geo_interface__)
        if not g0.is_valid:
            inf.error(C, "Geometría inválida", a)
        g = g0 if g0.is_valid else g0.buffer(0)
        ACTG[a] = g
        if g.area < TOL:
            inf.aviso(C, "Área mínima (< 0.05 m²)", f"{a} {g.area:.3f} m²")
        pe = PE.get(r.get("ID_POL_ESP"))
        if pe is None:
            inf.error(C, "ID_POL_ESP inexistente", f"{a} → {r.get('ID_POL_ESP')}")
        elif g.difference(pe.buffer(TOL)).area > TOL:
            inf.error(C, "Actividad fuera de su polígono específico", f"{a} {g.difference(pe).area:.2f} m²")
        if PG is not None and g.difference(PG.buffer(TOL)).area > TOL:
            inf.error(C, "Actividad fuera del polígono general", f"{a} {g.difference(PG).area:.2f} m²")
        fi, ff = r.get("FECHA_INI"), r.get("FECHA_FIN")
        if not fi or not ff:
            inf.error(C, "Fecha vacía", a)
        elif fi > ff:
            inf.error(C, "FECHA_INI > FECHA_FIN", f"{a} {fi} > {ff}")
        elif ff > hoy:
            inf.aviso(C, "Fecha futura", f"{a} {ff}")
        for f in ("TIPO_ACT", "ALTITUD", "ANCHO_CM", "LARGO_CM", "PROFUN_MAX", "NMERO_UNE", "MAT_ARQUEO"):
            if r.get(f) in (None, "", 0) and not (f == "PROFUN_MAX" and r.get("TIPO_ACT") == "Recolección superficial"):
                inf.aviso(C, f"{f} vacío o 0", a)
        if r.get("ANCHO_CM") and r.get("LARGO_CM") and g.geom_type == "Polygon":
            an, la, modo = geom.ancho_largo(g)
            if geom.medidas_no_corresponden([r["ANCHO_CM"], r["LARGO_CM"]], (an, la)):
                inf.aviso(C, "ANCHO_CM/LARGO_CM no corresponden a la geometría",
                          f"{a} {r.get('TIPO_ACT')}: campos {r['ANCHO_CM']}×{r['LARGO_CM']} cm, geometría {an:.0f}×{la:.0f} cm ({modo})")
    for a, n in vistos.items():
        if n > 1:
            inf.error(C, "ID duplicado", f"{a} ×{n}")
    ids = list(ACTG)
    if ids:
        tree = STRtree([ACTG[a] for a in ids])
        for i, a in enumerate(ids):
            for j in tree.query(ACTG[a]):
                b = ids[int(j)]
                if b <= a:
                    continue
                inter = ACTG[a].intersection(ACTG[b]).area
                if inter < TOL:
                    continue
                tipo = "contenida" if inter > 0.95 * min(ACTG[a].area, ACTG[b].area) else "parcial"
                inf.info(C, f"Solape entre actividades ({tipo})", f"{a} ({ACT[a].get('TIPO_ACT')}) × {b} ({ACT[b].get('TIPO_ACT')}): {inter:.2f} m²")

    # ------------------------------------------------ unidad mínima
    U = "UNIDAD MINIMA"
    UNI = {}
    for _, uid, tipo, desc in M.unidades():
        UNI[uid] = (tipo, str(desc or ""))
        if re.search(r"sin descripci[oó]n", str(desc or ""), re.I):
            inf.aviso(U, "Descripción de relleno («sin descripción»)", f"{uid} {str(desc)[:70]}")

    # ------------------------------------------------ materiales y estructuras
    REF = collections.Counter()
    ACT_HAS = collections.defaultdict(collections.Counter)
    UNI_ACT = collections.defaultdict(set)
    UNIDEPTH = collections.defaultdict(list)
    ALLIDS = collections.Counter()
    for L in M.capas_materiales():
        mat = MATERIALES.get(rutas.norm(L))
        idf = mat.campo if mat else None
        for rec, s in M.registros(L):
            rid, a, u = rec.get(idf), rec.get("ID_ACT_ARQ"), rec.get("ID_UNI_EX")
            ALLIDS[rid] += 1
            if a not in ACT:
                inf.error(L, "ID_ACT_ARQ inexistente", f"{rid} → {a}")
                continue
            ACT_HAS[a][rutas.norm(L)] += 1
            if u:
                REF[u] += 1
                UNI_ACT[u].add(a)
                if u not in UNI:
                    inf.error(L, "ID_UNI_EX inexistente", f"{rid} → {u}")
            elif "ID_UNI_EX" in rec:
                inf.error(L, "Material sin unidad (ID_UNI_EX vacío)", rid)
            pi, pf = rec.get("PROFUN_INI"), rec.get("PROFUN_FIN")
            if pi is not None and pf is not None and u:
                UNIDEPTH[u].append((pi, pf))
            if not s.points:
                continue
            g = shape(s.__geo_interface__)
            if rutas.norm(L) == "ESTRUCTURAS":
                if not g.is_valid:
                    inf.error(L, "Geometría inválida", rid)
                    g = g.buffer(0)
                fuera = g.difference(ACTG.get(a, g)).area
                if fuera > TOL and fuera > 0.05 * g.area:
                    inf.aviso(L, "Estructura fuera de su actividad", f"{rid}: {fuera:.2f} m² ({100 * fuera / g.area:.0f} %)")
                if g.area < 0.005:
                    inf.aviso(L, "Estructura de área mínima (< 0.005 m²)", f"{rid} {g.area:.4f} m²")
            elif a in ACTG and not ACTG[a].buffer(0.02).contains(Point(s.points[0][:2])):
                inf.aviso(L, "Punto fuera de su actividad", rid)
    for rid, n in ALLIDS.items():
        if n > 1:
            inf.error("MATERIALES", "ID duplicado", f"{rid} ×{n}")
    for u, acts in UNI_ACT.items():
        if len(acts) > 1:
            inf.aviso(U, "Unidad compartida entre actividades", f"{u} → {sorted(acts)}")

    # ------------------------------------------------ rásteres (ortoplanos)
    R = "RASTER"
    RD = M.carpeta_raster()
    RAS = collections.defaultdict(list)
    try:
        import rasterio
    except ImportError:
        rasterio = None
        if RD:
            inf.info(R, "rasterio no instalado: no se revisan CRS ni extensión de los rásteres")
    for fn in sorted(os.listdir(RD)) if RD else []:
        if fn.startswith("."):
            continue
        if not fn.lower().endswith((".tif", ".tiff")):
            inf.aviso(R, "Archivo que no es GeoTIFF en la carpeta Raster", fn)
            continue
        m = re.match(r"^(\w+?(?:PI|DI)\d{5})_(\w+?N[PD]\d{4})\.tiff?$", fn)
        if not m:
            inf.error(R, "Nombre de ortoplano inválido (esperado <ID_ACT_ARQ>_<ID_UNI_EX>.tif)", fn)
            continue
        a, u = m.groups()
        RAS[a].append(u)
        if a not in ACT:
            inf.error(R, "Ortoplano de actividad inexistente", fn)
            continue
        if u not in UNI:
            inf.error(R, "Ortoplano de unidad inexistente", fn)
        elif u in UNI_ACT and a not in UNI_ACT[u]:
            inf.aviso(R, "Ortoplano con unidad de otra actividad", f"{fn} (unidad usada en {sorted(UNI_ACT[u])})")
        if rasterio:
            with rasterio.open(os.path.join(RD, fn)) as d:
                if not d.crs or d.crs.to_epsg() != 9377:
                    inf.error(R, "CRS del ortoplano distinto a EPSG:9377 (CTM12)", f"{fn}: {d.crs}")
                if a in ACTG and not box(*d.bounds).intersects(ACTG[a]):
                    inf.error(R, "Ortoplano no cubre su actividad", fn)
    for a, r in ACT.items():
        nmat = sum(v for k, v in ACT_HAS[a].items() if k != "ESTRUCTURAS")
        if r.get("TIPO_ACT") in TIPOS_CON_ORTOPLANO and nmat and not RAS.get(a):
            inf.error(R, "Ortoplano faltante (Corte/Cuadrícula/Trinchera con materiales)", f"{a} {r.get('TIPO_ACT')}")

    # ------------------------------------------------ coherencia actividad ↔ contenido
    for a, r in ACT.items():
        nmat = sum(v for k, v in ACT_HAS[a].items() if k != "ESTRUCTURAS")
        nest = ACT_HAS[a]["ESTRUCTURAS"]
        if r.get("MAT_ARQUEO") == "Positivo" and not nmat and not nest:
            inf.aviso(C, "MAT_ARQUEO Positivo sin registros de materiales", f"{a} {r.get('TIPO_ACT')}")
        if r.get("MAT_ARQUEO") == "Negativo" and (nmat or nest):
            inf.error(C, "MAT_ARQUEO Negativo con registros", f"{a} ({nmat} materiales, {nest} estructuras)")
        nu = len({u for u, acts in UNI_ACT.items() if a in acts})
        if r.get("NMERO_UNE") and nu and r["NMERO_UNE"] < nu:
            inf.aviso(C, "NMERO_UNE menor que las unidades usadas", f"{a} NMERO_UNE {r['NMERO_UNE']} < {nu}")
        deps = [pf for u, acts in UNI_ACT.items() if a in acts for _, pf in UNIDEPTH[u] if pf]
        if deps and r.get("PROFUN_MAX") and max(deps) > r["PROFUN_MAX"] + 5:
            inf.aviso(C, "PROFUN_MAX menor que la profundidad de sus registros", f"{a} PROFUN_MAX {r['PROFUN_MAX']} < {max(deps)}")
    for u in UNI:
        if not REF[u] and not any(u in us for us in RAS.values()):
            inf.aviso(U, "Unidad sin uso (sin materiales ni ortoplano)", f"{u} {UNI[u][1][:50]}")

    # ------------------------------------------------ metadato: conteos por capa
    MD = "METADATO"
    mp = M.ruta_metadato()
    if not mp:
        inf.error(MD, "No existe Metadato/*.xlsx")
    else:
        try:
            mw = openpyxl.load_workbook(mp, data_only=True)
            txt = "\n".join(str(c.value) for ws in mw.worksheets for row in ws.iter_rows() for c in row if c.value is not None)
            counts = collections.Counter()
            for a in ACT:
                counts.update(ACT_HAS[a])
            counts["ACTIVIDADES ARQUEOLOGICAS"] = len(ACT)
            for L, n in counts.items():
                if n and not re.search(rf"(?<!\d){n}(?!\d)", txt):
                    inf.aviso(MD, "Conteo de la capa no aparece en el metadato", f"{L}: {n}")
        except Exception as e:  # archivo dañado o protegido
            inf.error(MD, "Metadato no legible", str(e))

    inf.datos = dict(actividades=len(ACT), unidades=len(UNI), ortoplanos=sum(len(v) for v in RAS.values()),
                     materiales_por_capa=dict(sum((ACT_HAS[a] for a in ACT), collections.Counter())))
    return inf
