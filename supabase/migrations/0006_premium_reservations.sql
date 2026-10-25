-- Premium early access (payments aren't live): one reservation per user.
-- Nothing is charged and no payment details are stored — only the plan the
-- user wants and the payment method they would prefer, so launch can be planned.

create table public.premium_reservations (
  user_id        uuid primary key references auth.users (id) on delete cascade,
  plan           text not null default 'premium' check (plan in ('premium', 'clubs')),
  billing        text not null default 'monthly' check (billing in ('monthly', 'yearly')),
  payment_method text check (payment_method in ('cib', 'edahabia', 'baridimob', 'ccp')),
  created_at     timestamptz not null default now(),   -- queue position is ordered by this
  updated_at     timestamptz not null default now()
);

create index premium_reservations_created_idx on public.premium_reservations (created_at);

create trigger premium_reservations_updated_at before update on public.premium_reservations
  for each row execute function private.set_updated_at();

alter table public.premium_reservations enable row level security;

create policy "own premium reservation" on public.premium_reservations
  for all to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
