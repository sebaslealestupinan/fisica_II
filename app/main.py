"""Aplicación FastAPI: presentación del proyecto, datos experimentales y simulador."""
import csv
import io
import math
import statistics
import time
from contextlib import asynccontextmanager
from pathlib import Path

from urllib.parse import urlencode

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, delete, select

from . import acceso, fisica
from .config import EDIT_PASSWORD
from .importar import COLS_K, COLS_P, MAX_BYTES, leer as leer_csv, validar_k as _validar_k, validar_p as _validar_p
from .db import get_session, init_db
from .models import MedicionK, MedicionPeriodo, Resorte

BASE = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="MAS masa-resorte", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=BASE / "templates")


@app.middleware("http")
async def proteger_edicion(request: Request, call_next):
    """Con EDIT_PASSWORD definida, solo quien entró en /editar puede modificar datos."""
    if (EDIT_PASSWORD and request.method not in ("GET", "HEAD", "OPTIONS")
            and request.url.path not in ("/editar", "/salir")
            and not acceso.cookie_valida(request.cookies.get(acceso.COOKIE), EDIT_PASSWORD)):
        if request.headers.get("hx-request"):  # HTMX: redirige la página completa
            return Response(status_code=200, headers={"HX-Redirect": "/editar"})
        return RedirectResponse("/editar", status_code=303)
    return await call_next(request)


def es_editor(request: Request) -> bool:
    return (not EDIT_PASSWORD) or acceso.cookie_valida(request.cookies.get(acceso.COOKIE), EDIT_PASSWORD)


def render(request: Request, plantilla: str, **ctx):
    ctx.setdefault("seccion", plantilla.removesuffix(".html"))
    ctx.setdefault("proteccion", bool(EDIT_PASSWORD))
    ctx.setdefault("editor", es_editor(request))
    return templates.TemplateResponse(request, plantilla, ctx)


# ==========================================================================
# Helpers de datos
# ==========================================================================
def get_resorte(session: Session, resorte_id: int | None) -> Resorte:
    if resorte_id is not None:
        r = session.get(Resorte, resorte_id)
        if r:
            return r
    r = session.exec(select(Resorte).order_by(Resorte.id)).first()
    if r is None:  # no debería pasar: init_db crea uno
        r = Resorte(nombre="Resorte 1")
        session.add(r)
        session.commit()
        session.refresh(r)
    return r


def filas_k(session: Session, rid: int) -> list[dict]:
    meds = session.exec(select(MedicionK).where(MedicionK.resorte_id == rid).order_by(MedicionK.id)).all()
    filas = []
    for m in meds:
        dl = fisica.elongacion(m.longitud_inicial, m.longitud_final)
        filas.append({"id": m.id, "masa": m.masa, "l0": m.longitud_inicial, "lf": m.longitud_final,
                      "dl": dl, "k": fisica.constante_k(m.masa, dl)})
    return filas


def estadistica_k(filas: list[dict]) -> tuple[float | None, float | None]:
    ks = [f["k"] for f in filas if f["k"]]
    if not ks:
        return None, None
    return statistics.fmean(ks), (statistics.stdev(ks) if len(ks) > 1 else None)


def filas_periodo(session: Session, rid: int, k_prom: float | None) -> list[dict]:
    meds = session.exec(select(MedicionPeriodo).where(MedicionPeriodo.resorte_id == rid)
                        .order_by(MedicionPeriodo.id)).all()
    filas = []
    for m in meds:
        t_exp = fisica.periodo_experimental(m.tiempo_total, m.n_oscilaciones)
        t_teo = fisica.periodo_teorico(m.masa, k_prom)
        filas.append({"id": m.id, "masa": m.masa, "n": m.n_oscilaciones, "t": m.tiempo_total,
                      "t_exp": t_exp, "t_teo": t_teo, "error": fisica.error_porcentual(t_exp, t_teo)})
    return filas


def ctx_tabla_k(session: Session, rid: int, error: str | None = None) -> dict:
    filas = filas_k(session, rid)
    k_prom, k_std = estadistica_k(filas)
    return {"rid": rid, "filas": filas, "k_prom": k_prom, "k_std": k_std, "error": error}


def ctx_tabla_p(session: Session, rid: int, error: str | None = None) -> dict:
    k_prom, _std = estadistica_k(filas_k(session, rid))
    return {"rid": rid, "filas": filas_periodo(session, rid, k_prom), "k_prom": k_prom, "error": error}


# Cambiar una medición de k o de período cambia k_prom, y con él T_teo / % error de TODAS
# las filas de la tabla de períodos. Por eso la tabla de períodos se refresca fuera de banda
# (hx-swap-oob) cada vez que cambia la de k; el helper la agrega a la respuesta.
def _respuesta_k(request: Request, session: Session, rid: int, err: str | None = None):
    ctx_k = ctx_tabla_k(session, rid, err)
    ctx_p = ctx_tabla_p(session, rid)
    ctx_p["oob"] = True
    html = templates.get_template("partials/tabla_k.html").render({**ctx_k, "request": request})
    html += templates.get_template("partials/tabla_p.html").render({**ctx_p, "request": request})
    return HTMLResponse(html)


def cargar_resortes(session: Session) -> list[Resorte]:
    return session.exec(select(Resorte).order_by(Resorte.id)).all()


# ==========================================================================
# Páginas
# ==========================================================================
@app.get("/", response_class=HTMLResponse)
def inicio(request: Request):
    return render(request, "index.html", seccion="inicio")


@app.get("/modelo", response_class=HTMLResponse)
def modelo(request: Request):
    return render(request, "modelo.html")


@app.get("/procedimiento", response_class=HTMLResponse)
def procedimiento(request: Request):
    return render(request, "procedimiento.html")


@app.get("/simulador", response_class=HTMLResponse)
def simulador(request: Request, session: Session = Depends(get_session)):
    return render(request, "simulador.html", resortes=cargar_resortes(session))


@app.get("/datos", response_class=HTMLResponse)
def datos(request: Request, resorte: int | None = None, aviso: str | None = None, tipo: str = "ok",
          session: Session = Depends(get_session)):
    r = get_resorte(session, resorte)
    return render(request, "datos.html", resortes=cargar_resortes(session), resorte=r,
                  tk=ctx_tabla_k(session, r.id), tp=ctx_tabla_p(session, r.id), aviso=aviso, tipo_aviso=tipo)


@app.get("/comparacion", response_class=HTMLResponse)
def comparacion(request: Request, resorte: int | None = None, session: Session = Depends(get_session)):
    r = get_resorte(session, resorte)
    return render(request, "comparacion.html", resortes=cargar_resortes(session), resorte=r)


@app.get("/conclusiones", response_class=HTMLResponse)
def conclusiones(request: Request):
    return render(request, "conclusiones.html")


# ==========================================================================
# Acceso para editar
# ==========================================================================
@app.get("/editar", response_class=HTMLResponse)
def editar_pagina(request: Request):
    if not EDIT_PASSWORD:
        return RedirectResponse("/datos", status_code=303)
    return render(request, "editar.html", seccion="editar")


@app.post("/editar")
def editar_entrar(request: Request, password: str = Form("")):
    if not EDIT_PASSWORD:
        return RedirectResponse("/datos", status_code=303)
    if not acceso.password_correcta(password, EDIT_PASSWORD):
        time.sleep(1)  # frena el ensayo y error
        return render(request, "editar.html", seccion="editar", error="Contraseña incorrecta.")
    resp = RedirectResponse("/datos", status_code=303)
    seguro = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
    resp.set_cookie(acceso.COOKIE, acceso.token(EDIT_PASSWORD), max_age=acceso.DIAS * 86400,
                    httponly=True, samesite="lax", secure=seguro)
    return resp


@app.get("/salir")
def editar_salir():
    resp = RedirectResponse("/datos", status_code=303)
    resp.delete_cookie(acceso.COOKIE)
    return resp


# ==========================================================================
# Resortes
# ==========================================================================
@app.post("/resortes")
def crear_resorte(nombre: str = Form(...), session: Session = Depends(get_session)):
    nombre = nombre.strip()
    if not nombre:
        raise HTTPException(422, "El nombre no puede estar vacío")
    r = Resorte(nombre=nombre)
    session.add(r)
    session.commit()
    session.refresh(r)
    return RedirectResponse(f"/datos?resorte={r.id}", status_code=303)


@app.post("/resortes/{rid}/borrar")
def borrar_resorte(rid: int, session: Session = Depends(get_session)):
    if len(cargar_resortes(session)) <= 1:
        raise HTTPException(400, "Debe existir al menos un resorte")
    session.exec(delete(MedicionK).where(MedicionK.resorte_id == rid))
    session.exec(delete(MedicionPeriodo).where(MedicionPeriodo.resorte_id == rid))
    r = session.get(Resorte, rid)
    if r:
        session.delete(r)
    session.commit()
    return RedirectResponse("/datos", status_code=303)


# ==========================================================================
# Importar CSV y plantillas
# ==========================================================================
def _volver(rid: int, texto: str, tipo: str) -> RedirectResponse:
    q = urlencode({"resorte": rid, "aviso": texto, "tipo": tipo})
    return RedirectResponse(f"/datos?{q}", status_code=303)


@app.get("/datos/plantilla/{tabla}.csv")
def plantilla_csv(tabla: str):
    if tabla == "k":
        return _csv("plantilla_tabla_V_constante_k.csv", COLS_K, [])
    if tabla == "p":
        return _csv("plantilla_tabla_VI_periodo.csv", COLS_P, [])
    raise HTTPException(404)


@app.post("/datos/import/{tabla}")
def importar_csv(tabla: str, resorte_id: int = Form(...), archivo: UploadFile = File(...),
                 session: Session = Depends(get_session)):
    if tabla not in ("k", "p"):
        raise HTTPException(404)
    if session.get(Resorte, resorte_id) is None:
        raise HTTPException(404, "Resorte no encontrado")
    filas, errores = leer_csv(archivo.file.read(MAX_BYTES + 1), tabla)
    if errores:
        texto = "No se importó nada. " + " · ".join(errores[:5])
        if len(errores) > 5:
            texto += f" · (y {len(errores) - 5} errores más)"
        return _volver(resorte_id, texto, "error")
    for f in filas:
        if tabla == "k":
            session.add(MedicionK(resorte_id=resorte_id, masa=f[0], longitud_inicial=f[1], longitud_final=f[2]))
        else:
            session.add(MedicionPeriodo(resorte_id=resorte_id, masa=f[0], n_oscilaciones=f[1], tiempo_total=f[2]))
    session.commit()
    return _volver(resorte_id, f"Se importaron {len(filas)} filas en la Tabla {'V' if tabla == 'k' else 'VI'}.", "ok")


# ==========================================================================
# Tabla V (HTMX): constante elástica.   Entradas del usuario: g y cm
# ==========================================================================
@app.post("/datos/k", response_class=HTMLResponse)
def agregar_k(request: Request, resorte_id: int = Form(...), masa_g: float = Form(...),
              l0_cm: float = Form(...), lf_cm: float = Form(...), session: Session = Depends(get_session)):
    err = _validar_k(masa_g, l0_cm, lf_cm)
    if not err:
        session.add(MedicionK(resorte_id=resorte_id, masa=masa_g / 1000, longitud_inicial=l0_cm / 100,
                              longitud_final=lf_cm / 100))
        session.commit()
    return _respuesta_k(request, session, resorte_id, err)


@app.get("/datos/k/tabla/{rid}", response_class=HTMLResponse)
def tabla_k(request: Request, rid: int, session: Session = Depends(get_session)):
    return templates.TemplateResponse(request, "partials/tabla_k.html", ctx_tabla_k(session, rid))


@app.get("/datos/k/{mid}/editar", response_class=HTMLResponse)
def editar_k_form(request: Request, mid: int, session: Session = Depends(get_session)):
    m = session.get(MedicionK, mid)
    if not m:
        raise HTTPException(404)
    return templates.TemplateResponse(request, "partials/fila_k_editar.html", {"f": m, "rid": m.resorte_id})


@app.put("/datos/k/{mid}", response_class=HTMLResponse)
def guardar_k(request: Request, mid: int, masa_g: float = Form(...), l0_cm: float = Form(...),
              lf_cm: float = Form(...), session: Session = Depends(get_session)):
    m = session.get(MedicionK, mid)
    if not m:
        raise HTTPException(404)
    err = _validar_k(masa_g, l0_cm, lf_cm)
    if not err:
        m.masa, m.longitud_inicial, m.longitud_final = masa_g / 1000, l0_cm / 100, lf_cm / 100
        session.add(m)
        session.commit()
    return _respuesta_k(request, session, m.resorte_id, err)


@app.delete("/datos/k/{mid}", response_class=HTMLResponse)
def borrar_k(request: Request, mid: int, session: Session = Depends(get_session)):
    m = session.get(MedicionK, mid)
    if not m:
        raise HTTPException(404)
    rid = m.resorte_id
    session.delete(m)
    session.commit()
    return _respuesta_k(request, session, rid)


# ==========================================================================
# Tabla VI (HTMX): período.   Entradas del usuario: g, nº de oscilaciones, s
# ==========================================================================
@app.post("/datos/p", response_class=HTMLResponse)
def agregar_p(request: Request, resorte_id: int = Form(...), masa_g: float = Form(...),
              n: int = Form(...), t_s: float = Form(...), session: Session = Depends(get_session)):
    err = _validar_p(masa_g, n, t_s)
    if not err:
        session.add(MedicionPeriodo(resorte_id=resorte_id, masa=masa_g / 1000, n_oscilaciones=n, tiempo_total=t_s))
        session.commit()
    return templates.TemplateResponse(request, "partials/tabla_p.html", ctx_tabla_p(session, resorte_id, err))


@app.get("/datos/p/tabla/{rid}", response_class=HTMLResponse)
def tabla_p(request: Request, rid: int, session: Session = Depends(get_session)):
    return templates.TemplateResponse(request, "partials/tabla_p.html", ctx_tabla_p(session, rid))


@app.get("/datos/p/{mid}/editar", response_class=HTMLResponse)
def editar_p_form(request: Request, mid: int, session: Session = Depends(get_session)):
    m = session.get(MedicionPeriodo, mid)
    if not m:
        raise HTTPException(404)
    return templates.TemplateResponse(request, "partials/fila_p_editar.html", {"f": m, "rid": m.resorte_id})


@app.put("/datos/p/{mid}", response_class=HTMLResponse)
def guardar_p(request: Request, mid: int, masa_g: float = Form(...), n: int = Form(...),
              t_s: float = Form(...), session: Session = Depends(get_session)):
    m = session.get(MedicionPeriodo, mid)
    if not m:
        raise HTTPException(404)
    err = _validar_p(masa_g, n, t_s)
    if not err:
        m.masa, m.n_oscilaciones, m.tiempo_total = masa_g / 1000, n, t_s
        session.add(m)
        session.commit()
    return templates.TemplateResponse(request, "partials/tabla_p.html", ctx_tabla_p(session, m.resorte_id, err))


@app.delete("/datos/p/{mid}", response_class=HTMLResponse)
def borrar_p(request: Request, mid: int, session: Session = Depends(get_session)):
    m = session.get(MedicionPeriodo, mid)
    if not m:
        raise HTTPException(404)
    rid = m.resorte_id
    session.delete(m)
    session.commit()
    return templates.TemplateResponse(request, "partials/tabla_p.html", ctx_tabla_p(session, rid))


# ==========================================================================
# Exportar CSV
# ==========================================================================
def _csv(nombre: str, encabezado: list[str], filas: list[list]) -> StreamingResponse:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(encabezado)
    w.writerows(filas)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


def _n(v, d=6):
    return "" if v is None else round(v, d)


@app.get("/datos/export/k.csv")
def exportar_k(resorte: int, session: Session = Depends(get_session)):
    filas = filas_k(session, resorte)
    return _csv(f"tabla_V_constante_k_resorte{resorte}.csv",
                ["masa_kg", "longitud_inicial_m", "longitud_final_m", "elongacion_m", "k_N_m"],
                [[_n(f["masa"]), _n(f["l0"]), _n(f["lf"]), _n(f["dl"]), _n(f["k"])] for f in filas])


@app.get("/datos/export/p.csv")
def exportar_p(resorte: int, session: Session = Depends(get_session)):
    k_prom, _ = estadistica_k(filas_k(session, resorte))
    filas = filas_periodo(session, resorte, k_prom)
    return _csv(f"tabla_VI_periodo_resorte{resorte}.csv",
                ["masa_kg", "n_oscilaciones", "tiempo_total_s", "T_exp_s", "T_teorico_s", "error_pct"],
                [[_n(f["masa"]), f["n"], _n(f["t"]), _n(f["t_exp"]), _n(f["t_teo"]), _n(f["error"], 3)] for f in filas])


# ==========================================================================
# API JSON
# ==========================================================================
@app.get("/api/simulacion")
def api_simulacion(m: float = Query(gt=0), k: float = Query(gt=0), b: float = Query(0.0, ge=0),
                   A: float = Query(0.05, ge=0), fase: float = Query(0.0, description="radianes"),
                   t_max: float | None = Query(None, gt=0, le=600), n: int = Query(600, ge=10, le=5000)):
    """Misma simulación que el navegador, calculada con NumPy (sirve para validar)."""
    return JSONResponse(fisica.simular(m, k, b, A, fase, t_max, n))


@app.get("/api/parametros/{rid}")
def api_parametros(rid: int, session: Session = Depends(get_session)):
    """k promedio y períodos medidos por masa: alimenta el botón 'cargar mediciones' del simulador."""
    r = session.get(Resorte, rid)
    if not r:
        raise HTTPException(404, "Resorte no encontrado")
    k_prom, k_std = estadistica_k(filas_k(session, rid))
    por_masa: dict[float, list[float]] = {}
    for f in filas_periodo(session, rid, k_prom):
        if f["t_exp"] is not None:
            por_masa.setdefault(round(f["masa"], 6), []).append(f["t_exp"])
    masas = [{"masa": m, "T_exp": statistics.fmean(ts), "n": len(ts)} for m, ts in sorted(por_masa.items())]
    return {"resorte": r.nombre, "k_prom": k_prom, "k_std": k_std, "masas": masas}


@app.get("/api/comparacion/{rid}")
def api_comparacion(rid: int, session: Session = Depends(get_session)):
    r = session.get(Resorte, rid)
    if not r:
        raise HTTPException(404, "Resorte no encontrado")
    k_prom, k_std = estadistica_k(filas_k(session, rid))
    por_masa: dict[float, list[float]] = {}
    for f in filas_periodo(session, rid, k_prom):
        if f["t_exp"] is not None:
            por_masa.setdefault(round(f["masa"], 6), []).append(f["t_exp"])
    puntos = []
    for m, ts in sorted(por_masa.items()):
        t_exp = statistics.fmean(ts)
        t_teo = fisica.periodo_teorico(m, k_prom)
        puntos.append({"masa": m, "T_exp": t_exp, "T_teo": t_teo, "n": len(ts),
                       "error": fisica.error_porcentual(t_exp, t_teo)})
    ajuste = fisica.ajuste_t2_vs_m([p["masa"] for p in puntos], [p["T_exp"] for p in puntos])
    errores = [p["error"] for p in puntos if p["error"] is not None]
    return {"resorte": r.nombre, "k_prom": k_prom, "k_std": k_std, "puntos": puntos, "ajuste": ajuste,
            "error_medio": statistics.fmean(errores) if errores else None}
