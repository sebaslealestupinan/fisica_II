# MAS masa-resorte · Física 2

Sitio del proyecto «Modelado y simulación del movimiento armónico simple en un sistema masa-resorte».
FastAPI + SQLModel (SQLite) + Jinja2 + HTMX. Corre en local sin usuarios; opcionalmente se publica gratis (ver `GUIA_DESPLIEGUE.md`).

## Ejecutar

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Abrir http://127.0.0.1:8000. La base de datos se crea sola en `datos.db`.

Internet se necesita solo para cargar HTMX y KaTeX (fórmulas) desde CDN; el simulador y las gráficas
no dependen de nada externo.

## Variables de entorno (opcionales)

| Variable | Efecto |
|---|---|
| `DATABASE_URL` | Si se define (Postgres/Neon), se usa en lugar de `datos.db` |
| `EDIT_PASSWORD` | Si se define, modificar datos exige entrar en `/editar`; ver y simular sigue libre |

Sin ninguna de las dos, todo funciona como en local.

## Páginas

| Ruta | Contenido |
|---|---|
| `/` | Resumen, pregunta orientadora, objetivos |
| `/modelo` | Ecuaciones, supuestos, limitaciones, amortiguamiento |
| `/procedimiento` | Materiales, 12 pasos, metodología |
| `/datos` | Tablas V y VI editables (HTMX), exportar CSV |
| `/simulador` | Simulador interactivo con amortiguamiento |
| `/comparacion` | T vs m, T² vs m con ajuste lineal, k por dos métodos |
| `/conclusiones` | Por completar + referencias |

Importar mediciones: en `/datos`, botón «Importar CSV» (plantillas en `plantillas/`). Columnas: Tabla V `masa_g, longitud_inicial_cm, longitud_final_cm`; Tabla VI `masa_g, n_oscilaciones, tiempo_total_s`. Acepta `,` o `;`.

API: `/api/simulacion?m=&k=&b=&A=&fase=` (NumPy), `/api/parametros/{id}`, `/api/comparacion/{id}`.

## Pruebas

```bash
python tests/test_importar.py          # lector de CSV
python tests/test_acceso.py            # contraseña de edición y URL de base de datos
python tests/test_fisica.py            # solución analítica vs RK4 y vs JS (necesita node)
python tests/render_sitio.py /tmp/sitio
python tests/test_simulador_browser.py /tmp/sitio /tmp/capturas   # necesita playwright + Chrome
python tests/test_paginas.py /tmp/sitio /tmp/capturas
```

Las pruebas de navegador ajustan la ruta de Chrome (`/usr/bin/google-chrome`) en el propio archivo.

## Estructura

```
app/
  main.py        rutas FastAPI
  models.py      Resorte, MedicionK, MedicionPeriodo (SQLModel, unidades SI)
  db.py          motor SQLite
  fisica.py      cálculos y simulación (NumPy)
  static/js/     fisica.js (misma física), graficos.js, simulador.js, comparacion.js
  templates/     páginas Jinja2 y fragmentos HTMX en partials/
```
