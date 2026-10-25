-- 0009 · Read-only client access (STRIDE review, docs/security/stride.md)
--
-- Every write goes through the API (service role), which validates input and
-- keeps the shared demo account read-only. The browser never writes tables or
-- storage directly, but the "own rows" policies from 0001-0006 allowed it: a
-- signed-in user (including anyone holding the demo session) could call the
-- Supabase REST API with the public anon key and change rows, skipping the
-- API's checks. Users keep read access to their own rows; writes are removed.
-- Idempotent: safe to run again.

-- Profile and its parts ------------------------------------------------------
drop policy if exists "own profile" on public.profiles;
drop policy if exists "read own profile" on public.profiles;
create policy "read own profile" on public.profiles
  for select to authenticated using ((select auth.uid()) = user_id);

drop policy if exists "own skills" on public.profile_skills;
drop policy if exists "read own skills" on public.profile_skills;
create policy "read own skills" on public.profile_skills
  for select to authenticated using ((select auth.uid()) = user_id);

drop policy if exists "own languages" on public.profile_languages;
drop policy if exists "read own languages" on public.profile_languages;
create policy "read own languages" on public.profile_languages
  for select to authenticated using ((select auth.uid()) = user_id);

drop policy if exists "own experiences" on public.experiences;
drop policy if exists "read own experiences" on public.experiences;
create policy "read own experiences" on public.experiences
  for select to authenticated using ((select auth.uid()) = user_id);

drop policy if exists "own certificates" on public.certificates;
drop policy if exists "read own certificates" on public.certificates;
create policy "read own certificates" on public.certificates
  for select to authenticated using ((select auth.uid()) = user_id);

drop policy if exists "own links" on public.profile_links;
drop policy if exists "read own links" on public.profile_links;
create policy "read own links" on public.profile_links
  for select to authenticated using ((select auth.uid()) = user_id);

drop policy if exists "own notification settings" on public.notification_settings;
drop policy if exists "read own notification settings" on public.notification_settings;
create policy "read own notification settings" on public.notification_settings
  for select to authenticated using ((select auth.uid()) = user_id);

-- Consents: the audit log is written by the API only.
drop policy if exists "grant own consents" on public.consents;

-- Documents, chat, opportunity state, applications, premium ------------------
drop policy if exists "own documents" on public.documents;
drop policy if exists "read own documents" on public.documents;
create policy "read own documents" on public.documents
  for select to authenticated using ((select auth.uid()) = user_id);

drop policy if exists "own chat history" on public.chat_messages;
drop policy if exists "read own chat history" on public.chat_messages;
create policy "read own chat history" on public.chat_messages
  for select to authenticated using ((select auth.uid()) = user_id);

drop policy if exists "own opportunity state" on public.user_opportunities;
drop policy if exists "read own opportunity state" on public.user_opportunities;
create policy "read own opportunity state" on public.user_opportunities
  for select to authenticated using ((select auth.uid()) = user_id);

drop policy if exists "own applications" on public.applications;
drop policy if exists "read own applications" on public.applications;
create policy "read own applications" on public.applications
  for select to authenticated using ((select auth.uid()) = user_id);

drop policy if exists "own premium reservation" on public.premium_reservations;
drop policy if exists "read own premium reservation" on public.premium_reservations;
create policy "read own premium reservation" on public.premium_reservations
  for select to authenticated using ((select auth.uid()) = user_id);

-- Storage: CV files are uploaded and deleted by the API only.
drop policy if exists "own document files" on storage.objects;
drop policy if exists "read own document files" on storage.objects;
create policy "read own document files" on storage.objects
  for select to authenticated
  using (bucket_id = 'documents' and (storage.foldername(name))[1] = (select auth.uid())::text);
