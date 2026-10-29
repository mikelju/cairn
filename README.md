# Cairn

A traceable agentic demo for drug safety science.
It takes a public toxicology study (SEND, PhUSE PDS2014, fictitious compound) to a draft nonclinical summary in the style of CTD 2.6.6.3.
The model picks tools and drafts text; code places every number and every verbatim quotation, and scientific decisions are made by a person and audited.

Public sample data - fictitious compound - not GxP-validated.

Video walkthrough: VIDEO_URL (pending, recorded after the merge).

## Commands
- `make demo` builds the image and serves the app on `http://127.0.0.1:8000`; it runs offline and replays the recordings in `recordings/`.
- `make live AWS_PROFILE=<profile> QUESTION=Q2` asks one question to the live model (laptop only; spends money and prints its ceiling first).
- `make record AWS_PROFILE=<profile>` records the questions again; `record-draft`, `record-memo` and `record-judge` do the same for the nonclinical-summary draft, the data-quality memo and the judge.
- `make deploy` pushes the image to one Lightsail container service; see [docs/production.md](docs/production.md).
- `make changelog` regenerates `CHANGELOG.md` from the merged PR titles.
- `make smoke`, `make weights`, `make guidance` and `make guidance-check` cover the model profiles and the guidance index (a clean clone needs `make weights` before `npm run check`).

## More
- [docs/production.md](docs/production.md): what production would need.
- [docs/adr/](docs/adr/): decisions (Bedrock profiles, workflows).
- [docs/como-trabajar.md](docs/como-trabajar.md): how the project is developed with SDD Lite (in Spanish).
