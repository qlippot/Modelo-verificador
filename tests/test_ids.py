"""Reglas de IDs del catálogo V4 (ejemplos tomados del propio catálogo, código de registro ficticio R0125A22)."""
from modelo_verificador import ids


def test_ejemplos_del_catalogo():
    assert ids.analizar("R0125A220005")["tipo"] == "poligono"
    assert ids.analizar("R0125A220005ZO0001")["tipo"] == "zonificacion"
    a = ids.analizar("R0125A220005DI00001")
    assert a["tipo"] == "actividad" and a["consecutivo"] == 1 and a["poligono"] == "R0125A220005"
    assert ids.analizar("R0125A220005ND0001")["tipo"] == "unidad"
    m = ids.analizar("R0125A220005DI00001OB0001")
    assert m["capa"] == "OTROS OBJETOS O MATERIALES" and m["valido"]
    assert ids.analizar("R0125A220005DI00001OBC0001")["capa"] == "OBJETOS COMPUESTOS"
    assert ids.analizar("R0125A220005DI00003A0001")["capa"] == "ANOMALIAS CON SENSORES REMOTOS"


def test_longitudes_de_materiales():
    act = "R0125A220005PI00001"
    for capa, m in ids.MATERIALES.items():
        c = ids.material(act, capa, 7)
        assert len(c) == m.longitud, capa
        assert ids.analizar(c)["capa"] == capa
        assert ids.es_valido(c, capa)


def test_invalidos():
    assert not ids.analizar("R0125A220005PI0001C0001")["valido"]          # consecutivo de actividad de 4
    assert not ids.es_valido("R0125A220005PI00001C001", "CERAMICAS")      # consecutivo de 3
    assert not ids.es_valido("R0125A220005XX00001", "actividad")


def test_generacion_y_contador():
    assert ids.actividad("R0125A220005", 12) == "R0125A220005PI00012"
    assert ids.unidad("R0125A220005", 3, fase="DI") == "R0125A220005ND0003"
    assert len(ids.actividad_intervencion("R0125A22", 1)) == 19
    assert len(ids.unidad_intervencion("R0125A22", 1)) == 18
    c = ids.Contador(["R0125A220005PI00001C0004", "R0125A220005PI00001C0002"])
    assert c.nuevo("R0125A220005PI00001C") == "R0125A220005PI00001C0005"
    assert c.nuevo("R0125A220005PI00002C") == "R0125A220005PI00002C0001"


def test_ajuste_por_bytes():
    from modelo_verificador.texto import ajustar
    t = ajustar("á" * 200, 254)
    assert len(t.encode("utf-8")) <= 254 and t.endswith("…")
