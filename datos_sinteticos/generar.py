"""Genera los datos sintéticos de prueba (deterministas, todo ficticio).

Uso:  python datos_sinteticos/generar.py [carpeta_destino]     (por defecto, esta carpeta)

Crea:
  modelo_minimo/        Modelo V4 completo y correcto: debe pasar la verificación con 0 ERRORES y 0 AVISOS.
  modelo_con_errores/   El mismo Modelo con un error sembrado por regla (lista en MUTACIONES y esperado_errores.json),
                        y carpetas sin tildes («Documentacion…»), como en muchos Modelos reales.
  bd_materiales.xlsx    Base de datos de materiales para el codificador (con casos difíciles a propósito).
  config.json           Configuración del codificador para esa BD.

Proyecto ficticio: registro R0000A00, polígono específico R0000A000001, coordenadas CTM12 inventadas.
"""
import os
import sys
import copy
import shutil
import datetime

import numpy as np
import openpyxl
import shapefile
import rasterio
from rasterio.transform import from_bounds

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
from modelo_verificador import rutas  # noqa: E402

REG, PE = "R0000A00", "R0000A000001"
X0, Y0 = 4880000.0, 2070000.0           # origen ficticio (Este, Norte) en CTM12
D = datetime.date


def act_id(n):
    return f"{PE}PI{n:05d}"


def uni_id(n):
    return f"{PE}NP{n:04d}"


def rect(x, y, w, h):
    """Anillo horario cerrado, en metros relativos al origen."""
    return [(X0 + x, Y0 + y), (X0 + x, Y0 + y + h), (X0 + x + w, Y0 + y + h), (X0 + x + w, Y0 + y), (X0 + x, Y0 + y)]


# ============================================================== datos del Modelo mínimo
def datos_base():
    d = {}
    d["POLIGONO GENERAL"] = [dict(geom=rect(0, 0, 200, 200), REGIS_AUTO=REG, NOMBRE_PRO="Proyecto sintético de prueba",
                                  TITULAR="Titular ficticio")]
    d["POLIGONOS ESPECIFICOS"] = [dict(geom=rect(0, 0, 200, 200), REGIS_AUTO=REG, ID_POL_ESP=PE, NOMBRE_PRO="Proyecto sintético de prueba",
                                       NOMBRE_POL="Polígono sintético 1", NUMERA_POL="0001", FASE="Implementación de PMA",
                                       FECHA_PMA=D(2024, 11, 1), CODIGO_PMA="PMA-0000")]
    d["ZONIFICACION ARQUEOLOGICA"] = [
        dict(geom=rect(0, 0, 100, 200), ID_ZON_ARQ=f"{PE}ZO0001", ID_POL_ESP=PE, POTENCIAL="Alto"),
        dict(geom=rect(100, 0, 100, 200), ID_ZON_ARQ=f"{PE}ZO0002", ID_POL_ESP=PE, POTENCIAL="Bajo"),
    ]
    #       n  tipo                       x    y    w    h    corte prof une  mat         fechas
    acts = [(1, "Corte", 20, 20, 2, 2, 1, 60, 2, "Positivo", (D(2025, 2, 3), D(2025, 2, 7))),
            (2, "Corte", 40, 20, 2, 2, 2, 60, 2, "Positivo", (D(2025, 2, 10), D(2025, 2, 14))),
            (3, "Trinchera", 60, 20, 1, 20, None, 120, 2, "Positivo", (D(2025, 2, 17), D(2025, 2, 28))),
            (4, "Pozo de sondeo", 120, 50, 0.5, 0.5, None, 100, 1, "Negativo", (D(2025, 3, 3), D(2025, 3, 3))),
            (5, "Recolección superficial", 140, 140, 10, 10, None, 0, 1, "Positivo", (D(2025, 3, 4), D(2025, 3, 4))),
            (6, "Monitoreo", 150, 20, 5, 5, None, 150, 1, "Negativo", (D(2025, 3, 5), D(2025, 3, 20)))]
    d["ACTIVIDADES ARQUEOLOGICAS"] = [
        dict(geom=rect(x, y, w, h), ID_ACT_ARQ=act_id(n), ID_POL_ESP=PE, RNA_ARQ_L=1, RNA_ARQ=1, FECHA_INI=f[0], FECHA_FIN=f[1],
             TIPO_ACT=t, CORTE=c, ALTITUD=2600, ANCHO_CM=round(min(w, h) * 100), LARGO_CM=round(max(w, h) * 100),
             PROFUN_MAX=p, NMERO_UNE=u, MAT_ARQUEO=m, _rect=(x, y, w, h))
        for n, t, x, y, w, h, c, p, u, m, f in acts]
    d["UNIDADES"] = [
        (uni_id(1), "Unidad estratigráfica", "PI00001-E1: Relleno limo arenoso pardo oscuro. Profundidad: 0 - 30 cm."),
        (uni_id(2), "Unidad estratigráfica", "PI00001-E2: Arcilla compacta con fragmentos de ladrillo. Profundidad: 30 - 60 cm."),
        (uni_id(3), "Unidad estratigráfica", "PI00002-E1: Capa vegetal. Profundidad: 0 - 25 cm."),
        (uni_id(4), "Unidad estratigráfica", "PI00002-E2: Relleno con carbón disperso. Profundidad: 25 - 60 cm."),
        (uni_id(5), "Unidad estratigráfica", "PI00003-E1: Relleno antrópico heterogéneo. Profundidad: 0 - 40 cm."),
        (uni_id(6), "Unidad estratigráfica", "PI00003-E2: Nivel de cimentación. Profundidad: 40 - 120 cm."),
        (uni_id(7), "Superficie", "PI00005-RS: Recolección de materiales en superficie. Profundidad: 0 - 0 cm."),
    ]

    def p(n, dx, dy):  # punto dentro de la actividad n
        x, y, *_ = next(a["_rect"] for a in d["ACTIVIDADES ARQUEOLOGICAS"] if a["ID_ACT_ARQ"] == act_id(n))
        return (X0 + x + dx, Y0 + y + dy)

    cer = dict(INTEGRIDAD="Fragmento", UNID_CONJU="Unidad", FORMA="", CANT_CONJU=1, TIPO_CERAM="Loza fina",
               NOMBRE_PER="Sin identificar", OBSERVACI="Registro sintético")
    d["CERAMICAS"] = [
        dict(cer, geom=p(1, .5, .5), ID_CERAMIC=act_id(1) + "C0001", ID_ACT_ARQ=act_id(1), ID_UNI_EX=uni_id(1), PROFUN_INI=10, PROFUN_FIN=20),
        dict(cer, geom=p(1, 1.5, .5), ID_CERAMIC=act_id(1) + "C0002", ID_ACT_ARQ=act_id(1), ID_UNI_EX=uni_id(2), PROFUN_INI=35, PROFUN_FIN=45,
             FORMA="Plato"),
        dict(cer, geom=p(2, 1, 1), ID_CERAMIC=act_id(2) + "C0001", ID_ACT_ARQ=act_id(2), ID_UNI_EX=uni_id(3), PROFUN_INI=5, PROFUN_FIN=15),
        dict(cer, geom=p(3, .5, 3), ID_CERAMIC=act_id(3) + "C0001", ID_ACT_ARQ=act_id(3), ID_UNI_EX=uni_id(5), PROFUN_INI=10, PROFUN_FIN=30),
        dict(cer, geom=p(3, .5, 12), ID_CERAMIC=act_id(3) + "C0002", ID_ACT_ARQ=act_id(3), ID_UNI_EX=uni_id(6), PROFUN_INI=60, PROFUN_FIN=90,
             UNID_CONJU="Conjunto", CANT_CONJU=4),
        dict(cer, geom=p(5, 3, 3), ID_CERAMIC=act_id(5) + "C0001", ID_ACT_ARQ=act_id(5), ID_UNI_EX=uni_id(7), PROFUN_INI=0, PROFUN_FIN=0),
        dict(cer, geom=p(5, 7, 6), ID_CERAMIC=act_id(5) + "C0002", ID_ACT_ARQ=act_id(5), ID_UNI_EX=uni_id(7), PROFUN_INI=0, PROFUN_FIN=0,
             TIPO_CERAM="Mayólica"),
    ]
    met = dict(TIPO="Metal", COMPOSICIO="Hierro", TIPO_OBJEC="Clavo", EST_CONSER="Regular", OBSERVACI="Registro sintético")
    d["METALES"] = [
        dict(met, geom=p(1, 1, 1.5), ID_METALES=act_id(1) + "M0001", ID_ACT_ARQ=act_id(1), ID_UNI_EX=uni_id(2), PROFUN_INI=40, PROFUN_FIN=50),
        dict(met, geom=p(3, .5, 15), ID_METALES=act_id(3) + "M0001", ID_ACT_ARQ=act_id(3), ID_UNI_EX=uni_id(6), PROFUN_INI=45, PROFUN_FIN=55,
             COMPOSICIO="Cobre", TIPO_OBJEC="Botón", EST_CONSER="Bueno"),
    ]
    d["OSEOS ANIMALES"] = [
        dict(geom=p(2, .5, 1.5), ID_OSEOS_A=act_id(2) + "OA0001", ID_ACT_ARQ=act_id(2), ID_UNI_EX=uni_id(4), ESP_CONJU="Espécimen",
             IDENTIFICA="Fémur", LATERALIDA="Izquierda", CLASE="Mammalia", ORDEN="Artiodactyla", FAMILIA="Bovidae", GENERO="Bos",
             ESPECIE="Bos taurus", SEXO="Indeterminado", ALT_NO_ANT="", ALTERA_ANT="", COMPLETI="Fragmentado",
             OBSERVACI="Registro sintético", PROFUN_INI=30, PROFUN_FIN=40)]
    d["VIDRIOS"] = [
        dict(geom=p(5, 5, 5), ID_VIDRIOS=act_id(5) + "V0001", ID_ACT_ARQ=act_id(5), ID_UNI_EX=uni_id(7), UNID_CONJU="Unidad",
             FORMA="Botella cerveza", MET_PRODUC="Automático", TECNICA="Automático", COLOR="Ámbar", TIPO_OBJEC="Botella",
             OBSERVACI="Registro sintético", PROFUN_INI=0, PROFUN_FIN=0)]
    d["ESTRUCTURAS"] = [
        dict(geom=rect(20.2, 20.9, 1.6, 0.25), ID_EST=act_id(1) + "E0001", ID_ACT_ARQ=act_id(1), ID_UNI_EX=uni_id(2), TIPO_OBJEC="Muros",
             DESCRIPCIO="Muro de ladrillo cocido (sintético)", OBSERVACI="Trazado sintético", PROFUN_INI=30, PROFUN_FIN=60),
        dict(geom=rect(60.1, 30, 0.6, 6), ID_EST=act_id(3) + "E0001", ID_ACT_ARQ=act_id(3), ID_UNI_EX=uni_id(6), TIPO_OBJEC="Cimientos",
             DESCRIPCIO="Cimiento en piedra (sintético)", OBSERVACI="Trazado sintético", PROFUN_INI=40, PROFUN_FIN=120),
    ]
    # ortoplanos: <ID_ACT>_<ID_UNI>.tif sobre la actividad
    d["RASTER"] = [(act_id(1), uni_id(2)), (act_id(2), uni_id(4)), (act_id(3), uni_id(6))]
    d["RASTER_EXTRA"] = []
    d["CARPETAS_SIN_TILDE"] = False
    d["METADATO_PENDIENTE"] = []        # [(hoja, etiqueta)] filas que se dejan sin diligenciar
    return d


# ============================================================== errores sembrados
def _buscar(lista, campo, valor):
    return next(x for x in lista if x[campo] == valor)


def _mover(geom, dx, dy):
    if isinstance(geom, tuple):
        return (geom[0] + dx, geom[1] + dy)
    return [(x + dx, y + dy) for x, y in geom]


MUTACIONES = {
    "id_material_mal_formado": lambda d: d["CERAMICAS"][0].update(ID_CERAMIC=act_id(1) + "C001"),
    "fuera_de_dominio_metales": lambda d: d["METALES"][0].update(COMPOSICIO="Acero"),
    "fuera_de_dominio_zonificacion": lambda d: d["ZONIFICACION ARQUEOLOGICA"][0].update(POTENCIAL="ALTO"),
    "punto_fuera_de_actividad": lambda d: d["CERAMICAS"][1].update(geom=_mover(d["CERAMICAS"][1]["geom"], 10, 0)),
    "unidad_inexistente": lambda d: d["CERAMICAS"][3].update(ID_UNI_EX=uni_id(99)),
    "id_duplicado": lambda d: d["OSEOS ANIMALES"].append(dict(d["OSEOS ANIMALES"][0], geom=_mover(d["OSEOS ANIMALES"][0]["geom"], .3, 0))),
    "profundidad_invertida": lambda d: d["METALES"][1].update(PROFUN_INI=50, PROFUN_FIN=45),
    "fecha_ini_mayor_que_fin": lambda d: _buscar(d["ACTIVIDADES ARQUEOLOGICAS"], "ID_ACT_ARQ", act_id(2)).update(FECHA_INI=D(2025, 2, 20)),
    "fecha_siglo_errado": lambda d: _buscar(d["ACTIVIDADES ARQUEOLOGICAS"], "ID_ACT_ARQ", act_id(6)).update(FECHA_INI=D(1925, 3, 5)),
    "actividad_fuera_de_poligonos": lambda d: _buscar(d["ACTIVIDADES ARQUEOLOGICAS"], "ID_ACT_ARQ", act_id(6)).update(
        geom=_mover(_buscar(d["ACTIVIDADES ARQUEOLOGICAS"], "ID_ACT_ARQ", act_id(6))["geom"], 80, 0)),
    "ancho_con_cero_de_mas": lambda d: _buscar(d["ACTIVIDADES ARQUEOLOGICAS"], "ID_ACT_ARQ", act_id(1)).update(ANCHO_CM=2000),
    "negativo_con_materiales": lambda d: _buscar(d["ACTIVIDADES ARQUEOLOGICAS"], "ID_ACT_ARQ", act_id(5)).update(MAT_ARQUEO="Negativo"),
    "estructura_fuera_de_actividad": lambda d: d["ESTRUCTURAS"][1].update(geom=_mover(d["ESTRUCTURAS"][1]["geom"], 3, 0)),
    "unidad_sin_descripcion": lambda d: d.__setitem__("UNIDADES", [(u, t, "" if u == uni_id(3) else x) for u, t, x in d["UNIDADES"]]),
    "ortoplano_faltante": lambda d: d.__setitem__("RASTER", [r for r in d["RASTER"] if r[0] != act_id(3)]),
    "raster_nombre_invalido": lambda d: d["RASTER_EXTRA"].append(("ortoplano_corte1.tif", act_id(1))),
    "metadato_sin_diligenciar": lambda d: d["METADATO_PENDIENTE"].append(("CERÁMICAS", "RESUMEN")),
    "carpetas_sin_tilde": lambda d: d.__setitem__("CARPETAS_SIN_TILDE", True),
}


# ============================================================== escritura
def _escribir_capa(raiz, capa, filas):
    base = rutas.buscar_capa(raiz, capa)
    r = shapefile.Reader(base, encoding="utf-8")
    campos, st = r.fields[1:], r.shapeType
    r.close()
    for ext in (".shp", ".shx", ".dbf"):
        os.remove(base + ext)
    w = shapefile.Writer(base, shapeType=st, encoding="utf-8")
    for f in campos:
        w.field(*f)
    for fila in filas:
        g = fila["geom"]
        if st == shapefile.POINT:
            w.point(*g)
        else:
            w.poly([g])
        w.record(*[fila.get(f[0]) for f in campos])
    w.close()


def _unidades(raiz, filas):
    p = rutas.buscar_unidad_minima(raiz)
    wb = openpyxl.load_workbook(p)
    ws = wb.active
    for f in filas:
        ws.append(list(f))
    wb.save(p)


def _ortoplano(ruta, anillo):
    xs, ys = [p[0] for p in anillo], [p[1] for p in anillo]
    b = (min(xs) - .2, min(ys) - .2, max(xs) + .2, max(ys) + .2)
    w = h = 64
    img = np.full((3, h, w), 235, dtype=np.uint8)
    img[:, ::8, :] = 120
    img[:, :, ::8] = 120
    with rasterio.open(ruta, "w", driver="GTiff", width=w, height=h, count=3, dtype="uint8", crs="EPSG:9377",
                       transform=from_bounds(*b, w, h), compress="deflate") as dst:
        dst.write(img)


HOJA_A_CAPA = {"MUESTRA DE SUELOS": "MUESTRAS DE SUELOS", "ANOMALIAS CON SENSORES R": "ANOMALIAS CON SENSORES REMOTOS"}


def _metadato(raiz, conteos, pendientes):
    p = rutas.buscar_metadato(raiz)
    wb = openpyxl.load_workbook(p)
    entregadas = {c for c, n in conteos.items() if n}
    for ws in wb.worksheets:
        hoja = rutas.norm(ws.title)
        capa = HOJA_A_CAPA.get(hoja, hoja)
        general = hoja == "METADATO"
        entrega = general or capa in entregadas
        for row in ws.iter_rows(min_row=3):
            celda = ws.cell(row=row[0].row, column=6)
            if not str(celda.value or "").startswith("Diligenciar"):
                continue
            et = rutas.norm(ws.cell(row=row[0].row, column=3).value or "")
            if (ws.title.strip(), et.split(".")[0]) in [(h, e) for h, e in pendientes]:
                continue
            if et.startswith("CONFIRMAR LA ENTREGA"):
                v = "SI" if entrega else "NO"
            elif not entrega:
                v = "No aplica"
            elif et.startswith("AVANCE"):
                v = "Completo"
            elif et.startswith("FECHA"):
                v = "2025-03-31"
            elif et.startswith("RESUMEN"):
                v = "Modelo sintético de prueba." if general else f"Capa {ws.title.strip()} del Modelo sintético de prueba."
            elif et.startswith("NUMERO DE OBJETOS") or et.startswith("NUMERO TOTAL"):
                v = conteos.get(capa, 0)
            elif et.startswith("NUMERO DE CAPAS"):
                v = len(entregadas)
            elif et.startswith("RESPONSABLE") or et.startswith("PUNTO DE CONTACTO"):
                v = "Equipo sintético"
            elif et.startswith("TELEFONO"):
                v = "0000000000"
            elif et.startswith("CORREO"):
                v = "contacto@ejemplo.org"
            elif et.startswith("NUMERO DE RESOLUCION"):
                v = "Resolución 0000 de 2024"
            elif et.startswith("ANO DE APROBACION"):
                v = 2024
            elif et.startswith("EL POLIGONO HA SUFRIDO"):
                v = "NO"
            elif et.startswith("RESOLUCION U OFICIO"):
                v = "No aplica"
            else:
                v = "Dato sintético"
            celda.value = v
    wb.save(p)


SIN_TILDE = {"Documentación Actividades Arqueológicas": "Documentacion Actividades Arqueologicas",
             "Documentación Materiales Arqueológicos": "Documentacion Materiales Arqueologicos",
             "Zonificación Arqueológica": "Zonificacion Arqueologica"}


def construir(destino, d):
    if os.path.exists(destino):
        shutil.rmtree(destino)
    shutil.copytree(rutas.PLANTILLAS, destino, ignore=shutil.ignore_patterns(".DS_Store"))
    if d["CARPETAS_SIN_TILDE"]:
        for a, b in SIN_TILDE.items():
            os.rename(os.path.join(destino, a), os.path.join(destino, b))
    rutas.limpiar_cache()
    capas = ["POLIGONO GENERAL", "POLIGONOS ESPECIFICOS", "ZONIFICACION ARQUEOLOGICA", "ACTIVIDADES ARQUEOLOGICAS",
             "CERAMICAS", "METALES", "OSEOS ANIMALES", "VIDRIOS", "ESTRUCTURAS"]
    for c in capas:
        _escribir_capa(destino, c, d[c])
    _unidades(destino, d["UNIDADES"])
    rd = os.path.join(destino, "Raster")
    os.makedirs(rd)
    anillo = {a["ID_ACT_ARQ"]: a["geom"] for a in d["ACTIVIDADES ARQUEOLOGICAS"]}
    for a, u in d["RASTER"]:
        _ortoplano(os.path.join(rd, f"{a}_{u}.tif"), anillo[a])
    for nombre, a in d["RASTER_EXTRA"]:
        _ortoplano(os.path.join(rd, nombre), anillo[a])
    _metadato(destino, {c: len(d[c]) for c in capas}, d["METADATO_PENDIENTE"])
    rutas.limpiar_cache()
    return destino


def construir_minimo(destino):
    return construir(destino, datos_base())


def construir_errores(destino):
    d = datos_base()
    for f in MUTACIONES.values():
        f(d)
    return construir(destino, d)


# ============================================================== BD de materiales para el codificador
BD = {
    "Cerámica": (["Código", "Actividad", "Estrato", "Prof (cm)", "Integridad", "Cantidad", "Tipo", "Forma", "Observaciones"], [
        ["CE-001", "Corte 1", "E1", "5-10", "Fragmento", 1, "Loza fina", "", ""],
        ["CE-002", "CORTE  1", "e2", "", "Fragmento", 3, "Loza fina", "plato", "Tres bordes que remontan"],
        ["CE-003", "Corte 2", "E3", "70", "Fragmento", 1, "Gres", "", ""],
        ["CE-004", "Trinchera 1", "E1", "12-18", "Pieza completa", 1, "Mayólica", "olla",
         "Fragmento con decoración incisa y pintada en óxido de hierro; superficie erosionada en la cara externa, "
         "huellas de hollín en la base, restos de engobe crema en el borde. Comparación tipológica pendiente con colecciones "
         "de referencia; posible producción local de época republicana según pasta y acabado, sin confirmación."],
        ["CE-005", "Recolección superficial", "RS", "", "Fragmento", 2, "Loza fina", "", ""],
        ["CE-006", "Trinchera 7", "E1", "20", "Fragmento", 1, "", "", ""],
        ["CE-007", "", "", "", "Fragmento", 1, "", "", "Sin actividad registrada en campo"],
        ["CE-008", "Pozo 4", "E1", "40-50", "Fragmento", 1, "Loza fina", "", ""],
        ["", "Corte 1", "E1", "", "", "", "", "", "fila sin código: se ignora"],
        ["CE-010", "Pozo 9", "E1", "10", "Fragmento", 1, "", "", ""],
    ]),
    "Metales": (["ID", "Actividad", "Estrato", "Prof. inicial", "Prof. final", "Este", "Norte", "Tipo", "Composición", "Objeto", "Conservación"], [
        ["ME-001", "Corte 1", "E2", 35, 40, X0 + 21.0, Y0 + 21.0, "Metal", "Hierro", "Clavo forjado", "regular"],
        ["ME-002", "Trinchera 1", "E2", "", "", "", "", "Metal", "Cobre", "Botón", "BUENO"],
        ["ME-003", "trinchera 1", "E9", 200, 210, "", "", "Aleación", "Bronce", "Medalla", "malo"],
    ]),
    "Óseos": (["ID", "Actividad", "Estrato", "Profundidad", "Elemento", "Lado", "Cantidad", "Especie"], [
        ["OS-001", "Corte 2", "E2", "30-40", "Fémur", "izq", 1, "Bos taurus"],
        ["OS-002", "Corte 2", "E2", "", "Costilla", "", 4, ""],
    ]),
}

CONFIG = {
    "_comentario": "Configuración del codificador para bd_materiales.xlsx (datos sintéticos).",
    "modo": "reemplazar",
    "sin_profundidad": [0, 0],
    "actividades": {
        "exactas": {"Trinchera 1": act_id(3), "Recolección superficial": act_id(5)},
        "patrones": [{"regex": r"^corte\s*(\d+)$", "id": PE + "PI{1:05d}"},
                     {"regex": r"^pozo\s*(\d+)$", "id": PE + "PI{1:05d}"}],
        "por_defecto": act_id(5),
    },
    "unidades": {"superficie": ["RS"], "sin_estrato": "SE", "tipo": "Unidad estratigráfica", "fijas": {}},
    "hojas": {
        "Cerámica": {
            "capa": "CERAMICAS", "id_bd": "Código", "actividad": "Actividad", "estrato": "Estrato",
            "profundidad": {"rango": "Prof (cm)"},
            "campos": {
                "INTEGRIDAD": "Integridad",
                "UNID_CONJU": {"segun_cantidad": "Cantidad"},
                "CANT_CONJU": {"columna": "Cantidad", "defecto": 1},
                "FORMA": {"columna": "Forma", "mapa": {"plato": "Plato", "olla": "Olla"}},
                "TIPO_CERAM": {"columna": "Tipo", "defecto": "Sin identificar"},
                "NOMBRE_PER": {"valor": "Sin identificar"},
                "OBSERVACI": {"concatenar": [["", "Observaciones"], ["BD", "Código"]]},
            },
        },
        "Metales": {
            "capa": "METALES", "id_bd": "ID", "actividad": "Actividad", "estrato": "Estrato",
            "profundidad": {"ini": "Prof. inicial", "fin": "Prof. final"},
            "coordenadas": {"x": "Este", "y": "Norte"},
            "campos": {
                "TIPO": "Tipo", "COMPOSICIO": "Composición", "TIPO_OBJEC": "Objeto",
                "EST_CONSER": {"columna": "Conservación", "mapa": {"bueno": "Bueno", "regular": "Regular", "malo": "Malo"},
                               "defecto": "Sin identificar"},
                "OBSERVACI": {"concatenar": [["BD", "ID"]]},
            },
        },
        "Óseos": {
            "capa": "OSEOS ANIMALES", "id_bd": "ID", "actividad": "Actividad", "estrato": "Estrato",
            "profundidad": {"rango": "Profundidad"},
            "campos": {
                "ESP_CONJU": {"segun_cantidad": "Cantidad", "uno": "Espécimen", "varios": "Conjunto"},
                "IDENTIFICA": "Elemento",
                "LATERALIDA": {"columna": "Lado", "mapa": {"izq": "Izquierda", "der": "Derecha"}, "defecto": "Sin identificar"},
                "CLASE": {"valor": "Sin identificar"}, "ORDEN": {"valor": "Sin identificar"},
                "FAMILIA": {"valor": "Sin identificar"}, "GENERO": {"valor": "Sin identificar"},
                "ESPECIE": {"columna": "Especie", "defecto": "Sin identificar"},
                "SEXO": {"valor": "Indeterminado"}, "COMPLETI": {"valor": "Fragmentado"},
                "OBSERVACI": {"concatenar": [["BD", "ID"]]},
            },
        },
    },
}


def construir_bd(destino_xlsx):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for hoja, (hdr, filas) in BD.items():
        ws = wb.create_sheet(hoja)
        ws.append(hdr)
        for f in filas:
            ws.append([None if v == "" else v for v in f])
    wb.properties.creator = None
    wb.save(destino_xlsx)
    return destino_xlsx


def construir_todo(carpeta=AQUI):
    import json
    construir_minimo(os.path.join(carpeta, "modelo_minimo"))
    construir_errores(os.path.join(carpeta, "modelo_con_errores"))
    construir_bd(os.path.join(carpeta, "bd_materiales.xlsx"))
    with open(os.path.join(carpeta, "config.json"), "w", encoding="utf-8") as f:
        json.dump(CONFIG, f, ensure_ascii=False, indent=2)
    return carpeta


if __name__ == "__main__":
    print("ok", construir_todo(sys.argv[1] if len(sys.argv) > 1 else AQUI))
