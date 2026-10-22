-- Per-user state on an opportunity: "Save" and "Not interested" on the
-- dashboard and the opportunity page. One row per (user, opportunity),
-- created on the first action; a cleared flag is set back to null.

create table public.user_opportunities (
  user_id uuid not null references auth.users (id) on delete cascade,
  opportunity_id uuid not null references public.opportunities (id) on delete cascade,
  saved_at timestamptz,
  dismissed_at timestamptz,
  updated_at timestamptz not null default now(),
  primary key (user_id, opportunity_id)
);

-- FK lookups when an opportunity is deleted, and the "Saved" tab.
create index user_opportunities_opportunity_idx on public.user_opportunities (opportunity_id);
create index user_opportunities_saved_idx on public.user_opportunities (user_id, saved_at desc)
  where saved_at is not null;

create trigger user_opportunities_updated_at before update on public.user_opportunities
  for each row execute function private.set_updated_at();

alter table public.user_opportunities enable row level security;

create policy "own opportunity state" on public.user_opportunities
  for all to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
