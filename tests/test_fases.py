"""Verificación por fase del PAP (Registro / Diagnóstico / Implementación) y explicaciones de reglas."""
import pytest

from modelo_verificador.verificar import verificar_todo
from modelo_verificador.verificar.fase import normalizar
from modelo_verificador.verificar.explicaciones import explicar


def reglas(r, modulo=None):
    return {g["regla"] for g in r["grupos"] if modulo is None or g["modulo"] == modulo}


def test_registro_solo_zona_de_estudio(datos):
    r = verificar_todo(f"{datos}/modelo_con_errores", fase="registro")
    capas = {g["capa"] for g in r["grupos"]}
    assert capas <= {"POLIGONO GENERAL", "POLIGONOS ESPECIFICOS", "METADATO", "-"}
    assert r["fase_nombre"] == "Registro"
    # el polígono sintético dice «Implementación de PMA»
    assert "FASE del polígono no corresponde a la fase elegida" in reglas(r, "fase")


def test_diagnostico_marca_actividades_pi(datos):
    r = verificar_todo(f"{datos}/modelo_minimo", fase="diagnostico")
    assert "Actividad de Implementación (PI) en una entrega de Diagnóstico" in reglas(r, "fase")
    assert r["apto"]


def test_implementacion_coincide_con_todo(datos):
    a = verificar_todo(f"{datos}/modelo_con_errores", fase="implementacion")
    b = verificar_todo(f"{datos}/modelo_con_errores")
    assert a["conteo"] == b["conteo"] and not reglas(a, "fase")


def test_grupos_ordenados_y_explicados(datos):
    r = verificar_todo(f"{datos}/modelo_con_errores")
    niveles = [g["nivel"] for g in r["grupos"]]
    assert niveles == sorted(niveles, key=["ERROR", "AVISO", "INFO"].index)
    assert sum(g["n"] for g in r["grupos"]) == sum(r["conteo"].values())
    assert all(g["ayuda"] for g in r["grupos"] if g["nivel"] == "ERROR")


def test_normalizar():
    assert normalizar("Diagnóstico") == "diagnostico" and normalizar("IMPLEMENTACION") == "implementacion"
    assert normalizar(None) is None
    with pytest.raises(ValueError):
        normalizar("otra")
    assert explicar("Fuera de dominio: FASE")


# ---------------------------------------------------------------- un Modelo correcto por fase
FASES = ("registro", "diagnostico", "implementacion")


def no_info(r):
    return sorted((g["nivel"], g["capa"], g["regla"]) for g in r["grupos"] if g["nivel"] != "INFO")


@pytest.mark.parametrize("fase", FASES)
def test_modelo_de_la_fase_sin_errores_ni_avisos(datos, fase):
    """Cada Modelo sintético, verificado en su propia fase, no produce ningún hallazgo adicional."""
    r = verificar_todo(f"{datos}/modelo_fase_{fase}", fase=fase)
    assert no_info(r) == [], no_info(r)
    assert r["apto"]


@pytest.mark.parametrize("modelo", FASES)
@pytest.mark.parametrize("fase", FASES)
def test_fase_cruzada_avisa_que_no_corresponde(datos, modelo, fase):
    if modelo == fase:
        return
    r = verificar_todo(f"{datos}/modelo_fase_{modelo}", fase=fase)
    assert "FASE del polígono no corresponde a la fase elegida" in reglas(r, "fase")


def test_registro_no_exige_campos_posteriores(datos):
    """REGIS_AUTO e ID_POL_ESP vacíos: válidos en Registro, error en cualquier fase posterior o sin fase."""
    m = f"{datos}/modelo_fase_registro"
    post = {"Obligatorio después del Registro: REGIS_AUTO", "Obligatorio después del Registro: ID_POL_ESP"}
    assert not post & reglas(verificar_todo(m, fase="registro"))
    for fase in (None, "diagnostico", "implementacion"):
        assert post <= reglas(verificar_todo(m, fase=fase)), fase


def test_implementacion_exige_pma(datos):
    r = verificar_todo(f"{datos}/modelo_fase_diagnostico", fase="implementacion")
    assert {"Implementación sin PMA aprobado: FECHA_PMA vacío",
            "Implementación sin PMA aprobado: CODIGO_PMA vacío"} <= reglas(r, "fase")
    assert not r["apto"]
