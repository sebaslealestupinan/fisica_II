from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine, select

from .config import DATABASE_URL
from .models import Resorte

RUTA_DB = Path(__file__).resolve().parent.parent / "datos.db"

if DATABASE_URL:  # nube: Postgres (Neon). pre_ping/recycle porque Neon duerme las conexiones inactivas
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=300)
else:  # local: SQLite como siempre
    engine = create_engine(f"sqlite:///{RUTA_DB}", connect_args={"check_same_thread": False})


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        if s.exec(select(Resorte)).first() is None:
            s.add(Resorte(nombre="Resorte 1", descripcion="Resorte metálico del montaje"))
            s.commit()


def get_session():
    with Session(engine) as session:
        yield session
