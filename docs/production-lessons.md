# Production lessons

Selected operational lessons from running the pipeline — the expensive kind.

## Shadow → active, always gated

Every model or guardrail change ships in **shadow** first and is measured on a
real population before promotion. Promotions are reversible in one step (env
flag + restart). Acceptance thresholds are written and committed **before**
the evaluation page is opened — per-stratum thresholds and stop-rules such as
"any false admission on an own product reverts the whole package". A review
you can anchor is a review you can fool.

## Config drift made impossible, not monitored

A brand-token list feeding a guardrail had silently diverged from its
source-of-truth DB table — worth **~775 boxes/month** of avoidable Unknowns.
The fix was not a sync check but **generation**: the config file is built from
the table, so drift is impossible by construction. A CI check merely guards
against hand-edits of the generated file.

Corollary applied during rollout: admission from the recovered tokens was
gated to **brand level only** — an eyes-on replay showed the visual matcher
picking the wrong SKU inside the right brand in 28/30 cases.

## A safety check must be independent of the decision it guards

An earlier gate selected candidates with the same token check its verify step
used as a safety net — promotions passed verification *by construction*, and
40% of them were wrong. The gate was rolled back the same day. Since then:
a guard that shares its signal with the decision is treated as an echo, not
a safety layer.
