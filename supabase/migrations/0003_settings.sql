-- Settings pages (Account / Notifications / Privacy & AI / Agent & sources).
-- Preferences are stored now and honoured by the alert + scan pipelines when
-- they ship (AI notifications / ingestion phases).

-- Notifications → Alert rules + bundling.
alter table public.notification_settings
  add column rule_new_match          boolean not null default true,
  add column rule_deadline_reminders boolean not null default true,
  add column rule_application_updates boolean not null default true,
  add column rule_weekly_digest      boolean not null default true,
  add column rule_profile_tips       boolean not null default false,
  add column bundle_non_urgent       boolean not null default false;

-- Privacy & AI → new consent kinds (still an append-only audit).
alter table public.consents drop constraint consents_kind_check;
alter table public.consents add constraint consents_kind_check check (kind in (
  'terms_privacy', 'agent_matching', 'ai_cv_processing',
  'ai_drafts', 'chat_history', 'anonymized_stats'
));

-- Privacy & AI → retention; Agent & sources → scan preferences. The agent
-- settings shape is validated by the API (AgentSettings in app/models.py),
-- missing keys fall back to its defaults.
alter table public.profiles
  add column history_retention text not null default '12_months'
    check (history_retention in ('12_months', 'never')),
  add column agent_settings jsonb not null default '{}'::jsonb;
