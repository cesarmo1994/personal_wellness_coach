# Variables de ambiente

## Objetivo

Centralizar las variables necesarias para correr la app localmente y en produccion.

## Variables actuales

### `OPENAI_API_KEY`

Requerida en backend.

Uso:

- Analisis de planes.
- Creacion de planes por conversacion.
- Respuestas del coach IA.

Ejemplo local en PowerShell:

```powershell
$env:OPENAI_API_KEY="sk-..."
```

Reglas:

- No subir a GitHub.
- No pegar en `app.js`.
- No incluir comillas dentro del valor en Render.
- No incluir comandos como `$env:OPENAI_MODEL=...` en el mismo campo.

### `OPENAI_MODEL`

Modelo usado por defecto para las llamadas a OpenAI.

Valor actual recomendado:

```text
gpt-5.2
```

Ejemplo local:

```powershell
$env:OPENAI_MODEL="gpt-5.2"
```

### `DATA_DIR`

Directorio donde la beta guarda estado y uploads cuando aun no existe Supabase.

Local por defecto:

```text
data/
```

Render con disco:

```text
/var/data
```

Nota:

- Esta variable es transitoria.
- Para escalar, los datos deben pasar a Supabase.

### `PORT`

Puerto asignado por Render o definido localmente.

Local por defecto:

```text
3000
```

Render lo inyecta automaticamente.

## Variables Supabase futuras

### `SUPABASE_URL`

URL del proyecto Supabase.

Ejemplo:

```text
https://xxxx.supabase.co
```

### `SUPABASE_ANON_KEY`

Key publica limitada por RLS.

Uso futuro:

- Puede ser usada por frontend cuando exista autenticacion real.
- Debe combinarse con Row Level Security.

### `SUPABASE_SERVICE_ROLE_KEY`

Key privada de servidor.

Uso:

- Tareas backend privilegiadas.
- Migraciones operativas.
- Procesos controlados de archivos.

Reglas:

- Solo backend.
- Nunca frontend.
- Nunca GitHub.

## Variables Strava futuras

### `STRAVA_CLIENT_ID`

ID publico de la aplicacion creada en Strava.

### `STRAVA_CLIENT_SECRET`

Secreto privado de la aplicacion Strava.

Reglas:

- Solo backend.
- Nunca frontend.
- Nunca GitHub.

### `STRAVA_VERIFY_TOKEN`

Token definido por nosotros para validar la creacion del webhook de Strava.

### `STRAVA_WEBHOOK_CALLBACK_URL`

URL publica donde Strava enviara eventos.

Ejemplo:

```text
https://wellness.ckmecr.com/api/strava/webhook
```

## Variables de URL

### `PUBLIC_APP_URL`

URL publica de la aplicacion.

Actual:

```text
https://personal-wellness-coach.onrender.com
```

Objetivo:

```text
https://wellness.ckmecr.com
```

## Checklist de Render

Variables requeridas hoy:

- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `DATA_DIR`

Variables requeridas para Supabase:

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`

Variables requeridas para Strava:

- `STRAVA_CLIENT_ID`
- `STRAVA_CLIENT_SECRET`
- `STRAVA_VERIFY_TOKEN`
- `STRAVA_WEBHOOK_CALLBACK_URL`

## Errores comunes

Error: `Incorrect API key provided: tu_api_key`

Causa:

- La variable tiene el texto placeholder en vez de una key real.

Error: `Invalid header value b'Bearer ... "$env:OPENAI_MODEL=...'`

Causa:

- Se pego mas de un comando o una linea completa de PowerShell dentro del valor de `OPENAI_API_KEY`.

Solucion:

- En Render, el valor debe ser solo la key.
- Sin comillas.
- Sin saltos de linea.
- Sin `$env:`.
