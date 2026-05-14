# Deployment

## Objetivo

Documentar como desplegar The Pichudo's App en Render desde GitHub.

## Repositorio

```text
https://github.com/cesarmo1994/personal_wellness_coach
```

## Servicio Render

Tipo:

```text
Web Service
```

Runtime:

```text
Python 3
```

Start command:

```text
python server.py
```

Health check:

```text
/healthz
```

URL actual:

```text
https://personal-wellness-coach.onrender.com
```

## Configuracion por `render.yaml`

El repo incluye `render.yaml` con:

- Servicio web Python.
- Plan `starter`.
- Variable `OPENAI_MODEL`.
- Variable `DATA_DIR=/var/data`.
- `OPENAI_API_KEY` marcada como secreta.
- Disco persistente montado en `/var/data`.

Nota:

- Render Free no soporta persistent disks.
- Si se usa Free, la app puede correr, pero no debe asumirse persistencia confiable de archivos/historial.
- Para beta seria, usar Starter o mover persistencia a Supabase.

## Pasos de deploy

1. Conectar GitHub a Render.
2. Seleccionar el repo `personal_wellness_coach`.
3. Crear Web Service.
4. Confirmar runtime Python.
5. Usar `python server.py` como start command.
6. Configurar variables de ambiente.
7. Confirmar health check `/healthz`.
8. Desplegar.
9. Probar la URL publica.

## Variables minimas

```text
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5.2
DATA_DIR=/var/data
```

## Validacion post-deploy

Abrir:

```text
https://personal-wellness-coach.onrender.com/healthz
```

Respuesta esperada:

```json
{
  "ok": true
}
```

Luego validar:

- Carga pantalla principal.
- Permite seleccionar usuario.
- Permite enviar mensaje al coach personal.
- Permite enviar mensaje grupal.
- `@coach` responde en grupo.
- Permite cargar PDF de plan.
- No aparece error de API key.

## Dominio recomendado

Subdominio:

```text
wellness.ckmecr.com
```

Pasos generales:

1. Agregar custom domain en Render.
2. Render dara un target DNS.
3. En el proveedor del dominio, crear CNAME:

```text
wellness -> target indicado por Render
```

4. Esperar propagacion DNS.
5. Confirmar HTTPS activo.
6. Actualizar `PUBLIC_APP_URL`.

## Rollback

Si un deploy falla:

1. Revisar logs de Render.
2. Confirmar variables de ambiente.
3. Revisar ultimo commit en GitHub.
4. Usar redeploy de un deploy anterior desde Render si es urgente.

## Siguientes mejoras de deployment

- Agregar smoke tests simples.
- Agregar GitHub Actions para revisar sintaxis Python.
- Separar entorno `staging` y `production`.
- Configurar logs/alertas para errores criticos.
