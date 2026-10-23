# Phase 03 - RAG over public guidelines: specification

Status: approved (frozen)
Approved by the user: 2026-10-22 (decided by the user's main session under the user's standing rule to take the recommended option)
Master plan: `../0_plan_maestro.md`
Definitions of phases 02a and 02b (rules 1-7, E1, E2, Observation, ValueRef, gateway, recordings) apply here unchanged unless this spec extends them.

## Objective
Leave guideline quotations that code places and checks: a library of 4 public guidelines with pinned SHA-256, a deterministic hybrid index with a local reranker and abstention, a `search_guidance` tool, `QuoteRef`, rule 8, E3 and E4, recorded Explore questions, and step 3 of the walkthrough with each quotation opening its highlighted page.
A visitor sees guidance retrieved, not remembered: every quotation is verbatim, with guideline, section and page, and comes from a passage retrieved in that run; when nothing in the library answers, the demo says so.
It is needed now because the phase 04 NOAEL rule cites the NOAEL definition passage of step 3, and the milestone after phase 03 is a walkthrough up to step 3.

## Dependency handling
The user started this phase on 2026-10-22 in parallel with phase 02c (decision recorded in `plan.md`).
Criteria marked **now** are built first and touch nothing under `src/cairn/web/`.
Criteria marked **gated** (step 3 UI and the highlighted page shown in the app) start only after phase 02c is merged into `main` and its step 3 mockup is approved, with this branch rebased on `main` first.

## Scope
In:
- Guideline library: the 4 public guidelines named in the PRD (ICH M4S(R2), ICH M3(R2), ICH S9 and the 2005 FDA guidance on the maximum safe starting dose in first-in-human trials), fetched from their official URLs with SHA-256 pinned in a versioned manifest, following the phase 01 `fetch.py` pin-or-verify pattern; the 4 PDFs are committed unmodified, with ICH copyright acknowledgement and source in the manifest (decision O2).
- Text per page with pypdfium2; passages by section and, above about 300 words, by paragraph, each with `page_start`, `page_end` and a readable stable ID (`M4S-2.6.6.3-02`, sentences `.s1`, `.s2`...); the `Passage` contract of the PRD (`passage_id`, `doc`, `section`, `page_start`, `page_end`, `text`, `sentences[{sentence_id, text}]`).
- A build-time verbatim test: every sentence of the index is found literally (after a fixed, documented whitespace normalisation) in the text of its page.
- Hybrid retrieval: BM25 and local bge-small-en-v1.5 embeddings searched in parallel, fused by RRF (k = 60); the top 20 reranked by local bge-reranker-v2-m3; abstention when the best reranker score is below a fixed threshold (never on the RRF score).
- A precomputed retrieval cache, reranker included, stored with the index: it covers the fixed queries (the two `nonclinical-summary` guidance queries and the G1-G3 queries) and every `search_guidance` query that appears in a committed recording, so replay (tests, `make demo`, the deployed app) never runs the reranker.
  Replay looks up the precomputed result by exact query string and fails loudly with "stale retrieval cache: rebuild" when it is missing; a test checks that every recorded query has a precomputed result equal to a fresh retrieval at build.
- `search_guidance(query)` in `cairn.tools.REGISTRY`, served over MCP, REST and the CLI with the same result hash, returning the top 5 passages with their scores and lexical, semantic and fused ranks, or an explicit abstention.
- `QuoteRef(passage_id, sentence_ids)` as a new content part; the renderer copies the stored sentence text verbatim and adds guideline, section and page; the model never writes quotation text.
- Rule 8 in the verifier, after rules 1-7; rule 1 accepts a `QuoteRef` as a reference and rule 2 resolves it.
- The E2 fixture "citation to a passage not retrieved" (moved here by 02a decision D4).
- E3 on the question loop over the recorded Q1-Q8 and G1-G3; E4 on retrieval and quotations.
- The question loop gains `search_guidance` and `QuoteRef`; recordings of Q1, Q3, Q4, Q5, Q7, Q8 and G1-G3 (and Q2 and Q6 again if the prompt or tool schema change makes them stale) through the existing gateway and `make record`, Bedrock in eu-west-1 only, under a spend ceiling (decision O5).
- Explore page with the recorded questions as buttons (replay only; the live box with access code is phase 06).
- Highlighted page images: the cited PDF page rendered with pypdfium2 with the quoted sentence highlighted over its character boxes, generated at build time for every quotation of the fixed queries and of the committed recordings, plus the official link with `#page=N`.
- Step 3 of the walkthrough, built to the approved phase 02c step 3 mockup.
- Offline operation: `make demo` and CI run with no network; the PDFs are in git (decision O2) and the model weights are downloaded once with a pinned revision and SHA-256 and cached (CI cache and a Docker layer, decision O1); tests run offline after that step.

Out:
- The live Explore box, access code, daily cap and container IAM key (phase 06).
- `DecisionRef`, the NOAEL rule and the `nonclinical-summary` workflow (phase 04); this phase only provides the passage it cites.
- Judge and E5 (phase 05); similar-question finder and Autoplay (deferred past v0.1.0).
- A managed index (OpenSearch, Bedrock Knowledge Bases), other guidelines, SOPs or internal documents.
- Dose calculation of any kind, including for G3.
- Any change to rules 1-7 beyond accepting `QuoteRef` in rules 1 and 2.

## Definitions taken from the PRD
- Rule 8: every quotation points to sentences of a passage retrieved in that run (returned by a `search_guidance` call of the same run, at or above the threshold), and the rendered quotation text is identical to the stored sentence text; that each stored sentence is literally on its page is checked once, at build time (C4).
  A `QuoteRef` to an unknown passage fails rule 2; a `QuoteRef` to a known passage that was not retrieved in the run, or whose text differs from the stored text, fails rule 8.
- E3, agent behaviour: on the recorded Q1-Q8 and G1-G3, the loop launches `run_job` first, uses the expected tools and arguments, and Q6, Q7 and Q8 are refused or blocked (Q6 as accepted in 02b deviation D3; Q7 declined as clinical advice; Q8 never includes TK animals in the means: either the tool schema rejects it or the model declines and explains why, user-approved change D109); pass or fail, 100% required. W1 and W2 follow fixed plans and are covered by E1, E2 and E6, not E3.
- E4, retrieval and quotations: about 25 in-library questions with hand-labelled reference passages (guideline, page and anchor sentence) and 5 out-of-library questions; recall@5 and MRR reported with and without the reranker; required recall@5 >= 0.9 (with the reranker), quotation verbatim rate 100% and abstention on all 5 out-of-library questions.
- Expected answers: G1 a verbatim ICH M4S(R2) passage on section 2.6.6.3 with its page; G2 the verbatim NOAEL definition from the 2005 FDA guidance with its page; G3 a verbatim ICH S9 passage within its scope, with no dose computed.
- Step 3: "Guidance, retrieved and quoted", about 30 seconds of the tour: the two fixed workflow queries with their top 3 passages (guideline, section, page) and lexical, semantic and fused ranks, the rest folded; a badge saying the results were computed at build; each quotation clickable to its highlighted page plus the official link; a line "Quotes: N · verbatim on the cited page: N/N".

## Acceptance criteria
Frozen on approval. Changing them requires a deviation approved by the user.
Numbering starts at C1 for this phase. Part: **now** = built before 02c is merged; **gated** = built only after 02c is in `main` and its step 3 mockup is approved.

| ID | Part | Observable criterion | How it is checked |
|---|---|---|---|
| C1 | now | From a clean clone, `uv sync` and `npm run check` pass: ruff, strict mypy, pytest with line coverage of at least 85% on `src/cairn`, and the hook suite, with no network after the one-time pinned weights download (cached in CI; decision O1) | Run the commands on a fresh clone; CI green on the PR |
| C2 | now | The 4 guidelines have their source URL, SHA-256, licence or redistribution note and retrieval date in a versioned manifest; fetching a file whose hash differs fails with a checksum error | pytest `test_guidelines_manifest_*` and `test_guideline_checksum_mismatch` |
| C3 | now | Every passage has a readable stable ID, guideline, section, `page_start` and `page_end`, and no passage exceeds the chunk word limit; rebuilding gives byte-identical passages | pytest `test_passages_*`, including a rebuild hash equality test |
| C4 | now | Build-time verbatim test: every sentence of every passage is found literally on its page text (fixed whitespace normalisation only); a planted altered sentence fails it | pytest `test_index_sentences_verbatim` plus its failing fixture |
| C5 | now | Retrieval is BM25 plus bge-small-en-v1.5 fused by RRF with k = 60, then bge-reranker-v2-m3 over the top 20; results are deterministic (same query, same ranks and scores to a fixed tolerance) and run with no network; the precomputed cache covers the fixed queries and every `search_guidance` query in a committed recording, each equal to a fresh retrieval at build; replay looks results up by exact query, fails with "stale retrieval cache: rebuild" when one is missing and never loads the reranker | pytest `test_retrieval_*` with sockets blocked, `test_retrieval_cache_*` (coverage of recorded queries, equality with a fresh retrieval, stale error, reranker not loaded in replay) |
| C6 | now | Abstention: when the best reranker score is below the threshold, `search_guidance` returns no passage and an explicit "no supporting passage in the library" result, and the answer contains no quotation; the threshold value and its calibration set (about 10 in-library and 10 out-of-library questions, disjoint from E4; threshold = midpoint between the lowest in-library and the highest out-of-library best score, decision O4) are versioned | pytest `test_search_guidance_abstains_*`; inspection of the calibration file |
| C7 | now | `search_guidance` is in the registry and returns the same result hash over MCP, REST and the CLI | pytest `test_registry_same_hash_search_guidance` |
| C8 | now | `QuoteRef` renders the stored sentences verbatim with guideline, section and page placed by code; model text never carries quotation text, and a model `Text` containing a stored sentence is not counted as a quotation | pytest `test_renderer_quoteref_*` |
| C9 | now | Rule 8 has a passing and a failing fixture (passage not retrieved in the run; text differing from the stored text); rules 1 and 2 accept and resolve `QuoteRef`; the E2 fixture "citation to a passage not retrieved" is blocked by rule 8; rules 1-7 fixtures still pass | pytest `test_rule_8_*`, `tests/evals/test_e2.py` |
| C10 | now | E4 passes in CI with no network: recall@5 >= 0.9 with the reranker over about 25 labelled questions, quotation verbatim rate 100%, abstention on all 5 out-of-library questions; recall@5 and MRR with and without the reranker are reported | pytest `tests/evals/test_e4.py` in the `evals` check |
| C11 | now | Recordings for Q1, Q3, Q4, Q5, Q7, Q8, G1, G2 and G3 (and Q2, Q6 re-recorded if stale) exist in git, each from Bedrock in eu-west-1 with model, region, date, latency, tokens and cost; total recording spend for this phase stays under 5 USD (decision O5) | pytest `test_recordings_metadata_*` and `test_recordings_present_*`; `make record` cost output |
| C12 | now | E3 passes at 100% in replay with no network: `run_job` first where the loop applies, expected tools and arguments per question, Q6 and Q7 refused or blocked as defined, Q8 never including TK animals in the means (rejected by the schema, or declined with an explanation; approved change D109), G1-G3 answered with `QuoteRef` to the expected guideline and no digit in model text | pytest `tests/evals/test_e3.py` in the `evals` check |
| C13 | now | Highlighted page images for every quotation of the fixed queries and of every committed recording (G1-G3 included) are generated at build with pypdfium2, the highlight boxes cover exactly the quoted sentence's characters, and each quotation carries the official link with `#page=N` | pytest `test_highlight_*` over the generated images' box metadata |
| C14 | gated | Explore page lists Q1-Q8 and G1-G3 as buttons; each replays offline to its rendered, verified answer with its RECORDED badge, and each quotation opens its highlighted page | pytest `test_explore_*`; browser walkthrough |
| C15 | gated | Step 3 in a browser at 1440x900 with the network disabled, built to the approved 02c step 3 mockup: the two fixed queries with top 3 passages and lexical, semantic and fused ranks, the rest folded, the "computed at build" badge, each quotation opening its highlighted page plus the official link, "Quotes: N · verbatim on the cited page: N/N", an "In production ->" line, no scroll and within the word cap (visible page, not only the template) | Walkthrough with screenshots in `evidence/`; `test_word_cap` extended to step 3 |
| C16 | gated | `make demo` serves step 3 and Explore from a clean clone with the network disabled, and the deployed HTTPS URL serves the same with `/healthz` 200 | `make demo-offline-check` extended to step 3; curl on the URL |
| C17 | now | No company name, logo or colour from the PRD, no third-party person's name and no AWS account ID appear in the repo or the app, and no GxP validation claim is added | Local grep of the PRD terms and 12-digit literals over tracked files, the diff and commit messages before every push |

Note: the Q8 wording in C12 and in the E3 definition was changed on the user's approval (D109 in the plan); the original wording was "Q8 rejected by the tool schema".

## Constraints and risks
- Phase 03 officially depends on 02c; only the gated criteria wait for it. If the 02c step 3 mockup asks for data the "now" part does not produce, a deviation is raised before building step 3.
- Memory: bge-reranker-v2-m3 has 567,755,777 parameters; its FP32 weights are 2.27 GB, more than the 2 GB RAM of the Lightsail medium power in use.
  fastembed supports `TextCrossEncoder("BAAI/bge-reranker-v2-m3-int8")` directly (onnx-community `onnx/model_int8.onnx`, 0.57 GB; fp16 is 1.14 GB), so no separate raw onnxruntime path is needed.
  CPU latency and peak RAM are not measured: the estimate is a peak of 0.9-1.3 GB and tens of seconds per query for 20 passages on 1 vCPU (estimate, not measurement).
  The abstention threshold must be calibrated on the same int8 variant that runs.
  In this phase the reranker runs only at build and when recording; replay reads the precomputed cache; the live box (phase 06) would rerank at request time (decision O1).
- Image size and build time grow with the weights: bge-small-en-v1.5 in fastembed is `Qdrant/bge-small-en-v1.5-onnx-Q`, 66 MB; the reranker is 0.57 GB in int8.
  Install footprint on Linux with Python 3.12, weights excluded: option A (bm25s + fastembed + onnxruntime) about 177 MB; option B (sentence-transformers + CPU torch) about 980 MB.
- Lightsail container service (Cairn uses medium in eu-west-1): medium 1 vCPU, 2 GB, 40 USD per month; large 2 vCPU, 4 GB, 80 USD per month (https://aws.amazon.com/lightsail/pricing/).
- The weights must reach CI and the image without network at test time: they are downloaded at build with a pinned revision and SHA-256 and cached (decision O1).
- Licences, all Apache-2.0 compatible: bge-small-en-v1.5 MIT; `Qdrant/bge-small-en-v1.5-onnx-Q` MIT; bge-reranker-v2-m3 Apache-2.0; its ONNX export used by fastembed (`onnx-community/bge-reranker-v2-m3-ONNX`) has no licence field and inherits Apache-2.0 from its base (inferred); fastembed 0.9.0 Apache-2.0; bm25s MIT; onnxruntime MIT; sentence-transformers Apache-2.0; PyTorch BSD-3-Clause with bundled Apache-2.0, MIT and BSL-1.0 components.
  pypdfium2 BSD-3-Clause / Apache-2.0 (verified on PyPI).
- Guideline redistribution: the 3 ICH PDFs carry no notice of their own; ICH's standard legal notice, seen in newer ICH PDFs such as S5(R3), allows use, reproduction and distribution with ICH copyright acknowledged, changes labelled, no implied endorsement and the ICH logo excluded.
  FDA site content is public domain (https://www.fda.gov/about-fda/about-website/website-policies).
  The 4 PDFs total about 2.1 MB and are committed (decision O2).
- Official URLs (HEAD 200, `application/pdf`): ICH M3(R2) https://database.ich.org/sites/default/files/M3_R2__Guideline.pdf; ICH S9 https://database.ich.org/sites/default/files/S9_Guideline.pdf; ICH M4S(R2) https://database.ich.org/sites/default/files/M4S_R2_Guideline.pdf (single underscore); FDA 2005 https://www.fda.gov/media/72309/download (needs a browser-like User-Agent).
  Hashes are pinned at implementation, not in this spec.
- The official URLs of ICH documents have changed in the past; pinned SHA-256 makes a changed PDF fail loudly, and the ICH version may have been updated (M4S(R2) and M3(R2) are current names, S9 has a Q&A addendum that is out of scope).
- Recording costs money and needs the user's AWS go-ahead; G-questions add retrieved passages to the prompt, so input tokens grow. Changing the loop prompt or tool schema makes Q2 and Q6 stale, forcing re-recording.
- Abstention threshold: a threshold calibrated on E4 questions would overfit; the calibration set must be separate (PRD).
- The 5.5 models remain unavailable for the account (02b deviation D2); recordings use Opus 4.6 with Sonnet 4.6 as fallback (decision O6).
- No edits under `src/cairn/web/` before the gate; the "now" part exposes everything through the registry, CLI and tests.

## Assumptions
- The 4 guidelines are the ones named by the PRD, in their current official versions at fetch time.
- Precomputed retrieval results (fixed and recorded queries) are stored with the index and checked by a test that re-runs retrieval and compares.
- The question loop keeps its cap of 6 calls, with `search_guidance` and a `QuoteRef`-capable `write_answer` added; the prompt version is bumped.
- The highlighted pages for the fixed queries and the committed recordings are generated at build; on-the-fly generation is only for the live box of phase 06.

## Decisions
Taken on 2026-10-22 by the user's main session under the user's standing rule to decide with the recommended option on the user's behalf; the literal answer is in `plan.md`, User decisions.

| ID | Question | Decision |
|---|---|---|
| O1 | Libraries and model weights for embeddings and reranker | A: `bm25s` + `fastembed` (bge-small-en-v1.5 int8 ONNX, 66 MB; bge-reranker-v2-m3 int8, 0.57 GB, via `TextCrossEncoder`); weights downloaded at image build and in CI with pinned revision and SHA-256 and cached (CI cache and a Docker layer), tests offline after the cache step; the reranker runs only at build and when recording in this phase and replay reads precomputed results, so the medium power (40 USD per month) suffices; latency and RSS benchmarked on 1 and 2 vCPU before phase 06 decides on large (80 USD per month), a smaller top-k or another reranker |
| O2 | Guideline PDFs: committed or fetched | C: commit all 4 unmodified, with ICH copyright acknowledgement and source in the manifest (about 2.1 MB) |
| O3 | Which 4 guidelines | Keep the PRD set: ICH M4S(R2), ICH M3(R2), ICH S9 and the FDA 2005 maximum safe starting dose guidance |
| O4 | Reranker threshold calibration | A: a separate set of about 10 in-library and 10 out-of-library questions; threshold = midpoint between the lowest in-library best score and the highest out-of-library best score, versioned with the set |
| O5 | Bedrock spend for the recordings | A: ceiling 5 USD for the phase; the agent runs `make record` with the `default` AWS profile as in 02b U2; no agent reads or prints AWS secrets or account IDs |
| O6 | Recording model | A: Opus 4.6 with Sonnet 4.6 as fallback, as 02b D2 |

## Open decisions
Questions the user must resolve before approving. Empty on approval.

| ID | Question | Options | Recommendation |
|---|---|---|---|
