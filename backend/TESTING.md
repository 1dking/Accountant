# Running the test suite

**Never run the suite against the production runtime or the production database.**
The prod VPS is not a test environment. Run tests on your dev box or in CI.

## Where the suite runs

| Environment | Python | Notes |
|---|---|---|
| Dev box (this repo) | 3.14 (Windows) | Works — see the `magic` stub note below. Slower. |
| CI (`.github/workflows/ci.yml`) | 3.12 (Linux) | Canonical. Real libmagic, real everything. |
| Prod VPS | 3.10 | **Do not run tests here.** |

## Invocation

```bash
cd backend
# Full suite (what CI runs):
.venv/Scripts/python -m pytest tests/financial tests/adversarial tests/api tests/integration -q

# A single file / subset:
.venv/Scripts/python -m pytest tests/api/test_auth.py -q
```

On Linux/macOS use `.venv/bin/python` instead of `.venv/Scripts/python`.

The suite uses a **fresh in-memory SQLite DB per test** by default (see
`tests/conftest.py`). Set `TEST_DATABASE_URL=postgresql+asyncpg://…` to run
against a throwaway PostgreSQL for true concurrent-write coverage — never point
it at a real database.

## Why async tests previously only ran on prod

pytest-asyncio itself is fine on 3.14 (minimal async + SQLAlchemy-async tests
pass). The blocker was **`python-magic-bin`**, which intermittently deadlocks
loading `libmagic` via ctypes on **Python 3.14 Windows** — freezing every
app-fixture test at import time (`create_app` → `documents.router` → `import
magic`). `magic` is only used for MIME sniffing on uploads
(`app/documents/service.py:163`).

`tests/conftest.py` now **stubs `magic` on Windows only** (`sys.platform ==
"win32"`), so the async suite runs on the dev box. Linux/CI keeps the real
library, so MIME behavior is still fully exercised there.

## Recommended (optional) hardening

The dev box only has Python 3.14, which is slow and needs the stub. To match CI
exactly, create a dedicated 3.12 venv (e.g. via `uv`: `uv venv --python 3.12
.venv-test && uv pip install -e ".[dev]"`, or a python.org 3.12 install) and run
the suite there. Not required — the stubbed 3.14 path is green.
