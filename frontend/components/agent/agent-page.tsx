"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Image from "next/image";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/button";
import { Pill, SectionLabel } from "@/components/ui/inputs";
import { Loading, Skeleton } from "@/components/ui/skeleton";
import { api, type Me, type Schemas } from "@/lib/api/client";
import { useOpportunityText } from "@/lib/opportunities";
import { cn } from "@/lib/utils";

type Msg = Schemas["ChatMessageOut"];
type History = Schemas["ChatHistory"];

const SUGGESTIONS = ["scholarships", "internships", "hackathons", "paste"] as const;
const HOW_TO_ASK = ["type", "field", "link"] as const;

/** Ask the agent (Figma). Until the AI chat ships, answers are look-ups in OppRadar's data. */
export function AgentPage() {
  const t = useTranslations("agent");
  const qc = useQueryClient();
  const params = useSearchParams();
  const me = useQuery({ queryKey: ["me"], queryFn: () => api<Me>("/me") });
  const history = useQuery({ queryKey: ["chat"], queryFn: () => api<History>("/chat/history") });
  const [local, setLocal] = useState<Msg[]>([]); // turns not stored (consent off / demo)
  const [input, setInput] = useState("");
  const end = useRef<HTMLDivElement>(null);
  const asked = useRef(false);
  // "Ask the agent about this" (opportunity page) opens /agent?opportunity=<id>.
  const [about, setAbout] = useState<string | null>(params.get("opportunity"));
  const subject = useQuery({
    queryKey: ["opportunity", about],
    queryFn: () => api<Schemas["MyOpportunity"]>(`/me/opportunities/${about}`),
    enabled: Boolean(about),
  });

  const send = useMutation({
    mutationFn: (message: string) =>
      api<History>("/chat", { method: "POST", body: JSON.stringify({ message, ...(about && { opportunity_id: about }) }) }),
    onSuccess: (reply) => {
      if (reply.saved) qc.setQueryData<History>(["chat"], (h) => (h ? { ...h, messages: [...h.messages, ...reply.messages] } : reply));
      else setLocal((l) => [...l, ...reply.messages]);
    },
  });
  const clear = useMutation({
    mutationFn: () => api("/chat/history", { method: "DELETE" }),
    onSuccess: () => {
      setLocal([]);
      qc.invalidateQueries({ queryKey: ["chat"] });
    },
  });

  const messages = [...(history.data?.messages ?? []), ...local];
  const recent = messages.filter((m) => m.role === "user").slice(-6).reverse();

  function submit(text: string) {
    const message = text.trim();
    if (!message || send.isPending) return;
    setInput("");
    send.mutate(message);
  }

  // "Ask the agent" bar on the dashboard links here with ?q=…
  useEffect(() => {
    const q = params.get("q");
    if (q && !asked.current && history.isSuccess) {
      asked.current = true;
      submit(q);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- run once when history is ready
  }, [history.isSuccess, params]);

  // Block body: newer browsers return a Promise from scrollIntoView, and an effect may only return a cleanup function.
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, send.isPending]);

  return (
    <div className="mx-auto grid max-w-[1112px] gap-6 lg:grid-cols-[1fr_250px]">
      <div className="min-w-0">
        <h1 className="font-display text-2xl font-bold tracking-[-0.5px] text-ink sm:text-[28px]">{t("title")}</h1>
        <p className="pt-1 text-sm text-body">{t("subtitle")}</p>

        <Alert tone="info" className="mt-4">
          {t("notice")}
        </Alert>

        <div className="flex flex-wrap gap-2 pt-4">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => (s === "paste" ? document.getElementById("ask-input")?.focus() : submit(t(`suggestions.${s}`)))}
              className="rounded-full border border-line bg-surface px-3.5 py-2 text-[13px] text-body hover:border-brand hover:text-ink"
            >
              {t(`suggestions.${s}`)}
            </button>
          ))}
        </div>

        {about && subject.data && (
          <p className="mt-4 flex flex-wrap items-center gap-2 rounded-field bg-brand-soft px-3.5 py-2 text-sm text-brand-strong">
            <span className="min-w-0 font-bold">{t("about", { title: subject.data.title })}</span>
            <button type="button" onClick={() => setAbout(null)} className="ms-auto text-xs font-bold underline">
              {t("clearAbout")}
            </button>
          </p>
        )}

        <div className="flex flex-col gap-4 pt-5" aria-live="polite">
          {history.isPending && (
            <Loading label={t("loading")}>
              <Skeleton className="ms-auto h-12 w-2/3 rounded-card" />
              <Skeleton className="mt-4 h-24 w-3/4 rounded-card" />
            </Loading>
          )}
          {history.isError && <Alert>{t("loadError", { error: history.error.message })}</Alert>}
          {messages.map((m, i) => (m.role === "user" ? <UserBubble key={m.id ?? `l${i}`} m={m} /> : <AgentCard key={m.id ?? `l${i}`} m={m} />))}
          {send.isPending && (
            <div className="flex w-fit items-center gap-2 rounded-card border border-line bg-surface px-4 py-3 text-sm text-muted">
              <Spinner className="text-brand" /> {t("searching")}
            </div>
          )}
          {send.isError && <Alert>{t("sendError", { error: send.error.message })}</Alert>}
          <div ref={end} />
        </div>

        <form
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            submit(input);
          }}
          className="sticky bottom-3 mt-5 flex items-center gap-2.5 rounded-card border border-line bg-surface px-3 py-2.5 shadow-card"
        >
          <Image src="/icons/ask-sparkle.svg" alt="" width={18} height={18} />
          <input
            id="ask-input"
            value={input}
            maxLength={1000}
            onChange={(e) => setInput(e.target.value)}
            placeholder={t("placeholder")}
            aria-label={t("title")}
            className="min-w-0 flex-1 bg-transparent text-[15px] text-ink outline-none placeholder:text-faint"
          />
          <button type="submit" disabled={!input.trim() || send.isPending} aria-label={t("send")} className="flex size-11 shrink-0 items-center justify-center rounded-field bg-brand hover:bg-brand-strong disabled:opacity-50">
            <Image src="/icons/arrow-right-white.svg" alt="" width={18} height={18} className="rtl:-scale-x-100" />
          </button>
        </form>
        <p className="pt-2 text-center text-xs text-muted">
          {t.rich("mistakes", { strong: (c) => <strong className="text-body">{c}</strong> })}
        </p>
      </div>

      <aside className="flex flex-col gap-4 self-start lg:sticky lg:top-24">
        <section className="rounded-card border border-line bg-surface p-4">
          <SectionLabel>{t("recent")}</SectionLabel>
          {recent.length ? (
            <ul className="flex flex-col pt-2">
              {recent.map((m, i) => (
                <li key={m.id ?? i}>
                  <button type="button" onClick={() => submit(m.content)} className="w-full truncate rounded-lg px-2 py-2 text-start text-[13px] text-body hover:bg-page">
                    {m.content}
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="pt-2 text-[13px] text-muted">{t("recentEmpty")}</p>
          )}
          {history.data && !history.data.saved && !me.data?.is_demo && (
            <p className="pt-2 text-xs text-muted">
              {t("notKept")}{" "}
              <Link href="/settings?tab=privacy" className="font-bold text-brand">
                {t("turnOn")}
              </Link>
            </p>
          )}
          {history.data?.saved && messages.length > 0 && (
            <button type="button" onClick={() => clear.mutate()} disabled={clear.isPending} className="mt-2 text-xs font-bold text-muted hover:text-danger">
              {t("clear")}
            </button>
          )}
        </section>
        <section className="rounded-card border border-line bg-page p-4">
          <SectionLabel>{t("howTo")}</SectionLabel>
          <ul className="flex list-disc flex-col gap-1.5 pt-2 ps-4 text-xs text-body">
            {HOW_TO_ASK.map((k) => <li key={k}>{t(`tips.${k}`)}</li>)}
          </ul>
        </section>
      </aside>
    </div>
  );
}

function UserBubble({ m }: { m: Msg }) {
  return <p className="ms-auto max-w-[85%] rounded-card rounded-ee-md bg-brand px-4 py-3 text-[15px] break-words whitespace-pre-wrap text-white">{m.content}</p>;
}

function AgentCard({ m }: { m: Msg }) {
  const t = useTranslations("agent");
  const { typeLabel, deadlineText } = useOpportunityText();
  const e = m.eligibility;
  // Sources worth showing: quoted ones, or ones not already shown as cards below.
  const cards = new Set(m.opportunities.map((o) => o.url));
  const sources = (m.citations as { url?: string; title?: string; quote?: string }[]).filter((c) => c.url && (c.quote || !cards.has(c.url)));
  return (
    <div className="max-w-full rounded-card rounded-es-md border border-line bg-surface p-4 sm:max-w-[90%]">
      {!m.in_source && <p className="mb-2 w-fit rounded-full bg-warning-tint px-3 py-1 text-xs font-bold text-warning">{t("notInSource")}</p>}
      {/* AI text is untrusted: rendered as plain text, never as HTML. */}
      <p className="text-sm whitespace-pre-wrap text-ink">{m.content}</p>
      {e && (
        <div className="mt-3 rounded-field border border-line bg-page/60 p-3.5 text-[13px]">
          <p className={cn("font-bold", e.eligible ? "text-success" : e.eligible === false ? "text-warning" : "text-muted")}>
            {e.eligible ? t("eligible") : e.eligible === false ? t("notEligible") : t("unclear")}
          </p>
          {([["met", e.met, "text-success", "✓"], ["gaps", e.gaps, "text-warning", "!"], ["next", e.next_steps, "text-brand", "→"]] as const).map(
            ([key, list, tone, mark]) =>
              list.length > 0 && (
                <div key={key} className="pt-2">
                  <p className="text-xs font-bold text-muted uppercase">{t(key)}</p>
                  {list.map((x) => (
                    <p key={x} className="flex gap-1.5 text-body">
                      <span className={tone} aria-hidden>
                        {mark}
                      </span>
                      {x}
                    </p>
                  ))}
                </div>
              ),
          )}
        </div>
      )}
      {sources.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5 pt-3 text-xs">
          <span className="font-bold text-muted">{t("sources")}:</span>
          {sources.map((cite, i) => {
            return cite.url ? (
              <a key={i} href={cite.url} target="_blank" rel="noopener noreferrer" title={cite.quote || undefined} className="rounded-full border border-line px-2.5 py-0.5 font-bold text-body hover:text-ink">
                {cite.title || new URL(cite.url).hostname}
              </a>
            ) : null;
          })}
        </div>
      )}
      {m.opportunities.length > 0 && (
        <ul className="flex flex-col gap-2.5 pt-3">
          {m.opportunities.map((o) => {
            const d = deadlineText(o.deadline);
            return (
              <li key={o.id} className="rounded-field border border-line bg-page/60 p-3.5">
                <div className="flex flex-wrap items-center gap-2">
                  <Pill className="h-6 text-[11px]">{typeLabel(o.type)}</Pill>
                  <span className={cn("text-xs font-bold", d.urgent ? "text-warning" : "text-muted")}>{d.text}</span>
                </div>
                <p className="pt-1.5 text-[15px] font-bold text-ink">{o.title}</p>
                <p className="text-[13px] text-muted">{o.organizer}</p>
                <div className="flex flex-wrap gap-2 pt-2.5">
                  <Link href={`/opportunities/${o.id}`} className="flex h-9 items-center rounded-field bg-brand px-4 text-[13px] font-bold text-white hover:bg-brand-strong">
                    {t("details")}
                  </Link>
                  <Link href={`/apply/${o.id}`} className="flex h-9 items-center rounded-field border border-brand px-4 text-[13px] font-bold text-brand hover:bg-brand-soft">
                    {t("assistant")}
                  </Link>
                  {o.url && (
                    <a href={o.url} target="_blank" rel="noopener noreferrer" className="flex h-9 items-center px-2 text-[13px] font-bold text-body hover:text-ink">
                      {t("official")} <span className="inline-block rtl:-scale-x-100">↗</span>
                    </a>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
