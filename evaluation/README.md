# Evaluation

Test suites, quality gates, and performance benchmarks.

## Test Infrastructure

- Framework: pytest + pytest-asyncio
- Test location: `backend/tests/`
- Config: `backend/pyproject.toml` (asyncio_mode = "auto")

## Files

| File | Purpose |
|------|---------|
| `test-suite.yaml` | Test categories, quality gates, coverage targets |
| `benchmarks.yaml` | Performance baselines and response time targets |

## Running Tests

```bash
cd backend && pytest -v              # All tests
cd backend && pytest -v -k "auth"    # Auth tests only
cd backend && pytest --cov=app       # With coverage
```

## Quality Gates

Before merging/deploying:
1. All tests pass
2. No new ruff lint errors (`ruff check .`)
3. Code formatted (`ruff format --check .`)
4. TypeScript builds without errors (`cd frontend && pnpm build`)
5. Health check passes after deployment
