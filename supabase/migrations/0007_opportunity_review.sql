-- Admin review of opportunities and organisation submissions.
-- Submissions (added_via = 'form') arrive with review_status = 'pending' and
-- stay hidden from the public until an admin approves them (the existing
-- "approved opportunities are public" policy). This adds who reviewed it,
-- when, the note shown to the submitter, and a contact address for the
-- organisation. Admins are users whose app_metadata.role is 'admin'.

alter table public.opportunities
  add column review_note   text check (review_note is null or length(review_note) <= 500),
  add column reviewed_at   timestamptz,
  add column reviewed_by   uuid references auth.users (id) on delete set null,
  add column contact_email text check (contact_email is null or contact_email ~ '^[^@\s]+@[^@\s]+\.[^@\s]+$');

create index opportunities_review_idx on public.opportunities (review_status, created_at desc);
create index opportunities_reviewed_by_idx on public.opportunities (reviewed_by);

-- Submitters can follow their own submissions, whatever their status.
create policy "own submissions" on public.opportunities
  for select to authenticated
  using (submitted_by = (select auth.uid()));
