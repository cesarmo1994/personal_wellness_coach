# The Pichudo's App

Web app movil para wellness coaching privado entre amigos.

## Correr localmente con OpenAI

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

Si todos estan en la misma red Wi-Fi, tambien pueden probar el link de tu computadora:

```text
http://192.168.0.10:3000/
```

## Capacidades actuales

- Selector de usuario sin contraseña: David, Pri, Ana y César.
- Cada usuario tiene su propio plan activo y check-ins.
- Chat grupal compartido entre los 4 usuarios.
- El coach solo responde en el chat grupal cuando alguien escribe `@coach`.
- Estado compartido por servidor en `data/app_state.json`.
- Retencion automatica de 30 dias para conversaciones, check-ins y archivos.
- Evidencia y archivos guardados en `data/uploads/`.
- Notificaciones del navegador para mensajes nuevos del grupo cuando la app esta abierta o en segundo plano.
- Cargar y analizar planes de nutricion, entrenamiento o wellness.
- Leer PDF directamente con OpenAI.
- Extraer texto de DOCX, XLSX, CSV, TSV, TXT y MD desde el backend.
- Crear planes por conversacion con IA, sin adjuntos.
- Chat diario con el coach usando los planes activos y check-ins recientes.
- Check-ins, accountability group y vista admin en modo beta local.

## Notas

- No pongas `OPENAI_API_KEY` en el navegador ni en `app.js`.
- El backend corre en `server.py` y mantiene la API key solo en ambiente de servidor.
- Para compartir por WhatsApp fuera de tu misma red Wi-Fi se necesita un URL publico HTTPS, por ejemplo Vercel/Render/Railway o un tunel temporal como ngrok/Cloudflare Tunnel.
- Push notifications reales con la app cerrada requieren HTTPS, service worker y Web Push/VAPID. La beta actual usa notificaciones del navegador mientras la app esta abierta o en segundo plano.
