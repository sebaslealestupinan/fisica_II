"""Renderiza las plantillas Jinja2 reales a HTML estático (sin FastAPI) para probarlas en un navegador.

Uso: python tests/render_sitio.py <carpeta_salida>
Crea <carpeta_salida>/ con las páginas y un enlace a app/static.
"""
import os
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

RAIZ = Path(__file__).resolve().parent.parent
salida = Path(sys.argv[1])
salida.mkdir(parents=True, exist_ok=True)
estatico = salida / "static"
if not estatico.exists():
    os.symlink(RAIZ / "app/static", estatico)

env = Environment(loader=FileSystemLoader(RAIZ / "app/templates"), autoescape=True)
env.globals["url_for"] = lambda nombre, path="": f"/static/{path}"


class R:  # resorte falso
    def __init__(self, id, nombre): self.id, self.nombre = id, nombre


resortes = [R(1, "Resorte 1"), R(2, "Resorte 2")]

# --- contexto realista para las tablas (misma forma que produce app/main.py) ---
sys.path.insert(0, str(RAIZ))
from app import fisica  # noqa: E402

_k_real = 24.0
_filas_k = []
for _i, _m in enumerate([0.1, 0.2, 0.3, 0.4], start=1):
    _dl = _m * fisica.G / _k_real * (1 + 0.01 * (-1) ** _i)   # pequeño error
    _filas_k.append({"id": _i, "masa": _m, "l0": 0.15, "lf": 0.15 + _dl, "dl": _dl, "k": fisica.constante_k(_m, _dl)})
_ks = [f["k"] for f in _filas_k]
_kprom = sum(_ks) / len(_ks)
_kstd = (sum((k - _kprom) ** 2 for k in _ks) / (len(_ks) - 1)) ** 0.5
_filas_p = []
for _i, (_m, _n, _t) in enumerate([(0.1, 10, 4.1), (0.2, 10, 5.8), (0.3, 10, 7.3)], start=1):
    _te = fisica.periodo_experimental(_t, _n); _tt = fisica.periodo_teorico(_m, _kprom)
    _filas_p.append({"id": _i, "masa": _m, "n": _n, "t": _t, "t_exp": _te, "t_teo": _tt, "error": fisica.error_porcentual(_te, _tt)})
TK = {"rid": 1, "filas": _filas_k, "k_prom": _kprom, "k_std": _kstd, "error": None}
TP = {"rid": 1, "filas": _filas_p, "k_prom": _kprom, "error": None}

paginas = {
    "index.html": {"seccion": "inicio"},
    "modelo.html": {"seccion": "modelo"},
    "procedimiento.html": {"seccion": "procedimiento"},
    "simulador.html": {"seccion": "simulador", "resortes": resortes},
    "conclusiones.html": {"seccion": "conclusiones"},
    "datos.html": {"seccion": "datos", "resortes": resortes, "resorte": resortes[0], "tk": TK, "tp": TP},
    "comparacion.html": {"seccion": "comparacion", "resortes": resortes, "resorte": resortes[0]},
}
for nombre, ctx in paginas.items():
    p = RAIZ / "app/templates" / nombre
    if not p.exists():
        print("(aún no existe)", nombre)
        continue
    (salida / nombre).write_text(env.get_template(nombre).render(**ctx), encoding="utf-8")
    print("renderizada", nombre)

# --- fragmentos HTMX (para inspeccionarlos) ---
from types import SimpleNamespace as NS  # noqa: E402
parciales = {
    "tabla_k.html": TK, "tabla_p.html": {**TP, "oob": True},
    "fila_k_editar.html": {"f": NS(id=2, masa=0.2, longitud_inicial=0.15, longitud_final=0.2318), "rid": 1},
    "fila_p_editar.html": {"f": NS(id=2, masa=0.2, n_oscilaciones=10, tiempo_total=5.8), "rid": 1},
    "tabla_k_error.html": {**TK, "error": "La longitud final debe ser mayor que la inicial (el resorte se estira)."},
    "tabla_p_vacia.html": {"rid": 1, "filas": [], "k_prom": None, "error": None},
}
for nombre, ctx in parciales.items():
    plantilla = nombre.replace("_error", "").replace("_vacia", "")
    (salida / ("parcial_" + nombre)).write_text(env.get_template("partials/" + plantilla).render(**ctx), encoding="utf-8")
    print("parcial", nombre)
