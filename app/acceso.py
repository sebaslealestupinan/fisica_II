"""Contraseña única para EDITAR (ver el sitio sigue siendo libre).

Si EDIT_PASSWORD no está definida, no se protege nada (modo local, como antes).
La cookie guarda un HMAC de la contraseña: cambiar la contraseña invalida las sesiones.
"""
import hashlib
import hmac

COOKIE = "mas_editor"
DIAS = 30


def token(password: str) -> str:
    return hmac.new(password.encode(), b"editor-v1", hashlib.sha256).hexdigest()


def cookie_valida(valor: str | None, password: str) -> bool:
    return bool(password) and bool(valor) and hmac.compare_digest(valor, token(password))


def password_correcta(intento: str, password: str) -> bool:
    return bool(password) and hmac.compare_digest(
        hashlib.sha256(intento.encode()).digest(), hashlib.sha256(password.encode()).digest()
    )
