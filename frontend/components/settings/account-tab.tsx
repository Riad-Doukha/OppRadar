"use client";

import { useQueryClient } from "@tanstack/react-query";
import Image from "next/image";
import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useEffect, useState, useTransition, type FormEvent } from "react";

import { Button, Spinner } from "@/components/ui/button";
import { Field, Input, PasswordInput } from "@/components/ui/field";
import { setLocale } from "@/i18n/actions";
import { LOCALES, LOCALE_NAMES, type Locale } from "@/i18n/config";
import { api, type Me } from "@/lib/api/client";
import { authError, passwordProblem } from "@/lib/auth";
import { createClient } from "@/lib/supabase/client";
import { THEMES, useTheme } from "@/lib/theme";

import { Badge, Choice, SettingRow, SettingsCard, Status } from "./ui";

type Msg = { text: string; error?: boolean } | null;

/** Saved on this device (not the account), so the demo account can use it too. */
function ThemeRow() {
  const t = useTranslations("settings.account");
  const tt = useTranslations("common.theme");
  const [theme, setTheme] = useTheme();
  return (
    <SettingRow title={t("theme")} description={t("themeHint")} last>
      <Choice label={t("theme")} value={theme} options={THEMES.map((o) => ({ value: o.value, label: tt(o.value) }))} onChange={setTheme} />
    </SettingRow>
  );
}

/** Interface language (cookie on this device); the page re-renders in the new language. */
function LanguageRow() {
  const t = useTranslations("settings.account");
  const locale = useLocale() as Locale;
  const router = useRouter();
  const [pending, start] = useTransition();
  const choose = (l: Locale) =>
    start(async () => {
      await setLocale(l);
      router.refresh();
    });
  return (
    <SettingRow title={t("language")} description={t("languageHint")}>
      <Choice label={t("language")} value={locale} disabled={pending} options={LOCALES.map((l) => ({ value: l, label: <span lang={l}>{LOCALE_NAMES[l]}</span> }))} onChange={choose} />
    </SettingRow>
  );
}

export function AccountTab({ me }: { me: Me }) {
  const t = useTranslations("settings.account");
  const ro = me.is_demo;
  return (
    <>
      <SettingsCard label={t("card")}>
        <EmailRow email={me.email} readOnly={ro} />
        <PasswordRow readOnly={ro} />
        <SettingRow title={t("twoFactor")} description={t("twoFactorHint")}>
          <Badge tone="warning">{t("off")}</Badge>
          <Button variant="outline" className="h-10 text-sm" disabled>
            {t("enableSoon")}
          </Button>
        </SettingRow>
        <LanguageRow />
        <ThemeRow />
      </SettingsCard>

      <SessionsCard readOnly={ro} />
      <DangerZone readOnly={ro} />
    </>
  );
}

function EmailRow({ email, readOnly }: { email: string; readOnly: boolean }) {
  const t = useTranslations("settings.account");
  const ta = useTranslations("auth");
  const tc = useTranslations("common");
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
    if (error) return setMsg({ text: ta(`errors.${authError(error)}`), error: true });
    setOpen(false);
    setMsg({ text: t("emailSent", { old: email, new: value.trim() }) });
  }

  return (
    <div className="border-b border-line">
      <SettingRow title={t("email")} description={t("emailUse", { email })} last>
        {!readOnly && !open && (
          <Button variant="ghost" className="h-10 text-sm" onClick={() => setOpen(true)}>
            {t("change")}
          </Button>
        )}
      </SettingRow>
      {open && (
        <form onSubmit={submit} className="flex flex-col gap-3 pb-4 sm:flex-row sm:items-end">
          <div className="flex-1">
            <Field label={t("newEmail")}>
              {(p) => <Input {...p} type="email" autoComplete="email" required value={value} onChange={(e) => setValue(e.target.value)} placeholder={ta("emailPlaceholder")} />}
            </Field>
          </div>
          <div className="flex gap-2">
            <Button type="submit" size="sm" disabled={busy || !/^\S+@\S+\.\S+$/.test(value.trim()) || value.trim() === email}>
              {busy && <Spinner />} {t("sendConfirmation")}
            </Button>
            <Button type="button" variant="ghost" size="sm" onClick={() => setOpen(false)}>
              {tc("cancel")}
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
  const t = useTranslations("settings.account");
  const ta = useTranslations("auth");
  const tc = useTranslations("common");
  const [open, setOpen] = useState(false);
  const [pw, setPw] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<Msg>(null);
  const rule = pw ? passwordProblem(pw) : null;
  const problem = rule && ta(`rules.${rule}`);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    const { error } = await createClient().auth.updateUser({ password: pw });
    setBusy(false);
    if (error) return setMsg({ text: ta(`errors.${authError(error)}`), error: true });
    setOpen(false);
    setPw("");
    setConfirm("");
    setMsg({ text: t("passwordUpdated") });
  }

  return (
    <div className="border-b border-line">
      <SettingRow title={t("password")} description={t("passwordHint")} last>
        {!readOnly && !open && (
          <Button variant="ghost" className="h-10 text-sm" onClick={() => setOpen(true)}>
            {t("update")}
          </Button>
        )}
      </SettingRow>
      {open && (
        <form onSubmit={submit} className="grid gap-3 pb-4 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
          <Field label={t("newPassword")} error={problem || undefined}>
            {(p) => <PasswordInput {...p} autoComplete="new-password" value={pw} onChange={(e) => setPw(e.target.value)} />}
          </Field>
          <Field label={t("confirm")} error={confirm && confirm !== pw ? t("mismatch") : undefined}>
            {(p) => <PasswordInput {...p} autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />}
          </Field>
          <div className="flex gap-2 sm:pb-[1px]">
            <Button type="submit" size="sm" disabled={busy || !pw || Boolean(problem) || pw !== confirm}>
              {busy && <Spinner />} {tc("save")}
            </Button>
            <Button type="button" variant="ghost" size="sm" onClick={() => setOpen(false)}>
              {tc("cancel")}
            </Button>
          </div>
        </form>
      )}
      <Status text={msg?.text ?? null} error={msg?.error} />
      {msg && <div className="pb-3" />}
    </div>
  );
}

/** Browser and OS names from the user agent — only for this device (null = unknown). */
function describeDevice(ua: string) {
  const browser = /Edg\//.test(ua) ? "Edge" : /OPR\//.test(ua) ? "Opera" : /Firefox\//.test(ua) ? "Firefox" : /Chrome\//.test(ua) ? "Chrome" : /Safari\//.test(ua) ? "Safari" : null;
  const os = /Windows/.test(ua) ? "Windows" : /Android/.test(ua) ? "Android" : /iPhone|iPad/.test(ua) ? "iOS" : /Mac OS X/.test(ua) ? "macOS" : /Linux/.test(ua) ? "Linux" : null;
  return { browser, os, mobile: /Android|iPhone|iPad|Mobile/.test(ua) };
}

function SessionsCard({ readOnly }: { readOnly: boolean }) {
  const t = useTranslations("settings.sessions");
  const ta = useTranslations("auth");
  const [device, setDevice] = useState<ReturnType<typeof describeDevice> | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<Msg>(null);
  useEffect(() => {
    setDevice(describeDevice(navigator.userAgent));
  }, []);

  async function signOutOthers() {
    setBusy(true);
    setMsg(null);
    const { error } = await createClient().auth.signOut({ scope: "others" });
    setBusy(false);
    setMsg(error ? { text: ta(`errors.${authError(error)}`), error: true } : { text: t("signedOut") });
  }

  return (
    <SettingsCard label={t("card")}>
      <div className="flex items-center gap-3.5 rounded-field border border-brand-soft bg-page px-4 py-[13px]">
        <Image src={device?.mobile ? "/icons/device-phone.svg" : "/icons/device-desktop.svg"} alt="" width={19} height={19} className={device?.mobile ? "icon-adapt" : undefined} />
        <div className="min-w-0 flex-1">
          <p className="text-sm text-ink">{device ? t("device", { browser: device.browser ?? t("browser"), os: device.os ?? t("yourDevice") }) : t("thisDevice")}</p>
          <p className="font-mono text-xs text-muted">{t("activeNow")}</p>
        </div>
        <span className="flex h-6 items-center rounded-full bg-success-tint px-3 text-[13px] font-bold text-success">{t("current")}</span>
      </div>
      <p className="pt-3 text-[13px] text-muted">{t("others")}</p>
      {!readOnly && (
        <button type="button" onClick={signOutOthers} disabled={busy} className="mt-3 flex items-center gap-2 text-sm font-bold text-brand hover:text-brand-strong disabled:opacity-60">
          {busy && <Spinner />} {t("signOutOthers")} <span className="inline-block rtl:-scale-x-100">→</span>
        </button>
      )}
      <Status text={msg?.text ?? null} error={msg?.error} />
    </SettingsCard>
  );
}

function DangerZone({ readOnly }: { readOnly: boolean }) {
  const t = useTranslations("settings.danger");
  const tc = useTranslations("common");
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
      setError(e instanceof Error ? e.message : t("failed"));
    }
  }

  return (
    <SettingsCard label={t("card")} danger>
      <SettingRow
        title={t("title")}
        description={t("body")}
        last
      >
        {!readOnly && !open && (
          <Button variant="outline" className="h-10 border-danger text-sm text-danger hover:bg-danger-soft" onClick={() => setOpen(true)}>
            {t("button")}
          </Button>
        )}
      </SettingRow>
      {open && (
        <div className="rounded-field border border-danger-line bg-danger-soft p-4">
          <p className="text-sm text-ink">
            {t.rich("typeToConfirm", { strong: (c) => <strong className="font-mono">{c}</strong> })}
          </p>
          <div className="mt-2.5 flex flex-col gap-2 sm:flex-row">
            <Input value={typed} onChange={(e) => setTyped(e.target.value)} aria-label={t("typeLabel")} className="sm:max-w-60" autoComplete="off" />
            <Button className="h-11 bg-danger text-sm hover:bg-danger-strong" disabled={typed !== "DELETE" || busy} onClick={remove}>
              {busy && <Spinner />} {t("permanent")}
            </Button>
            <Button variant="ghost" className="h-11 text-sm" onClick={() => (setOpen(false), setTyped(""))} disabled={busy}>
              {tc("cancel")}
            </Button>
          </div>
          <Status text={error} error />
        </div>
      )}
    </SettingsCard>
  );
}
