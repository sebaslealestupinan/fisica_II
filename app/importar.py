"""Lectura y validación de CSV con mediciones (sin dependencias de FastAPI).

Plantillas (unidades cómodas para el laboratorio: g, cm, s):
    Tabla V :  masa_g, longitud_inicial_cm, longitud_final_cm
    Tabla VI:  masa_g, n_oscilaciones, tiempo_total_s

Tolera: separador «,» o «;» (Excel en español usa «;»), decimales con coma cuando
el separador es «;», BOM de UTF-8, mayúsculas en los encabezados, filas vacías y
columnas en cualquier orden. Es todo-o-nada: si UNA fila tiene error no se guarda nada.
"""
from __future__ import annotations

import csv
import io

COLS_K = ["masa_g", "longitud_inicial_cm", "longitud_final_cm"]
COLS_P = ["masa_g", "n_oscilaciones", "tiempo_total_s"]
MAX_BYTES = 1_000_000
MAX_FILAS = 2000


# --- Validaciones (las usan también los formularios de la web) --------------
def validar_k(masa_g: float, l0_cm: float, lf_cm: float) -> str | None:
    if masa_g <= 0:
        return "La masa debe ser mayor que 0."
    if l0_cm <= 0 or lf_cm <= 0:
        return "Las longitudes deben ser mayores que 0."
    if lf_cm <= l0_cm:
        return "La longitud final debe ser mayor que la inicial (el resorte se estira)."
    return None


def validar_p(masa_g: float, n: int, t_s: float) -> str | None:
    if masa_g <= 0:
        return "La masa debe ser mayor que 0."
    if n <= 0:
        return "El número de oscilaciones debe ser al menos 1."
    if t_s <= 0:
        return "El tiempo total debe ser mayor que 0."
    return None


# --- Lectura -----------------------------------------------------------------
def _decodificar(datos: bytes) -> str:
    try:
        return datos.decode("utf-8-sig")
    except UnicodeDecodeError:
        return datos.decode("latin-1")  # CSV guardado por Excel antiguo


def _num(texto: str, coma_decimal: bool) -> float:
    t = texto.strip().replace(" ", "")
    if coma_decimal:
        t = t.replace(",", ".")
    v = float(t)  # ValueError si no es número
    if v != v or v in (float("inf"), float("-inf")):
        raise ValueError("no finito")
    return v


def leer(datos: bytes, tabla: str) -> tuple[list[tuple], list[str]]:
    """tabla: 'k' o 'p'. Devuelve (filas, errores). Si hay errores, `filas` viene vacía.

    Filas de 'k': (masa_kg, l0_m, lf_m).  Filas de 'p': (masa_kg, n, tiempo_s).
    """
    columnas = COLS_K if tabla == "k" else COLS_P
    if len(datos) > MAX_BYTES:
        return [], [f"El archivo es demasiado grande (máximo {MAX_BYTES // 1000} KB)."]
    texto = _decodificar(datos)
    if not texto.strip():
        return [], ["El archivo está vacío."]

    primera = next((l for l in texto.splitlines() if l.strip()), "")
    delim = ";" if primera.count(";") > primera.count(",") else ","
    coma_decimal = delim == ";"

    lector = csv.reader(io.StringIO(texto), delimiter=delim)
    filas_crudas = [(i, f) for i, f in enumerate(lector, start=1) if any(c.strip() for c in f)]
    if not filas_crudas:
        return [], ["El archivo no tiene filas."]

    _, enc = filas_crudas[0]
    enc = [c.strip().lower() for c in enc]
    faltan = [c for c in columnas if c not in enc]
    if faltan:
        return [], [f"Faltan columnas: {', '.join(faltan)}. Se esperaba: {', '.join(columnas)}. "
                    f"Encabezado leído: {', '.join(enc) or '(vacío)'}."]
    idx = {c: enc.index(c) for c in columnas}

    cuerpo = filas_crudas[1:]
    if not cuerpo:
        return [], ["El archivo solo tiene el encabezado: agrega al menos una fila de datos."]
    if len(cuerpo) > MAX_FILAS:
        return [], [f"Demasiadas filas (máximo {MAX_FILAS})."]

    filas, errores = [], []
    for n_linea, f in cuerpo:
        try:
            valores = {}
            for c in columnas:
                if idx[c] >= len(f) or not f[idx[c]].strip():
                    raise ValueError(f"falta «{c}»")
                try:
                    valores[c] = _num(f[idx[c]], coma_decimal)
                except ValueError:
                    raise ValueError(f"«{f[idx[c]].strip()}» no es un número en «{c}»")
            if tabla == "k":
                err = validar_k(valores["masa_g"], valores["longitud_inicial_cm"], valores["longitud_final_cm"])
                if not err:
                    filas.append((valores["masa_g"] / 1000, valores["longitud_inicial_cm"] / 100,
                                  valores["longitud_final_cm"] / 100))
            else:
                n = valores["n_oscilaciones"]
                if n != int(n):
                    raise ValueError("«n_oscilaciones» debe ser un número entero")
                err = validar_p(valores["masa_g"], int(n), valores["tiempo_total_s"])
                if not err:
                    filas.append((valores["masa_g"] / 1000, int(n), valores["tiempo_total_s"]))
            if err:
                raise ValueError(err)
        except ValueError as e:
            errores.append(f"Línea {n_linea}: {e}")
    if errores:
        return [], errores
    return filas, []
