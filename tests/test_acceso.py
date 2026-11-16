"""Pruebas de config.normalizar_url y acceso (sin FastAPI)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import acceso  # noqa: E402
from app.config import normalizar_url  # noqa: E402

n = 0
def ok(c, m):
    global n; n += 1
    assert c, m

neon = "postgresql://u:p@ep-x.neon.tech/db?sslmode=require"
ok(normalizar_url(neon) == "postgresql+psycopg://u:p@ep-x.neon.tech/db?sslmode=require", "postgresql://")
ok(normalizar_url("postgres://u:p@h/db") == "postgresql+psycopg://u:p@h/db", "postgres://")
ok(normalizar_url("  " + neon + "\n").startswith("postgresql+psycopg://"), "espacios")
ok(normalizar_url("postgresql+psycopg://u:p@h/db") == "postgresql+psycopg://u:p@h/db", "ya normalizada")
ok(normalizar_url("") == "", "vacía = local")

pw = "grupo2026"
t = acceso.token(pw)
ok(acceso.cookie_valida(t, pw), "cookie válida")
ok(not acceso.cookie_valida(None, pw), "sin cookie")
ok(not acceso.cookie_valida("x" * 64, pw), "cookie falsa")
ok(not acceso.cookie_valida(t, "otra"), "cambia la contraseña → invalida")
ok(not acceso.cookie_valida(t, ""), "sin contraseña configurada nunca valida")
ok(acceso.password_correcta(pw, pw), "contraseña correcta")
ok(not acceso.password_correcta("mal", pw), "contraseña incorrecta")
ok(not acceso.password_correcta("", pw), "vacía")
ok(not acceso.password_correcta("ñ", ""), "sin configurar")
ok(acceso.password_correcta("contraseña-ñ", "contraseña-ñ"), "unicode")
print(f"OK {n} comprobaciones")
