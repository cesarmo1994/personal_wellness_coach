# Check-ins diarios con evidencia

## Objetivo

Documentar la implementacion de `PPH-16`: registro diario de progreso con
texto, evidencia y persistencia en Supabase.

## Flujo

1. El usuario autenticado completa el formulario de check-in.
2. Si adjunta archivo, `POST /api/upload-evidence` guarda la evidencia en el
   bucket privado `checkin-evidence`.
3. Al enviar el check-in, `POST /api/checkin` crea o actualiza el registro del
   dia en `public.checkins`.
4. El frontend mantiene una copia local para respuesta rapida y dashboard.
5. El coach IA recibe los check-ins recientes como contexto.

## Endpoint principal

### `POST /api/checkin`

Payload:

```json
{
  "user": "César",
  "date": "2026-05-15",
  "done": ["Entrenamiento", "Nutrición"],
  "note": "Cumplí el plan y subí evidencia.",
  "evidence": {
    "label": "foto.jpg guardado",
    "url": "https://...",
    "fileId": "...",
    "checkinId": "..."
  }
}
```

Respuesta:

```json
{
  "ok": true,
  "checkin": {
    "id": "...",
    "checkin_date": "2026-05-15",
    "goal_completed": true
  }
}
```

## Persistencia

Tabla principal:

- `public.checkins`

Campos usados:

- `profile_id`
- `team_id`
- `checkin_date`
- `goal_completed`
- `notes`
- `metrics`

La columna `metrics` guarda:

- items completados (`completed_items`)
- cantidad de items completados (`completed_count`)
- metadata de evidencia cargada

## Evidencia

La evidencia se guarda en:

- Bucket: `checkin-evidence`
- Tabla metadata: `public.checkin_files`
- Path: `profiles/{profile_id}/checkins/{checkin_id}/{filename}`

El bucket es privado. El backend devuelve signed URLs temporales.

## Contexto IA

Cuando el usuario autenticado conversa con el coach, el backend consulta los
ultimos check-ins desde Supabase y los usa como contexto reciente. Si no hay
sesion o no hay registros en DB, se mantiene el contexto enviado por el
frontend.

## Dashboard

El dashboard de progreso sigue usando el estado hidratado del frontend para
mantener una experiencia rapida en mobile. Cada check-in exitoso queda tambien
persistido en Supabase para recuperacion, auditoria y contexto del coach.
