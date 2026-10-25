-- Applications the user tracks (Apply assistant + Applications page) and
-- opportunity references on chat answers (Ask the agent).

create table public.applications (
  id             uuid primary key default gen_random_uuid(),
  user_id        uuid not null references auth.users (id) on delete cascade,
  opportunity_id uuid not null references public.opportunities (id) on delete cascade,
  status         text not null default 'submitted'
                   check (status in ('draft', 'submitted', 'accepted', 'rejected', 'withdrawn')),
  reference      text check (char_length(reference) <= 120),   -- organizer's receipt / reference
  notes          text not null default '' check (char_length(notes) <= 2000),
  submitted_at   timestamptz,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now(),
  unique (user_id, opportunity_id)
);

create index applications_opportunity_idx on public.applications (opportunity_id);

create trigger applications_updated_at before update on public.applications
  for each row execute function private.set_updated_at();

alter table public.applications enable row level security;

create policy "own applications" on public.applications
  for all to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);

-- Opportunities an answer points to (rendered as cards in the chat).
alter table public.chat_messages
  add column opportunity_ids uuid[] not null default '{}';
