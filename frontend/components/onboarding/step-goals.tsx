"use client";

import { useTranslations } from "next-intl";
import { useMemo, useState } from "react";

import { Field, Input } from "@/components/ui/field";
import { SectionLabel } from "@/components/ui/inputs";
import type { Schemas } from "@/lib/api/client";
import { defined } from "@/lib/onboarding/body";
import { useAutosave } from "@/lib/onboarding/save-status";
import { cn } from "@/lib/utils";

import { Row, StepFrame, useWizard } from "./frame";

type LinkKind = Schemas["LinkIn"]["kind"];
const GOAL_MIN = 20;
const GOAL_MAX = 300;
const LINKS: { kind: LinkKind; placeholder: string }[] = [
  { kind: "linkedin", placeholder: "linkedin.com/in/your-name" },
  { kind: "github", placeholder: "github.com/your-name" },
  { kind: "portfolio", placeholder: "your-site.com" },
  { kind: "other", placeholder: "https://" },
];

export function StepGoals() {
  const t = useTranslations("onboarding.goals");
  const { me } = useWizard();
  const [goal, setGoal] = useState(me.goal ?? "");
  const [links, setLinks] = useState<Record<LinkKind, string>>(() => {
    const init = { linkedin: "", github: "", portfolio: "", other: "" };
    me.links.forEach((l) => (init[l.kind] ||= l.url));
    return init;
  });

  const trimmed = goal.trim();
  const body = useMemo(
    () =>
      defined({
        // Partial goals (< 20 chars) are kept locally until they are valid.
        goal: !trimmed ? null : trimmed.length >= GOAL_MIN ? trimmed : undefined,
        links: (Object.entries(links) as [LinkKind, string][]).filter(([, url]) => url.trim()).map(([kind, url]) => ({ kind, url: url.trim() })),
      }),
    [trimmed, links],
  );
  const { flush } = useAutosave("/me/onboarding/goals", body, { enabled: !me.is_demo });

  const errors = {
    goal: trimmed.length < GOAL_MIN ? t("tooShort", { n: GOAL_MIN }) : trimmed.length > GOAL_MAX ? t("tooLong", { n: GOAL_MAX }) : null,
  };

  return (
    <StepFrame step={4} errors={errors} flush={flush}>
      {(show) => (
        <>
          <div>
            <label htmlFor="goal" className="text-[13px] font-bold text-ink">
              {t("goal")} <span className="font-normal text-muted">{t("range", { min: GOAL_MIN, max: GOAL_MAX })}</span>
            </label>
            <textarea
              id="goal"
              value={goal}
              maxLength={GOAL_MAX}
              onChange={(e) => setGoal(e.target.value)}
              aria-invalid={(show && Boolean(errors.goal)) || undefined}
              aria-describedby="goal-hint"
              rows={4}
              placeholder={t("placeholder")}
              className={cn(
                "mt-1.5 block w-full resize-none rounded-field border bg-surface px-3.5 py-3 text-[15px] leading-[22.5px] text-ink outline-none placeholder:text-faint focus:border-brand focus:shadow-focus",
                show && errors.goal ? "border-danger" : "border-line",
              )}
            />
            <div id="goal-hint" className="flex justify-between gap-3 pt-1.5 text-xs">
              <p className={show && errors.goal ? "text-danger" : "text-muted"}>
                {show && errors.goal ? errors.goal : t("example")}
              </p>
              <p className="shrink-0 font-mono text-muted">
                {trimmed.length} / {GOAL_MAX}
              </p>
            </div>
          </div>

          <SectionLabel className="pt-7">{t("links")}</SectionLabel>
          <p className="pt-1.5 text-xs text-muted">{t("linksHint")}</p>
          <Row className="pt-3.5">
            {LINKS.map((l) => (
              <Field key={l.kind} label={t(l.kind)}>
                {(p) => <Input {...p} type="url" inputMode="url" value={links[l.kind]} onChange={(e) => setLinks((s) => ({ ...s, [l.kind]: e.target.value }))} placeholder={l.placeholder} />}
              </Field>
            ))}
          </Row>
        </>
      )}
    </StepFrame>
  );
}
