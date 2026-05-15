-- PPH-12: remove fixed beta profiles and seed the Google-auth admin profile.

begin;

delete from public.profiles
where auth_user_id is null
  and email is null
  and lower(display_name) in ('david', 'pri', 'ana', 'cesar', 'césar');

insert into public.profiles (
  display_name,
  handle,
  email,
  default_role,
  is_beta_user,
  metadata
)
values (
  'César',
  'cesar',
  'cesar@ckmecr.com',
  'owner',
  false,
  '{"source":"pph-12-google-auth-admin-seed"}'::jsonb
)
on conflict (email) do update
set
  display_name = excluded.display_name,
  default_role = 'owner',
  is_beta_user = false,
  metadata = profiles.metadata || excluded.metadata,
  updated_at = now();

with admin_profile as (
  select id from public.profiles where email = 'cesar@ckmecr.com' limit 1
),
default_team as (
  insert into public.teams (
    name,
    slug,
    kind,
    weekly_goal,
    owner_profile_id,
    metadata
  )
  select
    'Los Pichudos',
    'los-pichudos',
    'accountability_group',
    'Cumplir el objetivo de la semana',
    id,
    '{"source":"pph-12-google-auth-admin-seed"}'::jsonb
  from admin_profile
  on conflict (slug) do update
  set
    owner_profile_id = excluded.owner_profile_id,
    updated_at = now()
  returning id
)
insert into public.team_members (
  team_id,
  profile_id,
  role,
  metadata
)
select
  default_team.id,
  admin_profile.id,
  'team_admin',
  '{"source":"pph-12-google-auth-admin-seed"}'::jsonb
from default_team
cross join admin_profile
on conflict (team_id, profile_id) do update
set
  role = 'team_admin',
  removed_at = null,
  metadata = team_members.metadata || excluded.metadata;

commit;
