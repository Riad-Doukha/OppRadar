## What & why

<!-- One or two sentences. What does this PR do, and why? -->

Closes #<!-- issue number -->

## Type of change

- [ ] Feature (ingestion / matching / chat / UI)
- [ ] Fix
- [ ] Docs
- [ ] Refactor / chore (no behaviour change)
- [ ] Shared-file change (`schemas.py` / `llm.py`) — needs **both** AI owners' approval

## How to test

<!-- Commands, steps, or "n/a". -->

```
cd ai && pytest
```

## Checklist

- [ ] `pytest` passes locally (AI/backend changes)
- [ ] `npm run typecheck` passes (frontend changes)
- [ ] No secrets, CVs (`*.pdf`), or `data/private/` files committed
- [ ] New code has tests; public functions validate against `schemas.py`
- [ ] Docs updated (`README.md`, `docs/ai-design.md`, …) if behaviour changed
- [ ] PR targets **`develop`**, not `main`
