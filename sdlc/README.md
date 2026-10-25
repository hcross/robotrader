# SDLC definitions

This directory holds the **definitions** of the Robotrader delivery workflow.
The per-change runtime ledger lives in `.sdlc/<change-id>/` (dot).

| Path | Purpose |
|---|---|
| [`PROTOCOL.md`](PROTOCOL.md) | Normative workflow: lanes, stages, cold reviews, three-round cap, gates |
| [`agents/`](agents/) | Canonical agent profiles (source of the CLI adapters) |
| [`checklists/`](checklists/) | Reviewer checklists for SPEC, PLAN, DEV |
| [`schemas/`](schemas/) | JSON schemas for review verdicts and change state |
| [`templates/`](templates/) | Issue logbook, PR body, merge dossier, change artifacts |
| [`config.env`](config.env) | Runtime knobs and defaults |

Related:

- Human guide: [`../docs/sdlc/README.md`](../docs/sdlc/README.md)
- Decision record: [`../docs/adr/0004-agentic-sdlc.md`](../docs/adr/0004-agentic-sdlc.md)
- Spec store: [`../openspec/`](../openspec/)
- CLI adapters: [`../.claude/agents/`](../.claude/agents/) and [`../.agent/agents/`](../.agent/agents/)

After editing a profile in `agents/`, run:

```bash
scripts/sdlc/install-agents.sh
scripts/sdlc/install-agents.sh --check
```
