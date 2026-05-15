# Persistencia de chats

## Objetivo

Documentar la persistencia de conversaciones personales y grupales correspondiente a `PPH-14`.

## Alcance

La app conserva:

- Chat personal entre cada usuario y el coach IA.
- Chat grupal del accountability group.
- Mensajes de usuario.
- Respuestas del coach IA.
- Mensajes de sistema.
- Contexto de `@coach`.

## Tablas usadas

### `conversations`

Contiene los threads de chat.

Tipos:

- `personal`: una conversacion por usuario.
- `group`: una conversacion por equipo/grupo.

### `messages`

Contiene los mensajes.

Campos clave:

- `conversation_id`
- `profile_id`
- `team_id`
- `sender_type`
- `body`
- `mentions_coach`
- `created_at`
- `client_message_id`

## Migracion de soporte

La migracion versionada vive en:

```text
supabase/migrations/202605140004_chat_message_dedupe.sql
```

Esta migracion agrega:

- `client_message_id` en `messages`.
- Indice unico por `conversation_id` + `client_message_id`.
- Indice por `created_at`.

El objetivo de `client_message_id` es evitar duplicados cuando el frontend hace autosave varias veces.

## Funcionamiento backend

El endpoint actual:

```text
POST /api/app-state
```

mantiene el guardado beta en `app_state.json`, pero ahora tambien sincroniza mensajes hacia Supabase cuando existen:

```text
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
```

El endpoint:

```text
GET /api/app-state
```

lee el estado beta y luego intenta rehidratar los chats desde Supabase.

## Grupo beta

El chat grupal actual se guarda como equipo:

```text
Los Pichudos
```

Slug:

```text
los-pichudos
```

Los usuarios beta se crean/reutilizan como `profiles` y se agregan a `team_members`.

## Retencion

La retencion minima configurable es:

```text
CHAT_RETENTION_DAYS=30
```

Si no se configura, el backend usa 30 dias.

## Modo hibrido

Durante la beta:

- `app_state.json` sigue funcionando como respaldo local.
- Supabase se vuelve la fuente persistente para mensajes.
- Si Supabase no esta configurado, la app no se rompe y sigue usando el flujo anterior.
- Un dispositivo sin historia real debe aceptar la historia del servidor aunque su `updatedAt` local sea mas reciente por haber abierto la app.
- Al hidratar desde Supabase, el backend deduplica mensajes consecutivos identicos y mensajes default repetidos para limpiar duplicados generados durante pruebas/autosaves.

## Como validar

1. Ejecutar en Supabase:

```text
supabase/migrations/202605140004_chat_message_dedupe.sql
```

2. Confirmar variables en Render:

```text
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
```

3. En la app, enviar mensajes en:

- Coach personal.
- Chat grupal.
- Chat grupal con `@coach`.

4. Revisar Supabase:

- `conversations` debe tener threads personales y grupal.
- `messages` debe tener mensajes de usuarios y coach IA.
- `team_members` debe asociar usuarios al equipo `Los Pichudos`.

5. Recargar la app o abrir desde otro dispositivo.

Resultado esperado:

- Los chats se cargan desde la historia persistida.
- No se duplican mensajes con cada autosave.

## Pendientes fuera de PPH-14

- RLS final por usuario/equipo: `PPH-21`.
- Realtime nativo de Supabase para chat: `PPH-17`.
- Auth real y roles: `PPH-12`.
