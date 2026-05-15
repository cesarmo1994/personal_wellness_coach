# Chat grupal realtime con @coach

## Objetivo

Documentar `PPH-17`: convertir el chat grupal en una experiencia en vivo para
equipos y grupos privados.

## Flujo

1. El usuario envia un mensaje en el chat grupal.
2. El frontend lo agrega al estado local y lo sincroniza con `/api/app-state`.
3. El backend persiste el mensaje en `public.messages`.
4. Supabase Realtime emite el `INSERT` de `messages`.
5. Los clientes suscritos reciben el evento y fuerzan una hidratacion desde
   `/api/app-state`.
6. Si el texto contiene `@coach`, el frontend llama al coach IA y guarda la
   respuesta en el thread.

## Realtime

El frontend usa `supabase-js`:

```js
authClient
  .channel("pichudos-group-messages")
  .on(
    "postgres_changes",
    { event: "INSERT", schema: "public", table: "messages" },
    () => syncFromServer({ notify: true, force: true })
  )
  .subscribe();
```

La migracion `supabase/migrations/202605150006_realtime_messages.sql` agrega
`public.messages` a la publicacion `supabase_realtime` y concede `select` a
`anon`/`authenticated` para que el cliente pueda recibir eventos.

## Persistencia

Los mensajes se guardan en:

- `public.conversations`
- `public.messages`

El campo `client_message_id` evita duplicados cuando el frontend hace autosave
o cuando varios dispositivos hidratan el mismo thread.

## @coach

El coach IA solo responde cuando el mensaje grupal contiene `@coach`. La
respuesta se agrega como mensaje del thread y queda persistida por el mismo
flujo de sincronizacion.

## Fallback

La app mantiene polling cada 5 segundos con `/api/app-state`. Si Realtime no
esta disponible, el chat sigue sincronizando sin refrescar manualmente, solo con
mayor latencia.
