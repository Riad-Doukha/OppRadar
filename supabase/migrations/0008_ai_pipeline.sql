-- AI pipeline wiring: fields the new Opportunity / MatchResult schemas carry,
-- and a log of ingestion runs for the admin "sync" screen.

-- Where the deadline came from ('none' = rolling / not stated — never invented)
-- and the extractor's "needs review" notes.
alter table public.opportunities
  add column deadline_source text check (deadline_source in ('rule', 'llm', 'none')),
  add column review_notes    text[] not null default '{}';

-- Whether the match reasons were written by rules or phrased by the model.
alter table public.matches
  add column reasons_source text not null default 'rules' check (reasons_source in ('rules', 'llm')),
  add column updated_at     timestamptz not null default now();

-- One row per ingestion run (manual from /admin or scheduled): the counters and
-- free-tier usage of the IngestionReport, without the opportunities themselves.
create table public.ingestion_runs (
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
create index ingestion_runs_started_idx on public.ingestion_runs (started_at desc);

alter table public.ingestion_runs enable row level security;

create policy "admins read ingestion runs" on public.ingestion_runs
  for select to authenticated using ((select private.is_admin()));

-- Grounded chat answers: whether the answer is in the source, and the
-- eligibility checklist the assistant returns for an opportunity.
alter table public.chat_messages
  add column in_source   boolean not null default true,
  add column eligibility jsonb;
