# RegimeShift AI collaboration guide

This repository is designed for several AI coding agents working in parallel.

## Product invariants

- Paper trading only. Never point code at Alpaca live trading endpoints.
- Never commit credentials, account identifiers, or copied API responses.
- The Risk Agent is a deterministic hard gate. LLM output cannot bypass it.
- Every decision must remain inspectable as structured data.
- “No trade” is a valid and expected outcome.

## Repository boundaries

- `backend/src/regimeshift/domain/`: shared models and pure calculations.
- `backend/src/regimeshift/services/`: market-data and broker adapters.
- `backend/src/regimeshift/orchestration/`: agent pipeline and policy.
- `frontend/app/`: Next.js routes and route-local components.
- `docs/`: architecture and handoff notes.

Prefer adding a new adapter behind an existing protocol over changing domain
models. If a model must change, update backend tests and `frontend/lib/types.ts`
in the same change.

## Verification

- Backend: `cd backend && pytest`
- Frontend: `cd frontend && npm run lint && npm run build`

