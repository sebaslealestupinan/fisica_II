"""Física del sistema masa-resorte (con y sin amortiguamiento).

Ecuación del movimiento respecto a la posición de equilibrio:

    m x'' + b x' + k x = 0

En un resorte vertical la gravedad solo desplaza el equilibrio, por eso x se mide
desde la posición de equilibrio (positivo hacia abajo) y g no aparece en la dinámica.

La solución analítica de los tres regímenes se escribe con una forma común:

    x(t) = x0 * fe(t) + D * ge(t)
    v(t) = v0 * fe(t) - E * ge(t)

    D = v0 + γ x0,   E = ω0² x0 + γ v0,   γ = b / 2m

con fe = e^(-γt)·C(t) y ge = e^(-γt)·S(t):
    subamortiguado  (γ < ω0):  C = cos(ωd t),  S = sen(ωd t)/ωd
    crítico         (γ = ω0):  C = 1,          S = t
    sobreamortiguado (γ > ω0): C = cosh(r t),  S = senh(r t)/r
Este mismo código está en static/js/fisica.js.
"""
from __future__ import annotations

import math

import numpy as np

G = 9.81
DOS_PI = 2.0 * math.pi


# --------------------------------------------------------------------------
# Cálculos de las tablas experimentales
# --------------------------------------------------------------------------
def elongacion(l_inicial: float, l_final: float) -> float:
    return l_final - l_inicial


def constante_k(masa: float, dl: float) -> float | None:
    """k = m g / ΔL (resorte vertical en equilibrio)."""
    if dl is None or dl <= 0:
        return None
    return masa * G / dl


def periodo_experimental(tiempo_total: float, n: int) -> float | None:
    if not n or n <= 0:
        return None
    return tiempo_total / n


def periodo_teorico(masa: float, k: float | None) -> float | None:
    if not k or k <= 0 or masa <= 0:
        return None
    return DOS_PI * math.sqrt(masa / k)


def error_porcentual(t_exp: float | None, t_teo: float | None) -> float | None:
    if t_exp is None or not t_teo:
        return None
    return abs((t_exp - t_teo) / t_teo) * 100.0


# --------------------------------------------------------------------------
# Simulación
# --------------------------------------------------------------------------
def parametros(m: float, k: float, b: float) -> dict:
    w0 = math.sqrt(k / m)
    gamma = b / (2.0 * m)
    zeta = b / (2.0 * math.sqrt(k * m))
    disc = gamma * gamma - w0 * w0
    wd = math.sqrt(-disc) if disc < 0 else 0.0
    if b == 0:
        regimen = "ideal"
    elif abs(zeta - 1) < 1e-3:
        regimen = "critico"
    elif zeta < 1:
        regimen = "subamortiguado"
    else:
        regimen = "sobreamortiguado"
    return {
        "w0": w0,
        "f0": w0 / DOS_PI,
        "T0": DOS_PI / w0,
        "gamma": gamma,
        "zeta": zeta,
        "b_critico": 2.0 * math.sqrt(k * m),
        "wd": wd,
        "Td": DOS_PI / wd if wd > 0 else None,
        "tau": 1.0 / gamma if gamma > 0 else None,
        "regimen": regimen,
        "disc": disc,
    }


def condiciones_iniciales(amplitud: float, fase_rad: float, w0: float) -> tuple[float, float]:
    """x0 = A cos φ,  v0 = -A ω0 sen φ  (con φ=0: se suelta desde x=A en reposo)."""
    return amplitud * math.cos(fase_rad), -amplitud * w0 * math.sin(fase_rad)


def _fe_ge(m: float, k: float, b: float, t: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    w0 = math.sqrt(k / m)
    gamma = b / (2.0 * m)
    disc = gamma * gamma - w0 * w0
    if disc < 0:
        w = math.sqrt(-disc)
        wt = w * t
        e = np.exp(-gamma * t)
        s = np.where(np.abs(wt) < 1e-4, t * (1 - wt**2 / 6.0), np.sin(wt) / w)
        return e * np.cos(wt), e * s
    if disc == 0:
        e = np.exp(-gamma * t)
        return e, e * t
    r = math.sqrt(disc)
    rt = r * t
    e1 = np.exp((r - gamma) * t)   # exponentes <= 0: no hay desbordamiento
    e2 = np.exp((-r - gamma) * t)
    e0 = np.exp(-gamma * t)
    small = rt < 1e-4
    fe = np.where(small, e0 * (1 + rt**2 / 2.0), 0.5 * (e1 + e2))
    ge = np.where(small, e0 * t * (1 + rt**2 / 6.0), 0.5 * (e1 - e2) / r)
    return fe, ge


def ventana_tiempo(p: dict) -> float:
    """Ventana temporal sugerida para mostrar el movimiento (s)."""
    if p["regimen"] == "ideal":
        tw = 6 * p["T0"]
    elif p["disc"] < 0:
        tw = min(max(3 * p["Td"], 4.6 / p["gamma"]), 14 * p["Td"])
    else:
        r = math.sqrt(max(p["disc"], 0.0))
        lenta = p["w0"] ** 2 / (p["gamma"] + r)  # γ - r, estable numéricamente
        tw = max(4.6 / lenta, p["T0"])
    return min(max(tw, 0.5), 60.0)


def simular(m: float, k: float, b: float, amplitud: float, fase_rad: float = 0.0,
            t_max: float | None = None, n: int = 600) -> dict:
    p = parametros(m, k, b)
    x0, v0 = condiciones_iniciales(amplitud, fase_rad, p["w0"])
    if t_max is None:
        t_max = ventana_tiempo(p)
    t = np.linspace(0.0, t_max, n)
    fe, ge = _fe_ge(m, k, b, t)
    D = v0 + p["gamma"] * x0
    E = p["w0"] ** 2 * x0 + p["gamma"] * v0
    x = x0 * fe + D * ge
    v = v0 * fe - E * ge
    a = -(b * v + k * x) / m
    ec = 0.5 * m * v**2
    ep = 0.5 * k * x**2
    return {
        "parametros": p,
        "x0": x0,
        "v0": v0,
        "E0": 0.5 * k * x0**2 + 0.5 * m * v0**2,
        "t": t.tolist(),
        "x": x.tolist(),
        "v": v.tolist(),
        "a": a.tolist(),
        "Ec": ec.tolist(),
        "Ep": ep.tolist(),
        "Em": (ec + ep).tolist(),
    }


# --------------------------------------------------------------------------
# Ajuste lineal T² = (4π²/k) m + c   (para la página de comparación)
# --------------------------------------------------------------------------
def ajuste_t2_vs_m(masas: list[float], periodos: list[float]) -> dict | None:
    if len(masas) < 2 or len(set(masas)) < 2:
        return None
    x = np.array(masas, dtype=float)
    y = np.array(periodos, dtype=float) ** 2
    pendiente, ordenada = np.polyfit(x, y, 1)
    if pendiente <= 0:
        return None
    pred = pendiente * x + ordenada
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0
    return {
        "pendiente": float(pendiente),
        "ordenada": float(ordenada),
        "k_ajuste": float(DOS_PI**2 / pendiente),
        "r2": r2,
    }
