# Documentación Técnica de Integración — File Cloud Server

**URL base de producción:** `https://image-server-ax7b.onrender.com`  
**Documentación interactiva (Swagger):** `https://image-server-ax7b.onrender.com/docs`

---

## Índice

1. [Resumen de la API](#1-resumen-de-la-api)
2. [Tipos de archivo y límites](#2-tipos-de-archivo-y-límites)
3. [Referencia de endpoints](#3-referencia-de-endpoints)
4. [Modelos de respuesta](#4-modelos-de-respuesta)
5. [Códigos de error](#5-códigos-de-error)
6. [Ejemplos de integración](#6-ejemplos-de-integración)
   - [JavaScript / Node.js](#javascript--nodejs)
   - [Python](#python)
   - [PHP](#php)
   - [cURL](#curl)
7. [Restricciones y límites](#7-restricciones-y-límites)
8. [Notas de implementación](#8-notas-de-implementación)

---

## 1. Resumen de la API

La API es REST pura sobre HTTPS. No requiere autenticación. Las respuestas son siempre JSON excepto `GET /files/{filename}`, que devuelve el binario del archivo directamente.

CORS está habilitado para todos los orígenes (`*`), por lo que puede consumirse desde el navegador sin configuración adicional.

Las rutas canónicas son `/files/*`. Las rutas antiguas `/images/*` se mantienen como **aliases retrocompatibles** y funcionan exactamente igual.

---

## 2. Tipos de archivo y límites

| Categoría | Extensiones | MIME types aceptados | Límite |
|-----------|-------------|----------------------|--------|
| Imágenes | `.jpg` `.jpeg` `.png` `.gif` `.webp` `.bmp` | `image/jpeg` `image/png` `image/gif` `image/webp` `image/bmp` | **10 MB** |
| Audio WAV | `.wav` | `audio/wav` `audio/x-wav` `audio/wave` `audio/vnd.wave` | **50 MB** |
| Audio MP3 | `.mp3` | `audio/mpeg` `audio/mp3` | **50 MB** |
| Video MP4 | `.mp4` | `video/mp4` | **100 MB** |
| Ejecutable | `.exe` | `application/x-msdownload` `application/vnd.microsoft.portable-executable` `application/x-msdos-program` | **50 MB** |
| Archivo RAR | `.rar` | `application/vnd.rar` `application/x-rar-compressed` `application/x-rar` | **300 MB** |

> **Nota para `.exe` y `.rar`:** algunos clientes HTTP envían `application/octet-stream` en lugar del MIME correcto. El servidor detecta automáticamente el tipo por la **extensión del nombre de archivo** cuando esto ocurre, así que asegúrate de que el nombre incluya la extensión correcta.

---

## 3. Referencia de endpoints

### `GET /`
Verifica que el servidor esté activo.

**Respuesta `200`**
```json
{
  "status": "ok",
  "message": "File server running."
}
```

---

### `POST /upload`
Sube un archivo al servidor. Debe enviarse como `multipart/form-data`.

**Parámetros del body**

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `file` | `File` | Sí | Archivo a subir |

**Respuesta `201 Created`**
```json
{
  "message": "Archivo RAR subido correctamente.",
  "filename": "3f9a1b2cde4f56789abc0def12345678.rar",
  "url": "https://image-server-ax7b.onrender.com/files/3f9a1b2cde4f56789abc0def12345678.rar",
  "size_bytes": 52428800,
  "mime_type": "application/x-rar-compressed"
}
```

> El campo `url` es la URL absoluta y permanente del archivo. Es el valor que debes almacenar en tu base de datos.

---

### `GET /files`
Lista todos los archivos almacenados, ordenados por fecha de subida (más reciente primero). Soporta paginación.

**Alias retrocompatible:** `GET /images`

**Query parameters**

| Parámetro | Tipo | Por defecto | Rango | Descripción |
|-----------|------|-------------|-------|-------------|
| `page` | `integer` | `1` | ≥ 1 | Número de página |
| `page_size` | `integer` | `20` | 1 – 100 | Archivos por página |

**Ejemplo:** `GET /files?page=2&page_size=10`

**Respuesta `200`**
```json
{
  "total": 47,
  "page": 2,
  "page_size": 10,
  "files": [
    {
      "filename": "3f9a1b2cde4f56789abc0def12345678.rar",
      "size_bytes": 52428800,
      "mime_type": "application/x-rar-compressed",
      "url": "https://image-server-ax7b.onrender.com/files/3f9a1b2cde4f56789abc0def12345678.rar"
    }
  ]
}
```

---

### `GET /files/{filename}`
Descarga o sirve el archivo directamente. Para imágenes puede usarse como `src` en `<img>`.

**Alias retrocompatible:** `GET /images/{filename}`

**Parámetros de ruta**

| Parámetro | Descripción |
|-----------|-------------|
| `filename` | Nombre del archivo devuelto por `/upload` |

**Respuesta `200`** — binario del archivo con su `Content-Type` correcto.

---

### `GET /files/{filename}/info`
Devuelve la metadata completa del archivo. Para imágenes incluye dimensiones.

**Alias retrocompatible:** `GET /images/{filename}/info`

**Respuesta `200` — archivo no-imagen**
```json
{
  "filename": "3f9a1b2cde4f56789abc0def12345678.rar",
  "size_bytes": 52428800,
  "mime_type": "application/x-rar-compressed",
  "url": "https://image-server-ax7b.onrender.com/files/3f9a1b2cde4f56789abc0def12345678.rar"
}
```

**Respuesta `200` — imagen**
```json
{
  "filename": "3f9a1b2cde4f56789abc0def12345678.jpg",
  "size_bytes": 204800,
  "mime_type": "image/jpeg",
  "url": "https://image-server-ax7b.onrender.com/files/3f9a1b2cde4f56789abc0def12345678.jpg",
  "width": 1920,
  "height": 1080,
  "format": "JPEG"
}
```

---

### `DELETE /files/{filename}`
Elimina permanentemente un archivo del servidor.

**Alias retrocompatible:** `DELETE /images/{filename}`

**Respuesta `200`**
```json
{
  "message": "Archivo '3f9a1b2cde4f56789abc0def12345678.rar' eliminado correctamente."
}
```

---

## 4. Modelos de respuesta

### FileObject
Devuelto dentro del array `files` del endpoint `GET /files`.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `filename` | `string` | Nombre único del archivo en el servidor |
| `size_bytes` | `integer` | Tamaño en bytes |
| `mime_type` | `string` | Tipo MIME detectado |
| `url` | `string` | URL absoluta y permanente del archivo |

### FileInfo
Devuelto por `GET /files/{filename}/info`. Igual a `FileObject` más, solo para imágenes:

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `width` | `integer` | Ancho en píxeles |
| `height` | `integer` | Alto en píxeles |
| `format` | `string` | Formato (`JPEG`, `PNG`, `GIF`, `WEBP`) |

### UploadResponse
Devuelto por `POST /upload`.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `message` | `string` | Mensaje de confirmación |
| `filename` | `string` | Nombre único asignado al archivo |
| `url` | `string` | URL absoluta para acceder al archivo |
| `size_bytes` | `integer` | Tamaño del archivo guardado |
| `mime_type` | `string` | Tipo MIME del archivo aceptado |

---

## 5. Códigos de error

Todos los errores devuelven un JSON con el campo `detail`.

| Código | Situación |
|--------|-----------|
| `404 Not Found` | El archivo no existe |
| `413 Request Entity Too Large` | El archivo supera el límite para su tipo |
| `415 Unsupported Media Type` | El tipo MIME no está permitido |
| `422 Unprocessable Entity` | El archivo está corrupto o disfrazado (firma inválida) |

**Ejemplo de error:**
```json
{
  "detail": "El archivo supera el límite de 300 MB para este tipo."
}
```

---

## 6. Ejemplos de integración

### JavaScript / Node.js

**Subir cualquier archivo desde Node.js**
```javascript
import fs from 'fs';
import FormData from 'form-data';
import fetch from 'node-fetch';

const BASE_URL = 'https://image-server-ax7b.onrender.com';

async function uploadFile(filePath) {
  const form = new FormData();
  form.append('file', fs.createReadStream(filePath));

  const response = await fetch(`${BASE_URL}/upload`, {
    method: 'POST',
    body: form,
    headers: form.getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail);
  }

  return await response.json();
  // { filename, url, size_bytes, mime_type, message }
}

// Uso
const result = await uploadFile('./archivo.rar');
console.log('URL permanente:', result.url);
```

**Subir desde el navegador (frontend)**
```javascript
const BASE_URL = 'https://image-server-ax7b.onrender.com';

async function uploadFile(file) {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${BASE_URL}/upload`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail);
  }

  return await response.json();
}

// Ejemplo conectado a un <input type="file">
document.querySelector('#fileInput').addEventListener('change', async (e) => {
  const file = e.target.files[0];
  const result = await uploadFile(file);
  console.log('URL:', result.url);
});
```

**Listar archivos**
```javascript
async function listFiles(page = 1, pageSize = 20) {
  const url = new URL(`${BASE_URL}/files`);
  url.searchParams.set('page', page);
  url.searchParams.set('page_size', pageSize);

  const response = await fetch(url);
  return await response.json();
  // { total, page, page_size, files: [...] }
}
```

**Eliminar un archivo**
```javascript
async function deleteFile(filename) {
  const response = await fetch(`${BASE_URL}/files/${filename}`, {
    method: 'DELETE',
  });
  return await response.json();
}
```

---

### Python

```python
import requests

BASE_URL = "https://image-server-ax7b.onrender.com"

def upload_file(file_path: str) -> dict:
    with open(file_path, "rb") as f:
        response = requests.post(
            f"{BASE_URL}/upload",
            files={"file": (f.name, f)},
        )
    response.raise_for_status()
    return response.json()
    # { "filename": "...", "url": "...", "size_bytes": ..., "mime_type": ..., "message": "..." }

def list_files(page: int = 1, page_size: int = 20) -> dict:
    response = requests.get(
        f"{BASE_URL}/files",
        params={"page": page, "page_size": page_size},
    )
    response.raise_for_status()
    return response.json()

def get_file_info(filename: str) -> dict:
    response = requests.get(f"{BASE_URL}/files/{filename}/info")
    response.raise_for_status()
    return response.json()

def delete_file(filename: str) -> dict:
    response = requests.delete(f"{BASE_URL}/files/{filename}")
    response.raise_for_status()
    return response.json()


# Uso
result = upload_file("./backup.rar")
print("URL permanente:", result["url"])
```

---

### PHP

```php
<?php

define('BASE_URL', 'https://image-server-ax7b.onrender.com');

function uploadFile(string $filePath): array {
    $curl = curl_init(BASE_URL . '/upload');

    curl_setopt_array($curl, [
        CURLOPT_POST           => true,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_POSTFIELDS     => [
            'file' => new CURLFile($filePath, mime_content_type($filePath)),
        ],
    ]);

    $response = curl_exec($curl);
    $httpCode = curl_getinfo($curl, CURLINFO_HTTP_CODE);
    curl_close($curl);

    if ($httpCode !== 201) {
        throw new RuntimeException("Error al subir archivo: " . $response);
    }

    return json_decode($response, true);
    // ['filename' => '...', 'url' => '...', 'size_bytes' => ..., 'mime_type' => '...']
}

function listFiles(int $page = 1, int $pageSize = 20): array {
    $url  = BASE_URL . '/files?page=' . $page . '&page_size=' . $pageSize;
    $json = file_get_contents($url);
    return json_decode($json, true);
}

function deleteFile(string $filename): array {
    $curl = curl_init(BASE_URL . '/files/' . $filename);
    curl_setopt_array($curl, [
        CURLOPT_CUSTOMREQUEST  => 'DELETE',
        CURLOPT_RETURNTRANSFER => true,
    ]);
    $response = curl_exec($curl);
    curl_close($curl);
    return json_decode($response, true);
}

// Uso
$result = uploadFile('/ruta/a/backup.rar');
echo "URL permanente: " . $result['url'];
```

---

### cURL

**Subir una imagen**
```bash
curl -X POST https://image-server-ax7b.onrender.com/upload \
  -F "file=@/ruta/a/imagen.jpg"
```

**Subir un WAV**
```bash
curl -X POST https://image-server-ax7b.onrender.com/upload \
  -F "file=@/ruta/a/audio.wav"
```

**Subir un MP4**
```bash
curl -X POST https://image-server-ax7b.onrender.com/upload \
  -F "file=@/ruta/a/video.mp4"
```

**Subir un EXE**
```bash
curl -X POST https://image-server-ax7b.onrender.com/upload \
  -F "file=@/ruta/a/setup.exe"
```

**Subir un RAR**
```bash
curl -X POST https://image-server-ax7b.onrender.com/upload \
  -F "file=@/ruta/a/backup.rar"
```

**Listar archivos**
```bash
curl "https://image-server-ax7b.onrender.com/files?page=1&page_size=20"
```

**Ver metadata**
```bash
curl https://image-server-ax7b.onrender.com/files/3f9a1b2c...rar/info
```

**Descargar un archivo**
```bash
curl -o descargado.rar \
  https://image-server-ax7b.onrender.com/files/3f9a1b2c...rar
```

**Eliminar un archivo**
```bash
curl -X DELETE \
  https://image-server-ax7b.onrender.com/files/3f9a1b2c...rar
```

---

## 7. Restricciones y límites

| Parámetro | Valor |
|-----------|-------|
| Tamaño máximo — imágenes | **10 MB** |
| Tamaño máximo — WAV | **50 MB** |
| Tamaño máximo — MP3 | **50 MB** |
| Tamaño máximo — MP4 | **100 MB** |
| Tamaño máximo — EXE | **50 MB** |
| Tamaño máximo — RAR | **300 MB** |
| Máximo `page_size` en listado | **100** |
| Autenticación requerida | Ninguna |
| CORS | Todos los orígenes (`*`) |

---

## 8. Notas de implementación

### Nombres de archivo
El servidor **nunca conserva el nombre original** del archivo. Asigna un UUID hexadecimal de 32 caracteres seguido de la extensión original (ej. `3f9a1b2cde4f56789abc0def12345678.rar`). Esto garantiza unicidad y evita colisiones.

**Recomendación:** en tu base de datos guarda siempre el campo `url` completo devuelto por `/upload`, no el nombre original.

### Validación de archivos
El servidor realiza una doble validación para cada tipo:

1. **MIME type** del header `Content-Type` de la petición (o extensión del nombre si el cliente envía `application/octet-stream`).
2. **Firma de cabecera** del archivo real en disco para evitar archivos corruptos o disfrazados:

| Tipo | Firma verificada |
|------|-----------------|
| Imágenes | Validación completa con Pillow |
| WAV | `RIFF....WAVE` (primeros 12 bytes) |
| MP3 | `ID3` o frame sync MPEG (`0xFF 0xEx`) |
| MP4 | caja `ftyp` (primeros 64 bytes) |
| EXE | `MZ` (primeros 2 bytes — cabecera PE) |
| RAR | `Rar!` (primeros 4 bytes — RAR4 y RAR5) |

### Subida en streaming
Los archivos se escriben directamente a disco en chunks de 256 KB. El servidor **no carga el archivo completo en memoria**, lo que permite manejar archivos grandes (hasta 300 MB de RAR) sin saturar la RAM.

### Persistencia
Los archivos se almacenan en el disco persistente de Render montado en `/data/images`. Los archivos **sobreviven a redespliegues y reinicios** del servidor. No existe expiración automática.

### Mostrar imágenes en HTML
La URL devuelta por `/upload` puede usarse directamente:
```html
<img src="https://image-server-ax7b.onrender.com/files/3f9a1b2c...jpg" alt="Imagen" />
```

### Retrocompatibilidad
Las rutas `/images/*` siguen funcionando como aliases de `/files/*`. Si ya tienes URLs almacenadas con `/images/`, seguirán siendo válidas sin ningún cambio.
