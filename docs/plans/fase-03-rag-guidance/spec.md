# Phase 03 - RAG over public guidelines: specification

Status: draft
Approved by the user: -
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
- Guideline library: the 4 public guidelines named in the PRD (ICH M4S(R2), ICH M3(R2), ICH S9 and the 2005 FDA guidance on the maximum safe starting dose in first-in-human trials), fetched from their official URLs with SHA-256 pinned in a versioned manifest, following the phase 01 `fetch.py` pin-or-verify pattern; whether the PDFs are committed or fetched and verified is decision O2.
- Text per page with pypdfium2; passages by section and, above about 300 words, by paragraph, each with `page_start`, `page_end` and a readable stable ID (`M4S-2.6.6.3-02`, sentences `.s1`, `.s2`...); the `Passage` contract of the PRD (`passage_id`, `doc`, `section`, `page_start`, `page_end`, `text`, `sentences[{sentence_id, text}]`).
- A build-time verbatim test: every sentence of the index is found literally (after a fixed, documented whitespace normalisation) in the text of its page.
- Hybrid retrieval: BM25 and local bge-small-en-v1.5 embeddings searched in parallel, fused by RRF (k = 60); the top 20 reranked by local bge-reranker-v2-m3; abstention when the best reranker score is below a fixed threshold (never on the RRF score).
- Fixed queries (the two `nonclinical-summary` guidance queries and the G1-G3 queries) precomputed at build time, reranker included, and stored with the index.
- `search_guidance(query)` in `cairn.tools.REGISTRY`, served over MCP, REST and the CLI with the same result hash, returning the top 5 passages with their scores and lexical, semantic and fused ranks, or an explicit abstention.
- `QuoteRef(passage_id, sentence_ids)` as a new content part; the renderer copies the stored sentence text verbatim and adds guideline, section and page; the model never writes quotation text.
- Rule 8 in the verifier, after rules 1-7; rule 1 accepts a `QuoteRef` as a reference and rule 2 resolves it.
- The E2 fixture "citation to a passage not retrieved" (moved here by 02a decision D4).
- E3 on the question loop over the recorded Q1-Q8 and G1-G3; E4 on retrieval and quotations.
- The question loop gains `search_guidance` and `QuoteRef`; recordings of Q1, Q3, Q4, Q5, Q7, Q8 and G1-G3 (and Q2 and Q6 again if the prompt or tool schema change makes them stale) through the existing gateway and `make record`, Bedrock in eu-west-1 only, under a spend ceiling (decision O5).
- Explore page with the recorded questions as buttons (replay only; the live box with access code is phase 06).
- Highlighted page images: the cited PDF page rendered with pypdfium2 with the quoted sentence highlighted over its character boxes, generated at build time for the fixed queries, plus the official link with `#page=N`.
- Step 3 of the walkthrough, built to the approved phase 02c step 3 mockup.
- Offline operation: `make demo` and CI run with no network; how model weights, PDFs and the index reach CI and the image is decision O1/O2.

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
- E3, agent behaviour: on the recorded Q1-Q8 and G1-G3, the loop launches `run_job` first, uses the expected tools and arguments, and Q6, Q7 and Q8 are refused or blocked (Q6 as accepted in 02b deviation D3; Q7 declined as clinical advice; Q8 rejected by the tool schema); pass or fail, 100% required. W1 and W2 follow fixed plans and are covered by E1, E2 and E6, not E3.
- E4, retrieval and quotations: about 25 in-library questions with hand-labelled reference passages (guideline, page and anchor sentence) and 5 out-of-library questions; recall@5 and MRR reported with and without the reranker; required recall@5 >= 0.9 (with the reranker), quotation verbatim rate 100% and abstention on all 5 out-of-library questions.
- Expected answers: G1 a verbatim ICH M4S(R2) passage on section 2.6.6.3 with its page; G2 the verbatim NOAEL definition from the 2005 FDA guidance with its page; G3 a verbatim ICH S9 passage within its scope, with no dose computed.
- Step 3: "Guidance, retrieved and quoted", about 30 seconds of the tour: the two fixed workflow queries with their top 3 passages (guideline, section, page) and lexical, semantic and fused ranks, the rest folded; a badge saying the results were computed at build; each quotation clickable to its highlighted page plus the official link; a line "Quotes: N · verbatim on the cited page: N/N".

## Acceptance criteria
Frozen on approval. Changing them requires a deviation approved by the user.
Numbering starts at C1 for this phase. Part: **now** = built before 02c is merged; **gated** = built only after 02c is in `main` and its step 3 mockup is approved.

| ID | Part | Observable criterion | How it is checked |
|---|---|---|---|
| C1 | now | From a clean clone, `uv sync` and `npm run check` pass: ruff, strict mypy, pytest with line coverage of at least 85% on `src/cairn`, and the hook suite, with no network (weights, PDFs and index obtained per decision O1/O2) | Run the commands on a fresh clone; CI green on the PR |
| C2 | now | The 4 guidelines have their source URL, SHA-256, licence or redistribution note and retrieval date in a versioned manifest; fetching a file whose hash differs fails with a checksum error | pytest `test_guidelines_manifest_*` and `test_guideline_checksum_mismatch` |
| C3 | now | Every passage has a readable stable ID, guideline, section, `page_start` and `page_end`, and no passage exceeds the chunk word limit; rebuilding gives byte-identical passages | pytest `test_passages_*`, including a rebuild hash equality test |
| C4 | now | Build-time verbatim test: every sentence of every passage is found literally on its page text (fixed whitespace normalisation only); a planted altered sentence fails it | pytest `test_index_sentences_verbatim` plus its failing fixture |
| C5 | now | Retrieval is BM25 plus bge-small-en-v1.5 fused by RRF with k = 60, then bge-reranker-v2-m3 over the top 20; results are deterministic (same query, same ranks and scores to a fixed tolerance) and run with no network | pytest `test_retrieval_*` with sockets blocked |
| C6 | now | Abstention: when the best reranker score is below the threshold, `search_guidance` returns no passage and an explicit "no supporting passage in the library" result, and the answer contains no quotation; the threshold value and its calibration set (disjoint from E4) are versioned | pytest `test_search_guidance_abstains_*`; inspection of the calibration file |
| C7 | now | `search_guidance` is in the registry and returns the same result hash over MCP, REST and the CLI | pytest `test_registry_same_hash_search_guidance` |
| C8 | now | `QuoteRef` renders the stored sentences verbatim with guideline, section and page placed by code; model text never carries quotation text, and a model `Text` containing a stored sentence is not counted as a quotation | pytest `test_renderer_quoteref_*` |
| C9 | now | Rule 8 has a passing and a failing fixture (passage not retrieved in the run; text differing from the stored text); rules 1 and 2 accept and resolve `QuoteRef`; the E2 fixture "citation to a passage not retrieved" is blocked by rule 8; rules 1-7 fixtures still pass | pytest `test_rule_8_*`, `tests/evals/test_e2.py` |
| C10 | now | E4 passes in CI with no network: recall@5 >= 0.9 with the reranker over about 25 labelled questions, quotation verbatim rate 100%, abstention on all 5 out-of-library questions; recall@5 and MRR with and without the reranker are reported | pytest `tests/evals/test_e4.py` in the `evals` check |
| C11 | now | Recordings for Q1, Q3, Q4, Q5, Q7, Q8, G1, G2 and G3 (and Q2, Q6 re-recorded if stale) exist in git, each from Bedrock in eu-west-1 with model, region, date, latency, tokens and cost; total recording spend stays under the ceiling of decision O5 | pytest `test_recordings_metadata_*` and `test_recordings_present_*`; `make record` cost output |
| C12 | now | E3 passes at 100% in replay with no network: `run_job` first where the loop applies, expected tools and arguments per question, Q6-Q8 refused or blocked as defined, G1-G3 answered with `QuoteRef` to the expected guideline and no digit in model text | pytest `tests/evals/test_e3.py` in the `evals` check |
| C13 | now | Highlighted page images for every quotation of the fixed queries and of G1-G3 are generated at build with pypdfium2, the highlight boxes cover exactly the quoted sentence's characters, and each quotation carries the official link with `#page=N` | pytest `test_highlight_*` over the generated images' box metadata |
| C14 | gated | Explore page lists Q1-Q8 and G1-G3 as buttons; each replays offline to its rendered, verified answer with its RECORDED badge, and each quotation opens its highlighted page | pytest `test_explore_*`; browser walkthrough |
| C15 | gated | Step 3 in a browser at 1440x900 with the network disabled, built to the approved 02c step 3 mockup: the two fixed queries with top 3 passages and lexical, semantic and fused ranks, the rest folded, the "computed at build" badge, each quotation opening its highlighted page plus the official link, "Quotes: N · verbatim on the cited page: N/N", an "In production ->" line, no scroll and within the word cap (visible page, not only the template) | Walkthrough with screenshots in `evidence/`; `test_word_cap` extended to step 3 |
| C16 | gated | `make demo` serves step 3 and Explore from a clean clone with the network disabled, and the deployed HTTPS URL serves the same with `/healthz` 200 | `make demo-offline-check` extended to step 3; curl on the URL |
| C17 | now | No company name, logo or colour from the PRD, no third-party person's name and no AWS account ID appear in the repo or the app, and no GxP validation claim is added | Local grep of the PRD terms and 12-digit literals over tracked files, the diff and commit messages before every push |

## Constraints and risks
- Phase 03 officially depends on 02c; only the gated criteria wait for it. If the 02c step 3 mockup asks for data the "now" part does not produce, a deviation is raised before building step 3.
- Memory: bge-reranker-v2-m3 is an XLM-RoBERTa-large-class model (about 568M parameters, unverified here); in FP32 its weights alone are about 2.2 GB (unverified), more than the 2 GB RAM of the Lightsail medium power in use. Only the fixed queries need the reranker at runtime in this phase if all recorded answers are precomputed at build; the live box (phase 06) would rerank at request time. See decision O1.
- Image size and build time grow with the weights (embedding model about 130 MB in ONNX, reranker about 0.6-2.2 GB depending on quantisation; unverified).
- The weights must reach CI and the image without network at test time: either downloaded at build with a pinned revision and SHA-256 and cached, or vendored; both need decision O1.
- Licences (to verify before approval; not checked against primary sources in this draft): bge-small-en-v1.5 MIT, bge-reranker-v2-m3 Apache-2.0, fastembed Apache-2.0, bm25s MIT, sentence-transformers Apache-2.0, PyTorch BSD-3-Clause, pypdfium2 Apache-2.0 or BSD-3-Clause, onnxruntime MIT.
- Guideline redistribution (unverified): FDA guidance documents are US federal government works, generally public domain; ICH guidelines are published by ICH with a copyright notice that allows reproduction with acknowledgement, whose exact terms must be read before committing the PDFs. See decision O2.
- The official URLs of ICH documents have changed in the past; pinned SHA-256 makes a changed PDF fail loudly, and the ICH version may have been updated (M4S(R2) and M3(R2) are current names, S9 has a Q&A addendum that is out of scope).
- Recording costs money and needs the user's AWS go-ahead; G-questions add retrieved passages to the prompt, so input tokens grow. Changing the loop prompt or tool schema makes Q2 and Q6 stale, forcing re-recording.
- Abstention threshold: a threshold calibrated on E4 questions would overfit; the calibration set must be separate (PRD).
- The 5.5 models remain unavailable for the account (02b deviation D2); recordings use Opus 4.6 with Sonnet 4.6 as fallback unless the user decides otherwise.
- No edits under `src/cairn/web/` before the gate; the "now" part exposes everything through the registry, CLI and tests.

## Assumptions
- The 4 guidelines are the ones named by the PRD, in their current official versions at fetch time.
- Precomputed fixed-query results are stored in the repo or built into the image and checked by a test that re-runs retrieval and compares.
- The question loop keeps its cap of 6 calls, with `search_guidance` and a `QuoteRef`-capable `write_answer` added; the prompt version is bumped.
- The highlighted pages for the fixed queries are generated at build; on-the-fly generation is only for the live box of phase 06.

## Open decisions
Questions the user must resolve before approving. Empty on approval.

| ID | Question | Options | Recommendation |
|---|---|---|---|
| O1 | Libraries and model weights for embeddings and reranker | A: as in the PRD, `bm25s` + `fastembed` (ONNX, CPU, no PyTorch) for bge-small-en-v1.5, and a published ONNX export of bge-reranker-v2-m3 run with `onnxruntime`, quantised int8 if available; weights downloaded at image build and in CI with pinned revision and SHA-256, cached (CI cache and a Docker layer), tests run offline after the cache step. B: `sentence-transformers` with CPU-only PyTorch (several hundred MB more in the image, larger memory, simpler API). C: vendor the weights in git (LFS), heavy repo. Lightsail medium (2 GB) may need the large power (about 80 USD per month vs 40, unverified) if the reranker runs at request time | A, quantised reranker, reranker used only at build in this phase so medium power suffices; revisit the power in phase 06 with the live box |
| O2 | Guideline PDFs: committed or fetched | A: commit the FDA PDF (public domain) and the ICH PDFs only if the ICH notice allows redistribution, else fetch-and-verify at build; B: fetch-and-verify all 4 at build and in CI (network at build, cached); C: commit all 4 | A after reading the ICH terms; B if the terms are unclear |
| O3 | Which 4 guidelines | The PRD fixes them: ICH M4S(R2), ICH M3(R2), ICH S9, FDA 2005 maximum safe starting dose guidance; alternative: swap S9 for another guideline | Keep the PRD set |
| O4 | Reranker threshold calibration | A: a separate set of about 10 in-library and 10 out-of-library questions, threshold = midpoint between the lowest in-library best score and the highest out-of-library best score, versioned with the set; B: a fixed value from the model card; C: tune on E4 | A |
| O5 | Bedrock spend for the recordings | About 11 questions, up to 6 calls each, Opus 4.6 at 5 / 25 USD per million tokens; estimated under 2 USD for one pass (02b spent about 0.79 USD on Q2 and Q6 with retries); options: A: ceiling 5 USD, agent runs `make record` with the `default` profile as in 02b U2; B: ceiling 10 USD; C: user runs it | A |
| O6 | Recording model | A: Opus 4.6, Sonnet 4.6 fallback, as 02b D2; B: wait for 5.5 access | A |
