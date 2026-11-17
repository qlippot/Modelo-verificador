import os
import importlib.util

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DS = os.path.join(RAIZ, "datos_sinteticos")
_sp = importlib.util.spec_from_file_location("generar", os.path.join(DS, "generar.py"))
GEN = importlib.util.module_from_spec(_sp)
_sp.loader.exec_module(GEN)


@pytest.fixture(scope="session")
def datos(tmp_path_factory):
    """Datos sintéticos regenerados en una carpeta temporal (los del repositorio no se tocan)."""
    return GEN.construir_todo(str(tmp_path_factory.mktemp("sinteticos")))
