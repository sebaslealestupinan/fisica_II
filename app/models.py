"""Modelos SQLModel. Todo se guarda en unidades SI (kg, m, s).

Los valores derivados (elongación, k, T_exp, T_teórico, % error) NO se guardan:
se calculan al vuelo en fisica.py para que nunca queden desactualizados.
"""
from typing import Optional

from sqlmodel import Field, SQLModel


class Resorte(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str
    descripcion: str = ""


class MedicionK(SQLModel, table=True):
    """Tabla V: masa, longitud inicial y final."""
    id: Optional[int] = Field(default=None, primary_key=True)
    resorte_id: int = Field(foreign_key="resorte.id", index=True)
    masa: float              # kg
    longitud_inicial: float  # m
    longitud_final: float    # m


class MedicionPeriodo(SQLModel, table=True):
    """Tabla VI: masa, número de oscilaciones y tiempo total."""
    id: Optional[int] = Field(default=None, primary_key=True)
    resorte_id: int = Field(foreign_key="resorte.id", index=True)
    masa: float              # kg
    n_oscilaciones: int
    tiempo_total: float      # s
