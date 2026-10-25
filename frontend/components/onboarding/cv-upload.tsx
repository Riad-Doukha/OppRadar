"use client";

import { useTranslations } from "next-intl";
import { useEffect, useRef, useState, type DragEvent } from "react";

import { Alert } from "@/components/ui/alert";
import { Button, Spinner } from "@/components/ui/button";
import { SectionLabel } from "@/components/ui/inputs";
import { api, type Schemas } from "@/lib/api/client";
import { labelOf, useOptions } from "@/lib/onboarding/options";
import { cn } from "@/lib/utils";

type Doc = Schemas["DocumentDetail"];
export type Prefill = Schemas["CVPrefill"];

const MAX_BYTES = 5 * 1024 * 1024;
const STAGES = ["queued", "reading", "extracting"] as const;

/**
 * "Upload your CV (optional)": PDF -> POST /documents -> poll until the AI
 * extraction is done -> show what was found; the user decides to apply it.
 */
export function CvUpload({ readOnly, onApply }: { readOnly: boolean; onApply: (prefill: Prefill) => Promise<void> }) {
  const t = useTranslations("onboarding.cv");
  const input = useRef<HTMLInputElement>(null);
  const [doc, setDoc] = useState<Doc | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const [applying, setApplying] = useState(false);
  const [applied, setApplied] = useState(false);

  const processing = doc && !["done", "failed"].includes(doc.status);

  // Poll the document while it is being read (a few seconds; OCR'd scans take longer).
  useEffect(() => {
    if (!doc || !processing) return;
    const timer = setTimeout(async () => {
      try {
        setDoc(await api<Doc>(`/documents/${doc.id}`));
      } catch {
        setError(t("lost"));
        setDoc(null);
      }
    }, 1200);
    return () => clearTimeout(timer);
  }, [doc, processing, t]);

  async function upload(file: File | undefined) {
    if (!file) return;
    setError(null);
    setDismissed(false);
    setApplied(false);
    if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) return setError(t("pdfOnly"));
    if (file.size > MAX_BYTES) return setError(t("tooBig"));
    const form = new FormData();
    form.append("file", file);
    form.append("kind", "cv");
    // Uploading is the consent: the notice below the drop zone says what happens.
    form.append("consent_ai_processing", "true");
    try {
      setDoc({ id: "", kind: "cv", file_name: file.name, size_bytes: file.size, status: "queued", created_at: "", warnings: [], read_method: null, extraction: null, error: null, prefill: null });
      const created = await api<Doc>("/documents", { method: "POST", body: form });
      setDoc(created);
    } catch (e) {
      setDoc(null);
      setError(e instanceof Error ? e.message : t("uploadFailed"));
    }
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDragging(false);
    if (!readOnly) upload(e.dataTransfer.files[0]);
  }

  async function apply() {
    if (!doc?.prefill) return;
    setApplying(true);
    try {
      await onApply(doc.prefill);
      setApplied(true);
    } catch {
      setError(t("applyFailed"));
    }
    setApplying(false);
  }

  return (
    <section>
      <SectionLabel>{t("title")}</SectionLabel>

      {/* The whole drop zone opens the file picker (click, Enter or Space). */}
      <button
        type="button"
        disabled={readOnly || Boolean(processing)}
        onClick={() => input.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        aria-describedby="cv-upload-help"
        className={cn(
          "mt-2.5 flex w-full cursor-pointer flex-col items-center rounded-field border border-dashed bg-page p-[22px] text-center transition-colors hover:border-brand focus-visible:shadow-focus disabled:cursor-not-allowed disabled:hover:border-line",
          dragging ? "border-brand" : "border-line",
        )}
      >
        {/* eslint-disable-next-line @next/next/no-img-element -- decorative icon */}
        <img src="/icons/upload-purple.svg" alt="" width={26} height={26} className="mb-2.5" />
        <span className="text-sm font-bold text-ink">{t.rich("drop", { brand: (c) => <span className="text-brand">{c}</span> })}</span>
        <span className="text-xs text-muted">{t("max")}</span>
      </button>
      <input
        ref={input}
        type="file"
        accept="application/pdf,.pdf"
        className="sr-only"
        tabIndex={-1}
        aria-hidden
        onChange={(e) => {
          upload(e.target.files?.[0]);
          e.target.value = ""; // so picking the same file again still fires onChange
        }}
      />
      <p id="cv-upload-help" className="pt-1.5 text-xs text-muted">
        {readOnly ? t("demoOff") : t("notice")}
      </p>

      {error && <Alert className="mt-3.5">{error}</Alert>}

      {doc && !dismissed && (
        <div className="mt-3.5 rounded-field border border-brand-soft bg-page px-[18px] py-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex min-w-0 items-center gap-2">
              <span className="rounded-md bg-brand px-2 py-[3px] font-mono text-xs font-bold text-white">{t("badge")}</span>
              <span className="truncate text-sm font-bold text-ink">{doc.file_name}</span>
              {doc.status === "done" && (
                <span className="flex h-[22px] shrink-0 items-center gap-1.5 rounded-full bg-success-tint px-3 text-[11px] font-bold text-success">
                  {/* eslint-disable-next-line @next/next/no-img-element -- decorative icon */}
                  <img src="/icons/check-small-green.svg" alt="" width={12} height={12} />
                  {t("uploaded")}
                </span>
              )}
            </div>
            <button type="button" onClick={() => setDismissed(true)} className="text-[13px] font-bold text-brand hover:text-brand-strong">
              {t("manual")}
            </button>
          </div>

          {processing && (
            <p className="flex items-center gap-2 pt-3 text-[13px] text-body" aria-live="polite">
              <Spinner className="text-brand" /> {STAGES.includes(doc.status as (typeof STAGES)[number]) && t(doc.status as (typeof STAGES)[number])}
            </p>
          )}
          {doc.status === "failed" && <p className="pt-3 text-[13px] text-danger">{doc.error ?? t("unreadable")}</p>}
          {doc.status === "done" && doc.prefill && <Found prefill={doc.prefill} />}
          {doc.status === "done" && doc.prefill && (
            <div className="flex items-center gap-3 pt-3">
              <Button size="sm" onClick={apply} disabled={applying || applied || readOnly}>
                {applying && <Spinner />}
                {applied ? t("applied") : t("use")}
              </Button>
              {applied && <span className="text-xs text-muted">{t("checkSteps")}</span>}
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function Found({ prefill }: { prefill: Prefill }) {
  const t = useTranslations("onboarding.cv");
  const { CURRENT_YEARS, EDUCATION_LEVELS } = useOptions();
  const { about, education, skills } = prefill;
  const rows: [string, string | null | undefined][] = [
    [t("rows.fullName"), about?.full_name],
    [t("rows.birthYear"), about?.birth_year?.toString()],
    [t("rows.location"), about?.wilaya ?? about?.country],
    [t("rows.major"), [labelOf(EDUCATION_LEVELS, education?.education_level), education?.field_of_study].filter(Boolean).join(", ")],
    [t("rows.currentYear"), labelOf(CURRENT_YEARS, education?.current_year)],
    [t("rows.skills"), skills?.skills?.slice(0, 3).map((s) => s.name).join(", ")],
  ];
  return (
    <>
      <p className="pt-2.5 text-[13px] font-bold text-ink">{t("found")}</p>
      <dl className="grid gap-2 pt-2 text-[13px] text-body sm:grid-cols-2">
        {rows.map(([k, v]) => (
          <div key={k}>
            <dt className="inline">{k}: </dt>
            <dd className="inline font-bold">{v || <span className="font-normal text-muted">{t("notFound")}</span>}</dd>
          </div>
        ))}
      </dl>
    </>
  );
}
