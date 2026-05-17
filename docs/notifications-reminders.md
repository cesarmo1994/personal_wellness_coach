# Notificaciones y recordatorios

## Objetivo

Documentar la implementacion de `PPH-19`: recordatorios diarios para cerrar el
check-in y notificaciones del navegador para reforzar accountability.

## Flujo

1. El usuario abre la pantalla de check-in.
2. Configura una hora diaria, por defecto `21:00`.
3. Toca `Activar notificaciones` y concede permiso del navegador.
4. El frontend guarda la preferencia en `localStorage`.
5. Si llega la hora configurada y el usuario no ha hecho check-in del dia, la
   app muestra una notificacion.
6. Al tocar la notificacion, el service worker abre la app en `#checkin`.

## Alcance actual

- Recordatorio diario por dispositivo.
- Notificaciones usando `Notification` y `ServiceWorkerRegistration.showNotification`.
- Prevencion de recordatorios repetidos el mismo dia.
- No se dispara recordatorio cuando ya existe check-in del dia.
- Deep link local a la pantalla de check-in mediante hash.

## Limitaciones

Esta version no envia Web Push remoto desde backend cuando el navegador esta
cerrado por completo. Para eso se requiere configurar VAPID, suscripciones
`PushManager` y un job servidor que consulte usuarios pendientes.

La tabla `public.notification_subscriptions` ya existe en la arquitectura para
una evolucion posterior con Web Push real.

