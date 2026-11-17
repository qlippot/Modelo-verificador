"""Estructura común de resultados de las verificaciones (serializable a JSON para CLI / MCP / WebApp)."""
import collections

NIVELES = ("ERROR", "AVISO", "INFO")


class Informe:
    def __init__(self, modulo):
        self.modulo = modulo
        self.hallazgos = []      # dicts: nivel, capa, regla, detalle
        self.datos = {}          # resúmenes / conteos propios de cada módulo

    def add(self, capa, regla, detalle="", nivel="ERROR"):
        assert nivel in NIVELES
        self.hallazgos.append(dict(nivel=nivel, capa=capa, regla=regla, detalle=str(detalle)))

    def error(self, capa, regla, detalle=""):
        self.add(capa, regla, detalle, "ERROR")

    def aviso(self, capa, regla, detalle=""):
        self.add(capa, regla, detalle, "AVISO")

    def info(self, capa, regla, detalle=""):
        self.add(capa, regla, detalle, "INFO")

    def conteo(self):
        return dict(collections.Counter(h["nivel"] for h in self.hallazgos))

    def resumen(self, ejemplos=5):
        """{nivel · capa · regla: {n, ejemplos}}"""
        g = collections.defaultdict(list)
        for h in self.hallazgos:
            g[(NIVELES.index(h["nivel"]), h["nivel"], h["capa"], h["regla"])].append(h["detalle"])
        return {f"{n} · {c} · {r}": dict(n=len(v), ejemplos=v[:ejemplos]) for (_, n, c, r), v in sorted(g.items())}

    def to_dict(self, completo=False, ejemplos=5):
        d = dict(modulo=self.modulo, conteo=self.conteo(), datos=self.datos, resumen=self.resumen(ejemplos))
        if completo:
            d["hallazgos"] = self.hallazgos
        return d
