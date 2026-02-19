# CLAUDE.md - SpeculAI (TradeAgent) Developer Guide

## 1. Project Overview

SpeculAI (TradeAgent) is a Python-based autonomous trading agent that runs a daily analysis pipeline: ingest global stock data and technical indicators via yfinance, gather news via Perplexity API, retrieve past decision history for context, feed everything into an LLM (Claude CLI) for structured trade recommendations, then execute approved trades against Trading 212's Practice API (paper trading only). A React dashboard visualizes portfolio performance, trade history, decision reports, and benchmark comparisons (S&P 500, IWDA, VWCE). Architecture follows a **layered pattern with adapter interfaces** — routes call services, services call repositories, and all external I/O goes through swappable adapters (LLM, market data, news, broker).

**Tech stack:** Python 3.12+, FastAPI, PostgreSQL 16, SQLAlchemy 2.0, Alembic, React 18 + Vite 5, Tailwind CSS, TradingView Lightweight Charts, pandas-ta, yfinance, Perplexity API, Claude Code CLI, APScheduler, Docker Compose.

---

## 2. Git Workflow (gh CLI)

**Use the `gh` CLI for all GitHub operations.** Raw `git` is only for local operations (checkout, add, commit, pull, diff).

### Create a feature branch

```bash
# Always branch off main
git checkout main && git pull origin main
git checkout -b feature/<number>-<short-name>
```

### Push and create a PR

```bash
git push -u origin feature/<number>-<short-name>

gh pr create \
  --title "Feature <number>: <Short Title>" \
  --body "$(cat <<'EOF'
## Summary
<What this PR does, 1-3 bullet points>

## How to Test
<Step-by-step manual testing instructions>

## Checklist
- [ ] End-to-end manual testing completed (not just unit tests)
- [ ] All tests pass (`pytest`)
- [ ] No secrets or API keys in code
- [ ] Clean diff — no unrelated changes
EOF
)"
```

### Check PR status

```bash
gh pr list
gh pr status
gh pr view <number>
gh pr checks <number>
```

### Merge a PR

```bash
gh pr merge <number> --squash --delete-branch
```

### Work with issues

```bash
gh issue list
gh issue view <number>
gh issue create --title "Bug: ..." --body "..."
```

---

## 3. Feature Branch Process

### Branch naming

```
feature/<number>-<short-name>
```

Examples: `feature/01-project-scaffolding`, `feature/06-technical-analysis`, `feature/14-dashboard-portfolio`

The 19 feature branches are defined in `IMPLEMENTATION_PLAN.md`. Build them in order — each one depends on the previous (see the dependency graph at the bottom of that file).

### PR requirements checklist

Every PR must include:

1. **"How to Test" section** — Step-by-step instructions for manual end-to-end verification
2. **End-to-end testing proof** — You must actually run the app, hit the endpoints, check the UI, and verify behavior before submitting
3. **All automated tests pass** — `pytest` green, no skipped tests without reason
4. **No secrets** — No API keys, passwords, or tokens in code. All secrets go in `.env` (which is gitignored)
5. **Clean diff** — Only changes related to this feature. No drive-by refactors or unrelated formatting changes

---

## 4. Testing Requirements

Testing has three tiers. **All three are mandatory before submitting a PR.**

### Tier 1: Unit Tests (pytest)

```bash
pytest tests/unit/ -v
pytest tests/unit/ --cov=tradeagent --cov-report=term-missing
```

- Target: >= 80% coverage for `services/` and `adapters/`
- Frameworks: pytest, pytest-asyncio, pytest-cov, factory_boy
- Mock all external dependencies (adapters have mock implementations)

### Tier 2: Integration Tests

```bash
pytest tests/integration/ -v
```

- Full pipeline with mocked adapters
- API route tests against a test database
- Backtest engine tests with known historical data

### Tier 3: End-to-End Manual Testing

**Do not submit a PR without completing this tier.**

```bash
# 1. Start the full stack
docker compose up --build

# 2. Wait for backend to be healthy
curl http://localhost:8000/api/health

# 3. Test your feature manually:
#    - Hit the relevant API endpoints with curl or a browser
#    - Open the dashboard at http://localhost:3000
#    - Verify the behavior matches the acceptance criteria in the PRD
#    - Check logs for errors: docker compose logs backend -f
#    - Verify database state if needed: docker compose exec db psql -U tradeagent

# 4. Fix any bugs found during manual testing BEFORE submitting the PR
```

You must verify:
- The feature works as described in the PRD acceptance criteria
- Error cases are handled (try invalid inputs, missing data, service failures)
- The UI reflects backend changes correctly (if applicable)
- No stack traces leak to API responses
- Logs are clean and structured (JSON format)

---

## 5. Running the Project Locally

### Start everything

```bash
docker compose up --build
```

This starts three services:
| Service | URL | Description |
|---------|-----|-------------|
| `db` | `localhost:5432` | PostgreSQL 16 |
| `backend` | `http://localhost:8000` | FastAPI (Python) |
| `frontend` | `http://localhost:3000` | React dashboard |

### Startup sequence

1. PostgreSQL starts and runs healthcheck (`pg_isready`)
2. Backend waits for DB health, then runs: `alembic upgrade head` → `seed_watchlist.py` → `seed_benchmarks.py` → `uvicorn`
3. Frontend starts after backend is up

### Useful commands

```bash
# View backend logs
docker compose logs backend -f

# Connect to PostgreSQL
docker compose exec db psql -U tradeagent

# Run migrations manually
docker compose exec backend alembic upgrade head

# Run a single pipeline manually
docker compose exec backend python scripts/run_pipeline.py

# Run backtest
docker compose exec backend python -m tradeagent.backtest --start 2023-01-01 --end 2023-12-31 --initial-capital 50000

# Rebuild a single service
docker compose up --build backend

# Clean shutdown (removes volumes too)
docker compose down -v
```

---

## 6. Architecture Quick Reference

### Directory structure

```
tradeagent/
├── src/tradeagent/
│   ├── main.py                    # FastAPI entry point
│   ├── config.py                  # Pydantic Settings (YAML + env vars)
│   ├── scheduler.py               # APScheduler daily trigger
│   ├── api/
│   │   ├── routes/                # FastAPI route handlers
│   │   │   ├── portfolio.py
│   │   │   ├── trades.py
│   │   │   ├── decisions.py
│   │   │   ├── backtest.py
│   │   │   └── health.py
│   │   └── dependencies.py        # Shared FastAPI dependencies
│   ├── core/
│   │   ├── exceptions.py          # Custom exception hierarchy
│   │   ├── logging.py             # structlog JSON setup
│   │   └── types.py               # Shared enums (Action, Side, TradeStatus, etc.)
│   ├── models/                    # SQLAlchemy 2.0 models
│   ├── schemas/                   # Pydantic request/response schemas
│   ├── services/                  # Business logic
│   │   ├── pipeline.py            # Daily pipeline orchestrator
│   │   ├── screening.py           # Stock scoring and filtering
│   │   ├── technical_analysis.py  # RSI, MACD, Bollinger, SMA/EMA
│   │   ├── risk_manager.py        # Portfolio constraint enforcement
│   │   ├── memory.py              # Decision memory retrieval
│   │   ├── report_generator.py    # Decision report creation
│   │   └── backtest.py            # Backtesting engine
│   ├── adapters/                  # External service integrations
│   │   ├── llm/                   # LLM adapter (Claude CLI)
│   │   │   └── prompts/           # System and report prompts (.md files)
│   │   ├── market_data/           # yfinance adapter
│   │   ├── news/                  # Perplexity adapter
│   │   └── broker/                # Trading 212 + simulated broker
│   └── repositories/             # Data access layer (async SQLAlchemy)
├── frontend/                      # React + Vite + TypeScript
├── tests/
│   ├── conftest.py                # Shared fixtures, test DB
│   ├── unit/
│   ├── integration/
│   └── backtest/
├── scripts/                       # seed_watchlist.py, seed_benchmarks.py, run_pipeline.py
├── alembic/                       # Database migrations
├── config/
│   ├── config.yaml                # Runtime configuration
│   └── config.example.yaml        # Documented example
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── .env.example
```

### Layer rules

```
API routes → Services → Repositories → Database
                ↓
            Adapters → External Services (LLM, market data, news, broker)
```

- **Routes** handle HTTP, validation, response formatting. No business logic.
- **Services** contain all business logic. They call repositories and adapters.
- **Repositories** handle database queries. Async SQLAlchemy sessions.
- **Adapters** wrap external APIs behind abstract interfaces. Swappable via config.

Never skip layers. Routes must not call repositories or adapters directly.

---

## 7. Coding Conventions

### Python (backend)

- **Async everywhere**: All database operations, HTTP calls, and service methods use `async`/`await`
- **SQLAlchemy 2.0 style**: Use `select()`, `insert()`, `update()` — no legacy 1.x patterns
- **structlog**: All logging via `structlog`. Bind context fields (`pipeline_run_id`, `ticker`, etc.)
- **Type hints**: All function signatures must have type annotations. Use `typing` for complex types
- **Pydantic**: All API inputs/outputs use Pydantic models. All config uses Pydantic Settings
- **Naming**: `snake_case` for variables, functions, modules. `PascalCase` for classes. `SCREAMING_SNAKE` for constants
- **Imports**: stdlib first, then third-party, then local. Absolute imports only (`from tradeagent.services.pipeline import ...`)
- **Error handling**: Use custom exceptions from `core/exceptions.py`. Never catch bare `Exception` unless re-raising. Never expose stack traces in API responses

### TypeScript (frontend)

- **Strict mode**: `tsconfig.json` has `strict: true`
- **Functional components**: No class components. Use hooks for state and effects
- **Tailwind CSS**: All styling via Tailwind utility classes. No CSS files or styled-components
- **Naming**: `PascalCase` for components and types. `camelCase` for variables and functions. File names match component names (`PortfolioSummary.tsx`)
- **Dark theme**: Dark background, green for gains, red for losses. Desktop-only (min 1280px viewport)

---

## 8. Security Rules

1. **All API keys and secrets go in `.env` only** — never in code, config.yaml, or committed files
2. **`.env` is gitignored** — `.env.example` provides the template with placeholder values
3. **Do not log full LLM prompts/responses** — they may contain financial data. Log only: token count, response time, parse success/failure
4. **CORS is restricted** — Allow only `http://localhost:5173` (Vite dev) and `http://localhost:3000` (production frontend)
5. **No auth scaffolding** — The app runs locally. Do NOT add authentication, user management, or RBAC
6. **Pydantic validation on all API inputs** — Invalid inputs return 400 with descriptive error, not 500
7. **No stack traces in API responses** — FastAPI exception handlers return generic error messages for unhandled exceptions
8. **Input sanitization** — Validate and constrain all user-supplied query parameters (dates, ticker formats, pagination limits)

---

## 9. API Endpoints Reference

| Method | Endpoint | Description | Priority |
|--------|----------|-------------|----------|
| `GET` | `/api/health` | Health check (status, DB, last pipeline run) | P10 |
| `GET` | `/api/portfolio/summary` | Portfolio value, cash, positions with P&L | P9 |
| `GET` | `/api/portfolio/performance` | Time series with benchmark comparison | P9 |
| `GET` | `/api/trades` | Paginated trade history (filterable) | P9 |
| `GET` | `/api/decisions` | Paginated decision reports (filterable) | P9 |
| `GET` | `/api/decisions/{id}` | Full decision detail with context items | P9 |
| `POST` | `/api/pipeline/run` | Manually trigger pipeline (202 accepted) | P7 |
| `GET` | `/api/pipeline/status` | Current pipeline status + last run info | P7 |
| `POST` | `/api/backtest/run` | Start a backtest (202 accepted, async) | P8 |
| `GET` | `/api/backtest/{run_id}` | Get backtest results and metrics | P8 |

**Error format** (all endpoints):
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable description",
    "details": [{"field": "start_date", "issue": "Must be before end_date"}]
  }
}
```

**Pagination** (list endpoints):
```json
{
  "data": [...],
  "pagination": {"total": 150, "limit": 50, "offset": 0, "has_more": true}
}
```

---

## 10. Environment Variables

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://tradeagent:password@db:5432/tradeagent` |
| `T212_API_KEY` | Trading 212 API key | (from T212 dashboard) |
| `T212_API_SECRET` | Trading 212 API secret | (from T212 dashboard) |
| `T212_BASE_URL` | Trading 212 API base URL | `https://demo.trading212.com/api/v0` |
| `PERPLEXITY_API_KEY` | Perplexity API key | `pplx-xxx` |
| `PERPLEXITY_MODEL` | Perplexity model | `sonar` |
| `CLAUDE_CLI_PATH` | Path to Claude CLI binary | `claude` |

### Optional (with defaults)

| Variable | Default | Description |
|----------|---------|-------------|
| `CLAUDE_CLI_TIMEOUT` | `120` | Claude CLI subprocess timeout (seconds) |
| `PIPELINE_SCHEDULE_HOUR` | `7` | UTC hour for daily pipeline run |
| `PIPELINE_SCHEDULE_MINUTE` | `0` | Minute for daily pipeline run |
| `LOG_LEVEL` | `INFO` | Logging level |
| `BASE_CURRENCY` | `EUR` | Base currency for portfolio valuation |
| `FRONTEND_URL` | `http://localhost:5173` | Frontend URL for CORS |
| `DB_PASSWORD` | `tradeagent_dev` | PostgreSQL password (used by docker-compose) |

---

## 11. Common Commands Cheat Sheet

### Git / GitHub

```bash
git checkout main && git pull origin main              # Sync with main
git checkout -b feature/XX-name                        # New feature branch
git add <files> && git commit -m "description"         # Commit
git push -u origin feature/XX-name                     # Push branch
gh pr create --title "Feature XX: Name" --body "..."   # Create PR
gh pr list                                             # List open PRs
gh pr checks <number>                                  # Check CI status
gh pr merge <number> --squash --delete-branch          # Merge PR
gh issue list                                          # List issues
gh issue create --title "Title" --body "Details"       # Create issue
```

### Docker

```bash
docker compose up --build                              # Start all services
docker compose up --build backend                      # Rebuild + start backend only
docker compose down                                    # Stop all services
docker compose down -v                                 # Stop + remove volumes
docker compose logs backend -f                         # Stream backend logs
docker compose exec backend bash                       # Shell into backend
docker compose exec db psql -U tradeagent              # PostgreSQL shell
docker compose restart backend                         # Restart backend only
```

### Testing

```bash
pytest                                                 # Run all tests
pytest tests/unit/ -v                                  # Unit tests (verbose)
pytest tests/integration/ -v                           # Integration tests
pytest --cov=tradeagent --cov-report=term-missing      # Coverage report
pytest tests/unit/test_risk_manager.py -k "test_max"   # Run specific tests
```

### Database

```bash
docker compose exec backend alembic upgrade head       # Apply migrations
docker compose exec backend alembic downgrade -1       # Rollback one migration
docker compose exec backend alembic revision --autogenerate -m "description"  # New migration
docker compose exec db psql -U tradeagent -c "SELECT count(*) FROM stock;"    # Quick query
```

### API (manual testing)

```bash
curl http://localhost:8000/api/health                  # Health check
curl http://localhost:8000/api/portfolio/summary       # Portfolio summary
curl http://localhost:8000/api/trades?limit=10         # Recent trades
curl http://localhost:8000/api/decisions?action=BUY    # BUY decisions
curl -X POST http://localhost:8000/api/pipeline/run    # Trigger pipeline
curl http://localhost:8000/api/pipeline/status         # Pipeline status
```

### Frontend

```bash
cd frontend && npm install                             # Install deps
cd frontend && npm run dev                             # Dev server at :5173
cd frontend && npm run build                           # Production build
cd frontend && npm run lint                            # Lint check
```
