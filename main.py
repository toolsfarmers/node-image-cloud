import io
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

IMAGES_DIR = Path(os.getenv("IMAGES_DIR", "./data/images"))
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

IMAGE_MIMES = frozenset(
    {"image/jpeg", "image/png", "image/gif", "image/webp", "image/bmp"}
)
WAV_MIMES = frozenset(
    {"audio/wav", "audio/x-wav", "audio/wave", "audio/vnd.wave"}
)
MP3_MIMES = frozenset({"audio/mpeg", "audio/mp3"})
MP4_MIMES = frozenset({"video/mp4"})
EXE_MIMES = frozenset(
    {
        "application/x-msdownload",
        "application/vnd.microsoft.portable-executable",
        "application/x-msdos-program",
    }
)
RAR_MIMES = frozenset(
    {
        "application/vnd.rar",
        "application/x-rar-compressed",
        "application/x-rar",
    }
)

ALLOWED_MIME_TYPES = (
    IMAGE_MIMES | WAV_MIMES | MP3_MIMES | MP4_MIMES | EXE_MIMES | RAR_MIMES
)

EXTENSION_MIME_MAP = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".mp4": "video/mp4",
    ".exe": "application/x-msdownload",
    ".rar": "application/x-rar-compressed",
}

OCTET_STREAM = "application/octet-stream"
_CHUNK_SIZE = 256 * 1024  # 256 KB

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="File Server",
    description="Servidor de archivos (imágenes, audio, video, ejecutables y RAR) con almacenamiento persistente.",
    version="1.2.0",
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


def _mb_to_bytes(mb: int) -> int:
    return mb * 1024 * 1024


def _max_bytes_for_mime(mime: str) -> int:
    if mime in IMAGE_MIMES:
        return _mb_to_bytes(int(os.getenv("MAX_FILE_SIZE_MB", "10")))
    if mime in WAV_MIMES:
        return _mb_to_bytes(int(os.getenv("MAX_WAV_FILE_SIZE_MB", "50")))
    if mime in MP3_MIMES:
        return _mb_to_bytes(int(os.getenv("MAX_MP3_FILE_SIZE_MB", "50")))
    if mime in MP4_MIMES:
        return _mb_to_bytes(int(os.getenv("MAX_MP4_FILE_SIZE_MB", "100")))
    if mime in EXE_MIMES:
        return _mb_to_bytes(int(os.getenv("MAX_EXE_FILE_SIZE_MB", "50")))
    if mime in RAR_MIMES:
        return _mb_to_bytes(int(os.getenv("MAX_RAR_FILE_SIZE_MB", "300")))
    return _mb_to_bytes(10)


def _resolve_content_type(content_type: str, filename: str) -> str:
    ct = (content_type or "").split(";")[0].strip().lower()
    if ct in ALLOWED_MIME_TYPES:
        return ct
    if ct in ("", OCTET_STREAM):
        ext = Path(filename or "").suffix.lower()
        if ext in EXTENSION_MIME_MAP:
            return EXTENSION_MIME_MAP[ext]
    return ct


# ---------------------------------------------------------------------------
# Validators (signature-only checks — operate on header bytes, not full data)
# ---------------------------------------------------------------------------


def _validate_image(data: bytes) -> None:
    try:
        img = Image.open(io.BytesIO(data))
        img.verify()
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"El archivo no es una imagen válida: {exc}",
        )


def _validate_wav(header: bytes) -> None:
    if len(header) < 12 or header[:4] != b"RIFF" or header[8:12] != b"WAVE":
        raise HTTPException(status_code=422, detail="El archivo no es un WAV válido.")


def _validate_mp3(header: bytes) -> None:
    if len(header) < 2:
        raise HTTPException(status_code=422, detail="El archivo no es un MP3 válido.")
    if header[:3] == b"ID3":
        return
    if header[0] == 0xFF and (header[1] & 0xE0) == 0xE0:
        return
    raise HTTPException(status_code=422, detail="El archivo no es un MP3 válido.")


def _validate_mp4(header: bytes) -> None:
    if len(header) < 8:
        raise HTTPException(status_code=422, detail="El archivo no es un MP4 válido.")
    if header[4:8] == b"ftyp":
        return
    if b"ftyp" in header[:64]:
        return
    raise HTTPException(status_code=422, detail="El archivo no es un MP4 válido.")


def _validate_exe(header: bytes) -> None:
    if len(header) < 2 or header[:2] != b"MZ":
        raise HTTPException(
            status_code=422,
            detail="El archivo no es un ejecutable PE válido.",
        )


def _validate_rar(header: bytes) -> None:
    # RAR4: Rar!\x1a\x07\x00 — RAR5: Rar!\x1a\x07\x01\x00
    if len(header) < 4 or header[:4] != b"Rar!":
        raise HTTPException(status_code=422, detail="El archivo no es un RAR válido.")


_HEADER_VALIDATORS: dict = {
    **{m: _validate_wav for m in WAV_MIMES},
    **{m: _validate_mp3 for m in MP3_MIMES},
    **{m: _validate_mp4 for m in MP4_MIMES},
    **{m: _validate_exe for m in EXE_MIMES},
    **{m: _validate_rar for m in RAR_MIMES},
}


def _validate_header(mime: str, header: bytes) -> None:
    validator = _HEADER_VALIDATORS.get(mime)
    if validator:
        validator(header)


# ---------------------------------------------------------------------------
# Upload helpers
# ---------------------------------------------------------------------------


async def _stream_to_disk(
    file: UploadFile, dest: Path, max_bytes: int, max_mb: int
) -> int:
    """
    Stream the upload chunk-by-chunk directly to dest.
    Deletes the partial file and raises 413 if the size limit is exceeded.
    Returns the number of bytes written.
    """
    bytes_written = 0
    try:
        async with aiofiles.open(dest, "wb") as out:
            while True:
                chunk = await file.read(_CHUNK_SIZE)
                if not chunk:
                    break
                bytes_written += len(chunk)
                if bytes_written > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"El archivo supera el límite de {max_mb} MB para este tipo.",
                    )
                await out.write(chunk)
    except HTTPException:
        if dest.exists():
            dest.unlink()
        raise
    return bytes_written


def _read_file_header(path: Path, n: int = 64) -> bytes:
    with open(path, "rb") as f:
        return f.read(n)


def _upload_success_message(mime: str) -> str:
    if mime in IMAGE_MIMES:
        return "Imagen subida correctamente."
    if mime in WAV_MIMES:
        return "Archivo WAV subido correctamente."
    if mime in MP3_MIMES:
        return "Archivo MP3 subido correctamente."
    if mime in MP4_MIMES:
        return "Archivo MP4 subido correctamente."
    if mime in EXE_MIMES:
        return "Ejecutable subido correctamente."
    if mime in RAR_MIMES:
        return "Archivo RAR subido correctamente."
    return "Archivo subido correctamente."


def _safe_filename(original: str, unique_id: str) -> str:
    ext = Path(original).suffix.lower()
    if not ext:
        ext = ".bin"
    return f"{unique_id}{ext}"


def _file_info(path: Path, base_url: str = "") -> dict:
    stat = path.stat()
    mime, _ = mimetypes.guess_type(path.name)
    url = f"{base_url}/files/{path.name}" if base_url else f"/files/{path.name}"
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
    return {"status": "ok", "message": "File server running."}


@app.post("/upload", summary="Subir un archivo", status_code=201)
async def upload_file(request: Request, file: UploadFile = File(...)):
    """
    Recibe un archivo, valida tipo y tamaño según la categoría,
    y lo guarda en disco. Las imágenes se validan con Pillow;
    el resto solo por firma de cabecera. Los archivos grandes se
    escriben en streaming para no saturar la RAM.
    """
    content_type = _resolve_content_type(file.content_type or "", file.filename or "")
    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail=(
                f"Tipo de archivo no permitido: '{file.content_type}'. "
                f"Permitidos: {sorted(ALLOWED_MIME_TYPES)}. "
                f"Para .exe y .rar usa la extensión correcta si el cliente envía "
                f"'{OCTET_STREAM}'."
            ),
        )

    max_bytes = _max_bytes_for_mime(content_type)
    max_mb = max_bytes // (1024 * 1024)

    unique_id = uuid.uuid4().hex
    safe_name = _safe_filename(file.filename or "upload", unique_id)
    dest = IMAGES_DIR / safe_name

    if content_type in IMAGE_MIMES:
        # Images: load fully into memory for Pillow deep validation (max 10 MB)
        data = await file.read()
        if len(data) > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"El archivo supera el límite de {max_mb} MB para este tipo.",
            )
        _validate_image(data)
        async with aiofiles.open(dest, "wb") as f:
            await f.write(data)
        size = len(data)
    else:
        # All other types: stream to disk to avoid loading large files into RAM
        size = await _stream_to_disk(file, dest, max_bytes, max_mb)
        header = _read_file_header(dest)
        try:
            _validate_header(content_type, header)
        except HTTPException:
            dest.unlink(missing_ok=True)
            raise

    base_url = str(request.base_url).rstrip("/")
    full_url = f"{base_url}/files/{safe_name}"

    return JSONResponse(
        status_code=201,
        content={
            "message": _upload_success_message(content_type),
            "filename": safe_name,
            "url": full_url,
            "size_bytes": size,
            "mime_type": content_type,
        },
    )


@app.get("/files", summary="Listar todos los archivos")
def list_files(
    request: Request,
    page: int = Query(1, ge=1, description="Número de página"),
    page_size: int = Query(20, ge=1, le=100, description="Archivos por página"),
):
    """Devuelve la lista paginada de archivos almacenados."""
    all_files = sorted(
        IMAGES_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True
    )
    stored_files = [p for p in all_files if p.is_file()]

    total = len(stored_files)
    start = (page - 1) * page_size
    end = start + page_size
    page_files = stored_files[start:end]

    base_url = str(request.base_url).rstrip("/")

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "files": [_file_info(p, base_url) for p in page_files],
    }


# Keep /images as alias for backwards compatibility
@app.get("/images", summary="[Alias] Listar archivos — usar /files", include_in_schema=False)
def list_images_alias(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    return list_files(request, page, page_size)


@app.get("/files/{filename}/info", summary="Metadata de un archivo")
def file_info(filename: str, request: Request):
    """Devuelve metadata (tamaño, tipo MIME y dimensiones si es imagen)."""
    safe_filename = Path(filename).name
    path = IMAGES_DIR / safe_filename

    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Archivo no encontrado.")

    base_url = str(request.base_url).rstrip("/")
    info = _file_info(path, base_url)

    mime = info.get("mime_type") or ""
    if mime.startswith("image/"):
        try:
            with Image.open(path) as img:
                info["width"] = img.width
                info["height"] = img.height
                info["format"] = img.format
        except Exception:
            pass

    return info


@app.get("/files/{filename}", summary="Descargar un archivo")
def get_file(filename: str):
    """Sirve el archivo directamente."""
    safe_filename = Path(filename).name
    path = IMAGES_DIR / safe_filename

    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Archivo no encontrado.")

    mime, _ = mimetypes.guess_type(safe_filename)
    return FileResponse(path, media_type=mime or "application/octet-stream")


@app.delete("/files/{filename}", summary="Eliminar un archivo")
def delete_file(filename: str):
    """Elimina un archivo del almacenamiento."""
    safe_filename = Path(filename).name
    path = IMAGES_DIR / safe_filename

    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Archivo no encontrado.")

    path.unlink()
    return {"message": f"Archivo '{safe_filename}' eliminado correctamente."}


# ---------------------------------------------------------------------------
# /images/{filename} aliases for backwards compatibility
# ---------------------------------------------------------------------------

@app.get("/images/{filename}/info", include_in_schema=False)
def image_info_alias(filename: str, request: Request):
    return file_info(filename, request)


@app.get("/images/{filename}", include_in_schema=False)
def get_image_alias(filename: str):
    return get_file(filename)


@app.delete("/images/{filename}", include_in_schema=False)
def delete_image_alias(filename: str):
    return delete_file(filename)
