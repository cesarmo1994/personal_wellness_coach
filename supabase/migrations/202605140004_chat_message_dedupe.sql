-- Chat persistence support.
-- Jira: PPH-14

alter table public.messages
add column if not exists client_message_id text;

create unique index if not exists messages_conversation_client_message_id_idx
on public.messages (conversation_id, client_message_id)
where client_message_id is not null;

create index if not exists messages_created_at_idx
on public.messages (created_at desc);

grant select, insert, update, delete
on public.messages
to service_role;
