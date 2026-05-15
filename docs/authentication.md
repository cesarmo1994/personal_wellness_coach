# Autenticacion y roles

## Objetivo

Documentar la implementacion de autenticacion correspondiente a `PPH-12`.

## Proveedor

La app usa:

```text
Supabase Auth + Google OAuth
```

## Flujo

1. Usuario toca `Google`.
2. Supabase redirige al login de Google.
3. Google devuelve la sesion a la app.
4. El frontend envia el `access_token` al backend.
5. El backend valida el token contra Supabase Auth.
6. El backend crea o enlaza el `profile`.
7. El backend agrega el usuario al equipo `Los Pichudos`.
8. El frontend fija el usuario activo al perfil autenticado.
9. Las acciones sensibles mandan `Authorization: Bearer <access_token>`.

## Variables requeridas

En Render:

```text
SUPABASE_URL
SUPABASE_ANON_KEY
SUPABASE_SERVICE_ROLE_KEY
ADMIN_EMAILS
```

`ADMIN_EMAILS` es opcional. Si no existe, el default es:

```text
cesar@ckmecr.com
```

Para varios admins:

```text
ADMIN_EMAILS=cesar@ckmecr.com,otro@ckmecr.com
```

## Endpoints backend

### `GET /api/config`

Devuelve configuracion publica para inicializar Supabase en frontend:

```json
{
  "supabaseUrl": "...",
  "supabaseAnonKey": "...",
  "authProvider": "google"
}
```

### `POST /api/auth/session`

Recibe:

```json
{
  "accessToken": "..."
}
```

Valida la sesion con Supabase Auth y devuelve:

```json
{
  "profile": {
    "id": "...",
    "displayName": "Cesar",
    "email": "cesar@ckmecr.com",
    "role": "owner"
  },
  "team": {
    "id": "...",
    "name": "Los Pichudos"
  }
}
```

### Requests autenticados

Cuando hay sesion activa, el frontend agrega el bearer token en:

- `POST /api/analyze-plan`
- `POST /api/create-plan`
- `POST /api/chat`
- `POST /api/upload-evidence`
- `GET/POST /api/app-state`

El backend usa ese token para resolver el usuario real en cargas de planes,
planes creados por conversacion y evidencias de check-in. Si no hay token, se
mantiene el modo beta con el usuario seleccionado manualmente.

## Roles

Roles soportados:

- `athlete`
- `coach`
- `team_admin`
- `owner`

Regla inicial:

- Emails en `ADMIN_EMAILS` quedan como `owner`.
- Otros usuarios quedan como `athlete`.
- Owners se agregan al equipo como `team_admin`.

## Fallback beta

Si Supabase Auth no esta configurado en el backend:

- La app sigue funcionando con selector beta.
- El boton muestra estado `Beta`.
- No se bloquea el uso actual.

Si Supabase Auth si esta configurado:

- La app muestra una puerta de acceso con Google.
- El selector manual queda bloqueado despues del login.
- El usuario activo sale del perfil validado por Supabase Auth.

## Configuracion en Supabase

En Supabase:

1. Ir a Authentication.
2. Ir a Providers.
3. Activar Google.
4. Configurar Client ID y Client Secret de Google Cloud.
5. Agregar redirect URL de la app.

Redirect URL para Render:

```text
https://personal-wellness-coach.onrender.com
```

Redirect URL futura:

```text
https://wellness.ckmecr.com
```

## Notas de seguridad

- `SUPABASE_ANON_KEY` puede llegar al frontend.
- `SUPABASE_SERVICE_ROLE_KEY` nunca debe llegar al frontend.
- El backend valida el token antes de enlazar perfiles.
- Las politicas RLS finales se implementan en `PPH-21`.
