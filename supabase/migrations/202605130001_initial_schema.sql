-- Personal Wellness Coach initial Supabase schema.
-- Jira: PPH-11

create extension if not exists pgcrypto;

create type public.app_role as enum (
  'athlete',
  'coach',
  'team_admin',
  'owner'
);

create type public.team_kind as enum (
  'accountability_group',
  'sports_team',
  'solo'
);

create type public.plan_type as enum (
  'nutrition',
  'training',
  'wellness',
  'combined'
);

create type public.plan_status as enum (
  'draft',
  'active',
  'archived'
);

create type public.plan_source as enum (
  'upload',
  'conversation',
  'manual',
  'migration'
);

create type public.file_kind as enum (
  'pdf',
  'docx',
  'xlsx',
  'csv',
  'txt',
  'image',
  'audio',
  'other'
);

create type public.conversation_kind as enum (
  'personal',
  'group'
);

create type public.message_sender_type as enum (
  'user',
  'coach_ai',
  'system'
);

create type public.insight_kind as enum (
  'plan_analysis',
  'daily_feedback',
  'weekly_summary',
  'risk_alert',
  'strava_summary',
  'general'
);

create type public.subscription_channel as enum (
  'web_push',
  'email',
  'sms',
  'whatsapp'
);

create table public.profiles (
  id uuid primary key default gen_random_uuid(),
  auth_user_id uuid unique references auth.users(id) on delete set null,
  display_name text not null,
  handle text unique,
  email text unique,
  avatar_url text,
  default_role public.app_role not null default 'athlete',
  timezone text not null default 'America/Costa_Rica',
  locale text not null default 'es',
  is_beta_user boolean not null default false,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.teams (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  slug text unique,
  kind public.team_kind not null default 'accountability_group',
  weekly_goal text,
  active_challenge text,
  owner_profile_id uuid references public.profiles(id) on delete set null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.team_members (
  id uuid primary key default gen_random_uuid(),
  team_id uuid not null references public.teams(id) on delete cascade,
  profile_id uuid not null references public.profiles(id) on delete cascade,
  role public.app_role not null default 'athlete',
  joined_at timestamptz not null default now(),
  removed_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  unique (team_id, profile_id)
);

create table public.plans (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null references public.profiles(id) on delete cascade,
  team_id uuid references public.teams(id) on delete set null,
  plan_type public.plan_type not null,
  status public.plan_status not null default 'draft',
  source public.plan_source not null default 'manual',
  title text not null,
  user_notes text,
  summary text,
  structured_plan jsonb not null default '{}'::jsonb,
  weekly_goal text,
  starts_on date,
  ends_on date,
  created_by_profile_id uuid references public.profiles(id) on delete set null,
  activated_at timestamptz,
  archived_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index plans_one_active_per_profile_type_idx
  on public.plans (profile_id, plan_type)
  where status = 'active';

create table public.plan_files (
  id uuid primary key default gen_random_uuid(),
  plan_id uuid not null references public.plans(id) on delete cascade,
  profile_id uuid not null references public.profiles(id) on delete cascade,
  team_id uuid references public.teams(id) on delete set null,
  bucket text not null default 'plan-files',
  storage_path text not null,
  original_filename text not null,
  content_type text,
  file_kind public.file_kind not null default 'other',
  size_bytes bigint,
  extracted_text text,
  openai_file_id text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (bucket, storage_path)
);

create table public.checkins (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null references public.profiles(id) on delete cascade,
  team_id uuid references public.teams(id) on delete set null,
  plan_id uuid references public.plans(id) on delete set null,
  checkin_date date not null default current_date,
  goal_completed boolean not null default false,
  mood_score smallint check (mood_score between 1 and 5),
  energy_score smallint check (energy_score between 1 and 5),
  soreness_score smallint check (soreness_score between 1 and 5),
  sleep_hours numeric(4,2) check (sleep_hours >= 0 and sleep_hours <= 24),
  notes text,
  metrics jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (profile_id, checkin_date)
);

create table public.checkin_files (
  id uuid primary key default gen_random_uuid(),
  checkin_id uuid not null references public.checkins(id) on delete cascade,
  profile_id uuid not null references public.profiles(id) on delete cascade,
  team_id uuid references public.teams(id) on delete set null,
  bucket text not null default 'checkin-evidence',
  storage_path text not null,
  original_filename text not null,
  content_type text,
  file_kind public.file_kind not null default 'other',
  size_bytes bigint,
  caption text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (bucket, storage_path)
);

create table public.conversations (
  id uuid primary key default gen_random_uuid(),
  kind public.conversation_kind not null,
  profile_id uuid references public.profiles(id) on delete cascade,
  team_id uuid references public.teams(id) on delete cascade,
  title text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint conversations_scope_check check (
    (kind = 'personal' and profile_id is not null and team_id is null)
    or
    (kind = 'group' and team_id is not null)
  )
);

create unique index conversations_one_personal_per_profile_idx
  on public.conversations (profile_id)
  where kind = 'personal';

create unique index conversations_one_group_per_team_idx
  on public.conversations (team_id)
  where kind = 'group';

create table public.messages (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references public.conversations(id) on delete cascade,
  profile_id uuid references public.profiles(id) on delete set null,
  team_id uuid references public.teams(id) on delete set null,
  sender_type public.message_sender_type not null default 'user',
  body text not null,
  mentions_coach boolean not null default false,
  attachments jsonb not null default '[]'::jsonb,
  ai_context jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table public.ai_insights (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid references public.profiles(id) on delete cascade,
  team_id uuid references public.teams(id) on delete cascade,
  plan_id uuid references public.plans(id) on delete set null,
  checkin_id uuid references public.checkins(id) on delete set null,
  message_id uuid references public.messages(id) on delete set null,
  insight_kind public.insight_kind not null default 'general',
  title text,
  body text not null,
  model text,
  prompt_version text,
  input_summary jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  constraint ai_insights_scope_check check (profile_id is not null or team_id is not null)
);

create table public.notification_subscriptions (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null references public.profiles(id) on delete cascade,
  channel public.subscription_channel not null default 'web_push',
  endpoint text not null,
  p256dh_key text,
  auth_key text,
  is_active boolean not null default true,
  last_used_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (profile_id, channel, endpoint)
);

create table public.strava_connections (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null references public.profiles(id) on delete cascade,
  strava_athlete_id bigint not null unique,
  scope text not null,
  access_token text not null,
  refresh_token text not null,
  expires_at timestamptz not null,
  connected_at timestamptz not null default now(),
  last_sync_at timestamptz,
  revoked_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (profile_id)
);

create table public.strava_activities (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null references public.profiles(id) on delete cascade,
  strava_activity_id bigint not null unique,
  sport_type text,
  name text,
  started_at timestamptz not null,
  elapsed_time_seconds integer,
  moving_time_seconds integer,
  distance_meters numeric(12,2),
  total_elevation_gain_meters numeric(10,2),
  average_speed_mps numeric(10,4),
  average_heartrate numeric(6,2),
  perceived_exertion smallint check (perceived_exertion between 1 and 10),
  summary jsonb not null default '{}'::jsonb,
  raw_payload jsonb not null default '{}'::jsonb,
  deleted_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger profiles_set_updated_at
  before update on public.profiles
  for each row execute function public.set_updated_at();

create trigger teams_set_updated_at
  before update on public.teams
  for each row execute function public.set_updated_at();

create trigger plans_set_updated_at
  before update on public.plans
  for each row execute function public.set_updated_at();

create trigger checkins_set_updated_at
  before update on public.checkins
  for each row execute function public.set_updated_at();

create trigger conversations_set_updated_at
  before update on public.conversations
  for each row execute function public.set_updated_at();

create trigger notification_subscriptions_set_updated_at
  before update on public.notification_subscriptions
  for each row execute function public.set_updated_at();

create trigger strava_connections_set_updated_at
  before update on public.strava_connections
  for each row execute function public.set_updated_at();

create trigger strava_activities_set_updated_at
  before update on public.strava_activities
  for each row execute function public.set_updated_at();

create index profiles_auth_user_id_idx on public.profiles (auth_user_id);
create index team_members_profile_id_idx on public.team_members (profile_id);
create index team_members_team_role_idx on public.team_members (team_id, role);
create index plans_profile_status_idx on public.plans (profile_id, status);
create index plans_team_status_idx on public.plans (team_id, status);
create index plan_files_plan_id_idx on public.plan_files (plan_id);
create index checkins_profile_date_idx on public.checkins (profile_id, checkin_date desc);
create index checkins_team_date_idx on public.checkins (team_id, checkin_date desc);
create index checkin_files_checkin_id_idx on public.checkin_files (checkin_id);
create index conversations_team_id_idx on public.conversations (team_id);
create index messages_conversation_created_at_idx on public.messages (conversation_id, created_at desc);
create index messages_team_created_at_idx on public.messages (team_id, created_at desc);
create index ai_insights_profile_created_at_idx on public.ai_insights (profile_id, created_at desc);
create index ai_insights_team_created_at_idx on public.ai_insights (team_id, created_at desc);
create index notification_subscriptions_profile_active_idx on public.notification_subscriptions (profile_id, is_active);
create index strava_activities_profile_started_at_idx on public.strava_activities (profile_id, started_at desc);
create index strava_activities_sport_type_idx on public.strava_activities (sport_type);

comment on table public.profiles is 'Application profiles. auth_user_id is nullable to support current beta users before full Supabase Auth migration.';
comment on table public.teams is 'Accountability groups, sports teams, or solo containers.';
comment on table public.team_members is 'Profiles assigned to teams with product roles.';
comment on table public.plans is 'Active and historical nutrition, training, wellness, or combined plans.';
comment on table public.plan_files is 'Metadata for files stored in Supabase Storage bucket plan-files.';
comment on table public.checkins is 'Daily accountability check-ins and measurable subjective state.';
comment on table public.checkin_files is 'Metadata for evidence files stored in Supabase Storage bucket checkin-evidence.';
comment on table public.conversations is 'Personal and group chat containers.';
comment on table public.messages is 'Chat messages from users, coach AI, or system.';
comment on table public.ai_insights is 'Persisted AI recommendations, summaries, and risk alerts.';
comment on table public.notification_subscriptions is 'Push/email/SMS/WhatsApp subscription records.';
comment on table public.strava_connections is 'OAuth tokens and sync state for connected Strava athletes. Tokens must only be accessed server-side.';
comment on table public.strava_activities is 'Normalized Strava activities used for progress and coach insights.';
