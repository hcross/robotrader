# SPEC Review Checklist

> Read after `sdlc/PROTOCOL.md`. Every finding must cite a location and evidence.
> A reviewer that cannot verify an item marks it `UNCLEAR`, not `PASS`.

## 1. Decision surface (human)

- [ ] The Review Card states the outcome in one line a non-author can understand.
- [ ] The Review Card states why now, blast radius, risk, effort, and whether a decision is needed.
- [ ] The Review Card is ≤ 400 words and contains at least one diagram.
- [ ] Estimated read time (words/200 + 0.5 min per diagram) is ≤ 5.0 min.
- [ ] There is no prose wall: bullets, tables, diagrams; paragraphs ≤ 2 sentences.
- [ ] `Non-goals` is present and meaningful (not a restatement of the goals).

## 2. Problem and scope

- [ ] The problem is stated as an observed fact, not a solution in disguise.
- [ ] The scope has a clear boundary: what is in, what is out.
- [ ] The change is right-sized for its lane (M/S/L). Escalate if it is not.
- [ ] No hidden second change is bundled in.

## 3. Capabilities and deltas

- [ ] Every capability named in the proposal has exactly one delta spec file.
- [ ] New vs Modified vs Removed vs Renamed is used correctly.
- [ ] Modified requirements copy the entire existing block, not a fragment.
- [ ] Removed requirements carry a reason and a migration path.
- [ ] Requirement names and scenario names are unique and stable.

## 4. Requirement quality

- [ ] Every requirement uses SHALL or MUST.
- [ ] Every requirement is externally observable and testable.
- [ ] No implementation prescription unless it is a real constraint.
- [ ] No vague words without a measurable definition: "fast", "robust", "secure", "appropriate".
- [ ] No `TBD`, `TODO`, `???`, or unresolved open question.

## 5. Scenarios

- [ ] Every requirement has at least one `#### Scenario:`.
- [ ] Every scenario has both a `WHEN` and a `THEN`.
- [ ] Happy path, failure path, and boundary conditions are covered where relevant.
- [ ] Scenarios are independent: one behavior per scenario.
- [ ] The THEN is an observable outcome, not an internal call.

## 6. Consistency and risk

- [ ] No contradiction with an existing spec in `openspec/specs/`.
- [ ] No contradiction with an accepted ADR.
- [ ] Contract impact is identified (PolicyEnvelope, IPC, API, DB, CLI).
- [ ] Money, risk, vault, key, and hot-path impact are identified or explicitly `N/A`.
- [ ] Backtest/paper/live implications are identified or explicitly `N/A`.
- [ ] Multi-chain/venue isolation is preserved or explicitly addressed.

## 7. Traceability

- [ ] `Impact` lists the real files, services, and contracts.
- [ ] Each acceptance criterion maps to a scenario.
- [ ] The task list (when present) maps to scenarios or invariants.
- [ ] The change can be verified without reading the author's chat.

## Verdict rules

- `blocker`: unverifiable outcome, invariant risk, missing requirement/scenario coverage, contradiction.
- `major`: scope ambiguity, untestable requirement, missing failure path.
- `minor`: wording, structure, non-blocking clarity.
- `nit`: style.
- `APPROVE` requires zero open blocker/major.
