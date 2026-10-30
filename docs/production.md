# What production would need

Cairn is a demo on public data with a fictitious compound.
This is what would change to run it for real; nothing here is built.

## Deployment
- Today: one Lightsail container service (`make deploy`), one instance, no autoscaling, state in the image; threads and their pauses live in memory unless `CAIRN_THREADS_DB` points to a SQLite file, and a restart loses what is in memory.
- `make deploy` passes `CAIRN_ACCESS_CODE` and `CAIRN_LIVE_CAP_USD` to the container only if they are set in the environment (use `$env:` first, never the command line); values may only have letters, digits and hyphens.
- It does not pass AWS credentials: give the container its own IAM user limited to `bedrock:InvokeModel` on the model used, entered in the Lightsail console (not through the CLI or the shell history); production would use a role instead.
- Production: managed database for threads, decisions and the audit chain; at least two instances behind a load balancer; deploy from CI with a rollback.
- Offline mode (`make demo`) stays as the fallback and as the check that the recordings still replay.

## Live question
- Today: a shared access code (`CAIRN_ACCESS_CODE`, compared in constant time, never logged), one live question at a time, and a daily cap on spend (`CAIRN_LIVE_CAP_USD`, 2 USD per UTC day) kept in process memory.
- Production: per-user sign-in instead of a shared code, the cap and the spend ledger in the database (a restart resets the memory counter), per-user rate limits, and the other public endpoints (jobs, tools) behind the same sign-in.

## Secrets
- Today: the code comes from the environment; Bedrock credentials come from an AWS profile on the laptop and are never in the image.
- Production: a secrets manager, rotation, and a task role for Bedrock instead of profiles.

## Cost
- A typical live question costs about 0.07 USD (maximum seen 0.13 USD; code ceiling about 1.21 USD for six calls).
- A 2 USD daily cap allows about 28 typical questions; one question at a time means a day can overshoot by one question, so the hard maximum is about 3.2 USD.
- Recording spend on the laptop is capped per phase and printed before the first call.

## Limits of the demo
- Not GxP-validated: no validation package, no electronic signatures, no retention policy.
- Public SEND sample, one study; the guidance index covers four public guidelines.
- Models are Opus 4.6 and Sonnet 4.6 on Bedrock `eu-west-1` (see ADR-001); recordings are keyed by model and must be redone when it changes.
- The audit chain is tamper-evident, not tamper-proof: it needs external anchoring to be trusted beyond a demo.
