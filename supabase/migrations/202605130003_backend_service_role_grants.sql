-- Grants required for the backend service role.
-- Jira: PPH-13
--
-- The Supabase project was created with "Automatically expose new tables" disabled.
-- That is the safer default, but PostgREST still needs explicit SQL privileges
-- for the role used by the backend service key.

grant usage on schema public to service_role;

grant select, insert, update, delete
on all tables in schema public
to service_role;

grant usage, select
on all sequences in schema public
to service_role;

alter default privileges in schema public
grant select, insert, update, delete
on tables
to service_role;

alter default privileges in schema public
grant usage, select
on sequences
to service_role;
