# The Pichudo's App

Web app movil para wellness coaching privado entre amigos, con camino claro hacia una solucion vendible para atletas individuales y equipos deportivos.

## Estado actual

La app corre como una web app mobile-first con backend Python en `server.py` y frontend estatico en `index.html`, `app.js` y `styles.css`.

Capacidades actuales:

- Login con Google mediante Supabase Auth.
- Plan activo por usuario.
- Check-ins diarios y evidencia.
- Chat personal con coach IA.
- Chat grupal compartido.
- El coach responde en grupo solo cuando se usa `@coach`.
- Carga y analisis de planes de nutricion, entrenamiento y wellness.
- Lectura de PDF con OpenAI Files API.
- Extraccion local de DOCX, XLSX, CSV, TSV, TXT y MD.
- Retencion beta de 30 dias usando almacenamiento del servidor.
- Deploy en Render desde GitHub.

## Documentacion

- [Arquitectura productiva](docs/architecture.md)
- [Esquema de base de datos](docs/database-schema.md)
- [Buckets privados de Supabase Storage](docs/storage-buckets.md)
- [Persistencia de chats](docs/chat-persistence.md)
- [Analisis y creacion de planes con OpenAI](docs/plan-analysis.md)
- [Autenticacion y roles](docs/authentication.md)
- [Variables de ambiente](docs/environment.md)
- [Deployment en Render](docs/deployment.md)
- [Estrategia de storage y persistencia](docs/storage-strategy.md)

## Correr localmente

En PowerShell:

```powershell
$env:OPENAI_API_KEY="tu_api_key"
$env:OPENAI_MODEL="gpt-5.2"
python server.py
```

Luego abrir:

```text
http://127.0.0.1:3000/
```

Si todos estan en la misma red Wi-Fi, tambien se puede probar con el IP local de la computadora:

```text
http://192.168.0.10:3000/
```

## Produccion beta

URL actual:

```text
https://personal-wellness-coach.onrender.com
```

Repositorio:

```text
https://github.com/cesarmo1994/personal_wellness_coach
```

Epic Jira:

```text
https://ckmecr.atlassian.net/browse/PPH-9
```

Historia de arquitectura:

```text
https://ckmecr.atlassian.net/browse/PPH-10
```

## Notas de seguridad

- No poner `OPENAI_API_KEY` en el navegador, `app.js`, GitHub ni capturas.
- Las API keys deben vivir solo como variables de ambiente del servidor.
- Para produccion escalable, el historial, archivos y tokens externos deben moverse a Supabase.
- La integracion con Strava requiere OAuth por atleta y consentimiento explicito.
