-- OppRadar — initial schema
-- Applied with `supabase db reset` (or `supabase migration up`).
--
-- Shapes mirror ai/oppradar_ai/schemas.py (Opportunity, MatchResult,
-- Notification, ChatTurn) plus the richer onboarding profile from the Figma
-- design (landing / auth / onboarding). Enumerations are text + check
-- constraints so new values only need a constraint swap, not a type rewrite.
--
-- The backend talks to this database with the service-role key (bypasses RLS);
-- the policies below protect every other path (browser anon/authenticated keys).

-- --------------------------------------------------------------------------- --
-- Helpers
-- --------------------------------------------------------------------------- --
create schema if not exists private;

create or replace function private.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

-- Admins carry {"role": "admin"} in auth.users.raw_app_meta_data (only the
-- service role can set app metadata, so users cannot promote themselves).
create or replace function private.is_admin()
returns boolean
language sql
stable
set search_path = ''
as $$
  select coalesce((select auth.jwt()) -> 'app_metadata' ->> 'role', '') = 'admin';
$$;

grant usage on schema private to authenticated, anon;
grant execute on function private.is_admin() to authenticated, anon;

-- --------------------------------------------------------------------------- --
-- Opportunities (schemas.Opportunity)
-- --------------------------------------------------------------------------- --
create table public.opportunities (
  id                uuid primary key default gen_random_uuid(),
  external_id       text unique,                    -- AI's deterministic id, e.g. "opp-3f2a1c9d0e7b"
  title             text not null check (length(btrim(title)) > 0),
  organizer         text not null check (length(btrim(organizer)) > 0),
  type              text not null default 'other' check (type in (
                      'scholarship','job','internship','fellowship','hackathon','datathon',
                      'competition','bootcamp','research','volunteer','course','grant','other')),
  mode              text check (mode in ('remote','hybrid','onsite')),
  location          text not null default '',
  country           text not null default '',
  language          text not null default 'en',
  deadline          date,
  funding           text,
  eligibility       text[] not null default '{}',
  benefits          text[] not null default '{}',
  summary           text not null default '',
  url               text not null default '',
  source            text not null default 'manual',
  source_checked    timestamptz,
  trust_level       text not null default 'unknown' check (trust_level in (
                      'verified','likely_safe','unknown','suspicious','scam')),
  scam_flags        jsonb not null default '[]',    -- [{flag, detail}]
  added_via         text not null default 'pipeline' check (added_via in ('pipeline','form','user')),
  field_confidences jsonb not null default '[]',
  -- Organisation submissions wait for an admin before going public.
  review_status     text not null default 'approved' check (review_status in ('pending','approved','rejected')),
  submitted_by      uuid references auth.users (id) on delete set null,
  search            tsvector generated always as (
                      to_tsvector('simple',
                        coalesce(title, '') || ' ' || coalesce(organizer, '') || ' ' ||
                        coalesce(summary, '') || ' ' || coalesce(location, '') || ' ' ||
                        coalesce(country, ''))
                    ) stored,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);

create index opportunities_deadline_idx on public.opportunities (deadline);
create index opportunities_type_idx on public.opportunities (type);
create index opportunities_trust_idx on public.opportunities (trust_level);
create index opportunities_search_idx on public.opportunities using gin (search);
create index opportunities_pending_idx on public.opportunities (created_at)
  where review_status = 'pending';
create index opportunities_submitted_by_idx on public.opportunities (submitted_by);

create trigger opportunities_updated_at before update on public.opportunities
  for each row execute function private.set_updated_at();

-- --------------------------------------------------------------------------- --
-- Profile (onboarding steps 1-4) — one row per auth user
-- --------------------------------------------------------------------------- --
create table public.profiles (
  user_id                 uuid primary key references auth.users (id) on delete cascade,
  -- Step 1 · About you
  full_name               text not null default '',
  birth_year              smallint check (birth_year between 1940 and 2020),
  nationality             text,
  country                 text,
  wilaya                  text,
  -- Step 2 · Education
  education_level         text check (education_level in ('bac','licence','master','engineer','phd','other')),
  field_of_study          text,
  institution             text,
  current_year            smallint check (current_year between 1 and 10),
  graduation_year         smallint check (graduation_year between 1950 and 2100),
  gpa_value               numeric(4,2) check (gpa_value >= 0),
  gpa_scale               smallint check (gpa_scale in (4, 20)),
  -- Step 3 · Skills & interests
  interests               text[] not null default '{}',
  opportunity_types       text[] not null default '{}' check (opportunity_types <@ array[
                            'scholarship','job','internship','fellowship','hackathon','datathon',
                            'competition','bootcamp','research','volunteer','course','grant','other']),
  preferred_location      text check (preferred_location in ('algeria','abroad','remote','anywhere')),
  availability            text check (availability in ('full_time','part_time_10_20','under_10h','flexible')),
  -- Step 4 · Goal
  goal                    text check (goal is null or char_length(goal) between 20 and 300),
  -- Onboarding progress
  onboarding_step         smallint not null default 1 check (onboarding_step between 1 and 5),
  onboarding_completed_at timestamptz,
  agent_started_at        timestamptz,
  is_demo                 boolean not null default false,
  -- AI output (documents/profile_builder.py)
  summary                 text not null default '',
  completeness            numeric(4,3) not null default 0 check (completeness between 0 and 1),
  completeness_suggestions text[] not null default '{}',
  conflicts               text[] not null default '{}',
  field_confidences       jsonb not null default '[]',
  created_at              timestamptz not null default now(),
  updated_at              timestamptz not null default now(),
  constraint profiles_gpa_pair check ((gpa_value is null) = (gpa_scale is null)),
  constraint profiles_gpa_range check (gpa_value is null or gpa_value <= gpa_scale)
);

create trigger profiles_updated_at before update on public.profiles
  for each row execute function private.set_updated_at();

create table public.profile_skills (
  id        uuid primary key default gen_random_uuid(),
  user_id   uuid not null references public.profiles (user_id) on delete cascade,
  name      text not null check (length(btrim(name)) > 0),
  level     text check (level in ('beginner','intermediate','advanced')),
  position  smallint not null default 0
);
create unique index profile_skills_user_name_idx on public.profile_skills (user_id, lower(name));

create table public.profile_languages (
  id        uuid primary key default gen_random_uuid(),
  user_id   uuid not null references public.profiles (user_id) on delete cascade,
  language  text not null check (length(btrim(language)) > 0),
  level     text not null default 'good' check (level in ('basic','good','fluent')),
  position  smallint not null default 0
);
create unique index profile_languages_user_lang_idx on public.profile_languages (user_id, lower(language));

create table public.experiences (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references public.profiles (user_id) on delete cascade,
  kind          text not null default 'other' check (kind in (
                  'internship','hackathon','job','volunteer','competition','other')),
  title         text not null check (length(btrim(title)) > 0),
  organization  text not null default '',
  location      text not null default '',
  year          smallint check (year between 1950 and 2100),
  description   text not null default '',
  created_at    timestamptz not null default now()
);
create index experiences_user_idx on public.experiences (user_id);

create table public.certificates (
  id             uuid primary key default gen_random_uuid(),
  user_id        uuid not null references public.profiles (user_id) on delete cascade,
  title          text not null check (length(btrim(title)) > 0),
  issuer         text not null default '',
  year           smallint check (year between 1950 and 2100),
  credential_url text,
  created_at     timestamptz not null default now()
);
create index certificates_user_idx on public.certificates (user_id);

create table public.profile_links (
  id       uuid primary key default gen_random_uuid(),
  user_id  uuid not null references public.profiles (user_id) on delete cascade,
  kind     text not null check (kind in ('linkedin','github','portfolio','other')),
  url      text not null check (length(btrim(url)) > 0)
);
create index profile_links_user_idx on public.profile_links (user_id);

-- --------------------------------------------------------------------------- --
-- Step 5 · Alerts & consent
-- --------------------------------------------------------------------------- --
create table public.notification_settings (
  user_id            uuid primary key references public.profiles (user_id) on delete cascade,
  email_enabled      boolean not null default true,
  telegram_enabled   boolean not null default false,
  telegram_chat_id   text,                          -- set by the bot deep-link flow (notifications phase)
  telegram_linked_at timestamptz,
  threshold          smallint not null default 70 check (threshold between 50 and 100),
  frequency          text not null default 'instant' check (frequency in ('instant','daily','weekly')),
  quiet_start        time default '22:00',
  quiet_end          time default '07:00',
  updated_at         timestamptz not null default now(),
  constraint notification_settings_quiet_pair check ((quiet_start is null) = (quiet_end is null))
);

create trigger notification_settings_updated_at before update on public.notification_settings
  for each row execute function private.set_updated_at();

-- Append-only consent audit: revoking sets revoked_at, granting again adds a row.
create table public.consents (
  id             uuid primary key default gen_random_uuid(),
  user_id        uuid not null references public.profiles (user_id) on delete cascade,
  kind           text not null check (kind in ('terms_privacy','agent_matching','ai_cv_processing')),
  policy_version text not null default '1.0',
  granted_at     timestamptz not null default now(),
  revoked_at     timestamptz
);
create index consents_user_idx on public.consents (user_id);
create unique index consents_active_idx on public.consents (user_id, kind) where revoked_at is null;

-- --------------------------------------------------------------------------- --
-- Uploaded documents (CV upload in step 1) — files live in storage bucket "documents"
-- --------------------------------------------------------------------------- --
create table public.documents (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references public.profiles (user_id) on delete cascade,
  kind          text not null default 'cv' check (kind in ('cv','certificate','portfolio')),
  file_name     text not null,
  storage_path  text not null unique,               -- "<user_id>/<document id>.pdf"
  size_bytes    integer not null check (size_bytes between 1 and 5242880),
  status        text not null default 'queued' check (status in ('queued','reading','extracting','done','failed')),
  read_method   text,                               -- DocumentContent.method
  warnings      text[] not null default '{}',
  extraction    jsonb,                              -- CVExtraction / CertificateExtraction / PortfolioExtraction
  error         text,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);
create index documents_user_idx on public.documents (user_id, created_at desc);

create trigger documents_updated_at before update on public.documents
  for each row execute function private.set_updated_at();

-- --------------------------------------------------------------------------- --
-- Matches, notifications, chat (filled once the AI phases land)
-- --------------------------------------------------------------------------- --
create table public.matches (
  id                  uuid primary key default gen_random_uuid(),
  user_id             uuid not null references public.profiles (user_id) on delete cascade,
  opportunity_id      uuid not null references public.opportunities (id) on delete cascade,
  score               numeric(5,2) not null check (score between 0 and 100),
  semantic_similarity numeric(4,3) not null default 0 check (semantic_similarity between 0 and 1),
  bonus               numeric(4,3) not null default 0 check (bonus between 0 and 1),
  criteria            jsonb not null default '[]',  -- [{text, status, evidence}]
  top_reasons         text[] not null default '{}',
  unmet_requirements  text[] not null default '{}',
  created_at          timestamptz not null default now(),
  unique (user_id, opportunity_id)
);
create index matches_user_score_idx on public.matches (user_id, score desc);
create index matches_opportunity_idx on public.matches (opportunity_id);

create table public.notifications (
  id                uuid primary key default gen_random_uuid(),
  user_id           uuid not null references public.profiles (user_id) on delete cascade,
  opportunity_id    uuid not null references public.opportunities (id) on delete cascade,
  title             text not null,
  reason            text not null default '',
  score             numeric(5,2) not null check (score between 0 and 100),
  deadline          date,
  url               text not null default '',
  mode              text not null default 'instant' check (mode in ('instant','digest')),
  status            text not null default 'pending' check (status in ('sent','pending','suppressed')),
  suppressed_reason text,
  read_at           timestamptz,
  created_at        timestamptz not null default now()
);
create index notifications_user_idx on public.notifications (user_id, created_at desc);
create index notifications_opportunity_idx on public.notifications (opportunity_id);

create table public.chat_messages (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references public.profiles (user_id) on delete cascade,
  role        text not null check (role in ('user','assistant')),
  content     text not null,
  citations   jsonb not null default '[]',          -- ChatAnswer.citations
  eligibility jsonb,                                -- ChatAnswer.eligibility
  created_at  timestamptz not null default now()
);
create index chat_messages_user_idx on public.chat_messages (user_id, created_at);

-- --------------------------------------------------------------------------- --
-- New auth user -> profile + default alert settings (+ Terms consent from signup)
-- --------------------------------------------------------------------------- --
create or replace function private.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.profiles (user_id, full_name)
  values (new.id, coalesce(new.raw_user_meta_data ->> 'full_name', new.raw_user_meta_data ->> 'name', ''));

  insert into public.notification_settings (user_id) values (new.id);

  if coalesce((new.raw_user_meta_data ->> 'terms_accepted')::boolean, false) then
    insert into public.consents (user_id, kind, policy_version)
    values (new.id, 'terms_privacy', coalesce(new.raw_user_meta_data ->> 'policy_version', '1.0'));
  end if;
  return new;
end;
$$;

revoke execute on function private.handle_new_user() from public, anon, authenticated;

create trigger on_auth_user_created after insert on auth.users
  for each row execute function private.handle_new_user();

-- --------------------------------------------------------------------------- --
-- Row Level Security: users only see their own rows
-- --------------------------------------------------------------------------- --
alter table public.opportunities enable row level security;
alter table public.profiles enable row level security;
alter table public.profile_skills enable row level security;
alter table public.profile_languages enable row level security;
alter table public.experiences enable row level security;
alter table public.certificates enable row level security;
alter table public.profile_links enable row level security;
alter table public.notification_settings enable row level security;
alter table public.consents enable row level security;
alter table public.documents enable row level security;
alter table public.matches enable row level security;
alter table public.notifications enable row level security;
alter table public.chat_messages enable row level security;

create policy "approved opportunities are public" on public.opportunities
  for select using (review_status = 'approved' or (select private.is_admin()));
create policy "admins manage opportunities" on public.opportunities
  for all to authenticated
  using ((select private.is_admin())) with check ((select private.is_admin()));

create policy "own profile" on public.profiles
  for all to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);

create policy "own skills" on public.profile_skills
  for all to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "own languages" on public.profile_languages
  for all to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "own experiences" on public.experiences
  for all to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "own certificates" on public.certificates
  for all to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "own links" on public.profile_links
  for all to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "own notification settings" on public.notification_settings
  for all to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "own documents" on public.documents
  for all to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "own chat history" on public.chat_messages
  for all to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);

-- Consents are an audit log: readable, and only insertable by the owner.
create policy "read own consents" on public.consents
  for select to authenticated using ((select auth.uid()) = user_id);
create policy "grant own consents" on public.consents
  for insert to authenticated with check ((select auth.uid()) = user_id);

-- Matches and notifications are written by the backend only.
create policy "read own matches" on public.matches
  for select to authenticated using ((select auth.uid()) = user_id);
create policy "read own notifications" on public.notifications
  for select to authenticated using ((select auth.uid()) = user_id);

-- --------------------------------------------------------------------------- --
-- Storage: private "documents" bucket, one folder per user, PDF only, 5 MB
-- --------------------------------------------------------------------------- --
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('documents', 'documents', false, 5242880, array['application/pdf'])
on conflict (id) do nothing;

create policy "own document files" on storage.objects
  for all to authenticated
  using (bucket_id = 'documents' and (storage.foldername(name))[1] = (select auth.uid())::text)
  with check (bucket_id = 'documents' and (storage.foldername(name))[1] = (select auth.uid())::text);
