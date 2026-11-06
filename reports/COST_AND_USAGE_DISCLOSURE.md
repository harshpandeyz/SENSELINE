# COST_AND_USAGE_DISCLOSURE ($0 additional spend)

Restriction honored: **$0 additional API expenditure.** No paid model call was made in any
phase (pilot, full, supplementary, probes). No paid credential was configured in any trial
environment.

## Six-way accounting

| Item | Value | Source |
|---|---|---|
| Configured budget | $0 total cap; $0 per-trial cap; $0 input/output rates (all three configs) | `configs/experiment_matrix.json` spend_control + budgets |
| Provider pricing metadata | ollama/*: local, no price. `openrouter/…:free`: prompt $0 / completion $0 (`/api/v1/models`, read-only). opencode/*-free: $0 free-tier (agent-reported cost 0) | `results/free_model_availability.json` |
| Free-tier quota | OpenRouter: 50 requests/day (verified `/api/v1/auth/key`); exhausted 2026-11-05 and 2026-11-06, resets 00:00 UTC. opencode pool: ~2–4 requests before `free-limit` 429 (observed; reset window ~5.5 h) | quota probes + trial logs |
| Trial-level estimated cost | $0.00 for all 91 trials (usage.tokens × $0 rates) | `trial_index.json` → `usage.estimated_cost_usd: "0"` |
| Provider-reported usage | Tokens per trial recorded (e.g., 136750 qwen / 76163 llama / 268054 nemotron-full). OpenRouter account usage counter moved +$0.0008 across all free-tier probing (4.9868 → 4.9876 → 4.9884 of $5 prepaid; usage now ~$5.02, so paid calls fail closed with 402) | transcripts + account endpoint (read-only) |
| Confirmed billed charges | **None confirmed, none expected.** No billing record was pulled (owner-only). The $0.0008 counter delta on $0-priced models is disclosed, not billed. | — |

## Enforcement

- Paid paths in `scripts/run_experiment.py` require positive caps, per-trial caps, token budgets, model-specific rates, named credentials present in the environment, AND a provider-side hard limit with evidence. None were satisfiable under $0, so paid execution was structurally impossible, not merely declined.
- Zero-cost tier changed only the monetary zeros to exact-zero with evidence strings; token budgets, usage reporting, wall timeouts, and fail-closed sandboxing still apply.
- Provider hard-spend-limit evidence was not obtainable (OpenRouter: no limit set on a non-management key; NVIDIA/Meta: no verifiable balance/limit endpoint), so paid models were excluded. This is not claimed as enforced.

## Remaining owner-side verification

1. Confirm via the OpenRouter billing page that no charge corresponds to the +$0.0008 usage-counter delta.
2. If paid evaluation is ever authorized: set an explicit cap, a provider-side hard limit with dated evidence, and dedicated credentials — then rerun under the paid path (already implemented, never executed).
