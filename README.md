# Cairn

A traceable agentic demo for drug safety science.
It takes a public toxicology study (SEND, PhUSE PDS2014, fictitious compound) to a draft nonclinical summary in the style of CTD 2.6.6.3.
The model picks tools and drafts text; code places every number and every verbatim quotation, and scientific decisions are made by a person and audited.

Public sample data · fictitious compound · not GxP-validated.

## Status

Steps 1, 2 and 3 of the web demo and Explore work, and the question loop runs against recorded Bedrock answers.
Step 3 searches four public guidelines (hybrid index with a reranker) and quotes them verbatim with a highlighted page.
The master plan is in [docs/plans/0_plan_maestro.md](docs/plans/0_plan_maestro.md).

## Step 2 and the laptop commands

The web app never calls a model: step 2 only replays the recordings in `recordings/`.
Three commands reach Bedrock and run on a laptop only:
- `make record AWS_PROFILE=<profile>` records the questions again into `recordings/`.
- `make live AWS_PROFILE=<profile> QUESTION=Q2` asks one question to the live model.
- `make smoke AWS_PROFILE=<profile>` checks the model profiles and writes the smoke evidence.

All three need `AWS_PROFILE`, spend money, and print their estimated spending ceiling before the first call.

## Guidance retrieval commands

A clean clone needs the model weights before `npm run check` (the retrieval tests fail with "weights missing" otherwise):
- `make weights` downloads the pinned weights into `CAIRN_MODELS` and verifies every SHA-256.
- `make guidance` rebuilds the generated guidance files from the pinned guideline PDFs.
- `make guidance-check` compares the committed retrieval cache with a fresh retrieval.

## How we work

The project is developed with SDD Lite; the guide (in Spanish) is in [docs/como-trabajar.md](docs/como-trabajar.md).
