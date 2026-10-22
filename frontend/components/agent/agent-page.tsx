"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Image from "next/image";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/button";
import { Pill, SectionLabel } from "@/components/ui/inputs";
import { Loading, Skeleton } from "@/components/ui/skeleton";
import { api, type Me, type Schemas } from "@/lib/api/client";
import { TYPE_LABELS, deadlineText } from "@/lib/opportunities";
import { cn } from "@/lib/utils";

type Msg = Schemas["ChatMessageOut"];
type History = Schemas["ChatHistory"];

const SUGGESTIONS = ["Show scholarships closing this month", "Internships in data science", "Hackathons in Algiers", "Paste a link to an opportunity"];
const HOW_TO_ASK = ["Name a type: internship, hackathon, scholarship…", "Add a field or a place: “data”, “Oran”, “remote”", "Paste an official link to find it in OppRadar"];

/** Ask the agent (Figma). Until the AI chat ships, answers are look-ups in OppRadar's data. */
export function AgentPage() {
  const qc = useQueryClient();
  const params = useSearchParams();
  const me = useQuery({ queryKey: ["me"], queryFn: () => api<Me>("/me") });
  const history = useQuery({ queryKey: ["chat"], queryFn: () => api<History>("/chat/history") });
  const [local, setLocal] = useState<Msg[]>([]); // turns not stored (consent off / demo)
  const [input, setInput] = useState("");
  const end = useRef<HTMLDivElement>(null);
  const asked = useRef(false);

  const send = useMutation({
    mutationFn: (message: string) => api<History>("/chat", { method: "POST", body: JSON.stringify({ message }) }),
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
    const t = text.trim();
    if (!t || send.isPending) return;
    setInput("");
    send.mutate(t);
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

  useEffect(() => end.current?.scrollIntoView({ behavior: "smooth", block: "end" }), [messages.length, send.isPending]);

  return (
    <div className="mx-auto grid max-w-[1112px] gap-6 lg:grid-cols-[1fr_250px]">
      <div className="min-w-0">
        <h1 className="font-display text-2xl font-bold tracking-[-0.5px] text-ink sm:text-[28px]">Ask the agent</h1>
        <p className="pt-1 text-sm text-body">Ask about opportunities or paste a link — the agent searches what OppRadar has found so far.</p>

        <Alert tone="info" className="mt-4">
          The full agent — eligibility verdicts with sources, required documents, answers in Arabic, French or English — arrives with the AI phase. Until then, answers come from OppRadar&apos;s opportunity search.
        </Alert>

        <div className="flex flex-wrap gap-2 pt-4">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => (s.startsWith("Paste") ? document.getElementById("ask-input")?.focus() : submit(s))}
              className="rounded-full border border-line bg-surface px-3.5 py-2 text-[13px] text-body hover:border-brand hover:text-ink"
            >
              {s}
            </button>
          ))}
        </div>

        <div className="flex flex-col gap-4 pt-5" aria-live="polite">
          {history.isPending && (
            <Loading label="Loading your conversation…">
              <Skeleton className="ml-auto h-12 w-2/3 rounded-card" />
              <Skeleton className="mt-4 h-24 w-3/4 rounded-card" />
            </Loading>
          )}
          {history.isError && <Alert>We couldn&apos;t load your conversation: {history.error.message}</Alert>}
          {messages.map((m, i) => (m.role === "user" ? <UserBubble key={m.id ?? `l${i}`} m={m} /> : <AgentCard key={m.id ?? `l${i}`} m={m} />))}
          {send.isPending && (
            <div className="flex w-fit items-center gap-2 rounded-card border border-line bg-surface px-4 py-3 text-sm text-muted">
              <Spinner className="text-brand" /> Searching opportunities…
            </div>
          )}
          {send.isError && <Alert>Couldn&apos;t answer: {send.error.message}</Alert>}
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
            placeholder="Paste a link or ask about any opportunity…"
            aria-label="Ask the agent"
            className="min-w-0 flex-1 bg-transparent text-[15px] text-ink outline-none placeholder:text-faint"
          />
          <button type="submit" disabled={!input.trim() || send.isPending} aria-label="Send" className="flex size-11 shrink-0 items-center justify-center rounded-field bg-brand hover:bg-brand-strong disabled:opacity-50">
            <Image src="/icons/arrow-right-white.svg" alt="" width={18} height={18} />
          </button>
        </form>
        <p className="pt-2 text-center text-xs text-muted">
          The agent can make mistakes. <strong className="text-body">Always verify on the official page.</strong>
        </p>
      </div>

      <aside className="flex flex-col gap-4 self-start lg:sticky lg:top-24">
        <section className="rounded-card border border-line bg-surface p-4">
          <SectionLabel>Recent questions</SectionLabel>
          {recent.length ? (
            <ul className="flex flex-col pt-2">
              {recent.map((m, i) => (
                <li key={m.id ?? i}>
                  <button type="button" onClick={() => submit(m.content)} className="w-full truncate rounded-lg px-2 py-2 text-left text-[13px] text-body hover:bg-page">
                    {m.content}
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="pt-2 text-[13px] text-muted">Your questions will appear here.</p>
          )}
          {history.data && !history.data.saved && !me.data?.is_demo && (
            <p className="pt-2 text-xs text-muted">
              History isn&apos;t kept.{" "}
              <Link href="/settings?tab=privacy" className="font-bold text-brand">
                Turn it on
              </Link>
            </p>
          )}
          {history.data?.saved && messages.length > 0 && (
            <button type="button" onClick={() => clear.mutate()} disabled={clear.isPending} className="mt-2 text-xs font-bold text-muted hover:text-danger">
              Clear history
            </button>
          )}
        </section>
        <section className="rounded-card border border-line bg-page p-4">
          <SectionLabel>How to ask</SectionLabel>
          <ul className="flex list-disc flex-col gap-1.5 pt-2 pl-4 text-xs text-body">
            {HOW_TO_ASK.map((t) => <li key={t}>{t}</li>)}
          </ul>
        </section>
      </aside>
    </div>
  );
}

function UserBubble({ m }: { m: Msg }) {
  return <p className="ml-auto max-w-[85%] rounded-card rounded-br-md bg-brand px-4 py-3 text-[15px] break-words whitespace-pre-wrap text-white">{m.content}</p>;
}

function AgentCard({ m }: { m: Msg }) {
  return (
    <div className="max-w-full rounded-card rounded-bl-md border border-line bg-surface p-4 sm:max-w-[90%]">
      <p className="text-sm text-ink">{m.content}</p>
      {m.opportunities.length > 0 && (
        <ul className="flex flex-col gap-2.5 pt-3">
          {m.opportunities.map((o) => {
            const d = deadlineText(o.deadline);
            return (
              <li key={o.id} className="rounded-field border border-line bg-page/60 p-3.5">
                <div className="flex flex-wrap items-center gap-2">
                  <Pill className="h-6 text-[11px]">{TYPE_LABELS[o.type]}</Pill>
                  <span className={cn("text-xs font-bold", d.urgent ? "text-warning" : "text-muted")}>{d.text}</span>
                </div>
                <p className="pt-1.5 text-[15px] font-bold text-ink">{o.title}</p>
                <p className="text-[13px] text-muted">{o.organizer}</p>
                <div className="flex flex-wrap gap-2 pt-2.5">
                  <Link href={`/opportunities/${o.id}`} className="flex h-9 items-center rounded-field bg-brand px-4 text-[13px] font-bold text-white hover:bg-brand-strong">
                    View details
                  </Link>
                  <Link href={`/apply/${o.id}`} className="flex h-9 items-center rounded-field border border-brand px-4 text-[13px] font-bold text-brand hover:bg-brand-soft">
                    Apply assistant
                  </Link>
                  {o.url && (
                    <a href={o.url} target="_blank" rel="noopener noreferrer" className="flex h-9 items-center px-2 text-[13px] font-bold text-body hover:text-ink">
                      Official page ↗
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
