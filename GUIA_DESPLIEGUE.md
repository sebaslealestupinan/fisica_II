# Publicar el proyecto gratis (Render + Neon)

Todo se hace desde el navegador. Necesitan cuentas gratuitas en **GitHub**, **Neon** y **Render** (se puede entrar con la cuenta de GitHub).
Los planes gratuitos cambian con el tiempo: confirmen en cada sitio que siguen vigentes.

## 1. Subir el proyecto a GitHub
1. Crear un repositorio nuevo (puede ser privado).
2. Subir **todo el contenido de la carpeta `proyecto_mas`** (arrastrar los archivos en «Add file → Upload files»). El `.gitignore` ya evita subir `datos.db`.
   `render.yaml` y `requirements.txt` deben quedar en la raíz del repositorio, no dentro de otra carpeta.

## 2. Crear la base de datos en Neon
1. En neon.tech crear un proyecto (cualquier nombre y región).
2. En el panel, botón **Connect**, copiar la *connection string*. Empieza con `postgresql://...` y termina con `?sslmode=require`.

## 3. Crear el sitio en Render
1. En render.com: **New → Blueprint**, elegir el repositorio. Render lee `render.yaml`.
2. Cuando pida las variables:
   - `DATABASE_URL`: pegar la cadena de Neon.
   - `EDIT_PASSWORD`: inventar una contraseña para el grupo.
3. Esperar el despliegue. El enlace queda tipo `https://mas-masa-resorte.onrender.com`.

Si prefieren crearlo a mano (**New → Web Service**): Build `pip install -r requirements.txt`, Start `uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips='*'`, plan Free, y las dos variables de arriba.

## 4. Cómo se usa
- Cualquiera con el enlace ve el sitio y usa el simulador.
- Para agregar, editar, borrar o importar datos: botón **🔒 Editar** del menú e ingresar la contraseña.
- Si ya tienen datos en su computador: en `/datos` usar «Exportar CSV» de cada tabla y luego «Importar CSV» en el sitio publicado.

## 5. Antes de exponer
- El plan gratis de Render duerme la app tras ~15 min sin visitas; la primera carga tarda cerca de un minuto. **Ábranla unos minutos antes.**
- Hagan un respaldo: exporten los CSV de ambas tablas.
- Plan B: correr en local (`uvicorn app.main:app`), que sigue funcionando con SQLite si no se define `DATABASE_URL`.

## Si algo falla
En Render, pestaña **Logs**. Errores típicos: `DATABASE_URL` mal pegada (debe incluir usuario, contraseña y `?sslmode=require`) o `render.yaml` fuera de la raíz del repositorio.
