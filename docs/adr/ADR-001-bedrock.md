# ADR-001 - Model provider and profiles: Bedrock in eu-west-1

Status: accepted
Date: 2026-10-22
Evidence: `docs/adr/evidence/bedrock-smoke.json`

## Context
The agentic loop calls the models through Amazon Bedrock in `eu-west-1`, using EU inference profiles only (`eu.` prefix), so that requests stay in EU regions.
Calls use `messages.create`, never streaming, with a 45 second timeout and no automatic retries.
Tools are sent with `strict: true`.

## The gap (deviation D2)
The first plan named Opus 5.5, Sonnet 5.5 and Opus 4.8.
The account cannot use those models yet: they answer 403 "not available for this account" while the rollout reaches it.
Opus 4.6 and Sonnet 4.6 are enabled and answer normally.
The demo therefore uses Opus 4.6 for the question and draft prompts and for recordings, and Sonnet 4.6 as the fallback for a question Opus 4.6 refuses and as the judge model.
Switching back to the newer models is a change to the profile and price tables (`src/cairn/gateway.py`, `src/cairn/pricing.py`) plus re-recording, since a recording is keyed by model.

## Smoke test results
The smoke test sent a question prompt (with the study tools and the answer tool), a draft prompt and a judge prompt (with the verdict tool) to each profile.
The question prompt returns a tool call on both profiles, so strict tool schemas are accepted.
The judge prompt returns the structured verdict through its strict tool on both profiles.

| Model key | Profile | Call | Stop reason | Refusal | Tool called | Latency (s) | Input tokens | Output tokens | Cost (USD) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| opus-4-6 | `eu.anthropic.claude-opus-4-6-v1` | question | tool_use | no | run_job | 24.25 | 1598 | 76 | 0.00989 |
| opus-4-6 | `eu.anthropic.claude-opus-4-6-v1` | draft | end_turn | no | none | 2.61 | 16 | 73 | 0.00191 |
| opus-4-6 | `eu.anthropic.claude-opus-4-6-v1` | judge | tool_use | no | judge_verdict | 3.08 | 623 | 132 | 0.00642 |
| sonnet-4-6 | `eu.anthropic.claude-sonnet-4-6` | question | tool_use | no | run_job | 1.92 | 1598 | 77 | 0.00595 |
| sonnet-4-6 | `eu.anthropic.claude-sonnet-4-6` | draft | end_turn | no | none | 1.58 | 16 | 60 | 0.00095 |
| sonnet-4-6 | `eu.anthropic.claude-sonnet-4-6` | judge | tool_use | no | judge_verdict | 3.03 | 623 | 169 | 0.00440 |

Prices used, in USD per million tokens: Opus 4.6 input 5 and output 25; Sonnet 4.6 input 3 and output 15.
The smoke test cost 0.0295 USD in this run; an earlier run that failed on a schema error cost 0.0135 USD for its four successful calls.

## Findings
- Refusals: none. All six calls ended with `end_turn` or `tool_use`.
- Strict tools and structured output: accepted by both profiles once the answer tool schema carried its `$defs` at the schema root.
  The first run returned 400 "Reference to non-existent definition" for the answer tool on both profiles; the fix is in `src/cairn/loop.py` and changes the tool schema hash, so fixtures were updated.
- Quota errors: none (no 429 and no throttling in either run).
- Latency: 1.6 to 3.1 seconds per call, except the first Opus 4.6 question call at 24.25 seconds, likely a cold start; the 45 second timeout holds.
- Cost: well under a cent per call; a full question loop is a few cents.

## Decision
Use Bedrock `eu-west-1` with the profiles `eu.anthropic.claude-opus-4-6-v1` (key `opus-4-6`) and `eu.anthropic.claude-sonnet-4-6` (key `sonnet-4-6`).
Opus 4.6 records the questions; Sonnet 4.6 is the refusal fallback and the judge.
Revisit when the account gains access to the newer models.
