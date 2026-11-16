"""Verifica la solución analítica (Python y JS) contra una integración RK4 independiente.

Uso:  python tests/test_fisica.py     (requiere numpy y node en el PATH)
"""
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from app import fisica  # noqa: E402

CASOS = [
    ("ideal",            0.20, 20.0, 0.00, 0.08, 0.0),
    ("ideal con fase",   0.20, 20.0, 0.00, 0.08, math.pi / 3),
    ("subamortiguado",   0.20, 20.0, 0.60, 0.08, 0.0),
    ("subamort. fase",   0.50, 35.0, 1.20, 0.05, 1.0),
    ("critico exacto",   0.25, 25.0, 5.00, 0.10, 0.0),   # bc = 2*sqrt(25*0.25) = 5
    ("casi critico",     0.20, 20.0, 4.0001, 0.08, 0.0),
    ("sobreamortiguado", 0.20, 20.0, 10.0, 0.08, 0.0),
    ("sobre extremo",    0.05, 200., 30.0, 0.20, 0.0),   # r*t enorme: prueba desbordamiento
]


def rk4(m, k, b, x0, v0, t):
    xs = np.zeros_like(t)
    x, v = x0, v0
    xs[0] = x
    f = lambda x, v: (v, -(b * v + k * x) / m)
    for i in range(1, len(t)):
        h = t[i] - t[i - 1]
        # sub-pasos para precisión
        n = 20
        hh = h / n
        for _ in range(n):
            k1 = f(x, v)
            k2 = f(x + hh / 2 * k1[0], v + hh / 2 * k1[1])
            k3 = f(x + hh / 2 * k2[0], v + hh / 2 * k2[1])
            k4 = f(x + hh * k3[0], v + hh * k3[1])
            x += hh / 6 * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0])
            v += hh / 6 * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1])
        xs[i] = x
    return xs


def main():
    # --- Python vs RK4 ---
    fallos = 0
    resultados_py = {}
    for nombre, m, k, b, A, phi in CASOS:
        sim = fisica.simular(m, k, b, A, phi, n=300)
        t = np.array(sim["t"])
        x_rk = rk4(m, k, b, sim["x0"], sim["v0"], t)
        x_an = np.array(sim["x"])
        escala = max(np.max(np.abs(x_rk)), 1e-12)
        err = np.max(np.abs(x_an - x_rk)) / escala
        em = np.array(sim["Em"])
        ok = err < 1e-6 and np.all(np.isfinite(x_an)) and np.all(np.isfinite(sim["a"]))
        # La energía total no puede crecer (b>=0) y es constante si b=0
        if b == 0:
            ok = ok and (em.max() - em.min()) / em.max() < 1e-9
        else:
            ok = ok and np.all(np.diff(em) <= em.max() * 1e-9)
        print(f"[py] {nombre:18s} err_rel={err:.2e}  régimen={sim['parametros']['regimen']:16s} {'OK' if ok else 'FALLO'}")
        fallos += 0 if ok else 1
        resultados_py[nombre] = sim

    # --- JS vs Python ---
    js = f"""
    const F = require({json.dumps(str(RAIZ / 'app/static/js/fisica.js'))});
    const casos = {json.dumps([[n, m, k, b, A, phi] for n, m, k, b, A, phi in CASOS])};
    const out = {{}};
    for (const [n, m, k, b, A, phi] of casos) {{
      const p = F.parametros(m, k, b);
      const ic = F.condiciones(A, phi, p.w0);
      const sol = F.solucion(m, k, b, ic.x0, ic.v0);
      const tmax = F.ventana(p);
      const N = 300, xs = [], vs = [], as = [];
      for (let i = 0; i < N; i++) {{ const s = sol(tmax * i / (N - 1)); xs.push(s.x); vs.push(s.v); as.push(s.a); }}
      out[n] = {{ tmax, x: xs, v: vs, a: as, regimen: p.regimen }};
    }}
    console.log(JSON.stringify(out));
    """
    salida = subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout
    res_js = json.loads(salida)
    for nombre, *_ in CASOS:
        py = resultados_py[nombre]
        j = res_js[nombre]
        escala = max(np.max(np.abs(py["x"])), 1e-12)
        ex = np.max(np.abs(np.array(py["x"]) - np.array(j["x"]))) / escala
        ev = np.max(np.abs(np.array(py["v"]) - np.array(j["v"]))) / max(np.max(np.abs(py["v"])), 1e-12)
        et = abs(py["t"][-1] - j["tmax"])
        ok = ex < 1e-9 and ev < 1e-9 and et < 1e-9 and j["regimen"] == py["parametros"]["regimen"]
        print(f"[js] {nombre:18s} dx={ex:.1e} dv={ev:.1e} dt_ventana={et:.0e} {'OK' if ok else 'FALLO'}")
        fallos += 0 if ok else 1

    # --- Ajuste lineal y cálculos de tablas ---
    k_real = 24.0
    masas = [0.1, 0.2, 0.3, 0.4, 0.5]
    T = [2 * math.pi * math.sqrt(m / k_real) for m in masas]
    aj = fisica.ajuste_t2_vs_m(masas, T)
    ok = aj and abs(aj["k_ajuste"] - k_real) < 1e-9 and abs(aj["ordenada"]) < 1e-9
    print(f"[ajuste T² vs m] k_ajuste={aj['k_ajuste']:.6f}  {'OK' if ok else 'FALLO'}")
    fallos += 0 if ok else 1
    assert abs(fisica.constante_k(0.2, 0.0818) - 0.2 * 9.81 / 0.0818) < 1e-12
    assert fisica.constante_k(0.2, 0) is None and fisica.constante_k(0.2, -0.01) is None
    assert abs(fisica.error_porcentual(0.66, 0.6) - 10.0) < 1e-9
    assert fisica.periodo_teorico(0.2, None) is None

    print("\nTODO OK" if fallos == 0 else f"\n{fallos} FALLOS")
    sys.exit(1 if fallos else 0)


if __name__ == "__main__":
    main()
