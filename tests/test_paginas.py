"""Verifica contenido de plantillas/fragmentos y la página de comparación en Chrome.

Uso: python tests/test_paginas.py <carpeta_sitio_renderizado> <carpeta_capturas>
(primero: python tests/render_sitio.py <carpeta_sitio_renderizado>)
Nota: sin internet, htmx y KaTeX (CDN) no cargan; aquí solo se prueba lo que no depende de ellos.
"""
import http.server
import json
import math
import re
import socketserver
import statistics
import sys
import threading
from functools import partial
from pathlib import Path

from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from app import fisica  # noqa: E402

sitio, capturas = Path(sys.argv[1]), Path(sys.argv[2])
capturas.mkdir(parents=True, exist_ok=True)
fallos = []


def check(cond, msg):
    print(("  OK   " if cond else "  FALLO ") + msg)
    if not cond:
        fallos.append(msg)


leer = lambda n: (sitio / n).read_text(encoding="utf-8")

# ---------------------------------------------------------------- contenido
print("Fragmentos HTMX")
k = leer("parcial_tabla_k.html")
check('id="tabla-k"' in k and 'hx-post="/datos/k"' in k, "tabla_k: contenedor y formulario de alta")
check(k.count('hx-delete="/datos/k/') == 4 and k.count('hx-get="/datos/k/') == 4, "tabla_k: 4 filas con editar/borrar")
check("hx-swap-oob" not in k, "tabla_k: sin swap fuera de banda")
check(re.search(r"k promedio</td>\s*<td class=\"num\">2[34]\.\d\d ± 0\.\d\d", k) is not None, "tabla_k: k promedio ≈ 24 ± σ")
p = leer("parcial_tabla_p.html")
check('hx-swap-oob="true"' in p and 'id="tabla-p"' in p, "tabla_p con oob=True: se refresca fuera de banda")
check(p.count('hx-delete="/datos/p/') == 3 and "Para calcular el período teórico" not in p, "tabla_p: 3 filas, sin aviso (hay k)")
check(re.search(r"<td class=\"num\">\d+\.\d\d %</td>", p) is not None, "tabla_p: % de error calculado")
ek = leer("parcial_fila_k_editar.html")
check('value="200"' in ek and 'value="15"' in ek and 'value="23.18"' in ek, "fila_k_editar: valores convertidos a g y cm (200, 15, 23.18)")
check('hx-put="/datos/k/2"' in ek and 'hx-include="closest tr"' in ek and "/datos/k/tabla/1" in ek, "fila_k_editar: guardar y cancelar")
ep = leer("parcial_fila_p_editar.html")
check('value="200"' in ep and 'value="10"' in ep and 'value="5.8"' in ep, "fila_p_editar: valores 200 g, 10, 5.8 s")
check("longitud final debe ser mayor" in leer("parcial_tabla_k_error.html"), "mensaje de error se muestra")
check("Para calcular el período teórico" in leer("parcial_tabla_p_vacia.html") and "Aún no hay mediciones" in leer("parcial_tabla_p_vacia.html"),
      "tabla_p sin k ni filas: aviso y mensaje de vacío")

print("Páginas")
m = leer("modelo.html")
check(r"$$T = 2\pi\sqrt{\frac{m}{k}}$$" in m, "modelo: LaTeX intacto tras Jinja")
check(r"\(\omega_d=\sqrt{\omega_0^2-\gamma^2}\)" in m, "modelo: LaTeX en línea intacto")
check("\\(\\zeta &lt; 1\\)" in m, "modelo: «ζ < 1» escapado correctamente en HTML")
for pag in ["index", "modelo", "procedimiento", "simulador", "datos", "comparacion", "conclusiones"]:
    h = leer(pag + ".html")
    ok_nav = all(f'href="{u}"' in h for u in ["/", "/modelo", "/procedimiento", "/datos", "/simulador", "/comparacion", "/conclusiones"])
    check(ok_nav and h.count('class="activo') == 1, f"{pag}: navegación completa y exactamente una sección activa")
check("PEER" not in leer("conclusiones.html").split("Nota:")[0], "conclusiones: referencias de sismología (PEER) no incluidas")
check("Raúl Castilblanco" in leer("index.html") and "Jaider Stevan Barbosa Ávila" in leer("index.html"), "inicio: docente e integrantes")

# ---------------------------------------------------------------- navegador
puntos = []
masas = [0.1, 0.2, 0.3, 0.4, 0.5]
k_real, m_resorte = 24.0, 0.03
ruido = [1.01, 0.99, 1.005, 1.0, 0.995]
for mm, r in zip(masas, ruido):
    t_exp = 2 * math.pi * math.sqrt((mm + m_resorte / 3) / k_real) * r  # incluye masa del resorte
    t_teo = fisica.periodo_teorico(mm, 24.0)
    puntos.append({"masa": mm, "T_exp": t_exp, "T_teo": t_teo, "n": 3, "error": fisica.error_porcentual(t_exp, t_teo)})
ajuste = fisica.ajuste_t2_vs_m([p["masa"] for p in puntos], [p["T_exp"] for p in puntos])
API = {"resorte": "Resorte 1", "k_prom": 24.0, "k_std": 0.4, "puntos": puntos, "ajuste": ajuste,
       "error_medio": statistics.fmean(p["error"] for p in puntos)}
VACIA = {"resorte": "Resorte 1", "k_prom": None, "k_std": None, "puntos": [], "ajuste": None, "error_medio": None}
RESP = {"1": API, "2": VACIA}


class H(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        m_ = re.match(r"/api/comparacion/(\d+)", self.path)
        if m_:
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
            self.wfile.write(json.dumps(RESP[m_.group(1)]).encode())
        else:
            super().do_GET()

    def log_message(self, *a):
        pass


socketserver.TCPServer.allow_reuse_address = True
srv = socketserver.TCPServer(("127.0.0.1", 0), partial(H, directory=str(sitio)))
origen = f"http://127.0.0.1:{srv.server_address[1]}"
threading.Thread(target=srv.serve_forever, daemon=True).start()

errores = []
print("Comparación en Chrome")
with sync_playwright() as pw:
    nav = pw.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    pag = nav.new_page(viewport={"width": 1366, "height": 900})
    pag.on("console", lambda msg: errores.append(msg.text) if msg.type == "error" and msg.location.get("url", "").startswith(origen) else None)
    pag.on("pageerror", lambda e: errores.append(str(e)))
    pag.goto(origen + "/comparacion.html"); pag.wait_for_timeout(800)
    txt = lambda i: pag.inner_text("#" + i)
    check(txt("k-hooke").startswith("24.00"), f"k Hooke = {txt('k-hooke')}")
    check(abs(float(txt("k-ajuste").split()[0]) - ajuste["k_ajuste"]) < 0.006, f"k ajuste = {txt('k-ajuste')} (esperado {ajuste['k_ajuste']:.2f})")
    check(float(txt("k-ord")) > 0, f"ordenada > 0 por la masa del resorte ({txt('k-ord')} s²)")
    check(float(txt("k-r2")) > 0.99, f"R² = {txt('k-r2')}")
    filas = pag.locator("#cmp-filas tr").count()
    check(filas == 5, f"tabla resumen con {filas} filas")
    check(txt("cmp-errmed").endswith("%") and "—" not in txt("cmp-errmed"), f"error medio = {txt('cmp-errmed')}")
    check(pag.locator("#cmp-msg").is_hidden(), "sin aviso cuando hay datos y k")
    pag.screenshot(path=str(capturas / "10_comparacion.png"), full_page=True)

    pag.goto(origen + "/comparacion.html"); pag.evaluate("() => { document.getElementById('cmp').dataset.rid = '2'; }")
    pag.reload(); pag.evaluate("() => 0")
    # recargar con rid=2 usando el sitio estático: cambiar el atributo en el HTML servido no es posible, así que
    # se dispara el script de nuevo con otro rid
    pag.goto(origen + "/comparacion.html")
    pag.add_init_script("")  # no-op
    pag.evaluate("""async () => {
      document.getElementById('cmp').dataset.rid = '2';
      const s = document.createElement('script'); s.src = '/static/js/comparacion.js?x=' + Date.now(); document.body.appendChild(s);
    }""")
    pag.wait_for_timeout(800)
    check(pag.locator("#cmp-msg").is_visible() and "Aún no hay períodos" in txt("cmp-msg"), f"sin datos: «{txt('cmp-msg')}»")

    pag.goto(origen + "/datos.html"); pag.wait_for_timeout(500)
    pag.screenshot(path=str(capturas / "11_datos.png"), full_page=True)
    pag.goto(origen + "/index.html"); pag.wait_for_timeout(300)
    pag.screenshot(path=str(capturas / "12_inicio.png"), full_page=False)
    pag.set_viewport_size({"width": 420, "height": 900})
    for pg in ["datos", "comparacion", "modelo", "index"]:
        pag.goto(origen + f"/{pg}.html"); pag.wait_for_timeout(500)
        ancho = pag.evaluate("() => document.documentElement.scrollWidth")
        check(ancho <= 430, f"móvil: {pg} sin desbordamiento horizontal (scrollWidth={ancho})")
    nav.close()

check(not errores, f"sin errores de JS/consola propios {errores if errores else ''}")
print("\nTODO OK" if not fallos else f"\n{len(fallos)} FALLOS")
sys.exit(1 if fallos else 0)
