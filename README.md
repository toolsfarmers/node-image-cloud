# Image File Server

Servidor de imágenes construido con **FastAPI** y desplegado en **Render** con disco persistente.

## Endpoints

| Método   | Ruta                        | Descripción                         |
|----------|-----------------------------|-------------------------------------|
| `GET`    | `/`                         | Health check                        |
| `POST`   | `/upload`                   | Subir una imagen                    |
| `GET`    | `/images`                   | Listar imágenes (paginado)          |
| `GET`    | `/images/{filename}`        | Servir una imagen                   |
| `GET`    | `/images/{filename}/info`   | Metadata de una imagen              |
| `DELETE` | `/images/{filename}`        | Eliminar una imagen                 |

Documentación interactiva disponible en `/docs` (Swagger UI) y `/redoc`.

## Tipos de imagen permitidos

`image/jpeg`, `image/png`, `image/gif`, `image/webp`, `image/bmp`

Tamaño máximo por defecto: **10 MB** (configurable con `MAX_FILE_SIZE_MB`).

---

## Desarrollo local

```bash
# 1. Crear entorno virtual
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate  # Linux/macOS

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Iniciar el servidor
uvicorn main:app --reload
```

El servidor queda disponible en `http://localhost:8000`.  
Las imágenes se guardan en `./data/images/` en local.

---

## Despliegue en Render

1. Sube el repositorio a GitHub (o GitLab).
2. En el panel de Render crea un nuevo servicio usando **"New → Blueprint"** y apunta al repositorio. El archivo `render.yaml` configura automáticamente:
   - El servicio web con Python/uvicorn.
   - Un **disco persistente de 10 GB** montado en `/data/images` (las imágenes sobreviven a reinicios y redespliegues).
3. *(Alternativa)* Crea manualmente un "Web Service" con:
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - En la pestaña **Disks**, añade un disco con mount path `/data/images`.
   - Variable de entorno `IMAGES_DIR=/data/images`.

> **Nota:** El disco persistente requiere el plan **Starter** o superior en Render.

---

## Variables de entorno

| Variable          | Valor por defecto | Descripción                          |
|-------------------|-------------------|--------------------------------------|
| `IMAGES_DIR`      | `./data/images`   | Directorio donde se almacenan imágenes|
| `MAX_FILE_SIZE_MB`| `10`              | Tamaño máximo de imagen en MB        |
