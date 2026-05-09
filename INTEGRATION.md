# Documentación Técnica de Integración — Image Cloud Server

**URL base de producción:** `https://image-server-ax7b.onrender.com`  
**Documentación interactiva (Swagger):** `https://image-server-ax7b.onrender.com/docs`

---

## Índice

1. [Resumen de la API](#1-resumen-de-la-api)
2. [Referencia de endpoints](#2-referencia-de-endpoints)
3. [Modelos de respuesta](#3-modelos-de-respuesta)
4. [Códigos de error](#4-códigos-de-error)
5. [Ejemplos de integración](#5-ejemplos-de-integración)
   - [JavaScript / Node.js](#javascript--nodejs)
   - [Python](#python)
   - [PHP](#php)
   - [cURL](#curl)
6. [Restricciones y límites](#6-restricciones-y-límites)
7. [Notas de implementación](#7-notas-de-implementación)

---

## 1. Resumen de la API

La API es REST pura sobre HTTPS. No requiere autenticación. Las respuestas son siempre JSON excepto `GET /images/{filename}` que devuelve el binario de la imagen directamente.

CORS está habilitado para todos los orígenes (`*`), por lo que puede consumirse desde el navegador sin configuración adicional.

---

## 2. Referencia de endpoints

### `GET /`
Verifica que el servidor esté activo.

**Respuesta `200`**
```json
{
  "status": "ok",
  "message": "Image server running."
}
```

---

### `POST /upload`
Sube una imagen al servidor. El archivo debe enviarse como `multipart/form-data`.

**Parámetros del body**

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `file` | `File` | Sí | Archivo de imagen |

**Respuesta `201 Created`**
```json
{
  "message": "Imagen subida correctamente.",
  "filename": "3f9a1b2cde4f56789abc0def12345678.jpg",
  "url": "https://image-server-ax7b.onrender.com/images/3f9a1b2cde4f56789abc0def12345678.jpg",
  "size_bytes": 204800
}
```

> El campo `url` es la URL absoluta y permanente de la imagen. Es el valor que debes almacenar en tu base de datos.

---

### `GET /images`
Lista todas las imágenes almacenadas, ordenadas por fecha de subida (más reciente primero). Soporta paginación.

**Query parameters**

| Parámetro | Tipo | Por defecto | Rango | Descripción |
|-----------|------|-------------|-------|-------------|
| `page` | `integer` | `1` | ≥ 1 | Número de página |
| `page_size` | `integer` | `20` | 1 – 100 | Imágenes por página |

**Ejemplo:** `GET /images?page=2&page_size=10`

**Respuesta `200`**
```json
{
  "total": 47,
  "page": 2,
  "page_size": 10,
  "images": [
    {
      "filename": "3f9a1b2cde4f56789abc0def12345678.jpg",
      "size_bytes": 204800,
      "mime_type": "image/jpeg",
      "url": "https://image-server-ax7b.onrender.com/images/3f9a1b2cde4f56789abc0def12345678.jpg"
    }
  ]
}
```

---

### `GET /images/{filename}`
Sirve el binario de la imagen directamente. Úsalo como `src` en una etiqueta `<img>` o para descargar el archivo.

**Parámetros de ruta**

| Parámetro | Descripción |
|-----------|-------------|
| `filename` | Nombre del archivo devuelto por `/upload` |

**Respuesta `200`** — binario de la imagen con su `Content-Type` correcto (`image/jpeg`, `image/png`, etc.)

---

### `GET /images/{filename}/info`
Devuelve la metadata completa de una imagen incluyendo dimensiones.

**Respuesta `200`**
```json
{
  "filename": "3f9a1b2cde4f56789abc0def12345678.jpg",
  "size_bytes": 204800,
  "mime_type": "image/jpeg",
  "url": "https://image-server-ax7b.onrender.com/images/3f9a1b2cde4f56789abc0def12345678.jpg",
  "width": 1920,
  "height": 1080,
  "format": "JPEG"
}
```

---

### `DELETE /images/{filename}`
Elimina permanentemente una imagen del servidor.

**Respuesta `200`**
```json
{
  "message": "Imagen '3f9a1b2cde4f56789abc0def12345678.jpg' eliminada correctamente."
}
```

---

## 3. Modelos de respuesta

### ImageObject
Devuelto dentro del array `images` del endpoint `/images`.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `filename` | `string` | Nombre único del archivo en el servidor |
| `size_bytes` | `integer` | Tamaño en bytes |
| `mime_type` | `string` | Tipo MIME (`image/jpeg`, etc.) |
| `url` | `string` | URL absoluta y permanente de la imagen |

### ImageInfo
Devuelto por `/images/{filename}/info`. Extiende `ImageObject` con:

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `width` | `integer` | Ancho en píxeles |
| `height` | `integer` | Alto en píxeles |
| `format` | `string` | Formato interno (`JPEG`, `PNG`, `GIF`, `WEBP`) |

### UploadResponse
Devuelto por `POST /upload`.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `message` | `string` | Mensaje de confirmación |
| `filename` | `string` | Nombre único asignado al archivo |
| `url` | `string` | URL absoluta para acceder a la imagen |
| `size_bytes` | `integer` | Tamaño del archivo guardado |

---

## 4. Códigos de error

Todos los errores devuelven un JSON con el campo `detail`.

| Código | Situación |
|--------|-----------|
| `404 Not Found` | La imagen no existe |
| `413 Request Entity Too Large` | El archivo supera el límite de 10 MB |
| `415 Unsupported Media Type` | El tipo MIME no está permitido |
| `422 Unprocessable Entity` | El archivo no es una imagen válida (corrupto o disfrazado) |

**Ejemplo de error:**
```json
{
  "detail": "Tipo de archivo no permitido: 'application/pdf'. Permitidos: ['image/bmp', 'image/gif', 'image/jpeg', 'image/png', 'image/webp']"
}
```

---

## 5. Ejemplos de integración

### JavaScript / Node.js

**Subir una imagen desde Node.js**
```javascript
import fs from 'fs';
import FormData from 'form-data';
import fetch from 'node-fetch';

const BASE_URL = 'https://image-server-ax7b.onrender.com';

async function uploadImage(filePath) {
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
  // { filename, url, size_bytes, message }
}

// Uso
const result = await uploadImage('./foto.jpg');
console.log('URL permanente:', result.url);
```

**Subir desde el navegador (frontend)**
```javascript
const BASE_URL = 'https://image-server-ax7b.onrender.com';

async function uploadImage(file) {
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
  const result = await uploadImage(file);
  document.querySelector('#preview').src = result.url;
});
```

**Listar imágenes**
```javascript
async function listImages(page = 1, pageSize = 20) {
  const url = new URL(`${BASE_URL}/images`);
  url.searchParams.set('page', page);
  url.searchParams.set('page_size', pageSize);

  const response = await fetch(url);
  return await response.json();
  // { total, page, page_size, images: [...] }
}
```

**Eliminar una imagen**
```javascript
async function deleteImage(filename) {
  const response = await fetch(`${BASE_URL}/images/${filename}`, {
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

def upload_image(file_path: str) -> dict:
    with open(file_path, "rb") as f:
        response = requests.post(
            f"{BASE_URL}/upload",
            files={"file": (f.name, f, "image/jpeg")},
        )
    response.raise_for_status()
    return response.json()
    # { "filename": "...", "url": "...", "size_bytes": ..., "message": "..." }

def list_images(page: int = 1, page_size: int = 20) -> dict:
    response = requests.get(
        f"{BASE_URL}/images",
        params={"page": page, "page_size": page_size},
    )
    response.raise_for_status()
    return response.json()

def get_image_info(filename: str) -> dict:
    response = requests.get(f"{BASE_URL}/images/{filename}/info")
    response.raise_for_status()
    return response.json()

def delete_image(filename: str) -> dict:
    response = requests.delete(f"{BASE_URL}/images/{filename}")
    response.raise_for_status()
    return response.json()


# Uso
result = upload_image("./foto.jpg")
print("URL permanente:", result["url"])
```

---

### PHP

```php
<?php

define('BASE_URL', 'https://image-server-ax7b.onrender.com');

function uploadImage(string $filePath): array {
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
        throw new RuntimeException("Error al subir imagen: " . $response);
    }

    return json_decode($response, true);
    // ['filename' => '...', 'url' => '...', 'size_bytes' => ...]
}

function listImages(int $page = 1, int $pageSize = 20): array {
    $url  = BASE_URL . '/images?page=' . $page . '&page_size=' . $pageSize;
    $json = file_get_contents($url);
    return json_decode($json, true);
}

function deleteImage(string $filename): array {
    $curl = curl_init(BASE_URL . '/images/' . $filename);
    curl_setopt_array($curl, [
        CURLOPT_CUSTOMREQUEST  => 'DELETE',
        CURLOPT_RETURNTRANSFER => true,
    ]);
    $response = curl_exec($curl);
    curl_close($curl);
    return json_decode($response, true);
}

// Uso
$result = uploadImage('/ruta/a/foto.jpg');
echo "URL permanente: " . $result['url'];
```

---

### cURL

**Subir una imagen**
```bash
curl -X POST https://image-server-ax7b.onrender.com/upload \
  -F "file=@/ruta/a/imagen.jpg"
```

**Listar imágenes**
```bash
curl "https://image-server-ax7b.onrender.com/images?page=1&page_size=20"
```

**Ver metadata**
```bash
curl https://image-server-ax7b.onrender.com/images/3f9a1b2c...jpg/info
```

**Descargar una imagen**
```bash
curl -o descargada.jpg \
  https://image-server-ax7b.onrender.com/images/3f9a1b2c...jpg
```

**Eliminar una imagen**
```bash
curl -X DELETE \
  https://image-server-ax7b.onrender.com/images/3f9a1b2c...jpg
```

---

## 6. Restricciones y límites

| Parámetro | Valor |
|-----------|-------|
| Tamaño máximo por imagen | **10 MB** |
| Tipos de imagen permitidos | `image/jpeg`, `image/png`, `image/gif`, `image/webp`, `image/bmp` |
| Máximo `page_size` en listado | **100** |
| Autenticación requerida | Ninguna |
| CORS | Todos los orígenes (`*`) |

---

## 7. Notas de implementación

### Nombres de archivo
El servidor **nunca conserva el nombre original** del archivo. Asigna un UUID hexadecimal de 32 caracteres seguido de la extensión original (ej. `3f9a1b2cde4f56789abc0def12345678.jpg`). Esto garantiza unicidad y evita colisiones.

**Recomendación:** en tu base de datos guarda siempre el campo `url` completo devuelto por `/upload`, no el nombre original.

### Validación de imágenes
El servidor realiza una doble validación:
1. Comprueba el `Content-Type` del header de la petición.
2. Verifica el contenido real del archivo con la librería Pillow para evitar archivos corruptos o disfrazados como imágenes.

### Persistencia
Las imágenes se almacenan en el disco persistente de Render montado en `/data/images`. Los archivos **sobreviven a redespliegues y reinicios** del servidor. No existe expiración automática.

### Mostrar imágenes en HTML
La URL devuelta por `/upload` puede usarse directamente:
```html
<img src="https://image-server-ax7b.onrender.com/images/3f9a1b2c...jpg" alt="Imagen" />
```
