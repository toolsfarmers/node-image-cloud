import os
import uuid
import mimetypes
from pathlib import Path

import aiofiles
from fastapi import FastAPI, File, Request, UploadFile, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, UnidentifiedImageError

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# On Render, the persistent disk is mounted at this path.
# Locally it falls back to ./data/images so the server works without changes.
IMAGES_DIR = Path(os.getenv("IMAGES_DIR", "./data/images"))
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp", "image/bmp"}
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "10"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Image File Server",
    description="Servidor de imágenes con almacenamiento persistente en Render.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_filename(original: str, unique_id: str) -> str:
    """Return a filesystem-safe filename prefixed with a UUID."""
    ext = Path(original).suffix.lower()
    if not ext:
        ext = ".bin"
    return f"{unique_id}{ext}"


def _image_info(path: Path, base_url: str = "") -> dict:
    stat = path.stat()
    mime, _ = mimetypes.guess_type(path.name)
    url = f"{base_url}/images/{path.name}" if base_url else f"/images/{path.name}"
    return {
        "filename": path.name,
        "size_bytes": stat.st_size,
        "mime_type": mime or "application/octet-stream",
        "url": url,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/", summary="Health check")
def root():
    return {"status": "ok", "message": "Image server running."}


@app.post("/upload", summary="Subir una imagen", status_code=201)
async def upload_image(request: Request, file: UploadFile = File(...)):
    """
    Recibe un archivo de imagen, valida su tipo y tamaño,
    y lo guarda en el disco persistente.
    """
    # --- Validate MIME type via content-type header first ---
    content_type = file.content_type or ""
    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Tipo de archivo no permitido: '{content_type}'. "
                   f"Permitidos: {sorted(ALLOWED_MIME_TYPES)}",
        )

    # --- Read file into memory to check size and validate with Pillow ---
    data = await file.read()

    if len(data) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"El archivo supera el límite de {MAX_FILE_SIZE_MB} MB.",
        )

    try:
        import io
        img = Image.open(io.BytesIO(data))
        img.verify()  # Raises if not a valid image
    except (UnidentifiedImageError, Exception) as exc:
        raise HTTPException(
            status_code=422,
            detail=f"El archivo no es una imagen válida: {exc}",
        )

    # --- Persist to disk ---
    unique_id = uuid.uuid4().hex
    safe_name = _safe_filename(file.filename or "upload", unique_id)
    dest = IMAGES_DIR / safe_name

    async with aiofiles.open(dest, "wb") as f:
        await f.write(data)

    base_url = str(request.base_url).rstrip("/")
    full_url = f"{base_url}/images/{safe_name}"

    return JSONResponse(
        status_code=201,
        content={
            "message": "Imagen subida correctamente.",
            "filename": safe_name,
            "url": full_url,
            "size_bytes": len(data),
        },
    )


@app.get("/images", summary="Listar todas las imágenes")
def list_images(
    request: Request,
    page: int = Query(1, ge=1, description="Número de página"),
    page_size: int = Query(20, ge=1, le=100, description="Imágenes por página"),
):
    """Devuelve la lista paginada de imágenes almacenadas."""
    all_files = sorted(IMAGES_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    image_files = [p for p in all_files if p.is_file()]

    total = len(image_files)
    start = (page - 1) * page_size
    end = start + page_size
    page_files = image_files[start:end]

    base_url = str(request.base_url).rstrip("/")

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "images": [_image_info(p, base_url) for p in page_files],
    }


@app.get("/images/{filename}", summary="Obtener una imagen por nombre")
def get_image(filename: str):
    """Sirve el archivo de imagen directamente."""
    # Prevent path traversal
    safe_filename = Path(filename).name
    path = IMAGES_DIR / safe_filename

    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Imagen no encontrada.")

    mime, _ = mimetypes.guess_type(safe_filename)
    return FileResponse(path, media_type=mime or "application/octet-stream")


@app.delete("/images/{filename}", summary="Eliminar una imagen")
def delete_image(filename: str):
    """Elimina una imagen del almacenamiento."""
    safe_filename = Path(filename).name
    path = IMAGES_DIR / safe_filename

    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Imagen no encontrada.")

    path.unlink()
    return {"message": f"Imagen '{safe_filename}' eliminada correctamente."}


@app.get("/images/{filename}/info", summary="Metadata de una imagen")
def image_info(filename: str, request: Request):
    """Devuelve metadata (tamaño, tipo MIME, dimensiones) de una imagen."""
    safe_filename = Path(filename).name
    path = IMAGES_DIR / safe_filename

    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Imagen no encontrada.")

    base_url = str(request.base_url).rstrip("/")
    info = _image_info(path, base_url)

    try:
        with Image.open(path) as img:
            info["width"] = img.width
            info["height"] = img.height
            info["format"] = img.format
    except Exception:
        pass

    return info
