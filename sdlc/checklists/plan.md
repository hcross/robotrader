# PLAN Review Checklist

> Read after `sdlc/PROTOCOL.md` and the approved SPEC. The plan must not change the spec.

## 1. Traceability

- [ ] Every design decision traces to a requirement or an invariant.
- [ ] Every requirement is addressed by at least one task.
- [ ] No task implements behavior that is not in the spec.
- [ ] A spec gap is escalated as `spec-gap`, not patched in `design.md`.

## 2. Decisions

- [ ] Each decision names the alternatives considered.
- [ ] Each rejection has a technical reason, not a preference.
- [ ] Reversible decisions are separated from one-way doors.
- [ ] The simplest design that satisfies the spec was considered first.
- [ ] New dependencies are justified: maintenance, license, security, size.

## 3. Contracts and data

- [ ] `PolicyEnvelope` parity between Rust and Python is addressed when touched.
- [ ] IPC/API/DB/CLI changes are versioned or backward compatible.
- [ ] Schema evolution has a migration and a rollback.
- [ ] Serialization boundaries are explicit (JSON, MessagePack, Redis TTL).
- [ ] No implicit cross-chain or cross-venue data leakage.

## 4. Hot path and performance

- [ ] No LLM, blocking I/O, unbounded sleep, allocation, or logging in the hot path.
- [ ] The 50µs `HardRiskGate` budget is preserved; a measurement plan exists if touched.
- [ ] New loops or data structures have a complexity bound.
- [ ] Backpressure and failure modes are defined (Redis down, RPC down, exchange down).

## 5. Safety and security

- [ ] Capital protection is not weakened (dry powder, Kelly, drawdown, CostGuard).
- [ ] Vault/key material stays inside the enclave; zeroization and whitelist are preserved.
- [ ] Inputs crossing trust boundaries are validated.
- [ ] Secrets never enter logs, fixtures, transcripts, or evidence.
- [ ] Failure is fail-closed on money/risk paths.

## 6. Test strategy

- [ ] Each scenario has a named test or verification command.
- [ ] Unit, integration, and end-to-end coverage are proportioned to the risk.
- [ ] Determinism: backtest == paper == live is preserved or explicitly addressed.
- [ ] Negative and boundary tests are planned.
- [ ] Performance tests are planned where a budget exists.
- [ ] Test data contains no real keys or production data.

## 7. Rollout and rollback

- [ ] Deployment order is explicit (migration, service, feature flag).
- [ ] Rollback is a concrete procedure, not "revert the PR".
- [ ] Observability is planned: metrics, logs, alerts, dashboard impact.
- [ ] Cost impact is assessed (LLM spend, infra, RPC).

## 8. Tasks

- [ ] Tasks are checkboxes `- [ ] X.Y` grouped under numbered headings.
- [ ] Each task fits one session and is verifiable.
- [ ] Dependency order is correct; no circular task dependency.
- [ ] `## Verification` lists exact commands and expected evidence.
- [ ] No task hides a spec change.

## Verdict rules

- `blocker`: unsafe plan, missing rollback on a risky change, contract break without migration, untestable task.
- `major`: missing failure path, unjustified dependency, requirement not covered by a task.
- `minor`: sequencing, task granularity, observability detail.
- `nit`: style.
- `APPROVE` requires zero open blocker/major.
