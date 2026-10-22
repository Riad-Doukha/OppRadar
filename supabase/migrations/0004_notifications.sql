-- Generalise notifications beyond AI match alerts so the in-app bell and the
-- Notifications page can show every kind in the design: new match, deadline
-- reminder, application update, weekly digest, profile tip, security, system.
-- Match rows from the AI notifier keep working unchanged (kind defaults to
-- 'match'; opportunity + score are still set for them).

alter table public.notifications
  add column kind text not null default 'match'
    check (kind in ('match', 'deadline', 'application', 'digest', 'tip', 'security', 'system')),
  add column body text not null default '',
  add column action_url text,
  add column dedupe_key text,          -- one reminder per (user, key), e.g. 'deadline:<opp id>'
  add column dismissed_at timestamptz,
  alter column opportunity_id drop not null,
  alter column score drop not null;

-- Match alerts must still carry their opportunity and score.
alter table public.notifications add constraint notifications_match_fields
  check (kind <> 'match' or (opportunity_id is not null and score is not null));

create unique index notifications_dedupe_idx on public.notifications (user_id, dedupe_key)
  where dedupe_key is not null;
create index notifications_unread_idx on public.notifications (user_id)
  where read_at is null and dismissed_at is null;
