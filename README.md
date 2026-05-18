# File Cloud Server

Servidor de archivos construido con **FastAPI** y desplegado en **Render** con disco persistente.  
Soporta imágenes, audio (WAV, MP3), video (MP4), ejecutables (.exe) y archivos RAR.

## Endpoints

| Método   | Ruta                       | Descripción                         |
|----------|----------------------------|-------------------------------------|
| `GET`    | `/`                        | Health check                        |
| `POST`   | `/upload`                  | Subir un archivo                    |
| `GET`    | `/files`                   | Listar archivos (paginado)          |
| `GET`    | `/files/{filename}`        | Descargar un archivo                |
| `GET`    | `/files/{filename}/info`   | Metadata del archivo                |
| `DELETE` | `/files/{filename}`        | Eliminar un archivo                 |

Las rutas `/images/*` se mantienen como aliases retrocompatibles.

Documentación interactiva disponible en `/docs` (Swagger UI) y `/redoc`.

## Tipos de archivo permitidos

| Categoría | Extensiones | Límite |
|-----------|-------------|--------|
| Imágenes  | `.jpg` `.png` `.gif` `.webp` `.bmp` | 10 MB |
| WAV       | `.wav` | 50 MB |
| MP3       | `.mp3` | 50 MB |
| MP4       | `.mp4` | 100 MB |
| EXE       | `.exe` | 50 MB |
| RAR       | `.rar` | 300 MB |

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
Los archivos se guardan en `./data/images/` en local.

---

## Despliegue en Render

1. Sube el repositorio a GitHub (o GitLab).
2. En el panel de Render crea un nuevo servicio usando **"New → Blueprint"** y apunta al repositorio. El archivo `render.yaml` configura automáticamente:
   - El servicio web con Python/uvicorn.
   - Un **disco persistente de 50 GB** montado en `/data/images` (los archivos sobreviven a reinicios y redespliegues).
3. *(Alternativa)* Crea manualmente un "Web Service" con:
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - En la pestaña **Disks**, añade un disco con mount path `/data/images`.
   - Variable de entorno `IMAGES_DIR=/data/images`.

> **Nota:** El disco persistente requiere el plan **Starter** o superior en Render.

---

## Variables de entorno

| Variable                | Valor por defecto | Descripción                          |
|-------------------------|-------------------|--------------------------------------|
| `IMAGES_DIR`            | `./data/images`   | Directorio donde se almacenan archivos |
| `MAX_FILE_SIZE_MB`      | `10`              | Límite para imágenes en MB           |
| `MAX_WAV_FILE_SIZE_MB`  | `50`              | Límite para WAV en MB                |
| `MAX_MP3_FILE_SIZE_MB`  | `50`              | Límite para MP3 en MB                |
| `MAX_MP4_FILE_SIZE_MB`  | `100`             | Límite para MP4 en MB                |
| `MAX_EXE_FILE_SIZE_MB`  | `50`              | Límite para EXE en MB                |
| `MAX_RAR_FILE_SIZE_MB`  | `300`             | Límite para RAR en MB                |
