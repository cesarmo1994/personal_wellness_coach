# Esquema de base de datos

## Objetivo

Documentar el esquema PostgreSQL inicial para Supabase correspondiente a `PPH-11`.

La migracion versionada vive en:

```text
supabase/migrations/202605130001_initial_schema.sql
```

Permisos backend para el service role:

```text
supabase/migrations/202605130003_backend_service_role_grants.sql
```

## Proyecto Supabase

Proyecto:

```text
personal-wellness-coach
```

Organization:

```text
CKMECR
```

Project URL:

```text
https://uuwdhccchzeicdfsmpjz.supabase.co
```

Data API base URL:

```text
https://uuwdhccchzeicdfsmpjz.supabase.co/rest/v1/
```

Estado:

```text
Migracion inicial ejecutada correctamente en Supabase.
```

## Alcance

El modelo soporta:

- Usuarios beta y usuarios autenticados futuros.
- Atletas individuales.
- Accountability groups.
- Equipos deportivos.
- Planes de nutricion, entrenamiento, wellness o combinados.
- Archivos asociados a planes.
- Check-ins diarios con evidencia.
- Chat personal y chat grupal.
- Insights del coach IA.
- Suscripciones de notificaciones.
- Conexion futura con Strava.

## Tablas principales

### `profiles`

Representa un usuario dentro de la app.

Notas:

- `auth_user_id` es nullable para soportar la beta actual sin login real.
- Cuando se implemente Supabase Auth, `auth_user_id` apuntara a `auth.users(id)`.
- `default_role` permite distinguir atleta, coach, admin de equipo u owner.

### `teams`

Representa un grupo o equipo.

Usos:

- Accountability group de amigos.
- Equipo deportivo.
- Contenedor individual tipo solo, si se requiere.

### `team_members`

Relaciona usuarios con equipos.

Permite:

- Varios miembros por equipo.
- Roles por equipo.
- Remover miembros sin borrar datos historicos usando `removed_at`.

### `plans`

Guarda planes activos e historicos.

Tipos:

- `nutrition`
- `training`
- `wellness`
- `combined`

Regla inicial:

- Solo puede existir un plan activo por usuario y tipo de plan.

Esto permite que un atleta tenga simultaneamente:

- Un plan de nutricion activo.
- Un plan de entrenamiento activo.
- Un plan de wellness activo.

### `plan_files`

Metadata de archivos cargados para crear o respaldar planes.

El archivo real debe vivir en Supabase Storage, bucket:

```text
plan-files
```

### `checkins`

Registro diario del progreso del atleta.

Incluye:

- Fecha.
- Si cumplio el objetivo.
- Mood, energia, soreness y horas de sueno.
- Notas.
- Metricas flexibles en `metrics`.

Regla inicial:

- Un check-in por usuario por dia.

### `checkin_files`

Metadata de fotos, audios o archivos asociados a check-ins.

El archivo real debe vivir en Supabase Storage, bucket:

```text
checkin-evidence
```

### `conversations`

Contenedor para chats.

Tipos:

- `personal`: chat entre usuario y coach IA.
- `group`: chat compartido por equipo/grupo.

Reglas:

- Un chat personal por usuario.
- Un chat grupal por equipo.

### `messages`

Mensajes de chat.

Soporta:

- Mensajes de usuario.
- Respuestas del coach IA.
- Mensajes del sistema.
- `mentions_coach` para saber si el grupo invoco al coach con `@coach`.
- Adjuntos como metadata JSON.

### `ai_insights`

Guarda respuestas o conclusiones importantes del coach IA.

Ejemplos:

- Analisis de un plan.
- Feedback diario.
- Resumen semanal.
- Alertas de riesgo.
- Resumen basado en Strava.

### `notification_subscriptions`

Guarda suscripciones para notificaciones.

Canales previstos:

- Web push.
- Email.
- SMS.
- WhatsApp.

La primera implementacion realista deberia ser Web Push.

## Strava

### `strava_connections`

Guarda la conexion OAuth entre un usuario y Strava.

Incluye:

- `strava_athlete_id`
- scopes concedidos
- access token
- refresh token
- expiracion
- ultima sincronizacion
- revocacion

Seguridad:

- Tokens solo deben ser leidos por backend.
- No deben exponerse al frontend.
- RLS y funciones servidoras deben proteger esta tabla.

### `strava_activities`

Guarda actividades normalizadas desde Strava.

Campos relevantes:

- tipo de deporte
- fecha
- duracion
- distancia
- elevacion
- velocidad promedio
- frecuencia cardiaca promedio
- resumen para IA
- payload crudo para auditoria tecnica

## Indices

La migracion crea indices para:

- Buscar planes activos por usuario/equipo.
- Consultar check-ins recientes.
- Cargar mensajes por conversacion.
- Consultar insights recientes.
- Consultar actividades Strava recientes.
- Resolver membresias por equipo y perfil.

## Timestamps

Las tablas principales tienen:

- `created_at`
- `updated_at`

La migracion incluye trigger `set_updated_at()` para actualizar automaticamente `updated_at`.

## Row Level Security

`PPH-11` define el esquema base.

El proyecto fue creado con:

- Data API habilitada.
- Exposicion automatica de tablas deshabilitada.
- Automatic RLS habilitado.
- Postgres default.

Como la exposicion automatica de tablas esta deshabilitada, el backend necesita grants explicitos para operar via PostgREST usando `SUPABASE_SERVICE_ROLE_KEY`. Estos grants se manejan en:

```text
supabase/migrations/202605130003_backend_service_role_grants.sql
```

Las politicas RLS completas se implementaran en:

```text
PPH-21 - Implementar seguridad, privacidad y RLS
```

Hasta entonces:

- No exponer `SUPABASE_SERVICE_ROLE_KEY` al frontend.
- Usar backend para operaciones privilegiadas.
- Evitar habilitar acceso publico a tablas sensibles sin politicas.

## Storage relacionado

Buckets esperados:

- `plan-files`
- `checkin-evidence`
- `avatars`

La creacion de buckets y reglas de acceso se trabaja en:

```text
PPH-13 - Migrar storage de archivos a buckets privados
```

## Siguientes pasos

1. Agregar captura del Table Editor como evidencia visual en Jira.
2. Guardar `SUPABASE_URL`, `SUPABASE_ANON_KEY` y `SUPABASE_SERVICE_ROLE_KEY` en Render.
3. Crear datos beta iniciales en una migracion o script separado.
4. Conectar backend Python a Supabase.
5. Implementar RLS antes de abrir a usuarios externos.

## Pasos ejecutados para crear Supabase

1. Crear cuenta en Supabase.
2. Crear organization `CKMECR`.
3. Crear proyecto `personal-wellness-coach`.
4. Seleccionar Postgres default.
5. Activar Data API.
6. Desactivar exposicion automatica de nuevas tablas.
7. Activar automatic RLS.
8. Abrir SQL Editor.
9. Copiar el contenido de `supabase/migrations/202605130001_initial_schema.sql`.
10. Ejecutar el SQL completo.
11. Validar en Table Editor que las tablas fueron creadas.
