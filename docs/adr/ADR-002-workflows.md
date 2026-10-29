# ADR-002 - Workflows, question loop and tools

Status: accepted
Date: 2026-10-29

## Context
Cairn has two kinds of model work.
A free question needs the model to pick tools in an open-ended order; a workflow (the nonclinical summary, the data-quality memo) is a fixed sequence with people's pauses and checks between steps.
The tools themselves (study queries, guidance search) must be reusable from the web app, REST and MCP clients.

## Decision
- Workflows use LangGraph: a graph of named steps with state, pauses for human decisions, and a checkpoint per step.
  The checkpointer is in memory by default (`CAIRN_THREADS_DB=":memory:"`), so a restart loses the open pauses; with `CAIRN_THREADS_DB` set to a file they survive in SQLite.
  Each workflow is a YAML file in `workflows/` loaded into the `Workflow` model, so a second workflow is configuration, not code.
- Questions use a simple loop in `src/cairn/loop.py`: call the model, run the tool it picks, verify, repeat up to `MAX_CALLS`.
  A framework adds nothing here, and the loop keeps the 45 second timeout, `max_retries=0` and the verifier in plain sight.
- Tools are plain Python functions with no framework, exposed through MCP (and a thin REST route) from the same definitions.

## Consequences
- LangGraph is one dependency, used only by workflows; replacing it touches the workflow runner and nothing else.
- The loop is easy to read and test but has no built-in persistence or branching; if questions ever need pauses, they become a workflow.
- Adding a workflow means a YAML file, a prompt and eval cases; the graph, the checks and the web pages need no change.
  Recording its draft still needs a small command in `src/cairn/cli.py` (`record-memo` is coded there).
