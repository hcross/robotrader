## 1. <Task group>

- [ ] 1.1 <Verifiable action> (covers: <scenario or invariant>)
- [ ] 1.2 <Verifiable action> (covers: <scenario or invariant>)

## 2. <Task group>

- [ ] 2.1 <Verifiable action> (covers: <scenario or invariant>)
- [ ] 2.2 <Verifiable action> (covers: <scenario or invariant>)

## Verification

- `cd engine-rs && cargo test` → expected: <result>
- `PYTHONPATH=. python3 -m unittest discover -s backend/tests -v` → expected: <result>
- `cd frontend && npm run build` → expected: <result>
- `<additional command>` → expected: <evidence>
