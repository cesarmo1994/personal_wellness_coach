# Estrategia de storage y persistencia

## Objetivo

Definir donde vive cada tipo de dato para que la app pueda pasar de beta a produccion sin perder historial, archivos ni evidencia.

## Estado actual

La beta guarda datos en el servidor:

```text
data/app_state.json
data/uploads/
```

En Render con disco persistente:

```text
/var/data/app_state.json
/var/data/uploads/
```

Esto funciona para una beta pequena, pero no es la arquitectura final.

## Problema

El disco del servidor no es suficiente para escalar porque:

- Mezcla datos de aplicacion con runtime.
- Complica backups y migraciones.
- No sirve bien para multiples instancias.
- No da controles finos de seguridad por usuario/equipo.
- Render Free no garantiza disco persistente.

## Estrategia objetivo

### Supabase PostgreSQL

Guardar:

- Usuarios/perfiles.
- Equipos.
- Membresias.
- Plan activo.
- Historial de planes.
- Check-ins.
- Mensajes.
- Insights IA.
- Metadata de archivos.
- Conexiones externas como Strava.

El esquema inicial esta documentado en:

```text
docs/database-schema.md
```

La migracion versionada vive en:

```text
supabase/migrations/202605130001_initial_schema.sql
```

Proyecto Supabase actual:

```text
https://uuwdhccchzeicdfsmpjz.supabase.co
```

Data API base:

```text
https://uuwdhccchzeicdfsmpjz.supabase.co/rest/v1/
```

### Supabase Storage

Guardar:

- PDFs de planes.
- Documentos Word.
- Excel/CSV de planes.
- Fotos de progreso.
- Audios.
- Evidencia de check-ins.

### Render filesystem

Usar solo para:

- Archivos temporales durante procesamiento.
- Cache no critica.
- Logs generados por plataforma.

No usar para:

- Historial definitivo.
- Archivos de usuarios.
- Tokens OAuth.
- Datos comerciales.

## Buckets recomendados

### `plan-files`

Contenido:

- PDFs.
- DOCX.
- XLSX.
- CSV.
- TXT.

Acceso:

- Privado.
- Signed URLs temporales.

### `checkin-evidence`

Contenido:

- Fotos.
- Audios.
- Archivos asociados a check-ins.

Acceso:

- Privado.
- Visible para el atleta, su coach y miembros permitidos del equipo.

### `avatars`

Contenido:

- Fotos de perfil.
- Logos de equipos.

Acceso:

- Puede ser publico o privado segun decision de producto.

## Retencion

Beta actual:

- 30 dias de historial operativo.

Recomendacion productiva:

- Guardar historico completo.
- Usar 30 dias como contexto por defecto para IA.
- Definir limites por plan comercial.

Ejemplo:

- Individual beta: 30 dias visibles.
- Individual paid: 12 meses.
- Equipo: historico completo mientras la suscripcion este activa.

## Strava

Datos de Strava recomendados en DB:

- `strava_athlete_id`
- `access_token`
- `refresh_token`
- `expires_at`
- scopes concedidos
- fecha de ultima sincronizacion
- actividades sincronizadas

Datos de actividad:

- id de actividad Strava
- usuario interno
- tipo de deporte
- fecha
- duracion
- distancia
- elevacion
- ritmo/velocidad promedio
- esfuerzo percibido si existe en la app
- payload resumido para IA

Reglas:

- No guardar mas datos de los necesarios.
- Respetar revocacion de acceso.
- Si Strava manda evento de deauthorization, marcar conexion como revocada.
- Evitar polling agresivo; preferir webhooks.

## Privacidad

Los datos de wellness, entrenamiento, nutricion y progreso son sensibles.

Requisitos:

- Row Level Security en Supabase.
- Buckets privados.
- Signed URLs con expiracion.
- Consentimiento para procesar documentos con IA.
- Consentimiento separado para conectar Strava.
- Opcion futura de borrar datos del usuario.

## Migracion desde beta

Cuando se implemente Supabase:

1. Leer `app_state.json`.
2. Crear usuarios beta: David, Pri, Ana y Cesar.
3. Crear equipo inicial.
4. Insertar planes activos.
5. Insertar mensajes personales y grupales.
6. Insertar check-ins.
7. Subir archivos existentes a Supabase Storage.
8. Guardar metadata de archivos.
9. Validar conteos antes/despues.

## Criterio de salida

Esta estrategia se considera implementada cuando:

- La app no depende de `app_state.json` para datos productivos.
- Los archivos de usuario estan en storage privado.
- Los chats sobreviven redeploys y reinicios.
- La IA puede usar historial persistente.
- Strava puede sincronizar datos sin guardar tokens en archivos locales.
