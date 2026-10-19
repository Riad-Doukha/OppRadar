-- OppRadar — initial schema
-- Applied with `supabase db reset` (or `supabase migration up`).

-- Opportunities fetched & extracted by the AI ingestion pipeline.
create table public.opportunities (
  id            uuid primary key default gen_random_uuid(),
  source        text not null,                     -- e.g. "rss:yc-jobs"
  source_url    text not null,
  title         text not null,
  organization  text not null,
  opportunity_type text not null check (opportunity_type in
    ('internship','job','scholarship','competition','bootcamp','research','volunteer')),
  mode          text check (mode in ('remote','hybrid','onsite')),
  location      text,
  country       text,
  deadline      date,
  salary        text,
  description   text default '',
  tags          text[] default '{}',
  scam_label    text check (scam_label in ('safe','suspicious','scam')),
  scam_score    numeric(4,3) check (scam_score between 0 and 1),
  scam_reasons  jsonb default '[]',
  embedding     vector(1536),                     -- pgvector (optional extension)
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  unique (source, source_url)
);

create index opportunities_deadline_idx on public.opportunities (deadline);
create index opportunities_type_idx on public.opportunities (opportunity_type);

-- Parsed user profiles (from CV upload).
create table public.profiles (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users (id) on delete cascade,
  full_name   text,
  headline    text,
  skills      text[] default '{}',
  education   jsonb default '[]',
  experience  jsonb default '[]',
  languages   text[] default '{}',
  interests   text[] default '{}',
  preferences jsonb default '{}',                 -- {mode, countries, types}
  created_at  timestamptz not null default now()
);

-- Scored matches between a profile and an opportunity.
create table public.matches (
  id            uuid primary key default gen_random_uuid(),
  profile_id    uuid not null references public.profiles (id) on delete cascade,
  opportunity_id uuid not null references public.opportunities (id) on delete cascade,
  score         numeric(4,3) not null check (score between 0 and 1),
  similarity    numeric(4,3),
  skill_overlap numeric(4,3),
  reasons       jsonb default '[]',
  created_at    timestamptz not null default now(),
  unique (profile_id, opportunity_id)
);

-- Chat history with the assistant.
create table public.chat_messages (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users (id) on delete cascade,
  profile_id  uuid references public.profiles (id) on delete set null,
  role        text not null check (role in ('user','assistant')),
  content     text not null,
  sources     jsonb default '[]',                 -- opportunity ids cited
  created_at  timestamptz not null default now()
);

-- Row Level Security: users only see their own rows.
alter table public.profiles enable row level security;
alter table public.matches enable row level security;
alter table public.chat_messages enable row level security;
alter table public.opportunities enable row level security;

create policy "opportunities are readable by everyone"
  on public.opportunities for select using (true);

create policy "own profiles" on public.profiles
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

create policy "own matches" on public.matches
  for select using (
    exists (select 1 from public.profiles p where p.id = profile_id and p.user_id = auth.uid())
  );

create policy "own chat history" on public.chat_messages
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
