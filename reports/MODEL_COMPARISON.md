# MODEL_COMPARISON

Date: 2026-11-06 UTC. All figures pool GENUINE trials only (eligibility in
`results/experiment_analysis.json`). "No eligible executions" is reported as null, never as zero.

## Ranked viable configurations

### 1. `openrouter/nvidia/nemotron-3.5-super-vl:free` via opencode v2.2.5 — EVALUATED

Nemotron holds the substantial genuine full-run coverage (7 trials, 211/216). Qwen3 separately produced two early genuine pilot-history S05 implementations (combined 1/60, one passing case) — pilot-history attempts, not full-run results, and not ranked here.

| Scope | Trials | Cases | Accuracy | SCR | UAR | Notes |
|---|---|---|---|---|---|---|
| Full S01–S03 | 7 | 216 | 211/216 = 0.977 | 0/216 = 0.0 | null (no S06/S08) | Only misses: 5 reason-string vocabulary errors on correctly rejected inputs |
| Pilot S01+S05 | 2 | 62 | 61/62 = 0.984 | 0/62 = 0.0 | null | S01 31/32, S05 30/30 |
| Pilot S08 (genuine) | 1 | 45 | 0/45 = 0.0 | 41/45 = 0.911 | 3/23 = 0.130 | Validity-propagation failures (3 unsafe ACCEPTs) |
| Budget-breach S08 (exploratory) | 1 | 45 | 32/45 = 0.711 | 7/45 = 0.156 | 2/23 = 0.087 | Cut off at 60k/82740 tokens; excluded from primary metrics |

Strengths: exact decoding, affine units, calibration order, Type A/B uncertainty with correlation (S05 60/60 across phases). Decisive weakness: S08 validity propagation — evidence failures do not block ACCEPT. High S08 run variance (0.711 vs 0.0).

### 2/3. `ollama/qwen3:8b`, `ollama/llama3.2:1b` — TOOL-USE BOUNDARY (not ranked by quality)

48 full-run trials: 0 genuine in the full run; pilot-history adds two genuine qwen S05 implementations (combined 1/60, one passing case on `S05-zero-factor`). Zero tool_use events in successful-usage full-run transcripts vs 13 for nemotron; full-run starters never replaced. Verdict: local models cannot reliably operate the edit-only agent loop — a reproducible tool-use boundary, not a measurement-reasoning score; tool-use failures are never presented as reasoning failures.

### Probes (not ranked)

- `ollama/qwen2.5-coder:7b`: 1 S01 probe, usage reported, starter untouched (TOOL_USE).
- `opencode/beam-free`, `opencode/deepseek-v4.1-flash-free`: S01 pilots blocked by the shared opencode free-tier quota (provider.free-limit 429 after ~2–4 requests; INFRA). Pool depth is insufficient for agentic trials (~8 requests each).

## Selection outcome

Nemotron Super-VL Free is the sole qualified configuration for measurement-quality scoring. No second valid configuration exists under the $0 cap today (OpenRouter pool: 0/50 remaining; opencode pool: exhausted; locals: tool-use-bound). A second comparison requires the quota reset (00:00 UTC daily) or funded credits (out of scope).

## Metric definitions (applied identically)

- Functional accuracy = passed cases / evaluated genuine cases.
- SCR = corrupted cases / evaluated genuine cases (wrong/incompatible value claimed valid or ACCEPT; missing-unit-only and schema-only failures excluded).
- UAR = ACCEPT outputs / non-ACCEPT S06+S08 genuine cases.
- pass@3 (any-of-3 perfect trials), pass^3 (all-3 perfect) require ≥3 genuine trials per (model, task); full nemotron S02: 1/1 group → pass@3 = pass^3 = 1/2 over S01+S02 groups.
- Numerical errors are grouped by task/field/unit and never pooled across incompatible dimensions (`numerical_error_by_field_unit` in the JSON).
