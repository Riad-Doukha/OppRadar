"use client";

import { useQueryClient } from "@tanstack/react-query";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { Button, Spinner } from "@/components/ui/button";
import { Field, Input, PasswordInput } from "@/components/ui/field";
import { api, type Me } from "@/lib/api/client";
import { authErrorMessage, passwordProblem } from "@/lib/auth";
import { createClient } from "@/lib/supabase/client";

import { Badge, Choice, SettingRow, SettingsCard, Status } from "./ui";

type Msg = { text: string; error?: boolean } | null;

export function AccountTab({ me }: { me: Me }) {
  const ro = me.is_demo;
  return (
    <>
      <SettingsCard label="Account">
        <EmailRow email={me.email} readOnly={ro} />
        <PasswordRow readOnly={ro} />
        <SettingRow title="Two-factor authentication" description="Extra code when signing in from a new device">
          <Badge tone="warning">Off</Badge>
          <Button variant="outline" className="h-10 text-sm" disabled title="Coming soon">
            Enable · soon
          </Button>
        </SettingRow>
        <SettingRow title="Interface language" description="English for now · العربية with a full right-to-left layout is coming">
          <Choice label="Interface language" value="en" options={[{ value: "en", label: "English" }, { value: "ar", label: "العربية", soon: true }]} />
        </SettingRow>
        <SettingRow title="Theme" description="Light is tuned for daylight outdoors — a dark theme that follows your system is coming" last>
          <Choice label="Theme" value="light" options={[{ value: "light", label: "Light" }, { value: "system", label: "System", soon: true }]} />
        </SettingRow>
      </SettingsCard>

      <SessionsCard readOnly={ro} />
      <DangerZone readOnly={ro} />
    </>
  );
}

function EmailRow({ email, readOnly }: { email: string; readOnly: boolean }) {
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<Msg>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    const { error } = await createClient().auth.updateUser(
      { email: value.trim() },
      { emailRedirectTo: `${window.location.origin}/auth/callback?next=/settings` },
    );
    setBusy(false);
    if (error) return setMsg({ text: authErrorMessage(error), error: true });
    setOpen(false);
    setMsg({ text: `Confirmation links sent to ${email} and ${value.trim()}. The change applies once both are confirmed.` });
  }

  return (
    <div className="border-b border-line">
      <SettingRow title="Email" description={`${email} · used for alerts & sign-in`} last>
        {!readOnly && !open && (
          <Button variant="ghost" className="h-10 text-sm" onClick={() => setOpen(true)}>
            Change
          </Button>
        )}
      </SettingRow>
      {open && (
        <form onSubmit={submit} className="flex flex-col gap-3 pb-4 sm:flex-row sm:items-end">
          <div className="flex-1">
            <Field label="New email">
              {(p) => <Input {...p} type="email" autoComplete="email" required value={value} onChange={(e) => setValue(e.target.value)} placeholder="you@university.dz" />}
            </Field>
          </div>
          <div className="flex gap-2">
            <Button type="submit" size="sm" disabled={busy || !/^\S+@\S+\.\S+$/.test(value.trim()) || value.trim() === email}>
              {busy && <Spinner />} Send confirmation
            </Button>
            <Button type="button" variant="ghost" size="sm" onClick={() => setOpen(false)}>
              Cancel
            </Button>
          </div>
        </form>
      )}
      <Status text={msg?.text ?? null} error={msg?.error} />
      {msg && <div className="pb-3" />}
    </div>
  );
}

function PasswordRow({ readOnly }: { readOnly: boolean }) {
  const [open, setOpen] = useState(false);
  const [pw, setPw] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<Msg>(null);
  const problem = pw ? passwordProblem(pw) : null;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    const { error } = await createClient().auth.updateUser({ password: pw });
    setBusy(false);
    if (error) return setMsg({ text: authErrorMessage(error), error: true });
    setOpen(false);
    setPw("");
    setConfirm("");
    setMsg({ text: "Password updated." });
  }

  return (
    <div className="border-b border-line">
      <SettingRow title="Password" description="8+ characters with a number" last>
        {!readOnly && !open && (
          <Button variant="ghost" className="h-10 text-sm" onClick={() => setOpen(true)}>
            Update
          </Button>
        )}
      </SettingRow>
      {open && (
        <form onSubmit={submit} className="grid gap-3 pb-4 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
          <Field label="New password" error={problem ?? undefined}>
            {(p) => <PasswordInput {...p} autoComplete="new-password" value={pw} onChange={(e) => setPw(e.target.value)} />}
          </Field>
          <Field label="Confirm" error={confirm && confirm !== pw ? "Doesn't match." : undefined}>
            {(p) => <PasswordInput {...p} autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />}
          </Field>
          <div className="flex gap-2 sm:pb-[1px]">
            <Button type="submit" size="sm" disabled={busy || !pw || Boolean(problem) || pw !== confirm}>
              {busy && <Spinner />} Save
            </Button>
            <Button type="button" variant="ghost" size="sm" onClick={() => setOpen(false)}>
              Cancel
            </Button>
          </div>
        </form>
      )}
      <Status text={msg?.text ?? null} error={msg?.error} />
      {msg && <div className="pb-3" />}
    </div>
  );
}

/** "Chrome on Windows" from the user agent — only for this device. */
function describeDevice(ua: string) {
  const browser = /Edg\//.test(ua) ? "Edge" : /OPR\//.test(ua) ? "Opera" : /Firefox\//.test(ua) ? "Firefox" : /Chrome\//.test(ua) ? "Chrome" : /Safari\//.test(ua) ? "Safari" : "Browser";
  const os = /Windows/.test(ua) ? "Windows" : /Android/.test(ua) ? "Android" : /iPhone|iPad/.test(ua) ? "iOS" : /Mac OS X/.test(ua) ? "macOS" : /Linux/.test(ua) ? "Linux" : "your device";
  return { label: `${browser} on ${os}`, mobile: /Android|iPhone|iPad|Mobile/.test(ua) };
}

function SessionsCard({ readOnly }: { readOnly: boolean }) {
  const [device, setDevice] = useState<{ label: string; mobile: boolean } | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<Msg>(null);
  useEffect(() => setDevice(describeDevice(navigator.userAgent)), []);

  async function signOutOthers() {
    setBusy(true);
    setMsg(null);
    const { error } = await createClient().auth.signOut({ scope: "others" });
    setBusy(false);
    setMsg(error ? { text: authErrorMessage(error), error: true } : { text: "Signed out on every other device." });
  }

  return (
    <SettingsCard label="Active sessions">
      <div className="flex items-center gap-3.5 rounded-field border border-brand-soft bg-page px-4 py-[13px]">
        <Image src={device?.mobile ? "/icons/device-phone.svg" : "/icons/device-desktop.svg"} alt="" width={19} height={19} />
        <div className="min-w-0 flex-1">
          <p className="text-sm text-ink">{device?.label ?? "This device"}</p>
          <p className="font-mono text-xs text-muted">this device · active now</p>
        </div>
        <span className="flex h-6 items-center rounded-full bg-[#ecfdf5] px-3 text-[13px] font-bold text-success">Current</span>
      </div>
      <p className="pt-3 text-[13px] text-muted">Other devices aren&apos;t listed individually yet. If you signed in somewhere you don&apos;t recognise, sign them all out.</p>
      {!readOnly && (
        <button type="button" onClick={signOutOthers} disabled={busy} className="mt-3 flex items-center gap-2 text-sm font-bold text-brand hover:text-brand-strong disabled:opacity-60">
          {busy && <Spinner />} Sign out everywhere else →
        </button>
      )}
      <Status text={msg?.text ?? null} error={msg?.error} />
    </SettingsCard>
  );
}

function DangerZone({ readOnly }: { readOnly: boolean }) {
  const router = useRouter();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function remove() {
    setBusy(true);
    setError(null);
    try {
      await api("/me", { method: "DELETE" });
      await createClient().auth.signOut();
      qc.clear();
      router.push("/?deleted=1");
      router.refresh();
    } catch (e) {
      setBusy(false);
      setError(e instanceof Error ? e.message : "Couldn't delete the account.");
    }
  }

  return (
    <SettingsCard label="Danger zone" danger>
      <SettingRow
        title="Delete my account"
        description="Permanently removes your profile, CV files, saved opportunities and settings. Alerts stop immediately. This can't be undone."
        last
      >
        {!readOnly && !open && (
          <Button variant="outline" className="h-10 border-danger text-sm text-danger hover:bg-danger-soft" onClick={() => setOpen(true)}>
            Delete account
          </Button>
        )}
      </SettingRow>
      {open && (
        <div className="rounded-field border border-danger-line bg-danger-soft p-4">
          <p className="text-sm text-ink">
            Type <strong className="font-mono">DELETE</strong> to confirm.
          </p>
          <div className="mt-2.5 flex flex-col gap-2 sm:flex-row">
            <Input value={typed} onChange={(e) => setTyped(e.target.value)} aria-label="Type DELETE to confirm" className="sm:max-w-60" autoComplete="off" />
            <Button className="h-11 bg-danger text-sm hover:bg-[#b91c1c]" disabled={typed !== "DELETE" || busy} onClick={remove}>
              {busy && <Spinner />} Delete permanently
            </Button>
            <Button variant="ghost" className="h-11 text-sm" onClick={() => (setOpen(false), setTyped(""))} disabled={busy}>
              Cancel
            </Button>
          </div>
          <Status text={error} error />
        </div>
      )}
    </SettingsCard>
  );
}
