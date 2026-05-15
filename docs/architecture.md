# Arquitectura productiva

## Objetivo

Definir la arquitectura base para llevar The Pichudo's App desde una beta funcional hacia una plataforma escalable para atletas individuales, accountability groups y equipos deportivos.

Esta documentacion corresponde a la historia Jira `PPH-10`.

## Principios

- Mobile-first: la experiencia principal vive en navegador movil.
- Web app antes que app nativa: evitar Android/iOS mientras validamos el producto.
- Backend como frontera segura: credenciales, OpenAI, Strava y Supabase service role nunca deben ir al frontend.
- Persistencia fuera de Render: Render ejecuta la app; Supabase debe guardar datos, archivos e historial.
- Integraciones con consentimiento: OpenAI procesa contenido cargado por usuarios; Strava requiere OAuth por atleta.
- Producto beta, arquitectura seria: aunque el primer uso sea entre amigos, el diseno debe soportar equipos y monetizacion.

## Arquitectura objetivo

```text
Usuario movil
  |
  v
Render Web Service
  - Python backend
  - frontend estatico
  - API interna de la app
  |
  +--> OpenAI API
  |     - analisis de PDF, documentos y notas
  |     - creacion de planes
  |     - coach IA personal y grupal
  |
  +--> Supabase PostgreSQL
  |     - usuarios y perfiles
  |     - equipos y miembros
  |     - planes activos
  |     - check-ins
  |     - mensajes personales y grupales
  |     - insights generados por IA
  |     - conexiones OAuth externas
  |
  +--> Supabase Storage
  |     - PDFs
  |     - Word/Excel
  |     - fotos de progreso
  |     - audios y evidencia
  |
  +--> Supabase Realtime
  |     - chat grupal
  |     - actualizaciones de check-ins
  |
  +--> Strava API
        - autorizacion OAuth por atleta
        - sincronizacion de actividades
        - webhooks de actividades nuevas/actualizadas
```

## Servicios

### Render

Responsabilidad:

- Hospedar el backend Python y el frontend.
- Ejecutar despliegues desde GitHub.
- Exponer HTTPS.
- Mantener variables de ambiente productivas.

Uso actual:

- `server.py` atiende archivos estaticos y endpoints `/api/*`.
- `render.yaml` define servicio web Python.
- `/healthz` funciona como health check.

Destino:

- Mantener Render como plataforma de app.
- Evitar depender de disco local para persistencia critica.

### Supabase

Responsabilidad:

- Base de datos PostgreSQL.
- Auth.
- Storage privado.
- Realtime.
- Row Level Security.

Destino:

- Ser la fuente de verdad de datos.
- Reemplazar `data/app_state.json` y `data/uploads`.
- Guardar tokens OAuth de Strava cifrados o protegidos a nivel servidor.

Historias relacionadas:

- `PPH-11`: esquema de base de datos.
- `PPH-12`: auth y roles.
- `PPH-13`: storage privado.
- `PPH-14`: chats persistentes.
- `PPH-21`: seguridad, privacidad y RLS.

### OpenAI

Responsabilidad:

- Analizar planes cargados por archivo.
- Crear planes por conversacion.
- Generar recomendaciones, ajustes e insights.
- Responder como coach IA.

Notas:

- La API key debe existir solo en backend.
- Los archivos PDF se procesan mediante OpenAI Files API.
- Word/Excel/CSV/TXT pueden extraerse localmente y enviarse como texto.
- El contexto enviado a IA debe limitarse a datos relevantes, por ejemplo plan activo, ultimos check-ins y ultimos mensajes.

### Strava

Responsabilidad:

- Permitir que un atleta conecte su cuenta de Strava.
- Obtener entrenamientos reales.
- Complementar check-ins con datos de actividad.
- Alimentar insights del coach con distancia, duracion, ritmo, elevacion, tipo de deporte y frecuencia.

Flujo propuesto:

1. Usuario toca "Conectar Strava".
2. La app redirige al OAuth de Strava.
3. Strava pide consentimiento al atleta.
4. Backend recibe el `code` en un callback seguro.
5. Backend intercambia el `code` por tokens.
6. Backend guarda tokens asociados al usuario.
7. La app sincroniza actividades recientes.
8. Webhooks de Strava notifican actividades nuevas, actualizadas o eliminadas.
9. Backend procesa el evento y actualiza Supabase.

Scopes iniciales recomendados:

- `read`: leer perfil basico autorizado.
- `activity:read`: leer actividades visibles para la app.
- `activity:read_all`: solo si el producto necesita actividades privadas y el usuario da consentimiento claro.

Endpoints internos futuros:

- `GET /api/strava/connect`
- `GET /api/strava/callback`
- `POST /api/strava/webhook`
- `GET /api/strava/status`
- `POST /api/strava/sync`

Variables futuras:

- `STRAVA_CLIENT_ID`
- `STRAVA_CLIENT_SECRET`
- `STRAVA_VERIFY_TOKEN`
- `STRAVA_WEBHOOK_CALLBACK_URL`

Referencias oficiales:

- https://developers.strava.com/docs/
- https://developers.strava.com/docs/authentication
- https://developers.strava.com/docs/webhooks/
- https://developers.strava.com/docs/rate-limits/

## Modelo de usuarios objetivo

Beta actual:

- Login con Google via Supabase Auth.
- Perfil admin inicial: `cesar@ckmecr.com`.
- Los perfiles fijos David, Pri, Ana y Cesar fueron retirados del estado inicial.

Modelo productivo:

- Athlete: deportista individual.
- Coach: entrenador o wellness coach.
- Team admin: administra equipo, miembros y planes.
- Owner: administra la plataforma.

## Dominios

Actual:

- `https://personal-wellness-coach.onrender.com`

Objetivo recomendado:

- `https://wellness.ckmecr.com`

Futuro:

- `https://ckmecr.com` puede quedar como landing comercial.

## Fronteras de seguridad

Frontend puede conocer:

- URL publica de la app.
- Supabase anon key, cuando se implemente auth en frontend.
- Datos del usuario autenticado.

Frontend no puede conocer:

- `OPENAI_API_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `STRAVA_CLIENT_SECRET`
- refresh tokens de Strava
- secretos de webhook

Backend puede:

- Llamar OpenAI.
- Leer/escribir Supabase con service role cuando sea necesario.
- Manejar OAuth de Strava.
- Firmar URLs temporales para archivos.

## Decisiones actuales

- Mantener Python como backend inicial.
- Mantener Render como hosting.
- Mover persistencia escalable a Supabase.
- Mantener app web mobile-first.
- Usar Strava como integracion deportiva prioritaria despues de estabilizar Supabase.

## Decisiones pendientes

- Definir si Supabase Auth usara magic links, Google login o ambos.
- Definir si Render queda en Starter o si se mueve a un plan superior.
- Definir retencion comercial: 30 dias, 90 dias o historico completo por plan.
- Definir si el coach IA puede usar datos completos de Strava o solo resumen semanal.
- Definir politica de privacidad, consentimiento y disclaimer medico/deportivo.

## Criterios de cierre para PPH-10

- Documentacion de arquitectura creada.
- Variables de ambiente documentadas.
- Deployment documentado.
- Estrategia de persistencia documentada.
- Strava incluido como integracion futura de arquitectura.
- Siguiente paso claro: implementar Supabase en `PPH-11`.
