"""Verificación según la FASE del Programa de Arqueología Preventiva (PAP).

El catálogo ICANH organiza el Modelo por fases (hoja TEMAS / GRUPOS y dominio Dom_FASE):

* **Registro** — solo la Zona de Estudio (POLÍGONO GENERAL y POLÍGONOS ESPECÍFICOS). Los campos marcados
  «Obligación para el usuario posterior a la Fase de Registro» (REGIS_AUTO, ID_POL_ESP) aún no se exigen.
* **Diagnóstico** (diagnóstico y prospección → aprobación del PMA) — Zona de Estudio + Zonificación
  arqueológica + documentación de actividades y materiales. Actividades y unidades con código DI / ND.
* **Implementación** (implementación del PMA) — todo lo anterior; el PMA debe estar aprobado (FECHA_PMA,
  CODIGO_PMA). Actividades y unidades con código PI / NP (pueden convivir las DI de la fase anterior).

`filtrar` quita los hallazgos de capas que no corresponden a la fase; `verificar` añade las reglas propias
de la fase (campos exigidos, FASE de los polígonos y fase codificada en los IDs).
"""
from .. import catalogo as _cat, rutas
from ..modelo import Modelo
from .informe import Informe

ZONA_ESTUDIO = {"POLIGONO GENERAL", "POLIGONOS ESPECIFICOS"}

FASES = {
    "registro": dict(nombre="Registro", valores={"Registro"},
                     descripcion="Zona de Estudio: polígono general y polígonos específicos."),
    "diagnostico": dict(nombre="Diagnóstico y prospección", valores={"Diagnóstico y prospección", "Aprobación de PMA"},
                        descripcion="Zona de Estudio, Zonificación arqueológica y documentación de actividades y materiales (códigos DI / ND)."),
    "implementacion": dict(nombre="Implementación de PMA", valores={"Implementación de PMA", "Finalizado"},
                           descripcion="Todo el Modelo, con PMA aprobado (FECHA_PMA, CODIGO_PMA) y códigos PI / NP."),
}


def normalizar(fase):
    if fase in (None, ""):
        return None
    f = rutas.norm(fase).lower().replace(" ", "")
    for k in FASES:
        if f.startswith(k[:5]):
            return k
    raise ValueError(f"Fase desconocida: {fase!r}. Use una de: {', '.join(FASES)}")


def _hoja_metadato(regla):
    """«Sin diligenciar · hoja «X»» → X normalizado."""
    if "hoja «" in regla:
        return rutas.norm(regla.split("hoja «", 1)[1].rstrip("»"))
    return None


def corresponde(h, fase):
    """¿El hallazgo h aplica a la fase? (solo Registro recorta capas)."""
    if fase != "registro":
        return True
    capa = rutas.norm(h["capa"])
    if capa in ZONA_ESTUDIO or capa == "-":
        return True
    if capa == "METADATO":
        hoja = _hoja_metadato(h["regla"])
        return hoja is None or hoja in ZONA_ESTUDIO or hoja == "METADATO"
    return False


def filtrar(informe, fase):
    informe.hallazgos = [h for h in informe.hallazgos if corresponde(h, fase)]
    return informe


def verificar(modelo, fase):
    M = modelo if isinstance(modelo, Modelo) else Modelo(modelo)
    inf = Informe("fase")
    F = FASES[fase]
    cat = _cat.cargar()
    inf.datos = dict(fase=fase, nombre=F["nombre"], descripcion=F["descripcion"])

    # 1. Zona de estudio: FASE declarada en cada polígono específico
    PE = "POLIGONOS ESPECIFICOS"
    recs = [r for r, _ in M.registros(PE)]
    if not recs:
        inf.error(PE, "Capa vacía o inexistente")
    for i, r in enumerate(recs, start=1):
        quien = r.get("ID_POL_ESP") or f"fila {i}"
        v = str(r.get("FASE") or "").strip()
        if v and v not in F["valores"]:
            inf.aviso(PE, "FASE del polígono no corresponde a la fase elegida", f"{quien}: «{v}» (se eligió {F['nombre']})")

    if fase == "registro":
        return inf

    # 2. después del Registro: los campos «posterior a la Fase de Registro» pasan a ser obligatorios
    for capa in sorted(ZONA_ESTUDIO):
        posteriores = [a.nombre for a in cat.capa(capa).values() if "posterior" in a.obligacion.lower()]
        for i, (r, _) in enumerate(M.registros(capa), start=1):
            for f in posteriores:
                if f in r and str(r.get(f) or "").strip() == "":
                    inf.error(capa, f"Obligatorio después del Registro: {f}", f"fila {i}")

    # 3. capas que la fase debe entregar
    presentes = set(M.capas_presentes())
    if "ZONIFICACION ARQUEOLOGICA" not in presentes:
        (inf.error if fase == "diagnostico" else inf.aviso)(
            "ZONIFICACION ARQUEOLOGICA", "Falta la capa de la fase", "La zonificación se entrega para la aprobación del PMA")
    if "ACTIVIDADES ARQUEOLOGICAS" not in presentes:
        inf.error("ACTIVIDADES ARQUEOLOGICAS", "Falta la capa de la fase")

    # 4. fase codificada en los IDs de actividades (DI / PI)
    C = "ACTIVIDADES ARQUEOLOGICAS"
    for a in M.actividades():
        cod = str(a)[12:14] if len(str(a)) == 19 and str(a)[8] != "I" else None
        if fase == "diagnostico" and cod == "PI":
            inf.aviso(C, "Actividad de Implementación (PI) en una entrega de Diagnóstico", a)

    # 5. implementación: PMA aprobado
    if fase == "implementacion":
        for i, r in enumerate(recs, start=1):
            for f in ("FECHA_PMA", "CODIGO_PMA"):
                if str(r.get(f) or "").strip() == "":
                    inf.error(PE, f"Implementación sin PMA aprobado: {f} vacío", r.get("ID_POL_ESP") or f"fila {i}")
    return inf
