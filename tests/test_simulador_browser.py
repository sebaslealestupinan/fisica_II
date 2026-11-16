"""Prueba el simulador en Chrome real: errores de consola, interacción, valores en pantalla.

Uso: python tests/test_simulador_browser.py <carpeta_sitio_renderizado> <carpeta_capturas>
"""
import http.server
import json
import socketserver
import sys
import threading
from functools import partial
from pathlib import Path

from playwright.sync_api import sync_playwright

sitio, capturas = Path(sys.argv[1]), Path(sys.argv[2])
capturas.mkdir(parents=True, exist_ok=True)

# /api/parametros/<id> simulado, para probar el botón "Cargar"
class H(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/api/parametros/1"):
            cuerpo = json.dumps({"resorte": "Resorte 1", "k_prom": 24.0, "k_std": 0.5,
                                 "masas": [{"masa": 0.1, "T_exp": 0.41, "n": 3}, {"masa": 0.3, "T_exp": 0.72, "n": 2}]}).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
            self.wfile.write(cuerpo)
        elif self.path.startswith("/api/parametros/2"):
            cuerpo = json.dumps({"resorte": "Resorte 2", "k_prom": None, "k_std": None, "masas": []}).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
            self.wfile.write(cuerpo)
        else:
            super().do_GET()
    def log_message(self, *a): pass

socketserver.TCPServer.allow_reuse_address = True
srv = socketserver.TCPServer(("127.0.0.1", 0), partial(H, directory=str(sitio)))
puerto = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = f"http://127.0.0.1:{puerto}/simulador.html"

errores, fallos = [], []
def check(cond, msg):
    print(("  OK   " if cond else "  FALLO ") + msg)
    if not cond: fallos.append(msg)

with sync_playwright() as pw:
    nav = pw.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    pag = nav.new_page(viewport={"width": 1366, "height": 900})
    pag.on("console", lambda m: errores.append(m.text) if m.type == "error" else None)
    pag.on("pageerror", lambda e: errores.append(str(e)))
    pag.goto(URL)
    pag.wait_for_timeout(800)

    txt = lambda i: pag.inner_text("#" + i)
    num = lambda i: float(txt(i).replace("—", "nan").replace("%", "").strip())

    print("Estado inicial (m=0.2, k=20, b=0, A=8 cm)")
    check(abs(num("p-w0") - 10.0) < 1e-6, f"ω0 = {txt('p-w0')} (esperado 10.000)")
    check(abs(num("p-T0") - 0.6283) < 1e-4, f"T0 = {txt('p-T0')} (esperado 0.6283)")
    check("ideal" in txt("regimen").lower(), f"régimen = {txt('regimen')}")
    check(abs(num("p-E0") - 64.0) < 1e-6, f"E0 = {txt('p-E0')} mJ (½·20·0.08² = 64)")
    check(abs(num("p-loss")) < 1e-6, f"sin amortiguar: energía perdida = {txt('p-loss')}")
    pag.screenshot(path=str(capturas / "01_ideal.png"))

    print("Presets de amortiguamiento")
    for preset, esperado, zeta in [("sub", "subamortiguado", 0.15), ("crit", "críticamente", 1.0), ("sobre", "sobreamortiguado", 2.5)]:
        pag.click(f"[data-preset={preset}]")
        pag.wait_for_timeout(300)
        check(esperado in txt("regimen").lower(), f"{preset}: régimen = {txt('regimen')}")
        check(abs(num("p-zeta") - zeta) < 0.01, f"{preset}: ζ = {txt('p-zeta')} (esperado {zeta})")
        pag.screenshot(path=str(capturas / f"02_{preset}.png"))
    check(num("p-loss") > 90, f"sobreamortiguado: casi toda la energía se disipa ({txt('p-loss')})")

    print("Sliders y entrada numérica")
    pag.click("[data-preset=ideal]")
    pag.fill("#n-k", "50"); pag.press("#n-k", "Tab"); pag.wait_for_timeout(200)
    check(abs(num("p-w0") - 15.8114) < 1e-3, f"k=50 → ω0 = {txt('p-w0')} (esperado 15.811)")
    pag.fill("#n-m", "0.5"); pag.press("#n-m", "Tab"); pag.wait_for_timeout(200)
    check(abs(num("p-w0") - 10.0) < 1e-6, f"m=0.5,k=50 → ω0 = {txt('p-w0')} (esperado 10.000)")
    pag.fill("#n-k", "20"); pag.press("#n-k", "Tab")
    pag.fill("#n-m", "0.2"); pag.press("#n-m", "Tab")
    pag.fill("#n-A", "8"); pag.press("#n-A", "Tab")
    pag.fill("#n-phi", "0"); pag.press("#n-phi", "Tab")
    pag.fill("#n-b", "0"); pag.press("#n-b", "Tab")
    # fuera de rango se acota
    pag.fill("#n-k", "9999"); pag.press("#n-k", "Tab")
    check(num("p-w0") <= (200 / 0.2) ** 0.5 + 1e-3, f"k fuera de rango se acota (ω0 = {txt('p-w0')})")
    pag.fill("#n-k", "20"); pag.press("#n-k", "Tab")

    print("Animación: pausa y t avanza")
    pag.click("#btn-reset"); pag.wait_for_timeout(100)
    t1 = num("lv-t"); pag.wait_for_timeout(500); t2 = num("lv-t")
    check(t2 > t1, f"el tiempo avanza ({t1} → {t2})")
    pag.click("#btn-play"); pag.wait_for_timeout(100)
    t3 = num("lv-t"); pag.wait_for_timeout(400); t4 = num("lv-t")
    check(abs(t4 - t3) < 1e-9, "en pausa el tiempo no avanza")
    # coherencia: x(t) = A cos(ω t) en MAS ideal
    import math
    t = pag.evaluate("() => window.__sim.st.t"); x = num("lv-x")
    check(abs(x - 8 * math.cos(10 * t)) < 0.006, f"x(t={t}) = {x} cm  vs  A·cos(ωt) = {8*math.cos(10*t):.3f}")
    v = num("lv-v"); check(abs(v - (-0.08 * 10 * math.sin(10 * t))) < 0.0006, f"v(t) = {v} m/s coincide con −Aω·sen(ωt)")
    ec, ep, em = num("lv-ec"), num("lv-ep"), num("lv-em")
    check(abs(ec + ep - 64) < 0.05 and abs(em - 64) < 0.05, f"Ec+Ep = {ec+ep:.2f} mJ = E0 (se conserva)")
    # barra de tiempo
    pag.evaluate("() => { const r = document.getElementById('r-t'); r.value = 0.3; r.dispatchEvent(new Event('input')); }")
    pag.wait_for_timeout(100)
    check(abs(num("lv-t") - 0.3) < 0.01, f"barra de tiempo mueve t a ≈0.3 (t = {txt('lv-t')})")
    pag.click("#btn-play")  # reanudar

    print("Arrastrar la masa")
    caja = pag.locator("#escena").bounding_box()
    st = pag.evaluate("() => window.__sim.st")
    pag.click("#btn-reset"); pag.wait_for_timeout(50)
    # posición actual de la masa: x=A (cm) -> y
    W, H = caja["width"], caja["height"]
    cx = min(W * 0.40, 260); ye = H * 0.52; S = (H * 0.30) / 0.20
    ym = ye + 0.08 * S
    pag.mouse.move(caja["x"] + cx, caja["y"] + ym)
    pag.mouse.down()
    pag.mouse.move(caja["x"] + cx, caja["y"] + ye - 0.12 * S, steps=6)   # arriba: x = -12 cm
    pag.wait_for_timeout(100)
    pag.screenshot(path=str(capturas / "03_arrastrando.png"))
    t_antes = num("lv-t"); pag.wait_for_timeout(300)
    check(abs(num("lv-t") - t_antes) < 1e-9, "mientras se arrastra, el tiempo se detiene")
    pag.mouse.up(); pag.wait_for_timeout(150)
    check(abs(float(pag.input_value("#n-A")) - 12.0) < 0.3, f"al soltar, A = {pag.input_value('#n-A')} cm (esperado ≈ 12)")
    check(abs(float(pag.input_value("#n-phi")) - 180) < 1e-6, f"x₀ negativo → φ = {pag.input_value('#n-phi')}° (esperado 180)")
    check(abs(num("p-x0") + 12) < 0.3, f"x₀ = {txt('p-x0')} cm (esperado ≈ −12)")

    print("Cargar datos del experimento")
    pag.fill("#n-A", "8"); pag.press("#n-A", "Tab"); pag.fill("#n-phi", "0"); pag.press("#n-phi", "Tab")
    pag.select_option("#sel-resorte", "2"); pag.click("#btn-cargar"); pag.wait_for_timeout(300)
    check("aún no tiene" in txt("exp-info"), f"resorte sin datos: «{txt('exp-info')[:50]}…»")
    pag.select_option("#sel-resorte", "1"); pag.click("#btn-cargar"); pag.wait_for_timeout(300)
    check(abs(float(pag.input_value("#n-k")) - 24.0) < 0.06, f"k cargada = {pag.input_value('#n-k')} (esperado 24.0)")
    pag.select_option("#sel-masa", "0"); pag.wait_for_timeout(300)
    check(abs(float(pag.input_value("#n-m")) - 0.1) < 0.006, f"m cargada = {pag.input_value('#n-m')} (esperado 0.10)")
    cmp_txt = txt("exp-cmp")
    check("T0" in cmp_txt or "T" in cmp_txt and "error" in cmp_txt, f"comparación: {cmp_txt}")
    T0 = 2 * math.pi * math.sqrt(float(pag.input_value("#n-m")) / float(pag.input_value("#n-k")))
    check(abs(num("p-T0") - T0) < 1e-3, f"T0 mostrado {txt('p-T0')} s = 2π√(m/k) = {T0:.4f}")
    pag.screenshot(path=str(capturas / "04_experimento.png"))

    print("Casos límite (sin errores de consola)")
    pag.fill("#n-b", "9"); pag.press("#n-b", "Tab"); pag.wait_for_timeout(200)
    pag.fill("#n-m", "0.05"); pag.press("#n-m", "Tab"); pag.fill("#n-k", "200"); pag.press("#n-k", "Tab")
    pag.click("[data-preset=sobre]"); pag.wait_for_timeout(300)
    check("NaN" not in txt("lv-x") and "NaN" not in txt("lv-a"), "sobreamortiguado extremo: sin NaN")
    pag.set_viewport_size({"width": 420, "height": 900}); pag.wait_for_timeout(500)
    pag.screenshot(path=str(capturas / "05_movil.png"), full_page=False)
    ancho = pag.evaluate("() => document.documentElement.scrollWidth")
    check(ancho <= 430, f"vista móvil sin desbordamiento horizontal (scrollWidth={ancho})")

    nav.close()

check(not errores, f"sin errores de consola/JS {errores if errores else ''}")
print("\nTODO OK" if not fallos else f"\n{len(fallos)} FALLOS")
sys.exit(1 if fallos else 0)
