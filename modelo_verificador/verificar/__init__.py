"""Herramienta 1 — Verificación de un Modelo de Datos ICANH V4 (solo lectura).

    from modelo_verificador.verificar import verificar_todo
    res = verificar_todo("ruta/al/Modelo", fase="diagnostico")   # dict serializable a JSON

`fase` (registro / diagnostico / implementacion) limita la revisión a lo que se entrega en esa fase del PAP y
añade sus reglas propias; sin fase se revisa todo el Modelo.
"""
from ..modelo import Modelo
from . import formato, coherencia, faltantes, fase as _fase
from .explicaciones import explicar
from .informe import NIVELES

MODULOS = {"formato": formato.verificar, "coherencia": coherencia.verificar, "faltantes": faltantes.verificar}
FASES = _fase.FASES


def verificar_todo(raiz, modulos=("formato", "coherencia", "faltantes"), completo=False, ejemplos=5, fase=None):
    M = Modelo(raiz)
    fase = _fase.normalizar(fase)
    informes = [MODULOS[m](M) for m in modulos]
    if fase:
        informes = [_fase.filtrar(i, fase) for i in informes] + [_fase.verificar(M, fase)]
    total = {}
    for inf in informes:
        for k, v in inf.conteo().items():
            total[k] = total.get(k, 0) + v
    grupos = []
    for inf in informes:
        for clave, g in inf.resumen(ejemplos).items():
            nivel, capa, regla = clave.split(" · ", 2)
            grupos.append(dict(nivel=nivel, capa=capa, regla=regla, n=g["n"], ejemplos=g["ejemplos"],
                               modulo=inf.modulo, ayuda=explicar(regla)))
    grupos.sort(key=lambda g: (NIVELES.index(g["nivel"]), -g["n"]))
    return dict(modelo=M.raiz, fase=fase, fase_nombre=FASES[fase]["nombre"] if fase else None,
                capas=M.capas_presentes(), conteo=total, apto=total.get("ERROR", 0) == 0, grupos=grupos,
                modulos={i.modulo: i.to_dict(completo, ejemplos) for i in informes})
