"""Herramienta 1 — Verificación de un Modelo de Datos ICANH V4 (solo lectura).

    from modelo_verificador.verificar import verificar_todo
    res = verificar_todo("ruta/al/Modelo")      # dict serializable a JSON
"""
from ..modelo import Modelo
from . import formato, coherencia, faltantes

MODULOS = {"formato": formato.verificar, "coherencia": coherencia.verificar, "faltantes": faltantes.verificar}


def verificar_todo(raiz, modulos=("formato", "coherencia", "faltantes"), completo=False, ejemplos=5):
    M = Modelo(raiz)
    informes = [MODULOS[m](M) for m in modulos]
    total = {}
    for inf in informes:
        for k, v in inf.conteo().items():
            total[k] = total.get(k, 0) + v
    return dict(modelo=M.raiz, capas=M.capas_presentes(), conteo=total, apto=total.get("ERROR", 0) == 0,
                modulos={i.modulo: i.to_dict(completo, ejemplos) for i in informes})
