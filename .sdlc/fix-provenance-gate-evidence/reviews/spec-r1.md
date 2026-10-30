# SPEC Review — Round 1

## Summary

APPROVE. The specification for change `fix-provenance-gate-evidence` directly addresses all evidence, test, and grep gate hygiene findings from DEV-R1 on #15 (parent #7). It eliminates the literal `rust_leaf_backtest` comment token tripping the single-source grep gate in `backend/core/provenance.py`, specifies absence assertions for deprecated tokens in production modules and state store, aligns frontend fallback for unknown sources in `frontend/src/lib/provenance.js`, updates `check-provenance.mjs`, mandates uncropped `offline.png` evidence, and specifies recursive payload walk and missing spec-scenario test coverage. All 5 modified requirements and 28 scenarios are testable and observable, with 9 tasks mapped directly. Zero blockers, zero majors, two non-blocking style nits.

## Findings

### SPEC-R1-F01 — nit Paragraph length in Why section
- Location: `openspec/changes/fix-provenance-gate-evidence/proposal.md#L28`
- Evidence: Paragraph in `## Why` contains 3 sentences ("During the cold DEV review...", "Specifically, the documented...", "Additionally, formatMetric..."), exceeding the rule "paragraphs ≤ 2 sentences".
- Required fix: Split the paragraph into two paragraphs of at most two sentences each.
- Status: open
- Origin: initial

### SPEC-R1-F02 — nit Redundant Non-goals sections
- Location: `openspec/changes/fix-provenance-gate-evidence/proposal.md#L21-25; proposal.md#L47-53`
- Evidence: `proposal.md` includes `### Non-goals` inside the Review Card block at L21 and a second `## Non-goals` section at L47.
- Required fix: Consolidate the non-goals sections or streamline the heading hierarchy.
- Status: open
- Origin: initial

## Checks run
- `openspec validate fix-provenance-gate-evidence --strict` → PASS
- `scripts/sdlc/spec-lint.py --change fix-provenance-gate-evidence` → PASS (Review Card: 111 words, 1 diagram, ~1.1 min; tasks: 9 open)
- Read time: 1.1 min

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "fix-provenance-gate-evidence",
  "stage": "spec",
  "round": 1,
  "reviewer": "sdlc-spec-reviewer",
  "reviewed_sha": "c1a03f9487acf5b50ec6e624b9127ccc6b364f2e",
  "verdict": "APPROVE",
  "summary": "Specification approved: provenance grep gates, frontend unknown source fallback, uncropped offline evidence, and regression test suites are comprehensively specified.",
  "findings": [
    {
      "id": "SPEC-R1-F01",
      "severity": "nit",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/fix-provenance-gate-evidence/proposal.md#L28",
      "evidence": "Paragraph in ## Why contains 3 sentences, exceeding the style recommendation of paragraphs ≤ 2 sentences.",
      "required_fix": "Split the paragraph into two paragraphs of at most two sentences each."
    },
    {
      "id": "SPEC-R1-F02",
      "severity": "nit",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/fix-provenance-gate-evidence/proposal.md#L21-25; proposal.md#L47-53",
      "evidence": "Proposal includes redundant Non-goals sections at L21 (### Non-goals) and L47 (## Non-goals).",
      "required_fix": "Consolidate the non-goals sections or streamline the heading hierarchy."
    }
  ],
  "closed": []
}
```
