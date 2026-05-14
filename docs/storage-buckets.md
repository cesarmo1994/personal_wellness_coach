# Buckets privados de Supabase Storage

## Objetivo

Documentar la configuracion de storage privado correspondiente a `PPH-13`.

La migracion versionada vive en:

```text
supabase/migrations/202605130002_storage_buckets.sql
```

## Proyecto Supabase

Project URL:

```text
https://uuwdhccchzeicdfsmpjz.supabase.co
```

Storage API base:

```text
https://uuwdhccchzeicdfsmpjz.supabase.co/storage/v1/
```

## Buckets

### `plan-files`

Uso:

- PDFs de planes.
- Documentos Word.
- Excel/CSV/TSV.
- TXT/Markdown.

Configuracion:

- Publico: no.
- Limite: 25 MB.
- Acceso: backend y signed URLs temporales.

Mime types permitidos:

- `application/pdf`
- `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
- `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- `text/csv`
- `text/tab-separated-values`
- `text/plain`
- `text/markdown`

### `checkin-evidence`

Uso:

- Fotos de progreso.
- Audios.
- Videos cortos.
- PDFs adjuntos como evidencia.

Configuracion:

- Publico: no.
- Limite: 50 MB.
- Acceso: backend y signed URLs temporales.

Mime types permitidos:

- `image/jpeg`
- `image/png`
- `image/webp`
- `image/heic`
- `image/heif`
- `audio/mpeg`
- `audio/mp4`
- `audio/aac`
- `audio/wav`
- `audio/webm`
- `video/mp4`
- `video/quicktime`
- `application/pdf`

### `avatars`

Uso:

- Fotos de perfil.
- Logos de equipos.

Configuracion:

- Publico: no.
- Limite: 5 MB.
- Acceso: backend y signed URLs temporales.

Mime types permitidos:

- `image/jpeg`
- `image/png`
- `image/webp`

## Por que privados

Los archivos de esta app pueden contener informacion sensible:

- Nutricion.
- Entrenamiento.
- Wellness.
- Fotos corporales o evidencia personal.
- Audios.
- Documentos privados.

Por eso los buckets deben ser privados y los archivos deben consultarse mediante signed URLs temporales.

## Como ejecutar la migracion

1. Abrir Supabase.
2. Entrar al proyecto `personal-wellness-coach`.
3. Ir a SQL Editor.
4. Crear un query nuevo.
5. Copiar el contenido de:

```text
supabase/migrations/202605130002_storage_buckets.sql
```

6. Ejecutar el SQL.
7. Ir a Storage.
8. Confirmar que existen los buckets:

```text
plan-files
checkin-evidence
avatars
```

9. Confirmar que los 3 buckets aparecen como privados/no publicos.

## RLS y acceso

Supabase Storage controla acceso usando RLS sobre `storage.objects`.

Decision para esta fase:

- Los buckets quedan privados.
- El frontend no debe subir/leer directamente todavia.
- El backend usara `SUPABASE_SERVICE_ROLE_KEY` para subir archivos.
- El backend generara signed URLs temporales para lectura.
- Las politicas finales de usuario/equipo se implementaran en `PPH-21`.

## Metadata en base de datos

El archivo real vive en Supabase Storage.

La metadata vive en tablas publicas:

- `plan_files`
- `checkin_files`

Campos clave:

- `bucket`
- `storage_path`
- `original_filename`
- `content_type`
- `file_kind`
- `size_bytes`
- `profile_id`
- `team_id`

## Backend

El backend en `server.py` usa Supabase Storage cuando existen estas variables:

```text
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
```

Flujo para planes:

1. El usuario carga un PDF, Word, Excel, CSV o TXT.
2. El backend analiza el archivo con OpenAI.
3. El backend crea un registro `profiles` si el usuario beta todavia no existe.
4. El backend crea un registro `plans` en estado `draft`.
5. El backend sube el archivo a `plan-files`.
6. El backend registra metadata en `plan_files`.
7. El backend devuelve una signed URL temporal.

Flujo para evidencia:

1. El usuario carga foto, audio, video corto o PDF.
2. El backend crea/reutiliza el `checkin` del dia.
3. El backend sube el archivo a `checkin-evidence`.
4. El backend registra metadata en `checkin_files`.
5. El backend devuelve una signed URL temporal.

Fallback:

- Si Supabase no esta configurado, el backend mantiene el comportamiento beta local usando `DATA_DIR`.

## Convencion de paths

Path recomendado para planes:

```text
profiles/{profile_id}/plans/{plan_id}/{file_id}-{safe_filename}
```

Path recomendado para evidencias:

```text
profiles/{profile_id}/checkins/{checkin_id}/{file_id}-{safe_filename}
```

Path recomendado para avatars:

```text
profiles/{profile_id}/avatar/{file_id}-{safe_filename}
teams/{team_id}/avatar/{file_id}-{safe_filename}
```

## Referencias oficiales

- https://supabase.com/docs/guides/storage/buckets/creating-buckets
- https://supabase.com/docs/guides/storage/security/access-control
- https://supabase.com/docs/guides/storage/buckets/fundamentals
