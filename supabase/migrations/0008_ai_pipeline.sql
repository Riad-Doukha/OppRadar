-- AI pipeline wiring: fields the new Opportunity / MatchResult schemas carry,
-- and a log of ingestion runs for the admin "sync" screen.
-- Every statement is safe to re-run.

-- Where the deadline came from ('none' = rolling / not stated — never invented)
-- and the extractor's "needs review" notes.
alter table public.opportunities
  add column if not exists deadline_source text check (deadline_source in ('rule', 'llm', 'none')),
  add column if not exists review_notes    text[] not null default '{}';

-- Whether the match reasons were written by rules or phrased by the model.
alter table public.matches
  add column if not exists reasons_source text not null default 'rules' check (reasons_source in ('rules', 'llm')),
  add column if not exists updated_at     timestamptz not null default now();

-- One row per ingestion run (manual from /admin or scheduled): the counters and
-- free-tier usage of the IngestionReport, without the opportunities themselves.
create table if not exists public.ingestion_runs (
  id            uuid primary key default gen_random_uuid(),
  trigger       text not null default 'manual' check (trigger in ('manual', 'scheduled')),
  triggered_by  uuid references auth.users (id) on delete set null,
  started_at    timestamptz not null,
  finished_at   timestamptz not null,
  items_fetched integer not null default 0,
  items_new     integer not null default 0,
  items_saved   integer not null default 0,
  items_flagged integer not null default 0,
  users_matched integer not null default 0,
  report        jsonb not null default '{}',   -- IngestionReport minus opportunities
  error         text
);
create index if not exists ingestion_runs_started_idx on public.ingestion_runs (started_at desc);

alter table public.ingestion_runs enable row level security;

drop policy if exists "admins read ingestion runs" on public.ingestion_runs;
create policy "admins read ingestion runs" on public.ingestion_runs
  for select to authenticated using ((select private.is_admin()));

-- Grounded chat answers: whether the answer is in the source (the eligibility
-- column already exists since 0001).
alter table public.chat_messages
  add column if not exists in_source boolean not null default true;

-- An opportunity the AI read from a pasted link / announcement in chat
-- (shown with "Submit it for review").
alter table public.chat_messages
  add column if not exists extracted jsonb;

-- Email delivery: the user's language for emails, and when an alert was emailed.
alter table public.profiles
  add column if not exists locale text not null default 'en' check (locale in ('en', 'fr', 'ar'));
alter table public.notifications
  add column if not exists emailed_at timestamptz;
