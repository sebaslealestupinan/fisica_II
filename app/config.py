"""Configuración por variables de entorno (sin dependencias, fácil de probar)."""
import os


def normalizar_url(url: str) -> str:
    """Neon/Render entregan postgres:// o postgresql://; SQLAlchemy necesita el driver psycopg."""
    url = url.strip()
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


DATABASE_URL = normalizar_url(os.getenv("DATABASE_URL", ""))
EDIT_PASSWORD = os.getenv("EDIT_PASSWORD", "")
